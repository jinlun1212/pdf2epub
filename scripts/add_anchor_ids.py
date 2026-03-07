"""Phase 3: Add anchor IDs to tables, equations, business snapshots, and unlinked figures."""

import re
from pathlib import Path

EPUB_DIR = Path(__file__).resolve().parent.parent / "output" / "full_book_extracted" / "EPUB"


def normalize_id(prefix, num_str):
    """Convert '7.3' to 'tbl-7-3', '3A.1' to 'eq-3A-1' etc."""
    return f"{prefix}-{num_str.replace('.', '-')}"


def add_table_ids():
    """Add id='tbl-X-Y' anchors before <strong>Table X.Y</strong> captions."""
    count = 0
    for fp in sorted(EPUB_DIR.glob("full_book_v7_p*.xhtml"),
                     key=lambda p: int(re.search(r'p(\d+)', p.name).group(1))):
        text = fp.read_text(encoding="utf-8")
        changed = False

        for m in re.finditer(
            r'<strong>\s*(?:<a[^>]*>)?\s*Table\s+(\d+[A-Z]?\.\d+)\s*(?:</a>)?\s*</strong>',
            text
        ):
            tbl_num = m.group(1)
            tbl_id = normalize_id("tbl", tbl_num)

            # Skip if already has this id
            if f'id="{tbl_id}"' in text:
                continue

            # Insert anchor right before the <strong> tag
            anchor = f'<a id="{tbl_id}"></a>'
            # Find the start of the <strong> tag
            pos = m.start()
            # Check if <strong> is inside a <p> - if so, put anchor before the <p>
            before = text[max(0, pos-100):pos]
            p_match = re.search(r'<p[^>]*>\s*$', before)
            if p_match:
                insert_pos = pos - len(before) + p_match.start() + max(0, pos-100)
            else:
                insert_pos = pos

            text = text[:insert_pos] + anchor + "\n" + text[insert_pos:]
            changed = True
            count += 1

        if changed:
            fp.write_text(text, encoding="utf-8")

    return count


def add_equation_ids():
    """Add id='eq-X-Y' to <div class='equation'> elements containing equation numbers."""
    count = 0
    for fp in sorted(EPUB_DIR.glob("full_book_v7_p*.xhtml"),
                     key=lambda p: int(re.search(r'p(\d+)', p.name).group(1))):
        text = fp.read_text(encoding="utf-8")
        changed = False

        for m in re.finditer(
            r'<span\s+class="eq-number">\s*\((\d+[A-Z]?\.\d+)\)\s*</span>',
            text
        ):
            eq_num = m.group(1)
            eq_id = normalize_id("eq", eq_num)

            # Skip if already has this id
            if f'id="{eq_id}"' in text:
                continue

            # Look backwards for the parent <div class="equation">
            pos = m.start()
            before = text[max(0, pos-500):pos]

            # Find the nearest <div class="equation" that doesn't already have an id
            div_match = None
            for dm in re.finditer(r'<div\s+class="equation"(?:\s[^>]*)?>', before):
                div_match = dm

            if div_match:
                # Add id to the div tag
                div_text = div_match.group(0)
                if 'id=' not in div_text:
                    # Insert id into the div tag
                    actual_pos = max(0, pos-500) + div_match.start()
                    new_div = div_text.replace('<div class="equation"', f'<div class="equation" id="{eq_id}"', 1)
                    text = text[:actual_pos] + new_div + text[actual_pos + len(div_text):]
                    changed = True
                    count += 1
                else:
                    # Div already has an id - add anchor before div instead
                    actual_pos = max(0, pos-500) + div_match.start()
                    anchor = f'<a id="{eq_id}"></a>\n'
                    text = text[:actual_pos] + anchor + text[actual_pos:]
                    changed = True
                    count += 1
            else:
                # No parent div found - insert anchor before the eq-number span
                anchor = f'<a id="{eq_id}"></a>'
                text = text[:pos] + anchor + text[pos:]
                changed = True
                count += 1

        if changed:
            fp.write_text(text, encoding="utf-8")

    return count


def add_business_snapshot_ids():
    """Add id='bs-X-Y' anchors before <strong>Business Snapshot X.Y</strong>."""
    count = 0
    for fp in sorted(EPUB_DIR.glob("full_book_v7_p*.xhtml"),
                     key=lambda p: int(re.search(r'p(\d+)', p.name).group(1))):
        text = fp.read_text(encoding="utf-8")
        changed = False

        for m in re.finditer(
            r'<strong>\s*Business\s+Snapshot\s+(\d+\.\d+)\s*</strong>',
            text
        ):
            bs_num = m.group(1)
            bs_id = normalize_id("bs", bs_num)

            if f'id="{bs_id}"' in text:
                continue

            # Insert anchor before the <strong> or its parent <p>
            pos = m.start()
            before = text[max(0, pos-100):pos]
            p_match = re.search(r'<p[^>]*>\s*$', before)
            if p_match:
                insert_pos = pos - len(before) + p_match.start() + max(0, pos-100)
            else:
                insert_pos = pos

            anchor = f'<a id="{bs_id}"></a>\n'
            text = text[:insert_pos] + anchor + text[insert_pos:]
            changed = True
            count += 1

        if changed:
            fp.write_text(text, encoding="utf-8")

    return count


def add_missing_figure_ids():
    """Add id='fig-X-Y' anchors before figure captions that lack IDs."""
    count = 0
    for fp in sorted(EPUB_DIR.glob("full_book_v7_p*.xhtml"),
                     key=lambda p: int(re.search(r'p(\d+)', p.name).group(1))):
        text = fp.read_text(encoding="utf-8")
        changed = False

        for m in re.finditer(
            r'<strong>\s*(?:<a[^>]*>)?\s*Figure\s+(\d+[A-Z]?\.\d+)\s*(?:</a>)?\s*</strong>',
            text
        ):
            fig_num = m.group(1)
            fig_id = normalize_id("fig", fig_num)

            if f'id="{fig_id}"' in text:
                continue

            # Check nearby context for existing fig- id
            pos = m.start()
            context = text[max(0, pos-200):pos+10]
            if re.search(r'id="fig-', context):
                continue

            # Insert anchor before the <strong> or parent <p>
            before = text[max(0, pos-100):pos]
            p_match = re.search(r'<p[^>]*>\s*$', before)
            if p_match:
                insert_pos = pos - len(before) + p_match.start() + max(0, pos-100)
            else:
                insert_pos = pos

            anchor = f'<a id="{fig_id}"></a>\n'
            text = text[:insert_pos] + anchor + text[insert_pos:]
            changed = True
            count += 1

        if changed:
            fp.write_text(text, encoding="utf-8")

    return count


def main():
    print("Phase 3: Adding anchor IDs for cross-reference targets\n")

    print("Step 1: Adding table IDs...")
    n = add_table_ids()
    print(f"  Added {n} table anchors\n")

    print("Step 2: Adding equation IDs...")
    n = add_equation_ids()
    print(f"  Added {n} equation anchors\n")

    print("Step 3: Adding business snapshot IDs...")
    n = add_business_snapshot_ids()
    print(f"  Added {n} business snapshot anchors\n")

    print("Step 4: Adding missing figure IDs...")
    n = add_missing_figure_ids()
    print(f"  Added {n} figure anchors\n")

    print("Done!")


if __name__ == "__main__":
    main()
