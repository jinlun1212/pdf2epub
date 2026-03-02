#!/usr/bin/env python3
"""
Fix corrupted math equations in EPUB by using font-aware text extraction from the PDF.

The PDF uses custom PearsonMATHPRO fonts that place math symbol glyphs at standard
ASCII code points. When text was extracted for the EPUB, the font encoding was not
accounted for, so characters like 's' (which is sigma in PearsonMATHPRO01) were left
as-is instead of being converted to their true Unicode symbols.

This script:
1. Scans EPUB XHTML pages for equation content (class="equation" or class="eq-inline")
2. For each such page, extracts text from the corresponding PDF page using PyMuPDF,
   applying font-aware character corrections
3. Matches the corrected PDF text to the garbled EPUB equation text
4. Replaces the garbled text in the EPUB with the corrected version

Usage:
    python scripts/fix_equations.py [--dry-run] [--pages 350,472,624] [--verbose]
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from collections import defaultdict
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import fitz  # PyMuPDF

BASE_DIR = Path(__file__).parent.parent.resolve()
PDF_PATH = BASE_DIR / "options_futures_and_other_derivatives_11th.pdf"
EPUB_DIR = BASE_DIR / "output" / "full_book_extracted" / "EPUB"

# ---------------------------------------------------------------------------
# Font-aware character correction tables
#
# Each PearsonMATHPRO font places special glyphs at standard ASCII positions.
# The CharSet entries in the PDF FontDescriptor objects confirm what each
# glyph actually represents.  The keys below are the raw characters that
# PyMuPDF extracts; the values are the correct Unicode characters.
# ---------------------------------------------------------------------------

MATH_FONT_CORRECTIONS: dict[str, dict[str, str]] = {
    # Greek letters (CharSet: /A/a/b/d/f/g/h/j/k/l/m/p/r/s/t/u/v/x/z)
    "PearsonMATHPRO01": {
        "A": "\u0391",  # Alpha (capital) - but unlikely; keep as-is context-dep
        "a": "\u03B1",  # alpha
        "b": "\u03B2",  # beta
        "d": "\u03B4",  # delta
        "f": "\u03C6",  # phi
        "g": "\u03B3",  # gamma
        "h": "\u03B7",  # eta
        "j": "\u03B8",  # theta
        "k": "\u03BA",  # kappa
        "l": "\u03BB",  # lambda
        "m": "\u03BC",  # mu
        "p": "\u03C0",  # pi
        "r": "\u03C1",  # rho
        "s": "\u03C3",  # sigma
        "t": "\u03C4",  # tau
        "u": "\u03C5",  # upsilon
        "v": "\u03BD",  # nu
        "x": "\u03C7",  # chi
        "z": "\u03B6",  # zeta
    },
    # Mathematical operators
    # CharSet: /P/S/Uacute/asterisk/cent/ellipsis/equal/hyphen/numbersign/
    #          partialdiff/plus/q/registered/seven/six/space/summation/zero
    "PearsonMATHPRO02": {
        "0": "\u2202",  # partial differential (glyph name: partialdiff/zero)
        "6": "\u2264",  # less-than-or-equal (glyph name: six -> lessequal)
        "7": "\u2265",  # greater-than-or-equal (glyph name: seven -> greaterequal)
        "S": "\u2211",  # N-ary summation (glyph name: S/summation)
        "P": "\u220F",  # N-ary product
        "*": "\u00D7",  # multiplication sign (glyph name: asterisk)
        "+": "+",       # plus sign (identity, keep)
        "-": "\u2212",  # minus sign (true typographic minus)
        "=": "=",       # equals (identity, keep)
        "\u00DA": "\u222B",  # Uacute position -> integral sign
        "\u2026": "\u2026",  # horizontal ellipsis (identity)
        "\u00A2": "\u00B7",  # cent sign position -> middle dot / bullet operator
    },
    # Overline / tilde bar (CharSet: /n)
    "PearsonMATHPRO03": {
        "n": "\u0303",  # combining tilde (used as overline/tilde accent)
    },
    # Large delimiters / radicals (CharSet: /L/a/q)
    "PearsonMATHPRO07": {
        "a": "\u221A",  # square root (glyph name: a -> radical)
        "q": "\u221A",  # square root alternate
        "L": "\u221A",  # large radical
    },
    # Equals sign variants (CharSet: /equal)
    "PearsonMATHPRO08": {
        "=": "=",       # equals sign (identity)
    },
    # Decorators / accents (CharSet: /V/asterisk/at/greater)
    "PearsonMATHPRO11": {
        "*": "\u0302",  # combining circumflex accent (hat)
        "@": "\u0307",  # combining dot above
        ">": "\u20D7",  # combining right arrow above (vector)
        "V": "\u030C",  # combining caron (check mark)
    },
    # Large plus and comma (CharSet: /comma/plus)
    "PearsonMATHPRO12": {
        "+": "+",       # plus (display size)
        ",": ",",       # comma (display size)
    },
    # Very large delimiters (CharSet: /asterisk/c/f/g/parenleft/parenright/plus)
    "PearsonMATHPRO13": {
        "c": "\u222B",  # integral (large)
        "f": "\u222B",  # integral variant
        "g": "\u222C",  # double integral
        "*": "\u00D7",  # multiplication
    },
    # Large operators (CharSet: /P/quotedbl)
    "PearsonMATHPRO16": {
        "P": "\u220F",  # N-ary product (display size)
        '"': "\u2211",  # summation (display size)
    },
    # Delimiters of various sizes
    # CharSet: /.notdef/a/b/c/d/e/f/five/four/greater/greaterequal/n/
    #          one/section/six/space/sterling/three/two/yen
    "PearsonMATHPRO18": {
        "1": "(",       # open paren (glyph name: one -> parenleft)
        "2": ")",       # close paren (glyph name: two -> parenright)
        "3": "[",       # open bracket (glyph name: three -> bracketleft)
        "4": "]",       # close bracket (glyph name: four -> bracketright)
        "5": "{",       # open brace (glyph name: five -> braceleft)
        "6": "}",       # close brace (glyph name: six -> braceright)
        ">": "/",       # fraction bar / division slash (glyph name: greater)
        "a": "(",       # large open paren
        "b": ")",       # large close paren
        "c": "[",       # large open bracket
        "d": "]",       # large close bracket
        "e": "{",       # large open brace
        "f": "}",       # large close brace
    },
    # Large radical / bracket variants (CharSet: /numbersign/three)
    "PearsonMATHPRO19": {
        "3": "[",       # bracket variant
        "#": "\u221A",  # radical variant
    },
    # Tall radical / bracket variants (CharSet: /A/B/C/four/one/two)
    # Very tall glyphs (Ascent 5999) used for tall radicals and brackets
    # Context analysis: [PRO01 'σ'][PRO20 '2'][Roman 'T'] = σ√T
    "PearsonMATHPRO20": {
        "1": "(",       # tall open paren
        "2": "\u221A",  # square root (tall radical - confirmed by context σ√T)
        "4": "]",       # tall close bracket
        "A": "(",       # tall open paren variant
        "B": ")",       # tall close paren variant
        "C": "[",       # tall open bracket variant
    },
    # MathematicalPiLTStd already maps most chars correctly via ToUnicode,
    # but a few identity entries for completeness:
    "MathematicalPiLTStd": {
        # Most chars already correct (Delta, Sigma, etc.) - no corrections needed
    },
    # MathematicalPiLTStd-1 has custom glyphs at ASCII positions
    # CharSet: /five/one/two  (but also D, P, d, s at other codes)
    "MathematicalPiLTStd-1": {
        "5": "\u221A",  # square root
        "1": "\u222B",  # integral
        "2": "\u222B",  # integral variant / double integral
        "D": "\u2206",  # increment/Delta
        "P": "\u220F",  # product
        "d": "\u2202",  # partial differential
        "s": "\u2211",  # summation
    },
    # PearsonMATHPRO15 (CharSet: /E/U) - rarely seen
    "PearsonMATHPRO15": {
        "E": "\u2203",  # there exists
        "U": "\u222A",  # union
    },
}

# Characters in math fonts that should NOT be corrected (spaces, etc.)
SKIP_CHARS = {" ", "\t", "\n", "\r", "\x08", "\x1f"}


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
    """Return the correction table for a given font, or None if not a math font."""
    base = font_base_name(font_name)
    # Try exact match first, then prefix match
    if base in MATH_FONT_CORRECTIONS:
        return MATH_FONT_CORRECTIONS[base]
    # Handle numbered variants that may not be in the table
    for prefix in sorted(MATH_FONT_CORRECTIONS.keys(), key=len, reverse=True):
        if base.startswith(prefix):
            return MATH_FONT_CORRECTIONS[prefix]
    return None


def correct_char(char: str, font_name: str) -> str:
    """Correct a single character based on its font.

    Returns the corrected character, or the original if no correction is needed.
    """
    if char in SKIP_CHARS:
        return char
    table = get_correction_table(font_name)
    if table is None:
        return char
    return table.get(char, char)


# ---------------------------------------------------------------------------
# PDF text extraction with font-aware correction
# ---------------------------------------------------------------------------

class PDFLine:
    """Represents one line of text extracted from the PDF."""

    def __init__(self):
        self.spans: list[tuple[str, str, str]] = []  # (font, raw_text, corrected_text)

    @property
    def raw_text(self) -> str:
        return "".join(raw for _, raw, _ in self.spans)

    @property
    def corrected_text(self) -> str:
        return "".join(corr for _, _, corr in self.spans)

    @property
    def has_math(self) -> bool:
        return any(is_math_font(font) for font, _, _ in self.spans)

    def __repr__(self):
        return f"PDFLine(raw={self.raw_text!r}, corrected={self.corrected_text!r})"


def extract_page_lines(doc: fitz.Document, page_idx: int) -> list[PDFLine]:
    """Extract all text lines from a PDF page with font-aware correction."""
    page = doc[page_idx]
    text_dict = page.get_text("dict")
    lines: list[PDFLine] = []

    for block in text_dict.get("blocks", []):
        if block.get("type") == 1:  # image block
            continue
        for line_data in block.get("lines", []):
            pdf_line = PDFLine()
            for span in line_data.get("spans", []):
                font = span.get("font", "")
                raw = span.get("text", "")
                # Apply character-by-character correction
                corrected_chars = []
                for ch in raw:
                    corrected_chars.append(correct_char(ch, font))
                corrected = "".join(corrected_chars)
                pdf_line.spans.append((font, raw, corrected))
            if pdf_line.raw_text.strip():
                lines.append(pdf_line)

    return lines


def build_page_text(lines: list[PDFLine], corrected: bool = True) -> str:
    """Build full page text from extracted lines."""
    parts = []
    for line in lines:
        text = line.corrected_text if corrected else line.raw_text
        parts.append(text)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# EPUB processing
# ---------------------------------------------------------------------------

def has_equations(html: str) -> bool:
    """Check if an XHTML page contains equation content."""
    return 'class="equation"' in html or 'class="eq-inline"' in html


def extract_equation_texts(html: str) -> list[tuple[str, str, int, int]]:
    """Extract equation element texts from the EPUB HTML.

    Returns a list of (full_match, inner_text, start_pos, end_pos).
    inner_text has HTML tags stripped.
    """
    results = []

    # Match <div class="equation" ...><span class="eq-inline">...</span></div>
    # and also standalone <span class="eq-inline">...</span>
    pattern = re.compile(
        r'(<div\s+class="equation"[^>]*>\s*<span\s+class="eq-inline">)(.*?)(</span>\s*</div>)',
        re.DOTALL,
    )
    for m in pattern.finditer(html):
        full = m.group(0)
        inner_html = m.group(2)
        # Strip HTML tags to get raw text
        inner_text = re.sub(r"<[^>]+>", "", inner_html)
        # Decode HTML entities
        inner_text = (
            inner_text.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
        )
        results.append((full, inner_text, m.start(), m.end()))

    return results


def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace into single spaces and strip."""
    return re.sub(r"\s+", " ", text).strip()


