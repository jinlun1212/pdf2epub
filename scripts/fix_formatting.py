"""
Fix formatting issues in EPUB XHTML pages.

Safe structural cleanup:
1. Merge split chapter headings (each letter a separate <strong> tag)
2. Merge adjacent <em> tags
3. Merge adjacent <strong> tags
4. Remove redundant inline styles from <p> tags (already in CSS)

Run from anywhere: python scripts/fix_formatting.py [--dry-run] [--verbose]
"""
import sys
import io
import re
import argparse
from pathlib import Path

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.parent.resolve()
EPUB_DIR = BASE_DIR / "output" / "full_book_extracted" / "EPUB"

# Exact inline style that duplicates CSS p rules
REDUNDANT_P_STYLE = ' style="text-align: justify; text-justify: inter-word; -webkit-hyphens: auto; hyphens: auto;"'


def fix_split_letter_headings(html):
    """Merge chapter headings where each letter is a separate <strong> tag.

    Example: <strong>C</strong> <strong>H</strong> <strong>A</strong> ...
    becomes: <strong>CHAPTER</strong>
    """
    pattern = r'(<strong>[A-Z]</strong>\s*){2,}'

    def merge_letters(m):
        text = m.group(0)
        letters = re.findall(r'<strong>([A-Z])</strong>', text)
        merged = ''.join(letters)
        return f'<strong>{merged}</strong>'

    new_html = re.sub(pattern, merge_letters, html)
    return new_html, new_html != html


def fix_adjacent_em_tags(html):
    """Merge adjacent <em> tags: <em>X</em><em>Y</em> -> <em>XY</em>
    Also: <em>X</em> <em>Y</em> -> <em>X Y</em>
    """
    pattern = r'</em>(\s*)<em>'
    new_html = re.sub(pattern, r'\1', html)
    return new_html, new_html != html


def fix_adjacent_strong_tags(html):
    """Merge adjacent <strong> tags: <strong>X</strong><strong>Y</strong> -> <strong>XY</strong>"""
    pattern = r'</strong>(\s*)<strong>'
    new_html = re.sub(pattern, r'\1', html)
    return new_html, new_html != html


def fix_redundant_inline_styles(html):
    """Remove redundant inline styles from <p> tags that duplicate CSS rules."""
    if REDUNDANT_P_STYLE not in html:
        return html, False
    new_html = html.replace(REDUNDANT_P_STYLE, '')
    return new_html, new_html != html


# Fix registry — order matters (tag merging before content cleanup)
FIXES = [
    ('split_letter_headings', fix_split_letter_headings),
    ('adjacent_em_tags', fix_adjacent_em_tags),
    ('adjacent_strong_tags', fix_adjacent_strong_tags),
    ('redundant_inline_styles', fix_redundant_inline_styles),
]


def process_file(filepath, page_num, dry_run=False, verbose=False):
    """Apply all formatting fixes to a single XHTML file."""
    html = filepath.read_text(encoding='utf-8')
    original = html
    fixes = []

    for name, fix_func in FIXES:
        html, fixed = fix_func(html)
        if fixed:
            fixes.append(name)

    if html != original:
        if verbose and fixes:
            print(f"  Page {page_num}: {', '.join(fixes)}")
        if not dry_run:
            filepath.write_text(html, encoding='utf-8')

    return fixes


def main():
    parser = argparse.ArgumentParser(description='Fix EPUB formatting issues')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without modifying files')
    parser.add_argument('--pages', type=str, help='Comma-separated page numbers to process')
    parser.add_argument('--verbose', action='store_true', help='Show per-page details')
    args = parser.parse_args()

    print("Fixing EPUB formatting...")
    print(f"EPUB dir: {EPUB_DIR}")
    if args.dry_run:
        print("DRY RUN — no files will be modified")

    files = sorted(
        EPUB_DIR.glob('full_book_v7_p*.xhtml'),
        key=lambda f: int(f.stem.split('_p')[1])
    )

    if args.pages:
        page_set = set(int(p) for p in args.pages.split(','))
        files = [f for f in files if int(f.stem.split('_p')[1]) in page_set]

    print(f"Processing {len(files)} XHTML files\n")

    stats = {name: 0 for name, _ in FIXES}
    fixed_pages = []

    for f in files:
        page_num = int(f.stem.split('_p')[1])
        fixes = process_file(f, page_num, dry_run=args.dry_run, verbose=args.verbose)
        if fixes:
            fixed_pages.append((page_num, fixes))
            for fix in fixes:
                stats[fix] += 1

    print(f"\n{'='*50}")
    print(f"FORMATTING FIX SUMMARY")
    print(f"{'='*50}")
    print(f"Total pages modified: {len(fixed_pages)}")
    for fix_type, count in stats.items():
        print(f"  {fix_type}: {count} pages")

    if fixed_pages and args.verbose:
        print(f"\nAll fixed pages:")
        for page, fixes in fixed_pages:
            print(f"  Page {page}: {', '.join(fixes)}")


if __name__ == '__main__':
    main()
