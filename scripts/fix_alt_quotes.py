"""Fix unescaped double quotes inside alt attribute values.

The alt values are delimited by " but some contain literal " characters
that break XML parsing. We find alt="..."/> patterns and escape inner quotes.
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
        # The alt value runs from alt=" to "/> (end of img tag)
        def fix_img_alt(m):
            nonlocal alts_fixed
            before = m.group(1)
            alt_content = m.group(2)

            # Check if alt content has unescaped quotes
            if '"' in alt_content or '\u201c' in alt_content or '\u201d' in alt_content:
                # Escape all quotes in the content
                cleaned = alt_content.replace('"', '&quot;')
                cleaned = cleaned.replace('\u201c', '&quot;')
                cleaned = cleaned.replace('\u201d', '&quot;')
                # Also strip any HTML tags that might still be there
                cleaned = re.sub(r'<[^>]+>', '', cleaned).strip()
                alts_fixed += 1
                return f'{before}alt="{cleaned}"/>'
            return m.group(0)

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
