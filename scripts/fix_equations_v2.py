"""
Comprehensive equation formatting fix for all EPUB pages.

Fixes:
1. Add <link> to style.css in every XHTML <head>
2. Convert <p>-tag equations to <div class="equation"> blocks
3. Convert <strong>(N.N)</strong> equation numbers to <span class="eq-number">
4. Fix exponent grouping: e<span>-</span><sup>rT</sup> -> e<sup>-rT</sup>
5. Fix missing subscripts: S0 -> S<sub>0</sub>, F0, d1, d2, etc.
6. Strip redundant <span class="eq-inline"> wrappers on single operators
7. Merge consecutive fragmented equation divs into single blocks

Run: python scripts/fix_equations_v2.py [--dry-run] [--verbose] [--pages 100-200]
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

STATS = {}

def count(name):
    STATS[name] = STATS.get(name, 0) + 1


# -------------------------------------------------------------------
# Fix 1: Add stylesheet link to <head>
# -------------------------------------------------------------------
def fix_stylesheet_link(html):
    changed = False
    if 'href="style.css"' not in html:
        html = html.replace(
            '</head>',
            '    <link rel="stylesheet" type="text/css" href="style.css"/>\n  </head>'
        )
        changed = True
        count('stylesheet_link')
    return html, changed


# -------------------------------------------------------------------
# Fix 2: Convert <p>-tag numbered equations to <div class="equation">
# Pattern: <p>...equation content...<strong>(N.N)</strong></p>
# where the <p> content is predominantly math (has eq-inline or is short)
# -------------------------------------------------------------------
def fix_p_tag_equations(html):
    changed = False

    # Pattern: <p> containing eq-inline spans AND ending with <strong>(N.N)</strong>
    # These are numbered display equations stuck in <p> tags
    def convert_numbered_eq(m):
        nonlocal changed
        content = m.group(1)
        eq_num = m.group(2)
        changed = True
        count('p_to_div_numbered')
        # Clean up tab characters before equation number
        content = content.rstrip('\t ')
        return f'<div class="equation"><span class="eq-inline">{content}</span><span class="eq-number">({eq_num})</span></div>'

    # Match <p> with eq-inline content ending in <strong>(N.N)</strong>
    new = re.sub(
        r'<p>((?:(?!</p>).)*?<span class="eq-inline">(?:(?!</p>).)*?)\s*\t*\s*<strong>\((\d+[A-Za-z]?\.?\d*)\)</strong>\s*</p>',
        convert_numbered_eq,
        html,
        flags=re.DOTALL
    )
    if new != html:
        html = new

    # Also match <p> with math content ending in bold equation number, no eq-inline needed
    # Pattern: short <p> with math symbols ending in <strong>(N.N)</strong>
    def convert_math_p_numbered(m):
        nonlocal changed
        full = m.group(0)
        content = m.group(1)
        eq_num = m.group(2)
        # Only convert if it looks like an equation (has math operators or variables)
        text_only = re.sub(r'<[^>]+>', '', content).strip()
        if len(text_only) < 200 and re.search(r'[=+\-×÷<>≤≥∑∏∫]|<em>|<sup>|<sub>', content):
            changed = True
            count('p_to_div_numbered')
            content = content.rstrip('\t ')
            return f'<div class="equation"><span class="eq-inline">{content}</span><span class="eq-number">({eq_num})</span></div>'
        return full

    new = re.sub(
        r'<p>((?:(?!</p>).)*?)\s*\t*\s*<strong>\((\d+[A-Za-z]?\.?\d*)\)</strong>\s*</p>',
        convert_math_p_numbered,
        html,
        flags=re.DOTALL
    )
    if new != html:
        html = new

    # Convert unnumbered equation <p> tags that contain ONLY math
    # (no prose text, just variables and operators)
    def convert_unnumbered_eq(m):
        nonlocal changed
        content = m.group(1).strip()
        # Get plain text
        text_only = re.sub(r'<[^>]+>', '', content).strip()
        # Must be short, have math content, no long prose
        if (len(text_only) < 120 and
            len(text_only.split()) < 15 and
            re.search(r'[=<>≤≥]', text_only) and
            not re.search(r'\b(the|and|that|this|from|with|where|which|when|since|because)\b', text_only, re.I)):
            changed = True
            count('p_to_div_unnumbered')
            return f'<div class="equation"><span class="eq-inline">{content}</span></div>'
        return m.group(0)

    new = re.sub(
        r'<p>((?:(?!</p>).)*?<span class="eq-inline">(?:(?!</p>).)*?)</p>',
        convert_unnumbered_eq,
        html,
        flags=re.DOTALL
    )
    if new != html:
        html = new

    return html, changed


# -------------------------------------------------------------------
# Fix 3: Fix exponent grouping
# e<span class="eq-inline">-</span><em><sup>rT</sup></em> -> e<sup>-<em>rT</em></sup>
# e<span class="eq-inline">-</span><sup>... -> e<sup>-...
# -------------------------------------------------------------------
def fix_exponent_grouping(html):
    changed = False

    # Pattern: e followed by minus in eq-inline, then superscript
    # e<span class="eq-inline">-</span><em><sup>XY</sup></em>
    new = re.sub(
        r'<em>e</em><span class="eq-inline">-</span><em><sup>([^<]+)</sup></em>',
        r'<em>e</em><sup>-<em>\1</em></sup>',
        html
    )
    if new != html:
        changed = True
        count('exponent_fix')
        html = new

    # e<span class="eq-inline">-</span><sup>XY</sup>
    new = re.sub(
        r'<em>e</em><span class="eq-inline">-</span><sup>([^<]+)</sup>',
        r'<em>e</em><sup>-\1</sup>',
        html
    )
    if new != html:
        changed = True
        count('exponent_fix')
        html = new

    # Ke-rT pattern: Ke<span...>-</span><sup>rT</sup>
    new = re.sub(
        r'([A-Za-z])<em>e</em><span class="eq-inline">-</span><em><sup>([^<]+)</sup></em>',
        r'\1<em>e</em><sup>-<em>\2</em></sup>',
        html
    )
    if new != html:
        changed = True
        count('exponent_fix')
        html = new

    return html, changed


# -------------------------------------------------------------------
# Fix 4: Fix missing subscripts
# <em>S</em>0 -> <em>S</em><sub>0</sub>
# Also: d1, d2, F0, K0, c0, p0, etc.
# -------------------------------------------------------------------
SUBSCRIPT_VARS = r'[SFKVNUWcdfghkpqrstuvwx]'

def fix_missing_subscripts(html):
    changed = False

    # <em>VAR</em>N where N is a digit (outside of superscripts and existing subscripts)
    # But NOT inside <sup> tags
    new = re.sub(
        r'(<em>' + SUBSCRIPT_VARS + r'</em>)(\d)(?!</sub>)(?![^<]*</sup>)',
        r'\1<sub>\2</sub>',
        html
    )
    if new != html:
        changed = True
        count('subscript_fix')
        html = new

    # Also handle: <em>VAR</em>0 patterns
    new = re.sub(
        r'(<em>' + SUBSCRIPT_VARS + r'</em>)(\d{1,2})(?!</sub>)(?![\d.])',
        r'\1<sub>\2</sub>',
        html
    )
    if new != html:
        changed = True
        count('subscript_fix')
        html = new

    return html, changed


# -------------------------------------------------------------------
# Fix 5: Strip redundant eq-inline wrappers on single operators
# <span class="eq-inline">+</span> -> +
# <span class="eq-inline">=</span> -> =
# Only inside .equation divs
# -------------------------------------------------------------------
SINGLE_OPS = r'[+\-=×÷<>≤≥/()[\],;:.]'

def fix_redundant_eq_inline(html):
    changed = False

    # Inside equation divs, replace <span class="eq-inline">OP</span> with just OP
    def strip_in_equation(m):
        nonlocal changed
        eq_content = m.group(1)
        new_content = re.sub(
            r'<span class="eq-inline">(' + SINGLE_OPS + r')</span>',
            r'\1',
            eq_content
        )
        if new_content != eq_content:
            changed = True
            count('strip_eq_inline')
        return f'<div class="equation">{new_content}</div>'

    new = re.sub(
        r'<div class="equation">(.*?)</div>',
        strip_in_equation,
        html,
        flags=re.DOTALL
    )
    if new != html:
        html = new

    return html, changed


# -------------------------------------------------------------------
# Fix 6: Convert remaining <strong>(N.N)</strong> equation numbers
# inside div.equation to <span class="eq-number">
# -------------------------------------------------------------------
def fix_equation_numbers(html):
    changed = False

    # Inside div.equation, convert <strong>(N.N)</strong> to eq-number span
    def fix_in_equation(m):
        nonlocal changed
        eq_content = m.group(1)
        new_content = re.sub(
            r'\s*\t*<strong>\((\d+[A-Za-z]?\.?\d*)\)</strong>',
            r'<span class="eq-number">(\1)</span>',
            eq_content
        )
        if new_content != eq_content:
            changed = True
            count('eq_number_fix')
        return f'<div class="equation">{new_content}</div>'

    new = re.sub(
        r'<div class="equation">(.*?)</div>',
        fix_in_equation,
        html,
        flags=re.DOTALL
    )
    if new != html:
        html = new

    return html, changed


# -------------------------------------------------------------------
# Fix 7: Merge consecutive fragmented equation divs
# Detect: div.equation with "= " at end, followed by div.equation (numerator),
# followed by div.equation (denominator)
# -------------------------------------------------------------------
def fix_fragmented_equations(html):
    changed = False

    # Pattern: equation ending with "=" followed by two more equation divs (fraction)
    # This creates: LHS = fraction(num/den)
    def merge_fraction(m):
        nonlocal changed
        lhs = m.group(1).strip()
        num = m.group(2).strip()
        den = m.group(3).strip()

        # Strip nested eq-inline wrappers from inner content
        for tag in ['<span class="eq-inline">', '</span>']:
            num = num.replace(tag, '', 1) if tag in num else num
            den = den.replace(tag, '', 1) if tag in den else den

        changed = True
        count('merge_fraction')
        return (f'<div class="equation"><span class="eq-inline">{lhs}'
                f'<span class="fraction"><span class="num">{num}</span>'
                f'<span class="den">{den}</span></span></span></div>')

    # Match: div.equation with =, then div.equation (num), then div.equation (den)
    new = re.sub(
        r'<div class="equation"><span class="eq-inline">(.*?=\s*)</span></div>\s*'
        r'<div class="equation"><span class="eq-inline">(.*?)</span></div>\s*'
        r'<div class="equation"><span class="eq-inline">(.*?)</span></div>',
        merge_fraction,
        html,
        flags=re.DOTALL
    )
    if new != html:
        html = new

    return html, changed


# -------------------------------------------------------------------
# Fix registry
# -------------------------------------------------------------------
FIXES = [
    ('stylesheet_link', fix_stylesheet_link),
    ('p_tag_equations', fix_p_tag_equations),
    ('exponent_grouping', fix_exponent_grouping),
    ('missing_subscripts', fix_missing_subscripts),
    ('equation_numbers', fix_equation_numbers),
    ('redundant_eq_inline', fix_redundant_eq_inline),
    ('fragmented_equations', fix_fragmented_equations),
]


def process_file(filepath, page_num, dry_run=False, verbose=False):
    """Apply all equation fixes to a single XHTML file."""
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
    parser = argparse.ArgumentParser(description='Fix equation formatting in EPUB')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--pages', type=str, help='Page range, e.g., 100-200')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    print("Fixing equation formatting (v2)...")
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
    print(f"EQUATION FIX V2 SUMMARY")
    print(f"{'='*50}")
    print(f"Pages modified: {len(fixed_pages)}")
    for name, count_val in sorted(STATS.items()):
        print(f"  {name}: {count_val}")

    if args.verbose and fixed_pages:
        print(f"\nAll fixed pages:")
        for page, fixes in fixed_pages:
            print(f"  Page {page}: {', '.join(fixes)}")


if __name__ == '__main__':
    main()
