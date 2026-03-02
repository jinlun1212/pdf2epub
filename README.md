# PDF to EPUB Converter

Converts a PDF textbook to EPUB format with automated fixes and manual validation.

## Project Structure

```
├── scripts/                         # All scripts
│   ├── epub_extract.py              # Extract/modify/rebuild EPUB files
│   ├── fix_epub.py                  # Apply structural fixes to EPUB XHTML
│   ├── fix_equations.py             # Font-aware equation correction using PDF
│   ├── pdf_chapter_to_epub.py       # PDF-to-EPUB chapter conversion
│   ├── pdf_to_fixed_epub.py         # Fixed-layout PDF-to-EPUB conversion
│   └── ...                          # Screen capture & pipeline utilities
├── output/
│   ├── full_book.epub               # Original converted EPUB
│   ├── full_book_fixed.epub         # EPUB with all fixes applied
│   └── full_book.docx               # DOCX output
├── VALIDATION_REPORT.md             # Manual page-by-page validation results
├── AGENT_HANDOFF.md                 # Handoff documentation for continuing work
├── requirements.txt
└── .gitignore
```

## Setup

```bash
pip install -r requirements.txt
```

## Usage

### Extract EPUB for editing

```bash
python scripts/epub_extract.py output/full_book.epub --extract-only --temp-dir output/full_book_extracted
```

### Apply fixes to extracted EPUB

```bash
python scripts/fix_epub.py          # Structural fixes (orphans, index, etc.)
python scripts/fix_equations.py     # Font-aware equation corrections
```

### Rebuild EPUB after edits

```python
import sys; sys.path.insert(0, 'scripts')
from epub_extract import create_epub
create_epub("output/full_book_fixed.epub", "output/full_book_extracted")
```

## Current Status

See [VALIDATION_REPORT.md](VALIDATION_REPORT.md) for detailed findings and [AGENT_HANDOFF.md](AGENT_HANDOFF.md) for remaining work items.
