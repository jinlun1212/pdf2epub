#!/usr/bin/env python3
"""
Populate empty EPUB XHTML pages by extracting content from the source PDF.

The EPUB has 880 XHTML pages. 314 even-numbered pages (24-826) have completely
empty <body></body> tags. This script extracts text and images from the
corresponding PDF pages and generates proper XHTML content.

Usage:
    python scripts/fix_empty_pages.py [--dry-run] [--pages 24,26,28] [--verbose]
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import xml.sax.saxutils as saxutils
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import fitz  # PyMuPDF

BASE_DIR = Path(__file__).parent.parent.resolve()
PDF_PATH = BASE_DIR / "options_futures_and_other_derivatives_11th.pdf"
EPUB_DIR = BASE_DIR / "output" / "full_book_extracted" / "EPUB"
IMAGES_DIR = EPUB_DIR / "images"
OPF_PATH = EPUB_DIR / "content.opf"

# ---------------------------------------------------------------------------
# Font-aware character correction tables (from fix_equations.py)
# ---------------------------------------------------------------------------

MATH_FONT_CORRECTIONS: dict[str, dict[str, str]] = {
    "PearsonMATHPRO01": {
        "A": "\u0391",
        "a": "\u03B1", "b": "\u03B2", "d": "\u03B4", "f": "\u03C6",
        "g": "\u03B3", "h": "\u03B7", "j": "\u03B8", "k": "\u03BA",
        "l": "\u03BB", "m": "\u03BC", "p": "\u03C0", "r": "\u03C1",
        "s": "\u03C3", "t": "\u03C4", "u": "\u03C5", "v": "\u03BD",
        "x": "\u03C7", "z": "\u03B6",
    },
    "PearsonMATHPRO02": {
        "0": "\u2202", "6": "\u2264", "7": "\u2265",
        "S": "\u2211", "P": "\u220F",
        "*": "\u00D7", "+": "+", "-": "\u2212", "=": "=",
        "\u00DA": "\u222B", "\u2026": "\u2026", "\u00A2": "\u00B7",
        "q": "\u221A",
    },
    "PearsonMATHPRO03": {
        "n": "\u0303",
    },
    "PearsonMATHPRO07": {
        "a": "\u221A", "q": "\u221A", "L": "\u221A",
    },
    "PearsonMATHPRO08": {
        "=": "=",
    },
    "PearsonMATHPRO11": {
        "*": "\u0302", "@": "\u0307", ">": "\u20D7", "V": "\u030C",
    },
    "PearsonMATHPRO12": {
        "+": "+", ",": ",",
    },
    "PearsonMATHPRO13": {
        "c": "\u222B", "f": "\u222B", "g": "\u222C", "*": "\u00D7",
    },
    "PearsonMATHPRO16": {
        "P": "\u220F", '"': "\u2211",
    },
    "PearsonMATHPRO18": {
        "1": "(", "2": ")", "3": "[", "4": "]", "5": "{", "6": "}",
        ">": "/",
        "a": "(", "b": ")", "c": "[", "d": "]", "e": "{", "f": "}",
    },
    "PearsonMATHPRO19": {
        "3": "[", "#": "\u221A",
    },
    "PearsonMATHPRO20": {
        "1": "(", "2": "\u221A", "4": "]",
        "A": "(", "B": ")", "C": "[",
    },
    "MathematicalPiLTStd": {},
    "MathematicalPiLTStd-1": {
        "5": "\u221A", "1": "\u222B", "2": "\u222B",
        "D": "\u2206", "P": "\u220F", "d": "\u2202", "s": "\u2211",
    },
    "PearsonMATHPRO15": {
        "E": "\u2203", "U": "\u222A",
    },
}

SKIP_CHARS = {" ", "\t", "\n", "\r", "\x08", "\x1f"}

# Inline style used on existing non-empty pages
P_STYLE = 'style="text-align: justify; text-justify: inter-word; -webkit-hyphens: auto; hyphens: auto;"'


def font_base_name(font_name: str) -> str:
    """Strip the subset prefix (e.g., 'ABCDEF+') from a font name."""
    if "+" in font_name:
        return font_name.split("+", 1)[1]
    return font_name


def is_math_font(font_name: str) -> bool:
    """Check whether a font name corresponds to a known math font."""
    base = font_base_name(font_name)
    return any(base.startswith(prefix) for prefix in (
        "PearsonMATHPRO", "MathematicalPiLTStd",
    ))


def get_correction_table(font_name: str) -> dict[str, str] | None:
    """Return the correction table for a given font, or None."""
    base = font_base_name(font_name)
    if base in MATH_FONT_CORRECTIONS:
        return MATH_FONT_CORRECTIONS[base]
    for prefix in sorted(MATH_FONT_CORRECTIONS.keys(), key=len, reverse=True):
        if base.startswith(prefix):
            return MATH_FONT_CORRECTIONS[prefix]
    return None


def correct_char(char: str, font_name: str) -> str:
    """Correct a single character based on its font."""
    if char in SKIP_CHARS:
        return char
    table = get_correction_table(font_name)
    if table is None:
        return char
    return table.get(char, char)


def escape_xml(text: str) -> str:
    """Escape text for safe inclusion in XHTML."""
    return saxutils.escape(text)


# ---------------------------------------------------------------------------
# PDF content extraction
# ---------------------------------------------------------------------------

class SpanInfo:
    """Holds info about a single text span from the PDF."""
    __slots__ = ("text", "font", "size", "flags", "bbox", "is_math")

    def __init__(self, text: str, font: str, size: float, flags: int, bbox: tuple):
        self.text = text
        self.font = font
        self.size = size
        self.flags = flags
        self.bbox = bbox  # (x0, y0, x1, y1)
        self.is_math = is_math_font(font)

    @property
    def corrected_text(self) -> str:
        if not self.is_math:
            return self.text
        return "".join(correct_char(ch, self.font) for ch in self.text)

    @property
    def is_bold(self) -> bool:
        return bool(self.flags & 2**4)  # bit 4 = bold

    @property
    def is_italic(self) -> bool:
        return bool(self.flags & 2**1)  # bit 1 = italic

    @property
    def is_superscript(self) -> bool:
        return bool(self.flags & 2**0)  # bit 0 = superscript


class LineInfo:
    """One line of text from the PDF."""

    def __init__(self, spans: list[SpanInfo], bbox: tuple):
        self.spans = spans
        self.bbox = bbox  # (x0, y0, x1, y1)

    @property
    def text(self) -> str:
        return "".join(s.corrected_text for s in self.spans).strip()

    @property
    def avg_size(self) -> float:
        if not self.spans:
            return 0
        total = sum(s.size * len(s.text) for s in self.spans)
        chars = sum(len(s.text) for s in self.spans)
        return total / max(chars, 1)

    @property
    def is_bold(self) -> bool:
        """True if the majority of text in the line is bold."""
        bold_chars = sum(len(s.text) for s in self.spans if s.is_bold)
        total = sum(len(s.text) for s in self.spans)
        return bold_chars > total * 0.5 if total > 0 else False

    @property
    def is_italic(self) -> bool:
        """True if the majority of text in the line is italic."""
        italic_chars = sum(len(s.text) for s in self.spans if s.is_italic)
        total = sum(len(s.text) for s in self.spans)
        return italic_chars > total * 0.5 if total > 0 else False

    @property
    def has_math(self) -> bool:
        return any(s.is_math for s in self.spans)

    @property
    def y_center(self) -> float:
        return (self.bbox[1] + self.bbox[3]) / 2


class BlockInfo:
    """A text block from the PDF, containing multiple lines."""

    def __init__(self, lines: list[LineInfo], bbox: tuple, block_type: int = 0):
        self.lines = lines
        self.bbox = bbox
        self.block_type = block_type  # 0=text, 1=image


class ImageInfo:
    """An image found on a PDF page."""

    def __init__(self, xref: int, bbox: tuple, width: int, height: int):
        self.xref = xref
        self.bbox = bbox  # (x0, y0, x1, y1)
        self.width = width
        self.height = height


def extract_page_content(doc: fitz.Document, page_idx: int) -> tuple[list[BlockInfo], list[ImageInfo]]:
    """Extract all text blocks and images from a PDF page."""
    page = doc[page_idx]
    text_dict = page.get_text("dict")

    blocks: list[BlockInfo] = []
    for block in text_dict.get("blocks", []):
        btype = block.get("type", 0)
        bbbox = block.get("bbox", (0, 0, 0, 0))

        if btype == 1:
            # Image block - record it but handle separately
            blocks.append(BlockInfo([], bbbox, block_type=1))
            continue

        lines: list[LineInfo] = []
        for line_data in block.get("lines", []):
            spans: list[SpanInfo] = []
            for span in line_data.get("spans", []):
                text = span.get("text", "")
                if not text:
                    continue
                spans.append(SpanInfo(
                    text=text,
                    font=span.get("font", ""),
                    size=span.get("size", 10),
                    flags=span.get("flags", 0),
                    bbox=span.get("bbox", (0, 0, 0, 0)),
                ))
            if spans:
                line_bbox = line_data.get("bbox", (0, 0, 0, 0))
                line = LineInfo(spans, line_bbox)
                if line.text:
                    lines.append(line)

        if lines:
            blocks.append(BlockInfo(lines, bbbox, block_type=0))

    # Extract images
    images: list[ImageInfo] = []
    try:
        page_images = page.get_images(full=True)
        for img in page_images:
            xref = img[0]
            # Try to get the image position on the page
            images.append(ImageInfo(xref=xref, bbox=(0, 0, 0, 0), width=img[2], height=img[3]))
    except Exception:
        pass

    # Try to get image positions using get_image_info
    try:
        img_info_list = page.get_image_info()
        for i, info in enumerate(img_info_list):
            if i < len(images):
                images[i].bbox = (info["bbox"][0], info["bbox"][1], info["bbox"][2], info["bbox"][3])
    except Exception:
        pass

    return blocks, images


# ---------------------------------------------------------------------------
# Paragraph grouping and XHTML generation
# ---------------------------------------------------------------------------

def is_header_or_footer(line: LineInfo, page_height: float) -> bool:
    """Check if a line is likely a page header or footer (page number, chapter title)."""
    text = line.text.strip()

    # Skip if very close to top or bottom of page
    if line.bbox[1] < 55:  # header zone
        # Common headers: chapter title, page number
        if len(text) < 60:
            return True
    if line.bbox[3] > page_height - 45:  # footer zone
        if len(text) < 15:
            # Likely a page number
            try:
                int(text)
                return True
            except ValueError:
                pass
    return False


def classify_line(line: LineInfo) -> str:
    """Classify a line as h1, h2, or p based on font size and style."""
    avg = line.avg_size
    if avg >= 16 and line.is_bold:
        return "h1"
    if avg >= 13 and line.is_bold:
        return "h2"
    return "p"


def render_spans_to_html(spans: list[SpanInfo]) -> str:
    """Convert a list of SpanInfo into inline HTML with <em>/<strong> wrapping."""
    parts = []
    for span in spans:
        text = escape_xml(span.corrected_text)
        if not text.strip():
            parts.append(text)
            continue

        if span.is_math:
            # Wrap math content in a span
            text = f'<span class="eq-inline">{text}</span>'
        elif span.is_superscript:
            text = f'<sup>{text}</sup>'

        if span.is_bold and span.is_italic:
            text = f'<strong><em>{text}</em></strong>'
        elif span.is_bold:
            text = f'<strong>{text}</strong>'
        elif span.is_italic:
            text = f'<em>{text}</em>'

        parts.append(text)

    return "".join(parts)


def group_lines_into_paragraphs(
    blocks: list[BlockInfo],
    page_height: float,
) -> list[tuple[str, str]]:
    """Group text lines into paragraphs and classify them.

    Returns a list of (tag, html_content) where tag is 'h1', 'h2', 'p', or 'equation'.
    """
    elements: list[tuple[str, str]] = []

    for block in blocks:
        if block.block_type == 1:
            continue  # handled separately

        # Group lines within a block by proximity
        para_lines: list[list[LineInfo]] = []
        current_group: list[LineInfo] = []

        for i, line in enumerate(block.lines):
            if is_header_or_footer(line, page_height):
                continue

            if not current_group:
                current_group.append(line)
                continue

            prev_line = current_group[-1]
            # Vertical gap between lines
            gap = line.bbox[1] - prev_line.bbox[3]
            avg_line_height = (prev_line.bbox[3] - prev_line.bbox[1])

            # If line classification differs, start new paragraph
            prev_class = classify_line(prev_line)
            curr_class = classify_line(line)

            # Start a new group if:
            # 1. Large vertical gap (more than 1.5x line height)
            # 2. Classification changes (heading vs body text)
            if gap > avg_line_height * 1.5 or prev_class != curr_class:
                if current_group:
                    para_lines.append(current_group)
                current_group = [line]
            else:
                current_group.append(line)

        if current_group:
            para_lines.append(current_group)

        # Convert grouped lines into elements
        for group in para_lines:
            if not group:
                continue

            tag = classify_line(group[0])

            # Merge all spans from all lines in the group
            all_html_parts = []
            for j, line in enumerate(group):
                line_html = render_spans_to_html(line.spans)
                if j > 0:
                    all_html_parts.append(" ")
                all_html_parts.append(line_html)

            html_content = "".join(all_html_parts).strip()
            if not html_content:
                continue

            # Detect equation blocks: centered text that is mostly math
            if tag == "p" and group[0].has_math:
                math_chars = sum(
                    len(s.text) for line in group for s in line.spans if s.is_math
                )
                total_chars = sum(
                    len(s.text) for line in group for s in line.spans
                )
                if total_chars > 0 and math_chars / total_chars > 0.4:
                    tag = "equation"

            elements.append((tag, html_content))

    return elements


def build_xhtml_body(
    elements: list[tuple[str, str]],
    image_refs: list[tuple[str, str]],  # (filename, alt_text)
    page_num: int,
) -> str:
    """Build the XHTML body content from classified elements and images."""
    parts = []

    for tag, content in elements:
        if tag == "h1":
            parts.append(f'<h1>{content}</h1>')
        elif tag == "h2":
            parts.append(f'<h2><span class="fs-large"><strong>{content}</strong></span></h2>')
        elif tag == "equation":
            parts.append(
                f'<div class="equation"><span class="eq-inline">{content}</span></div>'
            )
        else:
            parts.append(f'<p {P_STYLE}>{content}</p>')

    # Add images at the end (matching existing convention)
    for img_filename, alt_text in image_refs:
        fig_id = img_filename.replace(".png", "").replace(".jpg", "")
        parts.append(
            f'<div id="fig-{fig_id}" class="fig-block">'
            f'<div class="fig-cap">{escape_xml(alt_text)}</div>'
            f'<img class="fig-img" src="images/{img_filename}" alt="{escape_xml(alt_text)}"/>'
            f'</div>'
        )

    return "\n".join(parts)


def build_full_xhtml(body_content: str, page_num: int) -> str:
    """Build a complete XHTML page with head and body."""
    return (
        f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" epub:prefix="z3998: http://www.daisy.org/z3998/2012/vocab/structure/#" lang="en" xml:lang="en">
  <head>
    <title>Options, Futures, and Other Derivatives (11th Edition) - p{page_num}</title>
  </head>
  <body>{body_content}
</body>
</html>
"""
    )


