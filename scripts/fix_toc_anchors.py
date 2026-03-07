"""Fix TOC anchors: add id="chap-N" anchors to chapter headings, rewrite nav.xhtml and toc.ncx."""

import re
import os
from pathlib import Path

EPUB_DIR = Path(__file__).resolve().parent.parent / "output" / "full_book_extracted" / "EPUB"

# Verified mapping: chapter number -> (page_num, current_heading_id, heading_pattern)
# Pattern types:
#   "h1_chapter_N" = h1 containing "CHAPTER N ..."
#   "h2_chapter_N" = h2 containing "CHAPTER N ..."
#   "h1_title" = h1 with just title text (Ch 1, 2, 12, 13)
#   "h2_standalone" = h2 with just <strong>CHAPTER</strong>
CHAPTER_MAP = {
    1:  (23, "chap-65", "h1_title"),
    2:  (46, "chap-89", "h1_title"),
    3:  (70, "sec-112", "h1_chapter_N"),
    4:  (98, "sec-137", "h1_chapter_N"),
    5:  (124, "sec-165", "h1_chapter_N"),
    6:  (152, "sec-194", "h2_chapter_N"),
    7:  (172, "sec-211", "h2_chapter_N"),
    8:  (201, "sec-239", "h2_standalone"),
    9:  (216, "sec-252", "h2_standalone"),
    10: (227, "sec-264", "h2_standalone"),
    11: (247, "sec-289", "h2_standalone"),
    12: (268, "sec-309", "h1_title"),
    13: (288, "sec-326", "h1_title"),
    14: (316, "sec-367", "h2_chapter_N"),
    15: (338, "chap-400", "h1_chapter_N"),
    16: (371, "sec-442", "h2_chapter_N"),
    17: (384, "sec-457", "h2_chapter_N"),
    18: (401, "sec-474", "h2_standalone"),
    19: (417, "sec-497", "h2_standalone"),
    20: (451, "sec-534", "h2_chapter_N"),
    21: (470, "sec-561", "h2_chapter_N"),
    22: (514, "sec-594", "h2_chapter_N"),
    23: (542, "sec-621", "h2_chapter_N"),
    24: (562, "sec-640", "h2_chapter_N"),
    25: (587, "sec-665", "h2_chapter_N"),
    26: (614, "sec-692", "h2_chapter_N"),
    27: (640, "sec-724", "h2_chapter_N"),
    28: (670, "sec-749", "h2_chapter_N"),
    29: (688, "sec-768", "h2_chapter_N"),
    30: (707, "sec-784", "h2_chapter_N"),
    31: (719, "sec-798", "h2_chapter_N"),
    32: (732, "sec-812", "h2_chapter_N"),
    33: (755, "sec-833", "h2_chapter_N"),
    34: (773, "sec-848", "h2_standalone"),
    35: (785, "sec-863", "h2_standalone"),
    36: (802, "sec-882", "h2_standalone"),
    37: (815, "sec-896", "h2_standalone"),
}

# Chapter titles from nav.xhtml
CHAPTER_TITLES = {
    1: "1. Introduction",
    2: "2. Futures markets and central counterparties",
    3: "3. Hedging strategies using futures",
    4: "4. Interest rates",
    5: "5. Determination of forward and futures prices",
    6: "6. Interest rate futures",
    7: "7. Swaps",
    8: "8. Securitization and the financial crisis of 2007\u20138",
    9: "9. XVAs",
    10: "10. Mechanics of options markets",
    11: "11. Properties of stock options",
    12: "12. Trading strategies involving options",
    13: "13. Binomial trees",
    14: "14. Wiener processes and It\u00f4\u2019s lemma",
    15: "15. The Black\u2013Scholes\u2013Merton model",
    16: "16. Employee stock options",
    17: "17. Options on stock indices and currencies",
    18: "18. Futures options and Black\u2019s model",
    19: "19. The Greek letters",
    20: "20. Volatility smiles and volatility surfaces",
    21: "21. Basic numerical procedures",
    22: "22. Value at risk and expected shortfall",
    23: "23. Estimating volatilities and correlations",
    24: "24. Credit risk",
    25: "25. Credit derivatives",
    26: "26. Exotic options",
    27: "27. More on models and numerical procedures",
    28: "28. Martingales and measures",
    29: "29. Interest rate derivatives: The standard market models",
    30: "30. Convexity, timing, and quanto adjustments",
    31: "31. Equilibrium models of the short rate",
    32: "32. No-arbitrage models of the short rate",
    33: "33. Modeling forward rates",
    34: "34. Swaps revisited",
    35: "35. Energy and commodity derivatives",
    36: "36. Real options",
    37: "37. Derivatives mishaps and what we can learn from them",
}


