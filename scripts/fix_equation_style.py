"""
Fix equation styling in EPUB XHTML pages.

Systematic fixes:
1. Convert fs-small subscripts to proper <sub> tags
2. Standardize equation number placement using eq-number class
3. Remove redundant inline styles from equation divs
4. Fix flat-text equations missing superscript/subscript markup
5. Convert footnote-marker fs-small spans to fn-marker class

Run from anywhere: python scripts/fix_equation_style.py [--dry-run] [--verbose]
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

# -------------------------------------------------------------------
# Fix 1: Convert fs-small fake subscripts to proper <sub> tags
# Pattern: <em>X</em> <span class="fs-small"><em>Y</em></span>
#      or: <em>X</em> <span class="fs-small">Y</span>
# These are variables with subscripts (S_0, F_0, t_i, etc.)
# -------------------------------------------------------------------

def fix_fs_small_subscripts(html):
    """Convert fs-small spans that act as subscripts into proper <sub> tags."""
    changed = False
    original = html

    # Pattern A: <em>VAR</em> <span class="fs-small"><em>SUB</em></span>
    # Match: italic variable followed by space + fs-small italic subscript
    # Only match single-char or short subscripts (1-3 chars)
    new = re.sub(
        r'(<em>[A-Za-zΔδσμρλεΣ∂∏]+</em>)\s*<span class="fs-small"><em>([A-Za-z0-9]{1,4})</em></span>',
        r'\1<sub><em>\2</em></sub>',
        html
    )
    if new != html:
        changed = True
        html = new

    # Pattern B: <em>VAR</em> <span class="fs-small">SUB</span>
    # Match: italic variable followed by space + fs-small plain subscript
    new = re.sub(
        r'(<em>[A-Za-zΔδσμρλεΣ∂∏]+</em>)\s*<span class="fs-small">([A-Za-z0-9]{1,4})</span>',
        r'\1<sub>\2</sub>',
        html
    )
    if new != html:
        changed = True
        html = new

    # Pattern C: plain var followed by fs-small subscript (no <em>)
    # e.g., S <span class="fs-small">0</span>
    # Only when preceded by a single capital letter
    new = re.sub(
        r'\b([A-Z])\s*<span class="fs-small">([0-9]{1,2})</span>',
        r'\1<sub>\2</sub>',
        html
    )
    if new != html:
        changed = True
        html = new

    return html, changed


# -------------------------------------------------------------------
# Fix 2: Convert standalone fs-small footnote markers to fn-marker
# Pattern: <span class="fs-small">N</span> at start/end of sentence
# These are footnote reference numbers (1, 2, 3...) not subscripts
# -------------------------------------------------------------------

def fix_footnote_markers(html):
    """Convert standalone fs-small numbers that are footnote markers."""
    changed = False

    # Pattern: Period or end of sentence followed by <span class="fs-small">N</span>
    # where N is a number 1-9 and appears after sentence-ending punctuation
    new = re.sub(
        r'([.!?])\s*<span class="fs-small">(\d{1,2})</span>',
        r'\1<span class="fn-marker">\2</span>',
        html
    )
    if new != html:
        changed = True
        html = new

    # Pattern: <span class="fs-small">N</span> at start of paragraph (footnote text)
    # Leave these alone -- they're footnote body markers

    return html, changed


# -------------------------------------------------------------------
# Fix 3: Remove redundant inline styles from equation divs
# The CSS .equation class already handles text-align and width
# -------------------------------------------------------------------

REDUNDANT_EQ_STYLE = ' style="text-align:center !important; width:100%;"'
REDUNDANT_EQ_STYLE2 = ' style="text-align: center !important; width: 100%;"'

def fix_equation_inline_styles(html):
    """Remove redundant inline styles from equation divs."""
    changed = False

    for style in [REDUNDANT_EQ_STYLE, REDUNDANT_EQ_STYLE2]:
        if style in html:
            html = html.replace(style, '')
            changed = True

    return html, changed


# -------------------------------------------------------------------
# Fix 4: Standardize equation numbers
# Convert standalone equation number paragraphs to inline eq-number spans
# Pattern: </div>\n<p><strong>(X.Y)</strong></p>
# -------------------------------------------------------------------

def fix_equation_numbers(html):
    """Move standalone equation number paragraphs into the equation div."""
    changed = False

    # Pattern: equation div closing, then <p><strong>(N.N)</strong></p>
    # Replace with eq-number span inside the equation div
    new = re.sub(
        r'(</span>)\s*</div>\s*<p>\s*<strong>\((\d+\.?\d*)\)</strong>\s*</p>',
        r'\1<span class="eq-number">(\2)</span></div>',
        html
    )
    if new != html:
        changed = True
        html = new

    # Also handle: equation number with &nbsp; spacing inside the div
    new = re.sub(
        r'(&nbsp;){2,}\((\d+\.?\d*)\)\s*</div>',
        r'<span class="eq-number">(\2)</span></div>',
        html
    )
    if new != html:
        changed = True
        html = new

    # Handle: equation number as <strong> at end of equation div
    new = re.sub(
        r'\s*<strong>\((\d+\.?\d*)\)</strong>\s*(</div>)',
        r'<span class="eq-number">(\1)</span>\2',
        html
    )
    if new != html:
        changed = True
        html = new

    return html, changed


# -------------------------------------------------------------------
# Fix 5: Fix flat-text equations missing sub/sup
# Common pattern: F0 = S0erT (should be F₀ = S₀eʳᵀ)
# -------------------------------------------------------------------

def fix_flat_equations(html):
    """Fix equations where subscripts/superscripts are flat text."""
    changed = False

    # Inside equation spans, fix common flat-text patterns:

    # Pattern: single capital letter followed by 0 (subscript zero)
    # e.g., F0, S0, K0 inside eq-inline
    # Only inside equation contexts to avoid false positives
    def fix_eq_content(m):
        nonlocal changed
        text = m.group(1)
        original_text = text

        # Fix VAR0 -> VAR<sub>0</sub> (e.g., F0 -> F<sub>0</sub>)
        text = re.sub(r'\b([FSKVcfpqr])0\b', r'\1<sub>0</sub>', text)

        # Fix e^{...} patterns: erT -> e<sup>rT</sup>
        text = re.sub(r'\be([\-]?[rqδσ][TtSs](?:/\d+)?)\b', r'e<sup>\1</sup>', text)

        # Fix e^{0.05x3/12} style: e followed by decimal number x fraction
        text = re.sub(r'\be(\d+\.\d+[×x]\d+/\d+)\b', r'e<sup>\1</sup>', text)

        if text != original_text:
            changed = True
        return f'<span class="eq-inline">{text}</span>'

    new = re.sub(
        r'<span class="eq-inline">(.*?)</span>',
        fix_eq_content,
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
    ('fs_small_subscripts', fix_fs_small_subscripts),
    ('footnote_markers', fix_footnote_markers),
    ('equation_inline_styles', fix_equation_inline_styles),
    ('equation_numbers', fix_equation_numbers),
    ('flat_equations', fix_flat_equations),
]


def process_file(filepath, page_num, dry_run=False, verbose=False):
    """Apply all equation style fixes to a single XHTML file."""
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
    parser = argparse.ArgumentParser(description='Fix equation styling in EPUB')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without modifying files')
    parser.add_argument('--pages', type=str, help='Comma-separated page numbers or range (e.g., 100-200)')
    parser.add_argument('--verbose', action='store_true', help='Show per-page details')
    args = parser.parse_args()

    print("Fixing equation styling...")
    print(f"EPUB dir: {EPUB_DIR}")
    if args.dry_run:
        print("DRY RUN — no files will be modified")

    files = sorted(
        EPUB_DIR.glob('full_book_v7_p*.xhtml'),
        key=lambda f: int(f.stem.split('_p')[1])
    )

    if args.pages:
        if '-' in args.pages and ',' not in args.pages:
            start, end = args.pages.split('-', 1)
            page_set = set(range(int(start), int(end) + 1))
        else:
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
    print(f"EQUATION STYLE FIX SUMMARY")
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
