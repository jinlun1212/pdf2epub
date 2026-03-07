"""Scan all 880 XHTML files and build a JSON map of chapters, sections,
figures, tables, equations, and business snapshots with their page numbers
and anchor IDs."""

import json
import re
import os
from pathlib import Path

EPUB_DIR = Path(__file__).resolve().parent.parent / "output" / "full_book_extracted" / "EPUB"
OUTPUT = Path(__file__).resolve().parent.parent / "output" / "chapter_map.json"

def extract_page_num(filename):
    m = re.search(r'p(\d+)\.xhtml$', filename)
    return int(m.group(1)) if m else None

def scan_all_pages():
    chapters = {}
    sections = {}
    figures = {}
    tables = {}
    equations = {}
    business_snapshots = {}
    nav_entries = {}

    # First, parse nav.xhtml to get expected chapter targets
    nav_path = EPUB_DIR / "nav.xhtml"
    if nav_path.exists():
        nav_text = nav_path.read_text(encoding="utf-8")
        # Pattern: <a href="full_book_v7_pNN.xhtml#chap-MM">Chapter Title</a>
        for m in re.finditer(
            r'<a\s+href="(full_book_v7_p(\d+)\.xhtml)(?:#(chap-\d+))?"\s*>(.*?)</a>',
            nav_text, re.DOTALL
        ):
            href_file, page_str, anchor, title = m.groups()
            title_clean = re.sub(r'<[^>]+>', '', title).strip()
            # Extract chapter number from title
            ch_match = re.match(r'(\d+)\.\s*', title_clean)
            if ch_match:
                ch_num = int(ch_match.group(1))
                nav_entries[ch_num] = {
                    "nav_file": href_file,
                    "nav_page": int(page_str),
                    "nav_anchor": anchor or None,
                    "nav_title": title_clean
                }

    # Scan all XHTML files
    xhtml_files = sorted(EPUB_DIR.glob("full_book_v7_p*.xhtml"),
                         key=lambda p: extract_page_num(p.name))

    for filepath in xhtml_files:
        page_num = extract_page_num(filepath.name)
        if page_num is None:
            continue

        try:
            text = filepath.read_text(encoding="utf-8")
        except Exception:
            text = filepath.read_text(encoding="utf-8", errors="replace")

        filename = filepath.name

        # --- Chapter headings ---
        # Look for h1/h2 containing "Chapter N" or chapter-style headings
        for m in re.finditer(
            r'<(h[12])[^>]*(?:\s+id="([^"]*)")?[^>]*>(.*?)</\1>',
            text, re.DOTALL | re.IGNORECASE
        ):
            tag, heading_id, content = m.groups()
            content_clean = re.sub(r'<[^>]+>', '', content).strip()
            # Match "CHAPTER N" or "N. Title" patterns in headings
            ch_match = re.search(r'CHAPTER\s+(\d+)', content_clean, re.IGNORECASE)
            if not ch_match:
                ch_match = re.search(r'^(\d+)\.\s+\S', content_clean)
            if ch_match:
                ch_num = int(ch_match.group(1))
                if ch_num not in chapters or tag.lower() == 'h1':
                    chapters[ch_num] = {
                        "heading_page": page_num,
                        "heading_file": filename,
                        "heading_id": heading_id,
                        "heading_text": content_clean[:100],
                        "heading_tag": tag.lower()
                    }

        # Also check for id="chap-" attributes anywhere
        for m in re.finditer(r'id="(chap-(\d+))"', text):
            anchor_id, anchor_num = m.groups()
            # Record this for cross-reference
            pass

        # --- Section headings with IDs ---
        for m in re.finditer(r'id="(sec-[^"]*)"', text):
            sec_id = m.group(1)
            # Try to extract section number from nearby text
            pos = m.start()
            context = text[max(0, pos-50):pos+200]
            sec_match = re.search(r'(\d+\.\d+)\s', context)
            if sec_match:
                sec_num = sec_match.group(1)
                sections[sec_num] = {
                    "page": page_num,
                    "file": filename,
                    "id": sec_id
                }

        # --- Figure IDs ---
        for m in re.finditer(r'id="(fig-[^"]*)"', text):
            fig_id = m.group(1)
            pos = m.start()
            context = text[pos:pos+300]
            fig_match = re.search(r'Figure\s+(\d+[A-Z]?\.\d+)', context)
            if fig_match:
                fig_num = fig_match.group(1)
                figures[fig_num] = {
                    "page": page_num,
                    "file": filename,
                    "id": fig_id
                }

        # --- Figure captions without IDs ---
        for m in re.finditer(
            r'<strong>\s*(?:<a[^>]*>)?\s*Figure\s+(\d+[A-Z]?\.\d+)\s*(?:</a>)?\s*</strong>',
            text
        ):
            fig_num = m.group(1)
            if fig_num not in figures:
                figures[fig_num] = {
                    "page": page_num,
                    "file": filename,
                    "id": None
                }

        # --- Table captions ---
        for m in re.finditer(
            r'<strong>\s*(?:<a[^>]*>)?\s*Table\s+(\d+[A-Z]?\.\d+)\s*(?:</a>)?\s*</strong>',
            text
        ):
            tbl_num = m.group(1)
            if tbl_num not in tables:
                # Check if parent has an id
                pos = m.start()
                before = text[max(0, pos-200):pos]
                id_match = re.search(r'id="([^"]*)"', before[-100:])
                tables[tbl_num] = {
                    "page": page_num,
                    "file": filename,
                    "id": id_match.group(1) if id_match else None
                }

        # --- Equation numbers ---
        for m in re.finditer(
            r'<span\s+class="eq-number">\s*\((\d+[A-Z]?\.\d+)\)\s*</span>',
            text
        ):
            eq_num = m.group(1)
            # Check if the parent div has an id
            pos = m.start()
            before = text[max(0, pos-200):pos]
            id_match = re.search(r'<div\s+class="equation"[^>]*id="([^"]*)"', before)
            if not id_match:
                id_match = re.search(r'id="(eq-[^"]*)"', before[-100:])
            equations[eq_num] = {
                "page": page_num,
                "file": filename,
                "id": id_match.group(1) if id_match else None
            }

        # --- Business Snapshots ---
        for m in re.finditer(
            r'<strong>\s*Business\s+Snapshot\s+(\d+\.\d+)\s*</strong>',
            text
        ):
            bs_num = m.group(1)
            if bs_num not in business_snapshots:
                pos = m.start()
                before = text[max(0, pos-200):pos]
                id_match = re.search(r'id="([^"]*)"', before[-100:])
                business_snapshots[bs_num] = {
                    "page": page_num,
                    "file": filename,
                    "id": id_match.group(1) if id_match else None
                }

    # Merge nav entries into chapters
    for ch_num, nav_info in nav_entries.items():
        if ch_num in chapters:
            chapters[ch_num].update(nav_info)
        else:
            chapters[ch_num] = {
                "heading_page": None,
                "heading_file": None,
                "heading_id": None,
                "heading_text": nav_info["nav_title"],
                "heading_tag": None,
                **nav_info
            }

    result = {
        "chapters": {str(k): v for k, v in sorted(chapters.items())},
        "sections": {k: v for k, v in sorted(sections.items(),
                     key=lambda x: [int(n) for n in x[0].split('.')])},
        "figures": {k: v for k, v in sorted(figures.items(),
                    key=lambda x: x[1]["page"])},
        "tables": {k: v for k, v in sorted(tables.items(),
                   key=lambda x: x[1]["page"])},
        "equations": {k: v for k, v in sorted(equations.items(),
                      key=lambda x: x[1]["page"])},
        "business_snapshots": {k: v for k, v in sorted(business_snapshots.items(),
                               key=lambda x: x[1]["page"])}
    }

    return result

def main():
    print("Scanning all XHTML files...")
    result = scan_all_pages()

    print(f"Found:")
    print(f"  Chapters:           {len(result['chapters'])}")
    print(f"  Sections:           {len(result['sections'])}")
    print(f"  Figures:            {len(result['figures'])}")
    print(f"  Tables:             {len(result['tables'])}")
    print(f"  Equations:          {len(result['equations'])}")
    print(f"  Business Snapshots: {len(result['business_snapshots'])}")

    # Summary of chapters with nav vs actual mismatches
    print("\nChapter mapping:")
    for ch_num, info in sorted(result['chapters'].items(), key=lambda x: int(x[0])):
        nav_page = info.get('nav_page', '?')
        heading_page = info.get('heading_page', '?')
        heading_id = info.get('heading_id', 'NONE')
        nav_anchor = info.get('nav_anchor', 'NONE')
        match = "OK" if str(nav_page) == str(heading_page) else "MISMATCH"
        print(f"  Ch {ch_num:>2}: nav->p{nav_page}, actual->p{heading_page}, "
              f"id={heading_id}, nav_anchor={nav_anchor} [{match}]")

    os.makedirs(OUTPUT.parent, exist_ok=True)
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to {OUTPUT}")

if __name__ == "__main__":
    main()
