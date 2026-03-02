# EPUB Manual Review Log
## Options, Futures, and Other Derivatives (11th Edition)

**Date:** 2026-03-02
**Reviewer:** Claude Code (automated agent)
**Method:** Manual page-by-page review of all 880 EPUB XHTML pages
**Reference:** PDF rendered as PNG images at 150 DPI (`output/pdf_renders/`)

---

## Review Process

### Phase 1: Systematic Structural Cleanup
**Script:** `scripts/fix_formatting.py`
**Scope:** All 880 pages

Applied 4 safe, structural-only fixes before manual review:

| Fix | Pages Affected | Description |
|-----|---------------|-------------|
| Split letter headings | 37 | `<strong>C</strong> <strong>H</strong>...` → `<strong>CHAPTER</strong>` |
| Adjacent `<em>` merge | 237 | `<em>X</em><em>Y</em>` → `<em>XY</em>` |
| Adjacent `<strong>` merge | 98 | Same pattern as em merge |
| Redundant inline styles | 853 | Removed `style="text-align: justify; ..."` that duplicated CSS rules |

**Total:** 853 pages modified (structural only, no content changes).

### Phase 2: Manual Review — Visual Comparison (All 880 pages)
**Method:** Render PDF pages as PNG images → visually inspect layout → compare with EPUB XHTML → fix discrepancies.
**Tool:** `scripts/render_pdf_pages.py` renders pages to `output/pdf_renders/page_NNNN.png`

This approach was adopted after recognizing that text extraction from the PDF suffers from the same encoding/font issues that caused problems in the original conversion. Visual comparison against rendered PDF images is the only reliable way to identify:
- Running chapter headers mixed into body text
- Figure/chart data (axis labels, data points) interpreted as body text
- Garbled equation notation from PearsonMATHPRO18 font encoding
- Table data linearized into paragraphs
- Two-column content interleaved

6 parallel review agents per batch, each covering ~25 pages.

---

## Common Issue Patterns Found

### 1. Running Chapter Headers in Body Text (VERY COMMON)
**Frequency:** ~400+ pages
**Description:** Nearly every page in the chapter content has "CHAPTER XX" and the chapter title (e.g., "Mechanics of Futures Markets") appearing as body text paragraphs. These are running headers in the PDF that got extracted as content.
**Fix applied:** Removed these paragraphs throughout all 880 pages.
**Pattern to detect:** `<p>CHAPTER \d+</p>` or `<p><strong>CHAPTER...</strong></p>` followed by chapter title as a separate `<p>`.

### 2. PearsonMATHPRO18 Font Encoding (COMMON)
**Frequency:** ~300+ pages (equation-heavy chapters)
**Description:** The PDF uses a custom font (PearsonMATHPRO18) that maps ASCII characters to math symbols. When extracted as text, these symbols become garbled:

| PDF Character | Extracted As | Correct Symbol |
|--------------|-------------|----------------|
| `$` | `+` | `$` (dollar sign) |
| `(` | `1` | `(` |
| `)` | `2` | `)` |
| `[` | `3` | `[` |
| `]` | `4` | `]` |
| `/` | `>` | `/` (division) |
| `σ` | `s` | `σ` (sigma) |
| `μ` | `m` | `μ` (mu) |
| `ε` | `P` or `∏` | `ε` (epsilon) |
| `ρ` | `r` | `ρ` (rho) |
| `λ` | `l` | `λ` (lambda) |
| `≤` | `6` | `≤` |
| `≥` | `7` | `≥` |
| `%` | `,` | `%` |
| `Σ` | `√` | `Σ` (summation) |
| `∂` | `0` | `∂` (partial) |
| `...` | `∫` | `...` (ellipsis) |

**Fix applied:** `scripts/fix_equations.py` handles many of these. Manual review fixed remaining instances where context was needed for disambiguation.

### 3. Figure/Chart Data as Body Text (COMMON)
**Frequency:** ~100+ pages
**Description:** When figures contain text (axis labels, data point values, tree node values, table cells), the PDF-to-text extraction pulls these out as body paragraphs. They appear as nonsensical sequences like:
- "0.4 0.8 1.2 1.6 2.0 2.4" (axis labels)
- "22 20.7 19.5 20.3 18.4 17.7" (binomial tree values)
- "100 90 80 70 60 50" (chart Y-axis)