# ---------------------------------------------------------------------------
# Image extraction and management
# ---------------------------------------------------------------------------

def get_existing_images(page_num: int) -> list[str]:
    """Find existing image files for a given page number."""
    pattern = f"p{page_num}_fig*.png"
    return sorted(f.name for f in IMAGES_DIR.glob(pattern))


def get_next_fig_number() -> int:
    """Find the highest existing figure number across all images."""
    max_num = 0
    for f in IMAGES_DIR.glob("p*_fig*.png"):
        m = re.search(r"_fig(\d+)", f.name)
        if m:
            num = int(m.group(1))
            if num > max_num:
                max_num = num
    return max_num + 1


def extract_and_save_image(
    doc: fitz.Document, xref: int, page_num: int, fig_num: int
) -> str | None:
    """Extract an image from the PDF and save it. Returns the filename or None."""
    try:
        pix = fitz.Pixmap(doc, xref)
        # Convert CMYK to RGB if necessary
        if pix.n - pix.alpha > 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        filename = f"p{page_num}_fig{fig_num}.png"
        filepath = IMAGES_DIR / filename
        pix.save(str(filepath))
        return filename
    except Exception as e:
        print(f"    Warning: Could not extract image xref={xref}: {e}")
        return None


# ---------------------------------------------------------------------------
# OPF manifest update
# ---------------------------------------------------------------------------

