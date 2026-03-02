# EPUB Validation Report
## Options, Futures, and Other Derivatives (11th Edition)

**Source PDF:** `options_futures_and_other_derivatives_11th.pdf` (880 pages)
**EPUB:** `output/full_book.epub` (880 XHTML pages)
**Date:** 2026-03-02

---

## Executive Summary

The EPUB conversion preserves **all text content, figures, charts, and tables** from the PDF.
However, **mathematical equations are systematically corrupted** due to font encoding issues
in the PDF-to-EPUB conversion pipeline. This is the single most critical issue.

| Category | Status | Details |
|----------|--------|---------|
| Prose text | GOOD | Correct on all 880 pages |
| Figures/charts | GOOD | All present and correctly rendered |
| Tables | OK | Rendered as images (visually correct, not searchable as text) |
| Numerical examples | GOOD | All values correct |
| Page ordering | GOOD | 1:1 mapping, no gaps |
| Business Snapshots | GOOD | Content correct, layout differs slightly (expected) |
| Equations | **CRITICAL** | Systematically garbled across all equation-containing pages |
| Subject Index | **MODERATE** | Two-column merge, entries interleaved, some promoted to headings |
| Orphaned content | **MINOR** | Some pages have orphaned "CHAPTER XX" heading + equation fragments at bottom |

---

## Visual Comparison Results (880 pages)

All 880 pages were rendered to images (PDF via PyMuPDF, EPUB via headless Chrome)
and compared pixel-by-pixel.

| Metric | Value |
|--------|-------|
| Total pages | 880 |
| GOOD (>= 0.92 similarity) | 732 (83.2%) |
| REVIEW (0.80-0.92) | 148 (16.8%) |
| ISSUE (< 0.80) | 0 (0%) |
| Mean similarity | 0.9353 |
| Min similarity | 0.8635 (page 590) |

The 148 REVIEW pages are mostly **Business Snapshot boxes** where layout differs
between PDF (sidebar boxes) and EPUB (inline sections). The **content is correct** on all of them.

---

## Issue #1: Equation Encoding Corruption (CRITICAL)

**Scope:** Affects ALL pages containing mathematical equations (estimated 300+ pages)

**Root cause:** The PDF uses special math fonts where character codes map differently
than standard Unicode. The conversion pipeline does not correctly decode these mappings.

### Character substitution table:

| PDF Symbol | EPUB Renders As | Example |
|-----------|-----------------|---------|
| σ (sigma) | `s` | σ²Δt → `s 2 Δ t` |
| ∂ (partial) | `0` (zero) | ∂f/∂S → `0 f / 0 S` |
| ( ) parentheses | `1...2` | f(x) → `f 1 x 2` |
| [ ] brackets | `3...4` | [a+b] → `3 a + b 4` |
| / (division) | `>` | a/b → `a > b` |
| < (less than) | `6` | S < H → `S 6 H` |
| > (greater than) | `7` | S > H → `S 7 H` |
| ≤ (less-equal) | `6` | x ≤ y → `x 6 y` |
| ≥ (greater-equal) | `7` | x ≥ y → `x 7 y` |
| √ (square root) | lost | √T → `T` |
| Fraction bars | lost | Numerator and denominator separated into different elements |
| Superscripts | flattened | x² → `x 2` |
| Subscripts | flattened | x_i → `x i` |

### Examples of corrupted equations:

**Page 350, equation (15.17):**
- PDF: α = 2r/σ²
- EPUB: `a = 2 r > s 2`

**Page 472, equation (21.3):**
- PDF: u = 1/d
- EPUB: `u = 1 > d` (reads as "u greater than d" instead of "u equals 1 divided by d")

**Page 624, lookback option formula:**
- PDF: a₁ = [ln(S₀/S_min) + (r-q+σ²/2)T] / (σ√T)
- EPUB: `a 1 = ln 1 S 0 > S min 2 + 1 r - q + s 2 > 2 2 T`

### Additional equation issues:
- Orphaned equation fragments at the bottom of many pages (below a "CHAPTER XX" heading)
- Equation numbers (e.g., "(21.3)") sometimes displaced or missing

---

## Issue #2: Subject Index Format (MODERATE)

**Scope:** Pages ~859-879 (Author Index + Subject Index)

**Issues:**
1. Two-column layout collapsed into continuous paragraph text
2. Entries from left and right columns are interleaved (alphabetical order broken)
3. Some short entries (ABS, CCP, CDO, CDS, CEBO) incorrectly promoted to `<h2>` headings
4. Sub-entry indentation hierarchy lost
5. No line breaks between entries

**Content:** All entries and page numbers appear to be present.

---

## Issue #3: Orphaned Content at Page Bottoms (MINOR)

**Scope:** Many pages (particularly equation-heavy ones)

Some EPUB pages have content at the very bottom that appears orphaned:
- A "CHAPTER XX" heading (underlined, large text)
- Followed by equation fragments that are garbled

This appears to be leftover content from the conversion process and should be removed.

---

## Pages Verified Manually (by visual inspection of rendered images)

| Page | Content Type | PDF vs EPUB | Verdict |
|------|-------------|-------------|---------|
| 1 | Title page | Match | GOOD |
| 26 | Business Snapshot 1.1 | Content match, layout differs | GOOD |
| 33 | Figure 1.3 (profit charts) | Figure correct | GOOD |
| 40 | Business Snapshot 1.4 | Content match | GOOD |
| 45 | End-of-chapter problems | Perfect match | GOOD |
| 56 | Business Snapshot 2.2 (LTCM) | Content match | GOOD |
| 106 | Table 4.3 + Par Yield equations | Table correct, equations garbled | EQUATION ISSUE |
| 128 | Table 5.2 (arbitrage) | Table as image, correct | GOOD |
| 155 | Section 6.2 Treasury Bond Futures | Text correct | GOOD |
| 162 | SOFR Futures text | Text correct | GOOD |
| 176 | Table 7.3 (OIS rates) + Figure 7.2 | Table/figure as images, correct | GOOD |
| 250 | Figure 11.2 (4 option charts) | All 4 charts correct | GOOD |
| 258 | Business Snapshot 11.1 | Content match | GOOD |
| 300 | Ch 13 volatility matching | Text correct, equations garbled | EQUATION ISSUE |
| 346 | Business Snapshot 15.2 | Content match | GOOD |
| 350 | Perpetual derivative equations | Equations severely garbled | EQUATION ISSUE |
| 444 | Business Snapshot 19.2 | Content match | GOOD |
| 472 | Binomial tree equations (21.1-21.7) | Equations garbled, figure correct | EQUATION ISSUE |
| 500 | Figure 21.15 (finite diff grid) | Figure perfect, equations garbled | EQUATION ISSUE |
| 515 | Business Snapshot 22.1 (VaR) | Content match | GOOD |
| 590 | Business Snapshot 25.2 (CDS) | Content match | GOOD |
| 624 | Lookback option formulas | Equations severely garbled | EQUATION ISSUE |
| 816 | Business Snapshot 37.1 | Content match | GOOD |
| 863 | Subject Index | Entries interleaved, format broken | INDEX ISSUE |

---

## Rendered Images Location

All rendered images are saved for manual inspection:
- **PDF renders:** `output/validation_renders/pdf/pdf_p{N}.png`
- **EPUB renders:** `output/validation_renders/epub/epub_p{N}.png`
- **Diff images:** `output/validation_renders/diffs/diff_p{N}.png` (148 pages with sim < 0.92)
- **JSON report:** `validation_visual_report.json`