def add_chapter_anchors():
    """Add id='chap-N' anchors to chapter heading elements in XHTML files."""
    changes = []

    for ch_num, (page_num, current_id, pattern) in CHAPTER_MAP.items():
        filepath = EPUB_DIR / f"full_book_v7_p{page_num}.xhtml"
        if not filepath.exists():
            print(f"  WARNING: {filepath.name} not found for Ch {ch_num}")
            continue

        text = filepath.read_text(encoding="utf-8")
        new_text = text
        anchor_tag = f'<a id="chap-{ch_num}"></a>'

        # Check if anchor already exists
        if f'id="chap-{ch_num}"' in text:
            print(f"  Ch {ch_num}: anchor chap-{ch_num} already exists in {filepath.name}")
            continue

        # Find the heading element by its current id
        # Pattern: <h1 id="sec-112" ...> or <h2 id="sec-239" ...>
        heading_pattern = re.compile(
            rf'(<(?:h[12])\s[^>]*id="{re.escape(current_id)}"[^>]*>)',
            re.DOTALL
        )
        m = heading_pattern.search(text)
        if not m:
            # Try the other order: id might be the only attribute
            heading_pattern = re.compile(
                rf'(<(?:h[12])\s+id="{re.escape(current_id)}"[^>]*>)',
                re.DOTALL
            )
            m = heading_pattern.search(text)

        if m:
            # Insert anchor right before the heading
            pos = m.start()
            new_text = text[:pos] + anchor_tag + "\n" + text[pos:]
            changes.append((ch_num, filepath.name, current_id))
            print(f"  Ch {ch_num}: added anchor before id={current_id} in {filepath.name}")
        else:
            print(f"  WARNING: Ch {ch_num}: could not find id={current_id} in {filepath.name}")
            continue

        filepath.write_text(new_text, encoding="utf-8")

    return changes


def rewrite_nav_xhtml():
    """Rewrite nav.xhtml with correct chapter page links."""
    nav_path = EPUB_DIR / "nav.xhtml"
    text = nav_path.read_text(encoding="utf-8")

    for ch_num, (page_num, _, _) in CHAPTER_MAP.items():
        title = CHAPTER_TITLES[ch_num]
        correct_href = f"full_book_v7_p{page_num}.xhtml#chap-{ch_num}"

        # Find and replace the chapter link
        # Pattern: <a href="full_book_v7_pNN.xhtml#chap-XX">N. Title</a>
        old_pattern = re.compile(
            rf'<a\s+href="full_book_v7_p\d+\.xhtml(?:#[^"]*)?"\s*>{re.escape(title)}</a>',
            re.DOTALL
        )
        new_link = f'<a href="{correct_href}">{title}</a>'

        if old_pattern.search(text):
            text = old_pattern.sub(new_link, text)
        else:
            # Try a more relaxed match (title might differ slightly)
            old_pattern2 = re.compile(
                rf'<a\s+href="full_book_v7_p\d+\.xhtml(?:#[^"]*)?">\s*{ch_num}\.\s+[^<]*</a>',
                re.DOTALL
            )
            if old_pattern2.search(text):
                text = old_pattern2.sub(new_link, text)
            else:
                print(f"  WARNING: nav.xhtml - could not find link for Ch {ch_num}")

    nav_path.write_text(text, encoding="utf-8")
    print(f"  Rewrote nav.xhtml")


def rewrite_toc_ncx():
    """Rewrite toc.ncx with correct chapter page links."""
    ncx_path = EPUB_DIR / "toc.ncx"
    text = ncx_path.read_text(encoding="utf-8")

    for ch_num, (page_num, _, _) in CHAPTER_MAP.items():
        correct_src = f"full_book_v7_p{page_num}.xhtml#chap-{ch_num}"

        # Pattern: <content src="full_book_v7_pNN.xhtml#chap-XX"/>
        old_pattern = re.compile(
            rf'(<navPoint\s+id="toc-ch{ch_num}">\s*'
            rf'<navLabel>\s*<text>[^<]*</text>\s*</navLabel>\s*'
            rf'<content\s+src=")full_book_v7_p\d+\.xhtml(?:#[^"]*)?("/>)',
            re.DOTALL
        )
        m = old_pattern.search(text)
        if m:
            text = text[:m.start(1)] + m.group(1) + correct_src + m.group(2) + text[m.end(2):]
        else:
            print(f"  WARNING: toc.ncx - could not find entry for Ch {ch_num}")

    ncx_path.write_text(text, encoding="utf-8")
    print(f"  Rewrote toc.ncx")


def main():
    print("Phase 2: Fixing TOC anchors\n")

    print("Step 1: Adding chapter anchors to XHTML files...")
    changes = add_chapter_anchors()
    print(f"  Added {len(changes)} chapter anchors\n")

    print("Step 2: Rewriting nav.xhtml...")
    rewrite_nav_xhtml()

    print("\nStep 3: Rewriting toc.ncx...")
    rewrite_toc_ncx()

    print(f"\nDone! Fixed TOC anchors for {len(CHAPTER_MAP)} chapters.")


if __name__ == "__main__":
    main()