def update_opf_with_images(new_images: list[str]):
    """Add new image entries to content.opf manifest."""
    if not new_images or not OPF_PATH.exists():
        return

    opf_text = OPF_PATH.read_text(encoding="utf-8")

    # Find existing image entries to avoid duplicates
    existing = set(re.findall(r'href="images/([^"]+)"', opf_text))

    entries_to_add = []
    for img_name in new_images:
        if img_name not in existing:
            img_id = "img_" + img_name.replace(".png", "").replace(".jpg", "")
            ext = img_name.rsplit(".", 1)[-1]
            media_type = "image/png" if ext == "png" else "image/jpeg"
            entry = f'    <item href="images/{img_name}" id="{img_id}" media-type="{media_type}"/>'
            entries_to_add.append(entry)

    if not entries_to_add:
        return

    # Insert before </manifest>
    insertion = "\n".join(entries_to_add)
    opf_text = opf_text.replace("  </manifest>", f"{insertion}\n  </manifest>")
    OPF_PATH.write_text(opf_text, encoding="utf-8")
    print(f"  Updated content.opf with {len(entries_to_add)} new image entries")


# ---------------------------------------------------------------------------
# Empty page detection
# ---------------------------------------------------------------------------

def is_empty_page(xhtml_path: Path) -> bool:
    """Check if a page has an empty body."""
    text = xhtml_path.read_text(encoding="utf-8")
    # Match <body></body> or <body/> or <body> with only whitespace </body>
    return bool(re.search(r"<body\s*/?\s*>\s*</body>", text))


