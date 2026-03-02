"""
Validate EPUB conversion against source PDF.
Compares text content page-by-page, checks figures, equations, and tables.
"""
import sys
import os
import re
import json
import unicodedata
from pathlib import Path
from difflib import SequenceMatcher
from html.parser import HTMLParser

import PyPDF2

# --- Config ---
BASE_DIR = Path(__file__).parent.parent.resolve()
PDF_PATH = str(BASE_DIR / "options_futures_and_other_derivatives_11th.pdf")
EPUB_DIR = str(BASE_DIR / "output" / "full_book_extracted" / "EPUB")
REPORT_PATH = str(BASE_DIR / "validation_report.json")

# --- HTML text extractor ---
class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self._skip = True
        # Add space for block elements
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


def extract_epub_text(xhtml_path):
    """Extract plain text from an XHTML file."""
    with open(xhtml_path, 'r', encoding='utf-8') as f:
        html = f.read()
    extractor = HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def extract_epub_features(xhtml_path):
    """Extract structural features: images, equations, tables."""
    with open(xhtml_path, 'r', encoding='utf-8') as f:
        html = f.read()

    images = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html)
    equations = re.findall(r'class="equation"', html)
    eq_inline = re.findall(r'class="eq-inline"', html)
    tables = re.findall(r'<table', html)
    headings = re.findall(r'<h[1-6][^>]*>(.*?)</h[1-6]>', html, re.DOTALL)

    return {
        'images': images,
        'num_equations': len(equations) + len(eq_inline),
        'num_tables': len(tables),
        'headings': [re.sub(r'<[^>]+>', '', h).strip() for h in headings],
    }


def normalize_text(text):
    """Normalize text for comparison: lowercase, remove extra whitespace, normalize unicode."""
    text = unicodedata.normalize('NFKD', text)
    # Remove common PDF artifacts
    text = re.sub(r'A\d+_HULL\d+_\d+_GE_\w+\.indd\s+\d+\s+\d+/\d+/\d+\s+\d+:\d+', '', text)
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)  # Remove punctuation for fuzzy match
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def similarity(a, b):
    """Compute similarity ratio between two strings."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def find_missing_words(pdf_text, epub_text):
    """Find significant words in PDF that are missing from EPUB."""
    pdf_words = set(pdf_text.split())
    epub_words = set(epub_text.split())
    # Filter out very short words and numbers
    missing = {w for w in (pdf_words - epub_words) if len(w) > 3}
    extra = {w for w in (epub_words - pdf_words) if len(w) > 3}
    return missing, extra


def main():
    print("Loading PDF...")
    reader = PyPDF2.PdfReader(PDF_PATH)
    num_pdf_pages = len(reader.pages)
    print(f"PDF pages: {num_pdf_pages}")

    epub_files = sorted(
        Path(EPUB_DIR).glob('full_book_v7_p*.xhtml'),
        key=lambda f: int(f.stem.split('_p')[1])
    )
    print(f"EPUB pages: {len(epub_files)}")

    results = []
    issues_count = 0

    for i, epub_file in enumerate(epub_files):
        page_num = int(epub_file.stem.split('_p')[1])
        pdf_idx = page_num - 1  # 0-based index

        if pdf_idx >= num_pdf_pages:
            results.append({
                'page': page_num,
                'status': 'ERROR',
                'issue': f'EPUB page {page_num} has no corresponding PDF page',
                'similarity': 0.0,
            })
            issues_count += 1
            continue

        # Extract texts
        pdf_text_raw = reader.pages[pdf_idx].extract_text() or ''
        epub_text_raw = extract_epub_text(str(epub_file))

        # Normalize for comparison
        pdf_norm = normalize_text(pdf_text_raw)
        epub_norm = normalize_text(epub_text_raw)

        # Compute similarity
        sim = similarity(pdf_norm, epub_norm)

        # Extract features
        features = extract_epub_features(str(epub_file))

        # Determine status
        issues = []

        if sim < 0.3:
            issues.append(f'Very low text similarity ({sim:.2f})')
        elif sim < 0.6:
            issues.append(f'Low text similarity ({sim:.2f})')
        elif sim < 0.8:
            issues.append(f'Moderate text similarity ({sim:.2f}) - check for missing content')

        # Check for missing significant words
        if sim < 0.95:
            missing, extra = find_missing_words(pdf_norm, epub_norm)
            if len(missing) > 5:
                sample = list(missing)[:10]
                issues.append(f'Missing words from PDF: {sample}')
            if len(extra) > 5:
                sample = list(extra)[:10]
                issues.append(f'Extra words in EPUB: {sample}')

        # Check if PDF has figure references but EPUB has no images
        if re.search(r'figure\s+\d+', pdf_text_raw, re.IGNORECASE) and not features['images']:
            # Check if there's an image on a nearby EPUB page (figures sometimes shift)
            issues.append('PDF references figures but EPUB page has no images')

        status = 'GOOD' if not issues else 'ISSUE'
        if issues:
            issues_count += 1

        result = {
            'page': page_num,
            'status': status,
            'similarity': round(sim, 4),
            'epub_file': epub_file.name,
            'features': features,
            'issues': issues,
            'pdf_text_preview': pdf_text_raw[:200].replace('\n', ' '),
            'epub_text_preview': epub_text_raw[:200],
        }
        results.append(result)

        if (i + 1) % 100 == 0:
            print(f"  Processed {i+1}/{len(epub_files)} pages...")

    # Save full report
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)

    # Print summary
    good = sum(1 for r in results if r['status'] == 'GOOD')
    issue = sum(1 for r in results if r['status'] == 'ISSUE')
    error = sum(1 for r in results if r['status'] == 'ERROR')

    print(f"\n{'='*60}")
    print(f"VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total pages:  {len(results)}")
    print(f"GOOD:         {good}")
    print(f"ISSUES:       {issue}")
    print(f"ERRORS:       {error}")

    # Similarity distribution
    sims = [r['similarity'] for r in results]
    print(f"\nSimilarity distribution:")
    for threshold in [0.95, 0.9, 0.8, 0.6, 0.3, 0.0]:
        count = sum(1 for s in sims if s >= threshold)
        print(f"  >= {threshold:.2f}: {count} pages")

    # Show pages with issues
    issue_pages = [r for r in results if r['status'] != 'GOOD']
    if issue_pages:
        print(f"\n{'='*60}")
        print(f"PAGES WITH ISSUES (showing first 50):")
        print(f"{'='*60}")
        for r in issue_pages[:50]:
            print(f"\nPage {r['page']} (sim={r['similarity']:.2f}):")
            for iss in r['issues']:
                print(f"  - {iss}")

    print(f"\nFull report saved to: {REPORT_PATH}")
    return results


if __name__ == '__main__':
    main()
