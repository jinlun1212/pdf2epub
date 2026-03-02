# Agent Handoff: PDF-to-EPUB Conversion & Validation

## Project Overview

This project converts a PDF textbook ("Options, Futures, and Other Derivatives" 11th Edition, 880 pages) to EPUB format and validates the conversion quality.

## Current State

### What's been done:

1. **PDF-to-EPUB conversion** (pre-existing) — The PDF was converted to EPUB using scripts in `scripts/`. The resulting `output/full_book.epub` contains 880 XHTML pages, 314 images, CSS, and EPUB metadata.

2. **Extraction** — `scripts/epub_extract.py` extracts the EPUB into `output/full_book_extracted/` for editing individual XHTML pages.

3. **Validation** — Two rounds of validation:
   - **Text-based** (`scripts/validate_epub.py`, `scripts/validate_deep.py`): Compared extracted text from PDF and EPUB. Found many false positives due to `SequenceMatcher(autojunk=True)` bug and PDF extraction artifacts.
   - **Visual/rendered** (`scripts/validate_visual.py`): Rendered all 880 pages as images (PDF via PyMuPDF, EPUB via Playwright+Chrome) and compared pixel-by-pixel. Results: 732 GOOD (83.2%), 148 REVIEW (16.8%), 0 ISSUE.

4. **Manual review** — Visually inspected ~25 representative pages covering text, figures, tables, equations, and index pages.

5. **Fixes applied** (`scripts/fix_epub.py`):
   - **Orphaned content removed** (380 pages): Removed `<h1 id="chap-XXX">CHAPTER XX</h1>` tags and trailing equation fragments at page bottoms.
   - **Index headings fixed** (13 pages): Converted incorrectly-tagged `<h2>` index entries back to `<p>` tags.
   - **Index line breaks** (22 pages): Added `<br/>` tags between merged index entries in long paragraphs.
   - **Equation encoding** (21 pages): Fixed `≤`/`≥` symbols and `∂f/∂t` partial derivative notation where context was unambiguous.

6. **Rebuilt EPUB** — `output/full_book_fixed.epub` (20.3 MB) contains all fixes.

### What still needs work:

#### Equation encoding (CRITICAL, ~300+ pages)

The PDF uses special math fonts where characters map to different Unicode code points. The conversion pipeline did not correctly decode these mappings. The following substitutions occur throughout equation-containing pages:

| PDF Symbol | Appears as in EPUB | Inside `<span class="eq-inline">` |
|-----------|-------------------|----------------------------------|
| σ (sigma) | `s` | Yes |
| ∂ (partial) | `0` (zero) | Yes |
| ( ) | `1...2` | Yes |
| [ ] | `3...4` | Yes |
| / (division) | `>` | Yes (and in `&gt;` form in text) |
| √ (square root) | lost entirely | Yes |
| Fraction bars | lost (num/denom in separate divs) | Yes |
| Superscripts | flattened | Yes |

**Why this is hard to fix automatically:**
- The substitutions are context-dependent: `0` could be the digit zero or `∂`, `2` could be the digit two or close-parenthesis, etc.
- Inside `<div class="equation"><span class="eq-inline">` blocks, ALL content is garbled since the font mapping applies to the entire equation.
- A proper fix requires either: (a) re-extracting equations from the PDF with correct font decoding, or (b) manually correcting each equation against the PDF.

**Recommended approach for equation fix:**
- Use PyMuPDF (`fitz`) to re-extract text from the PDF with font-aware decoding
- Build a mapping between garbled EPUB equation text and correct PDF equation text
- Or: render equations as images from the PDF and embed them in the EPUB

#### Index formatting (MODERATE)

The Subject/Author Index (pages ~857-880) has entries from two PDF columns interleaved. The line breaks added by `scripts/fix_epub.py` help but don't fully fix the ordering. A proper fix would require re-extracting the index from the PDF with column-aware parsing.

## File Structure

```
├── scripts/                         # All scripts
│   ├── epub_extract.py              # Extract/modify/rebuild EPUB files (CLI tool)
│   ├── fix_epub.py                  # Apply fixes to extracted EPUB XHTML files
│   ├── validate_visual.py           # Visual comparison (render + pixel diff)
│   ├── validate_epub.py             # Text-based validation (initial)
│   ├── validate_deep.py             # Improved text validation with artifact filtering
│   ├── pdf_chapter_to_epub.py       # Original: chapter-level PDF-to-EPUB conversion
│   ├── pdf_to_fixed_epub.py         # Original: fixed-layout PDF-to-EPUB conversion
│   ├── capture_books_epub_pages.sh  # macOS Books app screen capture
│   ├── capture_books_epub_until_end.py
│   ├── init_epub_screen_tracker.py
│   └── pages_first20_pipeline.py
├── output/
│   ├── full_book.epub               # Original converted EPUB (unmodified)
│   ├── full_book_fixed.epub         # Fixed EPUB (with all fixes applied)
│   ├── full_book.docx               # DOCX output
│   ├── full_book_extracted/         # Extracted EPUB files (for editing, regenerable)
│   └── validation_renders/          # Rendered images (regenerable, ~2GB)
├── VALIDATION_REPORT.md             # Full validation report with findings
├── AGENT_HANDOFF.md                 # This file
├── README.md
├── .gitignore
├── requirements.txt
└── validation_visual_report.json    # Per-page similarity scores
```

## Key Dependencies

```
PyPDF2        # PDF text extraction
PyMuPDF       # PDF page rendering (fitz)
Pillow        # Image processing
numpy         # Pixel comparison
playwright    # Browser automation for XHTML rendering
```

Chrome must be installed at `C:\Program Files\Google\Chrome\Application\chrome.exe` for EPUB rendering.

## Workflow to rebuild EPUB after edits:

```bash
# From the project root directory:
python -c "import sys; sys.path.insert(0,'scripts'); from epub_extract import create_epub; create_epub('output/full_book_fixed.epub', 'output/full_book_extracted')"
```

## Workflow to re-validate after changes:

```bash
python scripts/validate_visual.py  # Takes ~15 min (renders + compares all 880 pages)
```

## Workflow to apply fixes after extraction:

```bash
python scripts/fix_epub.py  # Applies all fixes to output/full_book_extracted/EPUB/
```