def find_empty_pages() -> list[tuple[int, Path]]:
    """Find all empty XHTML pages. Returns list of (page_num, path)."""
    empty = []
    for xhtml_path in sorted(
        EPUB_DIR.glob("full_book_v7_p*.xhtml"),
        key=lambda f: int(f.stem.split("_p")[1]),
    ):
        page_num = int(xhtml_path.stem.split("_p")[1])
        if is_empty_page(xhtml_path):
            empty.append((page_num, xhtml_path))
    return empty


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_page(
    doc: fitz.Document,
    page_num: int,
    xhtml_path: Path,
    next_fig: list[int],
    dry_run: bool = False,
    verbose: bool = False,
) -> tuple[bool, list[str]]:
    """Process a single empty page. Returns (success, list_of_new_images)."""
    pdf_page_idx = page_num - 1
    if pdf_page_idx < 0 or pdf_page_idx >= len(doc):
        print(f"  Page {page_num}: PDF page index {pdf_page_idx} out of range")
        return False, []

    page = doc[pdf_page_idx]
    page_height = page.rect.height

    # Extract content
    blocks, images = extract_page_content(doc, pdf_page_idx)

    # Classify text into paragraphs
    elements = group_lines_into_paragraphs(blocks, page_height)

    if not elements and not images:
        if verbose:
            print(f"  Page {page_num}: No content found in PDF")
        return False, []

    # Handle images
    existing_imgs = get_existing_images(page_num)
    image_refs: list[tuple[str, str]] = []
    new_images: list[str] = []

    if existing_imgs:
        # Use existing images
        for img_name in existing_imgs:
            alt_text = f"Figure from page {page_num}"
            image_refs.append((img_name, alt_text))
        if verbose:
            print(f"  Page {page_num}: Using {len(existing_imgs)} existing image(s)")
    elif images:
        # Extract new images from PDF
        for img_info in images:
            # Skip very small images (likely decorative elements or lines)
            if img_info.width < 50 or img_info.height < 50:
                continue
            fig_num = next_fig[0]
            next_fig[0] += 1
            if not dry_run:
                filename = extract_and_save_image(doc, img_info.xref, page_num, fig_num)
                if filename:
                    alt_text = f"Figure from page {page_num}"
                    image_refs.append((filename, alt_text))
                    new_images.append(filename)
            else:
                filename = f"p{page_num}_fig{fig_num}.png"
                alt_text = f"Figure from page {page_num}"
                image_refs.append((filename, alt_text))
                new_images.append(filename)

    # Build XHTML
    body_content = build_xhtml_body(elements, image_refs, page_num)
    full_xhtml = build_full_xhtml(body_content, page_num)

    if verbose:
        print(f"  Page {page_num}: {len(elements)} text elements, {len(image_refs)} images")
        for tag, content in elements[:3]:
            preview = re.sub(r"<[^>]+>", "", content)[:80]
            print(f"    [{tag}] {preview}")
        if len(elements) > 3:
            print(f"    ... and {len(elements) - 3} more elements")

    if not dry_run:
        xhtml_path.write_text(full_xhtml, encoding="utf-8")

    return True, new_images


