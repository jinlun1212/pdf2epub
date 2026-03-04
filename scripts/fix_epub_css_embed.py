"""
Embed CSS directly into each XHTML file and convert remaining inline equations.

Fixes two issues:
1. Some EPUB readers don't load external CSS files - embed <style> block in each page
2. Many equations still in <p> tags - convert to centered <div class="equation">

Run: python scripts/fix_epub_css_embed.py [--dry-run] [--verbose] [--pages 100-200]
"""
import sys
import io
import re
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.parent.resolve()
EPUB_DIR = BASE_DIR / "output" / "full_book_extracted" / "EPUB"
CSS_PATH = EPUB_DIR / "style.css"

STATS = {}

def count(name):
    STATS[name] = STATS.get(name, 0) + 1


def embed_css(html):
    """Replace <link> to style.css with embedded <style> block."""
    css_content = CSS_PATH.read_text(encoding='utf-8')
    changed = False

    # Remove existing <link> to style.css
    new = re.sub(
        r'\s*<link\s+rel="stylesheet"\s+type="text/css"\s+href="style\.css"\s*/>\s*',
        '',
        html
    )
    if new != html:
        html = new

    # Check if <style> already embedded
    if '<style>' in html or '<style ' in html:
        return html, False

    # Embed CSS as <style> block in <head>
    style_block = f'\n    <style type="text/css">\n{css_content}\n    </style>\n  '
    html = html.replace('</head>', f'{style_block}</head>')
    changed = True
    count('css_embedded')
    return html, changed


def convert_remaining_equations(html):
    """Convert remaining equations in <p> tags to centered <div class="equation">."""
    changed = False

    # Pattern 1: <p> that contains eq-inline spans and is SHORT (equation-like)
    # These are display equations that should be centered
    def maybe_convert(m):
        nonlocal changed
        full = m.group(0)
        content = m.group(1).strip()

        # Get plain text (strip HTML tags)
        text_only = re.sub(r'<[^>]+>', '', content).strip()

        # Skip if it's clearly prose (long text with common English words)
        word_count = len(text_only.split())
        has_prose = bool(re.search(
            r'\b(the|and|that|this|from|with|where|which|when|since|because|'
            r'however|therefore|assume|consider|suppose|we|is|are|was|were|'
            r'has|have|had|can|will|would|should|may|might|must|shall|'
            r'if|for|but|not|into|than|then|also|each|such|'
            r'company|market|price|rate|value|contract|option|futures|'
            r'interest|payment|hedg|portfolio|arbitrag|investor|'
            r'calculate|determine|estimate|explain|show|find|give)\b',
            text_only, re.I
        ))

        # Count eq-inline spans (math operators)
        eq_inline_count = len(re.findall(r'<span class="eq-inline">', content))

        # Heuristics for "is this a display equation?"
        is_equation = False

        # Short content with math operators = likely equation
        if word_count <= 12 and eq_inline_count >= 1 and not has_prose:
            is_equation = True

        # Very short with = sign = likely equation
        if word_count <= 8 and '=' in text_only:
            is_equation = True

        # Has eq-inline = or similar and is short enough
        if (eq_inline_count >= 2 and word_count <= 6):
            is_equation = True

        # Starts with a variable definition pattern: "X = ..."
        if re.match(r'^<em>[A-Za-z]</em>', content) and '=' in text_only and word_count <= 15 and not has_prose:
            is_equation = True

        if is_equation:
            changed = True
            count('p_to_equation')
            return f'<div class="equation"><span class="eq-inline">{content}</span></div>'

        return full

    new = re.sub(
        r'<p>((?:(?!</p>).)*?<span class="eq-inline">(?:(?!</p>).)*?)</p>',
        maybe_convert,
        html,
        flags=re.DOTALL
    )
    if new != html:
        html = new

    return html, changed


def process_file(filepath, page_num, dry_run=False, verbose=False):
    """Apply CSS embedding and equation fixes to a single XHTML file."""
    html = filepath.read_text(encoding='utf-8')
    original = html
    fixes = []

    html, fixed = embed_css(html)
    if fixed:
        fixes.append('css_embedded')

    html, fixed = convert_remaining_equations(html)
    if fixed:
        fixes.append('equations_converted')

    if html != original:
        if verbose and fixes:
            print(f"  Page {page_num}: {', '.join(fixes)}")
        if not dry_run:
            filepath.write_text(html, encoding='utf-8')

    return fixes


def parse_page_spec(spec):
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
    parser = argparse.ArgumentParser(description='Embed CSS and fix remaining equations')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--pages', type=str, help='Page range, e.g., 100-200')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    print("Embedding CSS and fixing remaining equations...")
    if args.dry_run:
        print("DRY RUN")

    files = sorted(
        EPUB_DIR.glob('full_book_v7_p*.xhtml'),
        key=lambda f: int(f.stem.split('_p')[1])
    )

    if args.pages:
        page_set = set(parse_page_spec(args.pages))
        files = [f for f in files if int(f.stem.split('_p')[1]) in page_set]

    print(f"Processing {len(files)} files\n")

    fixed_pages = []
    for f in files:
        pn = int(f.stem.split('_p')[1])
        fixes = process_file(f, pn, dry_run=args.dry_run, verbose=args.verbose)
        if fixes:
            fixed_pages.append((pn, fixes))

    print(f"\n{'='*50}")
    print(f"CSS EMBED & EQUATION FIX SUMMARY")
    print(f"{'='*50}")
    print(f"Pages modified: {len(fixed_pages)}")
    for name, count_val in sorted(STATS.items()):
        print(f"  {name}: {count_val}")


if __name__ == '__main__':
    main()
