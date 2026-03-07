"""Phase 4: Add cross-reference hyperlinks to plain-text references.

Wraps plain-text references like 'Table 7.3', 'Chapter 5', 'equation (13.11)',
'Section 4.2', 'Business Snapshot 4.1', 'Figure 2.1' with <a href> tags
pointing to the correct XHTML file and anchor.

Skips references that are:
- Already inside <a> tags
- Inside <strong> captions (these are the targets themselves)
- Inside heading tags (h1/h2/h3)
"""

import re
import json
from pathlib import Path

EPUB_DIR = Path(__file__).resolve().parent.parent / "output" / "full_book_extracted" / "EPUB"
TARGETS_FILE = Path(__file__).resolve().parent.parent / "output" / "xref_targets.json"


def load_targets():
    with open(TARGETS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def is_inside_tag(text, pos, tag_names):
    """Check if position is inside one of the specified HTML tags."""
    # Look backwards for the nearest opening/closing tag
    before = text[max(0, pos-500):pos]
    for tag in tag_names:
        # Find last opening tag
        open_matches = list(re.finditer(rf'<{tag}[\s>]', before, re.IGNORECASE))
        close_matches = list(re.finditer(rf'</{tag}>', before, re.IGNORECASE))
        if open_matches:
            last_open = open_matches[-1].start()
            last_close = close_matches[-1].start() if close_matches else -1
            if last_open > last_close:
                return True
    return False


def add_cross_references(targets):
    """Scan all XHTML files and add hyperlinks for cross-references."""
    stats = {
        'chapters': 0, 'tables': 0, 'equations': 0,
        'business_snapshots': 0, 'figures': 0, 'sections': 0,
        'files_modified': 0
    }

    for fp in sorted(EPUB_DIR.glob("full_book_v7_p*.xhtml"),
                     key=lambda p: int(re.search(r'p(\d+)', p.name).group(1))):
        text = fp.read_text(encoding="utf-8")
        current_file = fp.name
        original = text

        # Process each reference type using a function that replaces matches
        # We need to be careful about overlapping replacements, so we process
        # from right to left (largest positions first)

        replacements = []  # List of (start, end, new_text)

        # --- Chapter references ---
        # "Chapter N", "Chapters N", "chapter N"
        for m in re.finditer(r'(?<![<\w])(?:C|c)hapters?\s+(\d{1,2})(?!\d)(?!\.\d)', text):
            ch_num = m.group(1)
            if ch_num in targets['chapters']:
                t = targets['chapters'][ch_num]
                href = f"{t['file']}#{t['id']}"
                if t['file'] == current_file:
                    href = f"#{t['id']}"
                replacements.append((m.start(), m.end(), m.group(0), href, 'chapters'))

        # --- Table references ---
        # "Table X.Y", "Tables X.Y"
        for m in re.finditer(r'(?<![<\w])Tables?\s+(\d+[A-Z]?\.\d+)', text):
            tbl_num = m.group(1)
            if tbl_num in targets['tables']:
                t = targets['tables'][tbl_num]
                href = f"{t['file']}#{t['id']}"
                if t['file'] == current_file:
                    href = f"#{t['id']}"
                replacements.append((m.start(), m.end(), m.group(0), href, 'tables'))

        # --- Figure references ---
        # "Figure X.Y", "Figures X.Y"
        for m in re.finditer(r'(?<![<\w])Figures?\s+(\d+[A-Z]?\.\d+)', text):
            fig_num = m.group(1)
            if fig_num in targets['figures']:
                t = targets['figures'][fig_num]
                href = f"{t['file']}#{t['id']}"
                if t['file'] == current_file:
                    href = f"#{t['id']}"
                replacements.append((m.start(), m.end(), m.group(0), href, 'figures'))

        # --- Section references ---
        # "Section X.Y", "Sections X.Y"
        for m in re.finditer(r'(?<![<\w])Sections?\s+(\d+\.\d+)', text):
            sec_num = m.group(1)
            if sec_num in targets['sections']:
                t = targets['sections'][sec_num]
                href = f"{t['file']}#{t['id']}"
                if t['file'] == current_file:
                    href = f"#{t['id']}"
                replacements.append((m.start(), m.end(), m.group(0), href, 'sections'))

        # --- Equation references ---
        # "equation (X.Y)", "Equation (X.Y)", "equations (X.Y)"
        for m in re.finditer(r'(?<![<\w])(?:E|e)quations?\s+\((\d+[A-Z]?\.\d+)\)', text):
            eq_num = m.group(1)
            if eq_num in targets['equations']:
                t = targets['equations'][eq_num]
                href = f"{t['file']}#{t['id']}"
                if t['file'] == current_file:
                    href = f"#{t['id']}"
                replacements.append((m.start(), m.end(), m.group(0), href, 'equations'))

        # Also match standalone "(X.Y)" equation references preceded by "equation" or "from"
        # Pattern: "in (X.Y)" when context suggests equation
        # Skip this for now - too risky for false positives

        # --- Business Snapshot references ---
        # "Business Snapshot X.Y"
        for m in re.finditer(r'(?<![<\w])Business\s+Snapshots?\s+(\d+\.\d+)', text):
            bs_num = m.group(1)
            if bs_num in targets['business_snapshots']:
                t = targets['business_snapshots'][bs_num]
                href = f"{t['file']}#{t['id']}"
                if t['file'] == current_file:
                    href = f"#{t['id']}"
                replacements.append((m.start(), m.end(), m.group(0), href, 'business_snapshots'))

        # Filter out replacements that are inside <a>, <strong>, <h1>, <h2>, <h3> tags
        filtered = []
        for start, end, match_text, href, ref_type in replacements:
            # Check if already inside an <a> tag
            before = text[max(0, start-300):start]

            # Quick check: is there an unclosed <a> before this position?
            a_opens = len(re.findall(r'<a[\s>]', before))
            a_closes = len(re.findall(r'</a>', before))
            if a_opens > a_closes:
                continue  # Inside an <a> tag

            # Check if inside <strong> (caption target)
            strong_opens = len(re.findall(r'<strong>', before[-100:]))
            strong_closes = len(re.findall(r'</strong>', before[-100:]))
            if strong_opens > strong_closes:
                continue  # Inside <strong> tag

            # Check if inside heading tags
            skip = False
            for htag in ['h1', 'h2', 'h3']:
                h_opens = len(re.findall(rf'<{htag}[\s>]', before[-200:]))
                h_closes = len(re.findall(rf'</{htag}>', before[-200:]))
                if h_opens > h_closes:
                    skip = True
                    break
            if skip:
                continue

            # Check if inside eq-number span
            eqn_opens = len(re.findall(r'class="eq-number"', before[-100:]))
            eqn_closes = len(re.findall(r'</span>', before[-100:]))
            # This is imprecise but helps avoid wrapping equation numbers themselves

            filtered.append((start, end, match_text, href, ref_type))

        # Sort by position (reverse) to replace from end to start
        filtered.sort(key=lambda x: x[0], reverse=True)

        # Apply replacements
        for start, end, match_text, href, ref_type in filtered:
            link = f'<a href="{href}">{match_text}</a>'
            text = text[:start] + link + text[end:]
            stats[ref_type] += 1

        if text != original:
            fp.write_text(text, encoding="utf-8")
            stats['files_modified'] += 1

    return stats


def main():
    print("Phase 4: Building cross-reference hyperlinks\n")

    print("Loading targets...")
    targets = load_targets()
    for k, v in targets.items():
        print(f"  {k}: {len(v)} targets")

    print("\nScanning and adding hyperlinks...")
    stats = add_cross_references(targets)

    print(f"\nResults:")
    print(f"  Chapter links:           {stats['chapters']}")
    print(f"  Table links:             {stats['tables']}")
    print(f"  Equation links:          {stats['equations']}")
    print(f"  Business Snapshot links:  {stats['business_snapshots']}")
    print(f"  Figure links:            {stats['figures']}")
    print(f"  Section links:           {stats['sections']}")
    total = sum(v for k, v in stats.items() if k != 'files_modified')
    print(f"  Total links added:       {total}")
    print(f"  Files modified:          {stats['files_modified']}")


if __name__ == "__main__":
    main()
