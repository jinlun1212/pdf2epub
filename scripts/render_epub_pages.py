"""
Render EPUB XHTML pages as PNG images for visual comparison with PDF.

Uses Playwright (headless Chromium) to render each page with the stylesheet applied.

Usage:
    python scripts/render_epub_pages.py --pages 301-325
    python scripts/render_epub_pages.py --pages 53,100,273
    python scripts/render_epub_pages.py --all
    python scripts/render_epub_pages.py --all --force   # re-render existing

Output: output/epub_renders/page_NNNN.png
"""
import sys
import io
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.parent.resolve()
EPUB_DIR = BASE_DIR / "output" / "full_book_extracted" / "EPUB"
RENDER_DIR = BASE_DIR / "output" / "epub_renders"
CSS_PATH = EPUB_DIR / "style.css"


def render_pages(page_nums, force=False, width=800):
    """Render specified EPUB XHTML pages as PNG images."""
    from playwright.sync_api import sync_playwright

    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    css_text = CSS_PATH.read_text(encoding='utf-8') if CSS_PATH.exists() else ""

    rendered = 0
    skipped = 0

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={'width': width, 'height': 1200},
            device_scale_factor=1,
        )
        page = context.new_page()

        for pn in page_nums:
            xhtml_path = EPUB_DIR / f"full_book_v7_p{pn}.xhtml"
            out_path = RENDER_DIR / f"page_{pn:04d}.png"

            if not xhtml_path.exists():
                print(f"  Skipping page {pn} (XHTML not found)")
                skipped += 1
                continue

            if out_path.exists() and not force:
                skipped += 1
                continue

            # Load the XHTML file
            file_url = xhtml_path.as_uri()
            page.goto(file_url, wait_until='load')

            # Inject the stylesheet
            if css_text:
                page.add_style_tag(content=css_text)

            # Wait for images to load
            page.wait_for_timeout(200)

            # Screenshot full page
            page.screenshot(path=str(out_path), full_page=True)
            rendered += 1

            if rendered % 50 == 0:
                print(f"  Rendered {rendered} pages...")

        browser.close()

    print(f"Rendered {rendered} new pages to {RENDER_DIR}")
    if skipped:
        print(f"  ({skipped} skipped)")


def parse_page_spec(spec):
    """Parse page specification like '301-325' or '53,100,273'."""
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
    parser = argparse.ArgumentParser(description='Render EPUB pages as PNG')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--pages', type=str, help='Page numbers: 301-325 or 53,100,273')
    group.add_argument('--all', action='store_true', help='Render all pages')
    parser.add_argument('--force', action='store_true', help='Re-render existing images')
    parser.add_argument('--width', type=int, default=800, help='Viewport width (default 800)')
    args = parser.parse_args()

    if args.all:
        # Find all XHTML files
        files = sorted(EPUB_DIR.glob('full_book_v7_p*.xhtml'))
        page_nums = [int(f.stem.split('_p')[1]) for f in files]
    else:
        page_nums = parse_page_spec(args.pages)

    print(f"Rendering {len(page_nums)} EPUB pages...")
    render_pages(page_nums, force=args.force, width=args.width)


if __name__ == '__main__':
    main()
