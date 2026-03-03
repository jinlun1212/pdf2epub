# Page Audit SOP

This SOP is mandatory for page-by-page EPUB correction work. A page is not complete until the tracker entry is written by `scripts/record_page_audit.py` and `scripts/validate_page_audit.py --page N` passes.

## Goal

For every page from 1 to 880:

1. Render the source PDF page.
2. Render the current EPUB page.
3. Compare the two visually.
4. Fix the XHTML and/or CSS until the EPUB render matches the PDF in structure and meaning.
5. Re-render the EPUB page.
6. Record the completed audit in `page_audit_status.json`.

## Non-negotiable rules

1. Do not mark a page complete from XHTML inspection alone.
2. Do not mark a page complete from PDF text extraction alone.
3. Do not mark a page complete until both render images exist:
   `output/pdf_renders/page_NNNN.png`
   `output/epub_renders/page_NNNN.png`
4. Do not mark a page complete until you can describe:
   what the PDF render shows
   what the final EPUB render shows
   why they now match
5. If a table, figure, footnote, equation, or boxed snapshot is broken, reconstruct the structure in XHTML. Do not leave mashed paragraph text in place.

## Required setup

The EPUB stylesheet must be linked from every XHTML file. This is enforced on rebuild by `scripts/epub_extract.py`, but validate it if layout looks wrong.

Build commands:

```bash
python3 -c "import sys; sys.path.insert(0,'scripts'); from epub_extract import create_epub; create_epub('output/full_book_improved.epub','output/full_book_extracted')"
python3 scripts/validate_page_audit.py
```

Render commands:

```bash
python3 scripts/render_pdf_pages.py --pages 28,29
node scripts/render_epub_pages.js --pages 28,29
```

## Page workflow

1. Render the PDF page if missing.
2. Render the EPUB page.
3. Open both images side by side.
4. Identify issues in one of these categories:
   text flow / truncation
   paragraph alignment
   equation encoding or centering
   superscript / subscript
   table structure
   figure vs text leakage
   footnotes
   headings / TOC
   boxed content / snapshot layout
5. Inspect the XHTML for that exact page.
6. Fix the XHTML and/or CSS.
7. Rebuild the EPUB.
8. Re-render the EPUB page.
9. Compare again.
10. Only when the page matches, record the audit.

## Fix patterns

### Tables

If the PDF shows a table and the EPUB shows a paragraph blob, rebuild it as a real HTML table with caption, alignment, and notes below it.

Example pattern:

```html
<div id="tbl-1-1" class="table-wrap">
  <p class="table-caption"><strong>Table 1.1</strong> ...</p>
  <table class="table-plain">...</table>
  <hr class="footnote-rule"/>
  <p class="table-note"><sup>1</sup> ...</p>
</div>
```

### Equations

Equations must be centered. If the PDF shows math, do not leave plain inline text if the notation becomes ambiguous.

Preferred options:

1. MathML when it is reliable and readable.
2. A centered `.equation` block with correct subscripts and superscripts.

Bad:

```html
<div class="equation"><span class="eq-inline">ST - K</span></div>
```

Good:

```html
<div class="equation"><span class="eq-inline"><em>S</em><sub>T</sub> - <em>K</em></span></div>
```

### Figures and boxed content

If content belongs inside a figure, table, or business snapshot box in the PDF, do not leave it in the main text flow. Recreate the box or use the figure image where appropriate.

### Paragraph alignment

Main body text should render justified. If a page renders left-aligned, check stylesheet linkage before changing paragraph markup.

## Completion recording

Use this command only after the page matches:

```bash
python3 scripts/record_page_audit.py \
  --page 28 \
  --agent codex \
  --pdf-observation "PDF shows Table 1.1 as a compact 3-column table with two notes below it." \
  --epub-observation "EPUB now renders Table 1.1 as a compact table with Bid and Ask columns and notes below." \
  --comparison-summary "Caption, row structure, numeric alignment, and notes now match the PDF layout and meaning." \
  --issue "Mashed paragraph text replaced the table." \
  --issue "Footnotes were in the wrong place." \
  --fix "Rebuilt Table 1.1 as HTML table markup." \
  --fix "Moved notes below the table and added a stable anchor."
```

Then validate:

```bash
python3 scripts/validate_page_audit.py --page 28
```

## Tracker semantics

`page_audit_status.json` is the source of truth.

`pending` means not yet verified.

`completed` means:

1. Both renders exist.
2. The page was visually compared.
3. The final EPUB render matches the PDF.
4. The entry contains real observations and a comparison summary.

## What to do if unsure

If the EPUB and PDF differ and the correct structure is unclear:

1. Trust the rendered PDF page, not extracted PDF text.
2. Check the next and previous pages for continuation.
3. Prefer semantic HTML over screenshot placeholders unless the source is inherently image-based.
4. If a figure or table is too complex to reconstruct reliably, use the rendered image, but document that choice in the audit entry.