def strip_all_spaces(text: str) -> str:
    """Remove ALL whitespace from text for fuzzy matching."""
    return re.sub(r"\s+", "", text)


def find_matching_lines(
    eq_text: str,
    pdf_lines: list[PDFLine],
) -> tuple[int, int] | None:
    """Find the range of PDF lines that correspond to a given EPUB equation.

    Uses space-stripped comparison: the EPUB equation text with all spaces removed
    should match a contiguous sequence of PDF lines (also space-stripped).

    Returns (start_idx, end_idx_exclusive) or None.
    """
    eq_stripped = strip_all_spaces(eq_text)
    if not eq_stripped or len(eq_stripped) < 2:
        return None

    # Build space-stripped raw text for each line
    raw_stripped = [strip_all_spaces(l.raw_text) for l in pdf_lines]

    # Try window sizes from 1 to 8 lines
    max_window = min(8, len(pdf_lines))
    best_match: tuple[int, int, float] | None = None  # (start, end, score)

    for window_size in range(1, max_window + 1):
        for i in range(len(pdf_lines) - window_size + 1):
            combined = "".join(raw_stripped[i : i + window_size])
            if not combined:
                continue

            # Check for exact substring match (either direction)
            if eq_stripped == combined:
                score = 1.0
            elif eq_stripped in combined:
                score = len(eq_stripped) / len(combined)
            elif combined in eq_stripped:
                score = len(combined) / len(eq_stripped)
            else:
                # Try bigram similarity for partial matches
                score = _bigram_similarity(eq_stripped, combined)

            if score > 0.5:
                # Prefer exact matches and smaller windows (more precise)
                adjusted = score - (window_size * 0.01)
                if best_match is None or adjusted > best_match[2]:
                    best_match = (i, i + window_size, adjusted)
                # If we found an exact match, stop
                if score >= 0.99:
                    return (i, i + window_size)

    if best_match is not None:
        return (best_match[0], best_match[1])
    return None


