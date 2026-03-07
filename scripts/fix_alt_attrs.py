"""Clean HTML tags from alt attributes in all XHTML files.

The alt attributes may contain unescaped double quotes from HTML tags,
so we match the pattern: alt="..."/> where "/> closes the img tag.
"""

import re
from pathlib import Path

EPUB_DIR = Path(__file__).resolve().parent.parent / "output" / "full_book_extracted" / "EPUB"


def main():
    files_fixed = 0
    alts_fixed = 0

    for fp in sorted(EPUB_DIR.glob("full_book_v7_p*.xhtml"),
                     key=lambda p: int(re.search(r'p(\d+)', p.name).group(1))):
        text = fp.read_text(encoding="utf-8")
        original = text

        # Match <img ... alt="CONTENT"/> where CONTENT may contain unescaped quotes
        # Strategy: find 'alt="' then match up to '"/>' which closes the img tag
        def fix_img_alt(m):
            nonlocal alts_fixed
            before_alt = m.group(1)
            alt_content = m.group(2)
            if '<' in alt_content:
                cleaned = re.sub(r'<[^>]+>', '', alt_content).strip()
                # Also clean up any leftover double-quotes that were inside HTML attrs
                cleaned = cleaned.replace('"', '')
                alts_fixed += 1
                return f'{before_alt}alt="{cleaned}"/>'
            return m.group(0)

        # Pattern: everything before alt= in the img tag, then alt="..."/>
        text = re.sub(
            r'(<img\s[^>]*?)alt="(.*?)"/>',
            fix_img_alt,
            text,
            flags=re.DOTALL
        )

        if text != original:
            fp.write_text(text, encoding="utf-8")
            files_fixed += 1

    print(f"Fixed {alts_fixed} alt attributes in {files_fixed} files")


if __name__ == "__main__":
    main()
