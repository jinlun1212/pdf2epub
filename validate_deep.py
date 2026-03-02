"""
Deep validation: categorize issues, filter false positives from PDF artifacts,
and identify genuine conversion problems.
"""
import json
import re
import os
import sys
import io
from pathlib import Path

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from html.parser import HTMLParser
from difflib import SequenceMatcher
import unicodedata

import PyPDF2

PDF_PATH = "options_futures_and_other_derivatives_11th.pdf"
EPUB_DIR = "output/full_book_extracted/EPUB"

# PDF extraction artifacts to ignore
PDF_ARTIFACTS = re.compile(
    r'(?:'
    r'm\d+_hull\d+_\d+_ge_\w+|'    # file refs like m01_hull0654_11_ge_c01
    r'a\d+_hull\d+_\d+_ge_\w+|'     # file refs like a01_hull...
    r'indd|'                          # InDesign refs
    r'\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}|'  # timestamps
    r'03/05/2021|'                    # specific date
    r'04/05/2021|'
    r'z\d+_hull\d+_\d+_ge_\w+'       # more file refs
    r')',
    re.IGNORECASE
)

EPUB_ARTIFACTS = re.compile(
    r'(?:11th|edition|options\s*futures\s*and\s*other\s*derivatives)',
    re.IGNORECASE
)