def _bigram_similarity(a: str, b: str) -> float:
    """Bigram (character-pair) Jaccard similarity between two strings."""
    if not a or not b:
        return 0.0
    if len(a) < 2 or len(b) < 2:
        return 1.0 if a == b else 0.0
    ba = set(a[i : i + 2] for i in range(len(a) - 1))
    bb = set(b[i : i + 2] for i in range(len(b) - 1))
    intersection = len(ba & bb)
    union = len(ba | bb)
    return intersection / union if union > 0 else 0.0


def build_corrected_for_equation(
    eq_text: str,
    pdf_lines: list[PDFLine],
) -> str | None:
    """Given garbled equation text from EPUB, find the corresponding corrected text
    from the PDF extraction.

    Strategy:
    - The garbled EPUB text matches the UNCORRECTED PDF extraction (since the EPUB
      was built from the same extraction path that didn't account for font encoding).
    - Find where the equation text appears in the uncorrected PDF output.
    - Return the corrected version from the same position.
    """
    eq_norm = normalize_whitespace(eq_text)
    if not eq_norm or len(eq_norm) < 2:
        return None

    match = find_matching_lines(eq_text, pdf_lines)
    if match is None:
        return None

    start, end = match
    matched_lines = pdf_lines[start:end]

    # Build the corrected text from the matched lines
    corrected_parts = []
    for line in matched_lines:
        corrected_parts.append(line.corrected_text.strip())
    corrected = " ".join(corrected_parts)
    corrected_norm = normalize_whitespace(corrected)

    # Only return if there's actually a difference
    if corrected_norm != eq_norm:
        return corrected_norm

    return None


