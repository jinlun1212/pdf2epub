# PDF to EPUB to LaTeX Converter

This toolkit converts PDFs to EPUB format, then optionally to LaTeX.

## Files

- **pdf2epub.ipynb** — Jupyter notebook for PDF → EPUB conversion
- **epub2latex.py** — Standalone script for EPUB → LaTeX conversion

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

For **EPUB → LaTeX conversion**, you also need **pandoc** (command-line tool):

- **macOS:** `brew install pandoc`
- **Linux:** `sudo apt install pandoc`
- **Windows:** Download from https://pandoc.org/installing.html

## Usage

### PDF to EPUB (Jupyter Notebook)

1. Open `pdf2epub.ipynb` in Jupyter or VS Code
2. Edit variables:
   - `PDF_NAME` — path to your PDF
   - `CHAPTER_START_PAGE` / `CHAPTER_END_PAGE` — page range
3. Run cells in order
4. Output: `output/chapter1.epub`

### EPUB to LaTeX (Command-line)

```bash
python epub2latex.py book.epub book.tex
```

Or use in Python:

```python
from epub2latex import epub_to_latex

epub_to_latex("chapter1.epub", "chapter1.tex")
```

## LaTeX Compilation

After generating `book.tex`, compile to PDF:

```bash
pdflatex -interaction=nonstopmode book.tex
```

For better results with complex formatting:

```bash
xelatex book.tex
```

## Requirements

- Python 3.8+
- `ebooklib` — for EPUB handling
- `beautifulsoup4` — for HTML parsing (pdf2epub notebook)
- `qpdf` — for PDF splitting (pdf2epub notebook)
- `pdftohtml` — for PDF extraction (pdf2epub notebook)
- `pandoc` — for format conversion (epub2latex script)