**Fix applied:** Deleted garbled figure data from body text. The actual figures are preserved as images (PNG files in `EPUB/images/`).

### 4. Section Headings as Body Text (COMMON)
**Frequency:** ~200+ pages
**Description:** Section headings like "12.5 Black-Scholes-Merton Pricing Formulas" were formatted as `<p><strong>...</strong></p>` instead of proper `<h2>` tags.
**Fix applied:** Converted to `<h2 id="sec-XXX">` where appropriate.

### 5. Equation Structural Issues (MODERATE)
**Frequency:** ~150+ pages
**Description:** Multi-line equations split across separate `<div>` and `<p>` elements, losing their visual structure. Fractions displayed as `a / b` instead of stacked notation. Equation numbers (e.g., "(6.1)") sometimes separated from their equations.
**Fix applied:** Consolidated split equation elements where possible. Some complex equations remain imperfect due to limitations of text-based equation rendering.

### 6. Soft Hyphen Artifacts (MODERATE)
**Frequency:** ~50+ pages
**Description:** Words containing soft hyphens (`\u00AD`) that were used for line breaking in the PDF but shouldn't appear in flowing EPUB text. Example: "approx\u00ADimation".
**Fix applied:** Removed soft hyphens from body text.

### 7. Diacritical/Accent Issues (LOW)
**Frequency:** ~10 pages
**Description:** Names with accented characters corrupted. Examples: "Itô" appearing as "ItÔ", "Société Générale" as "Société Général".
**Fix applied:** Corrected specific instances found.

### 8. Index Two-Column Interleaving (MODERATE)
**Frequency:** Pages 859-880
**Description:** The Author Index and Subject Index use two-column layout in the PDF. Extraction linearized the columns by alternating entries from left and right, disrupting alphabetical order.
**Fix applied:** De-interleaved entries on reviewed pages, restoring correct alphabetical order where possible. Some pages may still have minor ordering issues.

### 9. Truncated/Sparse Pages (LOW)
**Frequency:** ~5 pages
**Description:** A few pages have significantly less content than the PDF original.
- Page 273: Missing Example 12.2
- Page 324: Only one sentence from a full page
- Page 726: ~12% content
- Pages 857-858: N(x) table data missing

**Status:** These pages need re-extraction from the PDF with more careful handling.

### 10. Full-Page Image Replacements (LOW)
**Frequency:** Pages 312-314 (Appendix equations)
**Description:** Some pages with dense mathematical content were so garbled that text-based fixes were impractical.
**Fix applied:** Where feasible, replaced entire page content with rendered PDF page images.

---

## Review Coverage by Batch

All batches used visual comparison against rendered PDF page images (150 DPI PNG).

### Batch 1: Pages 1–50 (Visual comparison)
- Front matter (1-23): Fixed running headers on preface pages, fixed chapter heading fragments
- Chapter 1-2: Section headings promoted to `<h2>`, section numbers added, figure data deleted
- 17 running headers removed, 7 section headings converted, 2 chapter headings fixed

### Batch 2: Pages 51–100 (Visual comparison)
- Chapters 2-4: 24 running headers removed, ~45 headings promoted
- Dollar sign fixes (`+` → `$`), table/figure data deleted (6 pages)
- Broken chapter headings reassembled (pages 70, 98)

### Batch 3: Pages 101–150 (Visual comparison)
- Chapters 4-5: 27 running headers removed, 35 headings promoted
- PearsonMATHPRO18 fixes (`+`→`$`, `>`→`/`, `,`→`%`), misplaced headings relocated
- Chapter 5 heading reassembled (page 124)

### Batch 4: Pages 151–200 (Visual comparison)
- Chapters 6-7: 24 running headers removed, 13 section numbers added
- Major rewrites on 3 pages (176, 178, 186) to fix content ordering
- Figure diagram labels and table data deleted from 5 pages