def apply_corrections_to_html(
    html: str,
    pdf_lines: list[PDFLine],
    page_num: int,
    verbose: bool = False,
) -> tuple[str, list[dict]]:
    """Apply font-aware corrections to equation elements in the EPUB HTML.

    Returns (corrected_html, list_of_changes).
    """
    changes: list[dict] = []
    equations = extract_equation_texts(html)

    if not equations:
        return html, changes

    # Process equations in reverse order so string positions stay valid
    for full_match, inner_text, start, end in reversed(equations):
        corrected = build_corrected_for_equation(inner_text, pdf_lines)
        if corrected is None:
            continue

        inner_text_norm = normalize_whitespace(inner_text)
        if corrected == inner_text_norm:
            continue

        # Build the replacement: keep the div/span wrapper, replace inner text
        # The full_match is: <div class="equation"...><span class="eq-inline">CONTENT</span></div>
        new_match = re.sub(
            r'(<span\s+class="eq-inline">)(.*?)(</span>)',
            lambda m: m.group(1) + corrected + m.group(3),
            full_match,
            flags=re.DOTALL,
        )

        if new_match != full_match:
            html = html[:start] + new_match + html[end:]
            changes.append({
                "page": page_num,
                "original": inner_text_norm,
                "corrected": corrected,
            })
            if verbose:
                print(f"  Page {page_num}: [{inner_text_norm[:60]}...]")
                print(f"         -> [{corrected[:60]}...]")

    return html, changes


