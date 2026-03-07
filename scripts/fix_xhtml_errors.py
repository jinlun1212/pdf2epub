"""Fix all remaining XHTML well-formedness errors in EPUB files."""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

EPUB_DIR = Path(__file__).resolve().parent.parent / "output" / "full_book_extracted" / "EPUB"


def fix_misplaced_anchors(text):
    """Fix anchors that were inserted inside HTML tags."""
    changed = False

    # Pattern 1: anchor inside closing tag: </su<a id=...></a>b> -> </sub><a id=...></a>
    def fix_inside_close(m):
        nonlocal changed
        changed = True
        tag_prefix = m.group(1)
        anchor = m.group(2)
        tag_suffix = m.group(3)
        return f"</{tag_prefix}{tag_suffix}>{anchor}"

    text = re.sub(
        r'</([\w]+)(<a id="[^"]+"></a>)([\w]+)>',
        fix_inside_close, text
    )

    # Pattern 2: anchor breaking close tag: <<a id=...></a>/em> -> </em><a id=...></a>
    def fix_breaking_close(m):
        nonlocal changed
        changed = True
        anchor = m.group(1)
        tag = m.group(2)
        return f"</{tag}>{anchor}"

    text = re.sub(
        r'<(<a id="[^"]+"></a>)/([\w]+)>',
        fix_breaking_close, text
    )

    # Pattern 3: anchor inside attribute value: class="den<a id=...></a>"
    def fix_inside_attr(m):
        nonlocal changed
        changed = True
        before = m.group(1)
        anchor = m.group(2)
        after = m.group(3)
        return f'{before}{after}" {anchor}'

    # This is tricky - need to find class="...ANCHOR..." and fix it
    text = re.sub(
        r'="([^"]*?)(<a id="[^"]+"></a>)([^"]*?)"',
        fix_inside_attr, text
    )

    return text, changed


def fix_unescaped_ampersands(text):
    """Escape bare & characters that aren't part of entities."""
    changed = False

    def replace_amp(m):
        nonlocal changed
        # Check if this & is part of a valid entity
        after = m.group(1)
        # Valid entities: &amp; &lt; &gt; &quot; &apos; &#NNN; &#xHHH;
        if re.match(r'(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);', after):
            return '&' + after
        changed = True
        return '&amp;' + after

    text = re.sub(r'&(.{0,10})', replace_amp, text)
    return text, changed


def fix_mismatched_tags(filepath):
    """Try to fix common tag mismatch issues."""
    text = filepath.read_text(encoding="utf-8")
    changed = False

    # Fix unclosed <span> tags by checking for </body> without matching </span>
    # This is complex - just check for obvious patterns

    # Pattern: <span ...>...</span missing closing >
    # Pattern: extra closing tags

    return text, changed


def main():
    errors_before = 0
    errors_after = 0
    files_fixed = 0

    for fp in sorted(EPUB_DIR.glob("full_book_v7_p*.xhtml"),
                     key=lambda p: int(re.search(r'p(\d+)', p.name).group(1))):
        page = int(re.search(r'p(\d+)', fp.name).group(1))
        text = fp.read_text(encoding="utf-8")

        # Check if file has errors
        try:
            ET.fromstring(text)
            continue  # No errors, skip
        except ET.ParseError:
            errors_before += 1

        original = text

        # Apply fixes
        text, c1 = fix_misplaced_anchors(text)
        text, c2 = fix_unescaped_ampersands(text)

        if text != original:
            fp.write_text(text, encoding="utf-8")
            files_fixed += 1

            # Check if errors are fixed
            try:
                ET.fromstring(text)
                print(f"  p{page}: FIXED")
            except ET.ParseError as e:
                errors_after += 1
                print(f"  p{page}: still has error: {str(e)[:80]}")
        else:
            errors_after += 1
            print(f"  p{page}: no automatic fix applied, error persists")

    print(f"\nBefore: {errors_before} errors")
    print(f"Fixed: {files_fixed} files")
    print(f"After: {errors_after} errors remaining")


if __name__ == "__main__":
    main()
