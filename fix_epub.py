"""
Fix identified issues in the extracted EPUB files:
1. Remove orphaned chapter headings and trailing equation fragments at page bottoms
2. Fix subject index formatting (remove incorrect <h2> tags, add line breaks between entries)
3. Apply safe equation character substitutions where context is unambiguous

Run from the project root directory.
"""
import sys
import io
import re
import os
from pathlib import Path

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

EPUB_DIR = Path("output/full_book_extracted/EPUB")

# Index pages (Subject Index + Author Index)
INDEX_PAGES = set(range(857, 881))  # pages 857-880


def fix_orphaned_content(html, page_num):
    """Remove orphaned <h1 id='chap-XXX'> tags and everything after them."""
    # Pattern: <h1 id="chap-NNN">..CHAPTER XX..</h1> followed by orphaned content
    # This appears at the bottom of many pages
    pattern = r'<h1 id="chap-\d+"[^>]*>.*?</h1>.*?(?=</body>)'
    match = re.search(pattern, html, re.DOTALL)
    if match:
        # Remove the h1 and everything after it (up to </body>)
        html = html[:match.start()] + html[match.end():]
        return html, True
    return html, False


def fix_index_headings(html, page_num):
    """Convert index entries incorrectly formatted as <h2> back to <p> tags."""
    if page_num not in INDEX_PAGES:
        return html, False

    changed = False
    # Match <h2 id="sec-XXX">...index entry with page numbers...</h2>
    # Index entries contain comma-separated page numbers like "202-204, 599, 827"
    # Legitimate section headings have <span class="fs-large"><strong>
    def replace_h2(m):
        nonlocal changed
        inner = m.group(1)
        content = m.group(2)
        # Check if this looks like an index entry (has page numbers)
        # vs a legitimate heading (has fs-large/strong markup)
        if 'class="fs-large"' in content and '<strong>' in content:
            # Legitimate section heading — keep as h2
            return m.group(0)
        # This is an index entry — convert to <p>
        changed = True
        return f'<p style="text-indent: 0; margin: 0.2em 0;"{inner}>{content}</p>'

    html = re.sub(
        r'<h2(\s+id="sec-\d+"[^>]*)>(.*?)</h2>',
        replace_h2,
        html,
        flags=re.DOTALL
    )
    return html, changed


def fix_index_paragraphs(html, page_num):
    """Try to add line breaks between merged index entries in long paragraphs.

    Index entries follow the pattern: "Term, NNN-NNN, NNN Another term, NNN"
    We split on the pattern where a page number/range is followed by a capital letter
    starting a new entry.
    """
    if page_num not in INDEX_PAGES:
        return html, False

    changed = False

    def split_entries(m):
        nonlocal changed
        text = m.group(1)
        # Split where a page number (or bold page number) is followed by a new index term
        # Pattern: "NNN " followed by capital letter starting a new entry
        # But be careful not to split within an entry like "Monte Carlo simulation and, 660-665"
        new_text = re.sub(
            r'((?:</strong>)?\s*\d+(?:–\d+)?)\s+([A-Z])',
            r'\1<br/>\2',
            text
        )
        if new_text != text:
            changed = True
        return f'<p style="text-indent: 0; margin: 0.2em 0; line-height: 1.6;">{new_text}</p>'

    # Only apply to long paragraphs (>200 chars) in index pages
    def maybe_split(m):
        full = m.group(0)
        inner = m.group(1)
        if len(inner) > 200:
            return split_entries(m)
        return full

    html = re.sub(
        r'<p[^>]*>((?:(?!</p>).)+)</p>',
        maybe_split,
        html,
        flags=re.DOTALL
    )
    return html, changed


