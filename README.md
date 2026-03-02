# PDF to EPUB Converter

Converts a PDF textbook to EPUB format with validation and automated fixes.

## Project Structure

```
├── scripts/                         # All scripts
│   ├── epub_extract.py              # Extract/modify/rebuild EPUB files
│   ├── fix_epub.py                  # Apply fixes to extracted EPUB XHTML
│   ├── validate_visual.py           # Visual comparison (render + pixel diff)
│   ├── validate_epub.py             # Text-based validation
│   ├── validate_deep.py             # Deep text validation with artifact filtering
│   ├── pdf_chapter_to_epub.py       # PDF-to-EPUB chapter conversion
│   ├── pdf_to_fixed_epub.py         # Fixed-layout PDF-to-EPUB conversion
│   └── ...                          # Screen capture & pipeline utilities
├── output/
│   ├── full_book.epub               # Original converted EPUB
│   ├── full_book_fixed.epub         # EPUB with all fixes applied
│   └── full_book.docx               # DOCX output
├── VALIDATION_REPORT.md             # Detailed validation findings
├── AGENT_HANDOFF.md                 # Handoff documentation for continuing work
├── validation_visual_report.json    # Per-page visual similarity scores
├── requirements.txt
└── .gitignore
```

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

Chrome must be installed at the default path for EPUB rendering via Playwright.

## Usage

### Extract EPUB for editing

```bash
python scripts/epub_extract.py output/full_book.epub --extract-only --temp-dir output/full_book_extracted
```

### Apply fixes to extracted EPUB

```bash
python scripts/fix_epub.py
```

### Rebuild EPUB after edits

```python
import sys; sys.path.insert(0, 'scripts')
from epub_extract import create_epub
create_epub("output/full_book_fixed.epub", "output/full_book_extracted")
```

### Run visual validation

```bash
python scripts/validate_visual.py
```

## Current Status

See [VALIDATION_REPORT.md](VALIDATION_REPORT.md) for detailed findings and [AGENT_HANDOFF.md](AGENT_HANDOFF.md) for remaining work items.