def apply_inline_math_corrections(
    html: str,
    pdf_lines: list[PDFLine],
    page_num: int,
    verbose: bool = False,
) -> tuple[str, list[dict]]:
    """Apply corrections to inline math that appears outside equation divs.

    These are math symbols embedded in regular paragraph text. We correct them
    by finding the corresponding PDF line and applying the font-based corrections
    character by character.

    This handles patterns like:
    - "s" that should be "sigma" in running text
    - "0 f / 0 t" that should be "partial f / partial t"
    - "6" and "7" that should be "less-equal" and "greater-equal"
    """
    changes: list[dict] = []

    # Build a lookup of uncorrected -> corrected for lines that have math content
    replacements: list[tuple[str, str]] = []
    for line in pdf_lines:
        if not line.has_math:
            continue
        raw = line.raw_text
        corr = line.corrected_text
        if raw != corr and len(raw.strip()) > 2:
            replacements.append((raw.strip(), corr.strip()))

    # Sort by length descending to match longer strings first
    replacements.sort(key=lambda x: len(x[0]), reverse=True)

    for raw, corr in replacements:
        # Only apply if the raw text appears in the HTML body text
        # Be careful not to match inside HTML tags or attributes
        # We search in the text content between tags
        escaped_raw = re.escape(raw)
        # Try to find and replace in text content (not inside tags)
        pattern = re.compile(
            r"(?<=>)([^<]*?" + escaped_raw + r"[^<]*?)(?=<)",
        )

        def replace_in_text(m):
            text = m.group(1)
            new_text = text.replace(raw, corr, 1)
            if new_text != text:
                changes.append({
                    "page": page_num,
                    "type": "inline",
                    "original": raw[:60],
                    "corrected": corr[:60],
                })
            return new_text

        new_html = pattern.sub(replace_in_text, html, count=1)
        if new_html != html:
            html = new_html

    return html, changes


# ---------------------------------------------------------------------------
# Main processing logic
# ---------------------------------------------------------------------------