def fix_equation_encoding(html, page_num):
    """Apply safe equation character substitutions.

    These fixes are conservative — only applied in contexts where we're confident
    about the substitution (e.g., inside equation divs, or in clear patterns).

    Known encoding issues from PDF font mapping:
    - sigma (σ) → 's' (too ambiguous for global fix)
    - partial (∂) → '0' (too ambiguous for global fix)
    - () → '1...2' (too ambiguous for global fix)
    - [] → '3...4' (too ambiguous for global fix)
    - / (division) → '>' in some equation contexts
    - < (less than) → '6' in comparison contexts
    - > (greater than) → '7' in comparison contexts
    - ≤ → '6'
    - ≥ → '7'

    We apply the following SAFE fixes:
    1. In inline text: "S 6 H" patterns → "S ≤ H" (variable DIGIT variable)
    2. In inline text: "S 7 H" patterns → "S ≥ H"
    3. In inline text: "f 6 0" patterns → "f ≤ 0" etc.
    """
    changed = False
    original = html

    # Fix inequality symbols in text context:
    # Pattern: italic variable + space + 6/7 + space + italic variable or number
    # e.g., <em>S</em> 6 <em>H</em> → <em>S</em> ≤ <em>H</em>

    # ≤ (was encoded as 6)
    new = re.sub(
        r'(</em>)\s+6\s+(<em>)',
        r'\1 ≤ \2',
        html
    )
    if new != html:
        changed = True
        html = new

    # ≥ (was encoded as 7)
    new = re.sub(
        r'(</em>)\s+7\s+(<em>)',
        r'\1 ≥ \2',
        html
    )
    if new != html:
        changed = True
        html = new

    # Also fix patterns like: variable 6 0 or 7 0 (comparison with zero)
    new = re.sub(
        r'(</em>)\s+6\s+0\b',
        r'\1 ≤ 0',
        html
    )
    if new != html:
        changed = True
        html = new

    new = re.sub(
        r'(</em>)\s+7\s+0\b',
        r'\1 ≥ 0',
        html
    )
    if new != html:
        changed = True
        html = new

    # Fix "0 f > 0 t" pattern (∂f/∂t) — very specific pattern
    new = re.sub(
        r'\b0\s+(<em>f</em>)\s*(?:&gt;|>)\s*0\s+(<em>[tsSxX]</em>)',
        r'∂\1/∂\2',
        html
    )
    if new != html:
        changed = True
        html = new

    # Fix standalone "0 f" at start of line/paragraph that means ∂f
    new = re.sub(
        r'>0\s+(<em>f</em>)<',
        r'>∂\1<',
        html
    )
    if new != html:
        changed = True
        html = new

    return html, changed


def process_file(filepath, page_num):
    """Apply all fixes to a single XHTML file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    original = html
    fixes = []

    html, fixed = fix_orphaned_content(html, page_num)
    if fixed:
        fixes.append("orphaned_content")

    html, fixed = fix_index_headings(html, page_num)
    if fixed:
        fixes.append("index_h2_tags")

    html, fixed = fix_index_paragraphs(html, page_num)
    if fixed:
        fixes.append("index_line_breaks")

    html, fixed = fix_equation_encoding(html, page_num)
    if fixed:
        fixes.append("equation_encoding")

    if html != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        return fixes
    return []


def main():
    print("Fixing EPUB issues...")
    print(f"EPUB dir: {EPUB_DIR}")

    files = sorted(
        EPUB_DIR.glob('full_book_v7_p*.xhtml'),
        key=lambda f: int(f.stem.split('_p')[1])
    )
    print(f"Found {len(files)} XHTML files")

    stats = {
        'orphaned_content': 0,
        'index_h2_tags': 0,
        'index_line_breaks': 0,
        'equation_encoding': 0,
    }
    fixed_pages = []

    for f in files:
        page_num = int(f.stem.split('_p')[1])
        fixes = process_file(f, page_num)
        if fixes:
            fixed_pages.append((page_num, fixes))
            for fix in fixes:
                stats[fix] += 1

    print(f"\n{'='*50}")
    print(f"FIX SUMMARY")
    print(f"{'='*50}")
    print(f"Total pages fixed: {len(fixed_pages)}")
    for fix_type, count in stats.items():
        print(f"  {fix_type}: {count} pages")

    if fixed_pages:
        print(f"\nSample of fixed pages:")
        for page, fixes in fixed_pages[:20]:
            print(f"  Page {page}: {', '.join(fixes)}")
        if len(fixed_pages) > 20:
            print(f"  ... and {len(fixed_pages) - 20} more")


if __name__ == '__main__':
    main()
