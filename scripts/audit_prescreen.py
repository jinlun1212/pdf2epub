"""
Pre-screen all EPUB pages to identify potential issues.

Checks:
1. EPUB render height (too short = truncated, too tall = overflow)
2. EPUB render content density (too low = mostly blank)
3. XHTML content analysis (encoding artifacts, missing structure)
4. Known problem patterns (garbled text, broken equations)

Output: output/audit_prescreen.json with page classifications
"""
import sys
import io
import json
import re
from pathlib import Path
from PIL import Image

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.parent.resolve()
EPUB_DIR = BASE_DIR / "output" / "full_book_extracted" / "EPUB"
PDF_RENDER_DIR = BASE_DIR / "output" / "pdf_renders"
EPUB_RENDER_DIR = BASE_DIR / "output" / "epub_renders"
OUTPUT_PATH = BASE_DIR / "output" / "audit_prescreen.json"

# Known encoding artifacts from PearsonMATHPRO18 font
ENCODING_PATTERNS = [
    (r'√', 'sqrt_for_sigma'),      # √ should be Σ
    (r'∫', 'integral_artifact'),     # ∫ misused as ... or ≥
    (r'[^\x00-\x7F\u00A0-\u024F\u0370-\u03FF\u2000-\u22FF\u2300-\u23FF\uFB00-\uFB06]',
     'unusual_unicode'),
]

# Content issues
CONTENT_PATTERNS = [
    (r'<body>\s*</body>', 'empty_body'),
    (r'<body>\s*<p>\s*</p>\s*</body>', 'single_empty_para'),
    (r'class="fs-small"', 'fs_small_remnant'),    # Should have been converted
]


def analyze_render(page_num):
    """Analyze EPUB and PDF renders for a page."""
    epub_path = EPUB_RENDER_DIR / f"page_{page_num:04d}.png"
    pdf_path = PDF_RENDER_DIR / f"page_{page_num:04d}.png"

    result = {}

    if epub_path.exists():
        img = Image.open(epub_path)
        w, h = img.size
        result['epub_width'] = w
        result['epub_height'] = h

        # Check content density (% of non-white pixels)
        gray = img.convert('L')
        pixels = list(gray.getdata())
        dark_pixels = sum(1 for p in pixels if p < 200)
        result['epub_density'] = round(dark_pixels / len(pixels) * 100, 2)
        img.close()
    else:
        result['epub_render_missing'] = True

    if pdf_path.exists():
        img = Image.open(pdf_path)
        w, h = img.size
        result['pdf_width'] = w
        result['pdf_height'] = h

        gray = img.convert('L')
        pixels = list(gray.getdata())
        dark_pixels = sum(1 for p in pixels if p < 200)
        result['pdf_density'] = round(dark_pixels / len(pixels) * 100, 2)
        img.close()
    else:
        result['pdf_render_missing'] = True

    return result


def analyze_xhtml(page_num):
    """Analyze XHTML content for issues."""
    path = EPUB_DIR / f"full_book_v7_p{page_num}.xhtml"
    if not path.exists():
        return {'xhtml_missing': True}

    html = path.read_text(encoding='utf-8')
    result = {
        'xhtml_size': len(html),
        'issues': []
    }

    # Check for encoding artifacts
    for pattern, name in ENCODING_PATTERNS:
        matches = re.findall(pattern, html)
        if matches:
            result['issues'].append(f"{name}:{len(matches)}")

    # Check for content issues
    for pattern, name in CONTENT_PATTERNS:
        if re.search(pattern, html):
            result['issues'].append(name)

    # Check for very short content (possibly truncated)
    body_match = re.search(r'<body>(.*?)</body>', html, re.DOTALL)
    if body_match:
        body_text = re.sub(r'<[^>]+>', '', body_match.group(1)).strip()
        result['text_length'] = len(body_text)
        if len(body_text) < 50:
            result['issues'].append('very_short_content')

    # Count structural elements
    result['equations'] = len(re.findall(r'class="equation"', html))
    result['tables'] = len(re.findall(r'<table', html))
    result['images'] = len(re.findall(r'<img', html))
    result['headings'] = len(re.findall(r'<h[1-6]', html))

    return result


def classify_page(page_num, render_info, xhtml_info):
    """Classify a page as needing visual review or likely good."""
    flags = []

    # Render-based checks
    if render_info.get('epub_render_missing'):
        flags.append('epub_render_missing')
    elif render_info.get('epub_density', 100) < 1.0:
        flags.append('epub_nearly_blank')
    elif render_info.get('epub_height', 0) < 200:
        flags.append('epub_very_short')

    # Content density comparison
    epub_density = render_info.get('epub_density', 0)
    pdf_density = render_info.get('pdf_density', 0)
    if pdf_density > 0 and epub_density > 0:
        ratio = epub_density / pdf_density
        if ratio < 0.3:
            flags.append('density_much_lower')
        elif ratio > 3.0:
            flags.append('density_much_higher')

    # XHTML-based checks
    if xhtml_info.get('xhtml_missing'):
        flags.append('xhtml_missing')
    issues = xhtml_info.get('issues', [])
    if issues:
        flags.extend(issues)

    if xhtml_info.get('text_length', 100) < 50:
        if not any(f in flags for f in ['very_short_content']):
            flags.append('very_short_content')

    # Complex pages are more likely to have issues
    has_complex = (xhtml_info.get('equations', 0) > 0 or
                   xhtml_info.get('tables', 0) > 0)

    if flags:
        return 'needs_review', flags
    elif has_complex:
        return 'review_complex', ['has_equations_or_tables']
    else:
        return 'likely_good', []


def main():
    print("Pre-screening all 880 EPUB pages...")

    results = {}
    needs_review = []
    review_complex = []
    likely_good = []

    for pn in range(1, 881):
        render_info = analyze_render(pn)
        xhtml_info = analyze_xhtml(pn)
        classification, flags = classify_page(pn, render_info, xhtml_info)

        results[str(pn)] = {
            'classification': classification,
            'flags': flags,
            'epub_density': render_info.get('epub_density'),
            'pdf_density': render_info.get('pdf_density'),
            'epub_height': render_info.get('epub_height'),
            'text_length': xhtml_info.get('text_length'),
            'equations': xhtml_info.get('equations', 0),
            'tables': xhtml_info.get('tables', 0),
            'images': xhtml_info.get('images', 0),
            'issues': xhtml_info.get('issues', []),
        }

        if classification == 'needs_review':
            needs_review.append(pn)
        elif classification == 'review_complex':
            review_complex.append(pn)
        else:
            likely_good.append(pn)

        if pn % 100 == 0:
            print(f"  Processed {pn} pages...")

    summary = {
        'total': 880,
        'needs_review': len(needs_review),
        'review_complex': len(review_complex),
        'likely_good': len(likely_good),
        'needs_review_pages': needs_review,
        'review_complex_pages': review_complex,
        'pages': results,
    }

    OUTPUT_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8'
    )

    print(f"\n{'='*50}")
    print(f"PRE-SCREEN SUMMARY")
    print(f"{'='*50}")
    print(f"Total pages:       {880}")
    print(f"Needs review:      {len(needs_review)}")
    print(f"Complex (eq/tbl):  {len(review_complex)}")
    print(f"Likely good:       {len(likely_good)}")

    if needs_review:
        print(f"\nPages needing review:")
        for pn in needs_review:
            flags = results[str(pn)]['flags']
            print(f"  Page {pn}: {', '.join(flags)}")

    print(f"\nResults saved to {OUTPUT_PATH}")


if __name__ == '__main__':
    main()