### Batch 5: Pages 201–250 (Visual comparison)
- Chapters 8-11: 20 running headers removed, 28 headings promoted
- Figure axis labels deleted (pages 228, 230, 249)
- Missing text restored (page 205), misplaced headings relocated (pages 240, 242)

### Batch 6: Pages 251–300 (Visual comparison)
- Chapters 11-13: 25 running headers removed, 12 section headings fixed
- 75 soft hyphens removed, 12 pages of figure captions/axis labels deleted
- Chapter headings fixed (pages 268, 288)

### Batch 7: Pages 301–450 (Visual comparison)
- Chapters 14-20: Figure data extensively cleaned from body text
- Pages 312-314 replaced with full-page images (appendix equations)

### Batch 8: Pages 451–600 (Visual comparison)
- Chapters 21-26: Binomial tree data cleaned from body text
- PearsonMATHPRO18 encoding fixes in options pricing formulas

### Batch 9: Pages 601–740 (Visual comparison)
- Chapters 27-33: Interest rate models, credit derivatives
- Complex multi-line equation consolidation

### Batch 10: Pages 741–880 (Visual comparison)
- Chapters 34-37 + back matter: Energy/commodity derivatives, real options
- Glossary (828-850): Verified good
- DerivaGem (851-856): Minor formatting
- N(x) tables (857-858): Data still missing
- Indexes (859-880): De-interleaved where possible

---

## Remaining Known Issues

### HIGH Priority
1. **Truncated pages** (273, 324, 726): Need re-extraction from PDF
2. **N(x) table data** (857-858): Table content missing, only headers present
3. **Some PearsonMATHPRO18 encoding** may remain in pages not caught by automated fix

### MODERATE Priority
4. **Equation layout**: Multi-line equations in text format can't fully replicate PDF visual layout
5. **Index ordering**: Some pages in 859-880 range may still have minor interleaving
6. **Subscripts**: Some subscripts rendered as `<span class="fs-small">` rather than `<sub>`

### LOW Priority
7. **Table formatting**: Tables extracted as images are visually correct but not text-searchable
8. **Cross-reference links**: Internal page references could be linked but currently are plain text

---

## Instructions for Future Agents

### How to Continue This Review

1. **Use visual comparison**: Always render PDF pages as images (`python scripts/render_pdf_pages.py --pages X-Y`) and compare visually. Do NOT extract text from the PDF — that's where the encoding issues originate.

2. **Focus on truncated pages first**: Pages 273, 324, 726, 857-858 need the most attention.

3. **Watch for PearsonMATHPRO18 patterns**: If you see sequences like `1X 2 2X 2` in equation contexts, it likely means `(X) (X)` — refer to the encoding table above.

4. **Figure data deletion**: If you see sequences of numbers that don't form sentences (axis labels, data points), check if there's already a figure image on that page. If so, delete the garbled text.

5. **Running headers**: Any standalone `<p>CHAPTER XX</p>` or chapter title as a paragraph should be removed — it's a page header, not content.

6. **Rebuild after edits**:
   ```bash
   python -c "import sys; sys.path.insert(0,'scripts'); from epub_extract import create_epub; create_epub('output/full_book_fixed.epub', 'output/full_book_extracted')"
   ```

### Key Scripts

| Script | Purpose |
|--------|---------|
| `scripts/fix_formatting.py` | Safe structural cleanup (tag merging, style removal) |
| `scripts/fix_epub.py` | Content fixes (orphaned headers, index, equation encoding) |
| `scripts/fix_equations.py` | Font-aware equation correction using PDF font metadata |
| `scripts/fix_empty_pages.py` | Populate empty pages from PDF extraction |
| `scripts/render_pdf_pages.py` | Render PDF pages as PNG for visual comparison |
| `scripts/epub_extract.py` | Extract/rebuild EPUB files |

### EPUB Structure
- **XHTML pages:** `output/full_book_extracted/EPUB/full_book_v7_p{1..880}.xhtml`
- **Images:** `output/full_book_extracted/EPUB/images/` (319 images)
- **CSS:** `output/full_book_extracted/EPUB/style.css`
- **PDF renders:** `output/pdf_renders/page_NNNN.png` (render on demand)