def main():
    parser = argparse.ArgumentParser(
        description="Populate empty EPUB pages from PDF content"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files",
    )
    parser.add_argument(
        "--pages",
        type=str,
        default=None,
        help="Comma-separated list of page numbers to process (default: all empty pages)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed information about each page",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("FIX EMPTY PAGES: Populate from PDF content")
    print("=" * 70)

    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found at {PDF_PATH}")
        sys.exit(1)

    if not EPUB_DIR.exists():
        print(f"ERROR: EPUB directory not found at {EPUB_DIR}")
        sys.exit(1)

    # Ensure images directory exists
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Find empty pages
    all_empty = find_empty_pages()
    print(f"Found {len(all_empty)} empty pages in EPUB")

    # Filter to specific pages if requested
    if args.pages:
        target_pages = set(int(p.strip()) for p in args.pages.split(","))
        pages_to_process = [(n, p) for n, p in all_empty if n in target_pages]
        # Also allow processing non-empty pages if explicitly requested
        for pn in target_pages:
            if not any(n == pn for n, _ in pages_to_process):
                xp = EPUB_DIR / f"full_book_v7_p{pn}.xhtml"
                if xp.exists():
                    pages_to_process.append((pn, xp))
        pages_to_process.sort(key=lambda x: x[0])
        print(f"Processing {len(pages_to_process)} specific page(s): {sorted(p for p, _ in pages_to_process)}")
    else:
        pages_to_process = all_empty

    if not pages_to_process:
        print("No pages to process.")
        return

    # Open PDF
    doc = fitz.open(str(PDF_PATH))
    print(f"PDF: {PDF_PATH.name} ({len(doc)} pages)")

    if args.dry_run:
        print("\n*** DRY RUN MODE - no files will be modified ***\n")

    # Track figure numbering
    next_fig = [get_next_fig_number()]
    print(f"Next figure number: {next_fig[0]}")

    # Process each page
    pages_populated = 0
    pages_failed = 0
    all_new_images: list[str] = []

    for page_num, xhtml_path in pages_to_process:
        success, new_imgs = process_page(
            doc, page_num, xhtml_path, next_fig,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
        if success:
            pages_populated += 1
            all_new_images.extend(new_imgs)
            if not args.verbose:
                # Brief progress indicator
                if pages_populated % 25 == 0:
                    print(f"  ... processed {pages_populated} pages so far")
        else:
            pages_failed += 1

    doc.close()

    # Update OPF with new images
    if all_new_images and not args.dry_run:
        update_opf_with_images(all_new_images)

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Empty pages found:     {len(all_empty)}")
    print(f"Pages processed:       {len(pages_to_process)}")
    print(f"Pages populated:       {pages_populated}")
    print(f"Pages with no content: {pages_failed}")
    print(f"New images extracted:  {len(all_new_images)}")

    if args.dry_run:
        print("\n*** DRY RUN - no files were modified ***")

    # Verification: show sample before/after
    if pages_populated > 0 and not args.dry_run:
        print("\n--- Sample verification ---")
        sample_count = 0
        for page_num, xhtml_path in pages_to_process[:5]:
            content = xhtml_path.read_text(encoding="utf-8")
            if "<body>" in content and "</body>" in content:
                body_start = content.index("<body>") + 6
                body_end = content.index("</body>")
                body = content[body_start:body_end].strip()
                if body:
                    # Strip HTML tags for preview
                    preview = re.sub(r"<[^>]+>", "", body)[:120]
                    print(f"  Page {page_num}: {preview}...")
                    sample_count += 1
            if sample_count >= 5:
                break

    print("\nDone.")


if __name__ == "__main__":
    main()
