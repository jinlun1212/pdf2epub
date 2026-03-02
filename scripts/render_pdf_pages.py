"""
Render PDF pages as PNG images for visual comparison with EPUB.

Usage:
    python scripts/render_pdf_pages.py --pages 301-325
    python scripts/render_pdf_pages.py --pages 53,100,273
    python scripts/render_pdf_pages.py --all

Output: output/pdf_renders/page_NNN.png
"""
import sys
import io
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.parent.resolve()
PDF_PATH = BASE_DIR / "options_futures_and_other_derivatives_11th.pdf"
RENDER_DIR = BASE_DIR / "output" / "pdf_renders"


def render_pages(page_nums, dpi=150):
    """Render specified PDF pages as PNG images."""
    import fitz
    RENDER_DIR.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(PDF_PATH))
    total = len(doc)

    rendered = 0
    for pn in page_nums:
        if pn < 1 or pn > total:
            print(f"  Skipping page {pn} (out of range 1-{total})")
            continue
        out_path = RENDER_DIR / f"page_{pn:04d}.png"
        if out_path.exists():
            continue  # skip already rendered
        page = doc[pn - 1]
        pix = page.get_pixmap(dpi=dpi)
        pix.save(str(out_path))
        rendered += 1

    doc.close()
    print(f"Rendered {rendered} new pages to {RENDER_DIR}")


def parse_page_spec(spec):
    """Parse page specification like '301-325' or '53,100,273' or 'all'."""
    pages = []
    for part in spec.split(','):
        part = part.strip()
        if '-' in part:
            start, end = part.split('-', 1)
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(part))
    return sorted(set(pages))


def main():
    parser = argparse.ArgumentParser(description='Render PDF pages as PNG')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--pages', type=str, help='Page numbers: 301-325 or 53,100,273')
    group.add_argument('--all', action='store_true', help='Render all 880 pages')
    parser.add_argument('--dpi', type=int, default=150, help='Resolution (default 150)')
    args = parser.parse_args()

    if args.all:
        import fitz
        doc = fitz.open(str(PDF_PATH))
        page_nums = list(range(1, len(doc) + 1))
        doc.close()
    else:
        page_nums = parse_page_spec(args.pages)

    print(f"Rendering {len(page_nums)} pages at {args.dpi} DPI...")
    render_pages(page_nums, dpi=args.dpi)


if __name__ == '__main__':
    main()