def process_page(
    doc: fitz.Document,
    xhtml_path: Path,
    page_num: int,
    dry_run: bool = False,
    verbose: bool = False,
) -> list[dict]:
    """Process a single EPUB page: extract PDF text, find equations, apply corrections."""
    # Read the EPUB XHTML
    html = xhtml_path.read_text(encoding="utf-8")

    if not has_equations(html):
        return []

    # PDF page index is 0-based, EPUB page number is 1-based
    pdf_page_idx = page_num - 1
    if pdf_page_idx < 0 or pdf_page_idx >= len(doc):
        return []

    # Extract PDF lines with font-aware correction
    pdf_lines = extract_page_lines(doc, pdf_page_idx)

    # Apply corrections to equation elements
    new_html, eq_changes = apply_corrections_to_html(
        html, pdf_lines, page_num, verbose=verbose
    )

    # Also apply inline math corrections
    new_html, inline_changes = apply_inline_math_corrections(
        new_html, pdf_lines, page_num, verbose=verbose
    )

    all_changes = eq_changes + inline_changes

    if all_changes and not dry_run:
        xhtml_path.write_text(new_html, encoding="utf-8")

    return all_changes


def main():
    parser = argparse.ArgumentParser(
        description="Fix corrupted math equations in EPUB using font-aware PDF extraction"
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
        help="Comma-separated list of page numbers to process (default: all)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed information about each correction",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("FIX EQUATIONS: Font-aware PDF text extraction")
    print("=" * 70)

    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found at {PDF_PATH}")
        sys.exit(1)

    if not EPUB_DIR.exists():
        print(f"ERROR: EPUB directory not found at {EPUB_DIR}")
        sys.exit(1)

    # Discover XHTML files
    xhtml_files = sorted(
        EPUB_DIR.glob("full_book_v7_p*.xhtml"),
        key=lambda f: int(f.stem.split("_p")[1]),
    )
    print(f"Found {len(xhtml_files)} XHTML files in {EPUB_DIR}")

    # Filter to specific pages if requested
    if args.pages:
        target_pages = set(int(p.strip()) for p in args.pages.split(","))
        xhtml_files = [
            f for f in xhtml_files if int(f.stem.split("_p")[1]) in target_pages
        ]
        print(f"Processing {len(xhtml_files)} specific page(s): {sorted(target_pages)}")

    # Open PDF
    doc = fitz.open(str(PDF_PATH))
    print(f"PDF: {PDF_PATH.name} ({len(doc)} pages)")

    if args.dry_run:
        print("\n*** DRY RUN MODE - no files will be modified ***\n")

    # Process each page
    total_changes = 0
    pages_changed = 0
    all_changes: list[dict] = []
    pages_with_equations = 0
    pages_scanned = 0

    for xhtml_path in xhtml_files:
        page_num = int(xhtml_path.stem.split("_p")[1])
        pages_scanned += 1

        # Quick check: does this page have equations?
        html_preview = xhtml_path.read_text(encoding="utf-8")
        if not has_equations(html_preview):
            continue

        pages_with_equations += 1

        changes = process_page(
            doc, xhtml_path, page_num,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

        if changes:
            pages_changed += 1
            total_changes += len(changes)
            all_changes.extend(changes)
            if not args.verbose:
                print(f"  Page {page_num}: {len(changes)} correction(s)")

    doc.close()

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Pages scanned:         {pages_scanned}")
    print(f"Pages with equations:  {pages_with_equations}")
    print(f"Pages corrected:       {pages_changed}")
    print(f"Total corrections:     {total_changes}")

    if args.dry_run:
        print("\n*** DRY RUN - no files were modified ***")

    if all_changes and args.verbose:
        print("\nDetailed changes:")
        for ch in all_changes[:50]:
            ch_type = ch.get("type", "equation")
            print(f"  Page {ch['page']} ({ch_type}):")
            print(f"    FROM: {ch['original'][:80]}")
            print(f"    TO:   {ch['corrected'][:80]}")
        if len(all_changes) > 50:
            print(f"  ... and {len(all_changes) - 50} more changes")

    print("\nDone.")


if __name__ == "__main__":
    main()