class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self._skip = True
        if tag in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'br', 'tr', 'td', 'th'):
            self.result.append(' ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self.result.append(data)

    def get_text(self):
        return ' '.join(''.join(self.result).split())


class HTMLStructureExtractor(HTMLParser):
    """Extract structural info: images, equations, tables with context."""
    def __init__(self):
        super().__init__()
        self.images = []
        self.equations = []
        self.tables = 0
        self.in_equation = False
        self.eq_text = []
        self.in_table = False
        self.table_data = []
        self.current_row = []
        self.current_cell = []
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag == 'img':
            self.images.append(attr_dict.get('src', ''))
        if attr_dict.get('class', '') in ('equation', 'eq-inline'):
            self.in_equation = True
            self.eq_text = []
        if tag == 'table':
            self.tables += 1
            self.in_table = True
            self.table_data = []
        if tag == 'tr':
            self.current_row = []
        if tag in ('td', 'th'):
            self.in_cell = True
            self.current_cell = []

    def handle_endtag(self, tag):
        if tag == 'div' and self.in_equation:
            self.equations.append(' '.join(''.join(self.eq_text).split()))
            self.in_equation = False
        if tag == 'span' and self.in_equation:
            pass  # eq-inline ends with span but we track via div
        if tag in ('td', 'th') and self.in_cell:
            self.in_cell = False
            self.current_row.append(''.join(self.current_cell).strip())
        if tag == 'tr' and self.in_table:
            self.table_data.append(self.current_row)
        if tag == 'table':
            self.in_table = False

    def handle_data(self, data):
        if self.in_equation:
            self.eq_text.append(data)
        if self.in_cell:
            self.current_cell.append(data)


def clean_pdf_text(text):
    """Remove PDF artifacts from text."""
    text = PDF_ARTIFACTS.sub('', text)
    text = re.sub(r'\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def clean_epub_text(text):
    """Remove EPUB header/footer artifacts."""
    text = re.sub(r'Options,?\s*Futures,?\s*and\s*Other\s*Derivatives\s*\(11th Edition\)\s*-\s*p\d+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def normalize(text):
    """Normalize for comparison."""
    text = unicodedata.normalize('NFKD', text)
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def similarity(a, b):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def check_figure_refs(pdf_text, epub_html):
    """Check if figures referenced in PDF have corresponding images in EPUB."""
    pdf_figs = set(re.findall(r'[Ff]igure\s+(\d+(?:\.\d+)?)', pdf_text))
    epub_imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', epub_html)
    epub_fig_refs = set(re.findall(r'[Ff]igure\s+(\d+(?:\.\d+)?)', epub_html))
    return pdf_figs, epub_imgs, epub_fig_refs


def check_table_content(pdf_text, epub_html):
    """Check if table content in PDF is present in EPUB."""
    pdf_tables = re.findall(r'[Tt]able\s+(\d+(?:\.\d+)?)', pdf_text)
    epub_tables = re.findall(r'<table', epub_html)
    epub_table_refs = re.findall(r'[Tt]able\s+(\d+(?:\.\d+)?)', epub_html)
    return pdf_tables, len(epub_tables), epub_table_refs


def categorize_page(page_num, pdf_text_raw, epub_text_raw, epub_html, sim_clean):
    """Categorize a page and identify specific issues."""
    issues = []
    category = 'content'  # default

    # Determine page type
    if page_num <= 3:
        category = 'front_matter'
    elif page_num <= 25:
        category = 'toc_preface'
    elif pdf_text_raw.strip() == '' and epub_text_raw.strip() == '':
        category = 'blank'
    elif re.search(r'^\s*(chapter|appendix)\s+\d+', pdf_text_raw, re.IGNORECASE | re.MULTILINE):
        category = 'chapter_start'

    # Check for genuine content issues
    if sim_clean >= 0.85:
        return category, 'GOOD', issues

    # For TOC pages, different extraction is expected
    if category == 'toc_preface' and sim_clean < 0.5:
        # TOC pages extract very differently - check if key headings are present
        issues.append(f'TOC/preface page - similarity {sim_clean:.2f} (expected for structured content)')
        return category, 'REVIEW', issues

    # For content pages with low similarity
    if sim_clean < 0.3:
        # Check if this might be a figure-heavy page
        if re.findall(r'<img', epub_html):
            issues.append(f'Low text sim ({sim_clean:.2f}) but has images - likely figure page')
            return category, 'REVIEW', issues

        # Check if page has mainly equation content
        if re.findall(r'class="equation"|class="eq-inline"', epub_html):
            issues.append(f'Low text sim ({sim_clean:.2f}) but has equations - check equation rendering')
            return category, 'REVIEW', issues

        # Check if page has table content
        if re.findall(r'<table', epub_html):
            issues.append(f'Low text sim ({sim_clean:.2f}) but has tables - check table content')
            return category, 'REVIEW', issues

        issues.append(f'Very low text similarity ({sim_clean:.2f}) - needs manual review')
        return category, 'ISSUE', issues

    elif sim_clean < 0.6:
        # Check what's different
        pdf_words = set(normalize(clean_pdf_text(pdf_text_raw)).split())
        epub_words = set(normalize(clean_epub_text(epub_text_raw)).split())
        missing = pdf_words - epub_words
        # Filter out short words and numbers
        missing_sig = {w for w in missing if len(w) > 3 and not w.isdigit()}
        if len(missing_sig) > 10:
            issues.append(f'Moderate sim ({sim_clean:.2f}), {len(missing_sig)} significant words missing from EPUB')
            return category, 'ISSUE', issues
        else:
            issues.append(f'Moderate sim ({sim_clean:.2f}), minor word differences')
            return category, 'REVIEW', issues

    elif sim_clean < 0.85:
        issues.append(f'Slightly low similarity ({sim_clean:.2f}) - minor differences')
        return category, 'REVIEW', issues

    return category, 'GOOD', issues


def main():
    print("Loading PDF...")
    reader = PyPDF2.PdfReader(PDF_PATH)

    epub_files = sorted(
        Path(EPUB_DIR).glob('full_book_v7_p*.xhtml'),
        key=lambda f: int(f.stem.split('_p')[1])
    )

    results = []
    stats = {'GOOD': 0, 'REVIEW': 0, 'ISSUE': 0}

    for i, epub_file in enumerate(epub_files):
        page_num = int(epub_file.stem.split('_p')[1])
        pdf_idx = page_num - 1

        pdf_text_raw = reader.pages[pdf_idx].extract_text() or ''

        with open(epub_file, 'r', encoding='utf-8') as f:
            epub_html = f.read()

        extractor = HTMLTextExtractor()
        extractor.feed(epub_html)
        epub_text_raw = extractor.get_text()

        # Clean both texts
        pdf_clean = normalize(clean_pdf_text(pdf_text_raw))
        epub_clean = normalize(clean_epub_text(epub_text_raw))

        sim_clean = similarity(pdf_clean, epub_clean)

        category, status, issues = categorize_page(
            page_num, pdf_text_raw, epub_text_raw, epub_html, sim_clean
        )

        # Also check figures
        pdf_figs, epub_imgs, epub_fig_refs = check_figure_refs(pdf_text_raw, epub_html)
        if pdf_figs and not epub_imgs and not epub_fig_refs:
            issues.append(f'PDF mentions figures {pdf_figs} but EPUB has no images')

        # Check tables
        pdf_table_refs, epub_table_count, epub_table_refs = check_table_content(pdf_text_raw, epub_html)

        stats[status] += 1

        results.append({
            'page': page_num,
            'category': category,
            'status': status,
            'similarity': round(sim_clean, 4),
            'issues': issues,
            'has_images': bool(epub_imgs),
            'has_equations': bool(re.findall(r'class="equation"|class="eq-inline"', epub_html)),
            'has_tables': epub_table_count > 0,
            'pdf_preview': pdf_text_raw[:150].replace('\n', ' '),
            'epub_preview': epub_text_raw[:150],
        })

        if (i + 1) % 100 == 0:
            print(f"  Processed {i+1}/{len(epub_files)} pages...")

    # Save results
    with open('validation_deep_report.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)

    # Print summary
    print(f"\n{'='*70}")
    print(f"DEEP VALIDATION SUMMARY (after filtering PDF artifacts)")
    print(f"{'='*70}")
    print(f"Total pages:  {len(results)}")
    print(f"GOOD:         {stats['GOOD']}")
    print(f"REVIEW:       {stats['REVIEW']} (minor/expected differences)")
    print(f"ISSUE:        {stats['ISSUE']} (needs fix)")

    # Similarity distribution
    sims = [r['similarity'] for r in results]
    print(f"\nCleaned similarity distribution:")
    for threshold in [0.95, 0.9, 0.85, 0.8, 0.6, 0.3, 0.0]:
        count = sum(1 for s in sims if s >= threshold)
        print(f"  >= {threshold:.2f}: {count} pages ({count*100/len(results):.1f}%)")

    # Show ISSUE pages
    issue_pages = [r for r in results if r['status'] == 'ISSUE']
    print(f"\n{'='*70}")
    print(f"PAGES REQUIRING FIXES ({len(issue_pages)} pages):")
    print(f"{'='*70}")
    for r in issue_pages:
        print(f"\nPage {r['page']} [{r['category']}] (sim={r['similarity']:.2f}):")
        for iss in r['issues']:
            print(f"  - {iss}")
        print(f"  PDF: {r['pdf_preview'][:100]}...")
        print(f"  EPUB: {r['epub_preview'][:100]}...")

    # Show REVIEW pages grouped by category
    review_pages = [r for r in results if r['status'] == 'REVIEW']
    print(f"\n{'='*70}")
    print(f"PAGES TO REVIEW ({len(review_pages)} pages):")
    print(f"{'='*70}")
    categories = {}
    for r in review_pages:
        categories.setdefault(r['category'], []).append(r)
    for cat, pages in sorted(categories.items()):
        print(f"\n  [{cat}] ({len(pages)} pages):")
        for r in pages[:5]:
            print(f"    Page {r['page']} (sim={r['similarity']:.2f}): {'; '.join(r['issues'][:1])}")
        if len(pages) > 5:
            print(f"    ... and {len(pages)-5} more")

    return results


if __name__ == '__main__':
    main()
