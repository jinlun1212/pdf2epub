"""
Visual validation: render PDF pages and EPUB XHTML pages to images,
then compare them pixel-by-pixel.

Uses PyMuPDF for PDF rendering and Playwright (with system Chrome) for XHTML rendering.
"""
import sys
import os
import io
import json
import time
from pathlib import Path

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import fitz  # PyMuPDF
from PIL import Image
import numpy as np
from playwright.sync_api import sync_playwright

# --- Configuration ---
BASE_DIR = Path(__file__).parent.resolve()
PDF_PATH = BASE_DIR / "options_futures_and_other_derivatives_11th.pdf"
EPUB_DIR = BASE_DIR / "output" / "full_book_extracted" / "EPUB"
CSS_PATH = EPUB_DIR / "style.css"
OUT_DIR = BASE_DIR / "output" / "validation_renders"
PDF_RENDER_DIR = OUT_DIR / "pdf"
EPUB_RENDER_DIR = OUT_DIR / "epub"
DIFF_DIR = OUT_DIR / "diffs"
REPORT_PATH = BASE_DIR / "validation_visual_report.json"

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DPI = 150
VIEWPORT_W = 850
VIEWPORT_H = 1200

# Thresholds
THRESHOLD_GOOD = 0.92
THRESHOLD_REVIEW = 0.80


def setup_dirs():
    for d in [PDF_RENDER_DIR, EPUB_RENDER_DIR, DIFF_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def render_all_pdf_pages(total):
    """Render PDF pages using PyMuPDF (very fast)."""
    doc = fitz.open(str(PDF_PATH))
    count = min(total, len(doc))
    rendered = {}
    for i in range(count):
        pn = i + 1
        out = PDF_RENDER_DIR / f"pdf_p{pn}.png"
        if not out.exists():
            pix = doc[i].get_pixmap(dpi=DPI)
            pix.save(str(out))
        rendered[pn] = out
        if pn % 100 == 0:
            print(f"  PDF: {pn}/{count}")
    doc.close()
    return rendered


def render_all_epub_pages(epub_files):
    """Render all EPUB XHTML pages using Playwright + system Chrome (single browser session)."""
    rendered = {}
    failed = []

    css_abs = CSS_PATH.resolve().as_posix()
    css_link = f'<link rel="stylesheet" type="text/css" href="file:///{css_abs}"/>'

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
        )
        page = browser.new_page(viewport={'width': VIEWPORT_W, 'height': VIEWPORT_H})

        for i, epub_file in enumerate(epub_files):
            pn = int(epub_file.stem.split('_p')[1])
            out_path = EPUB_RENDER_DIR / f"epub_p{pn}.png"

            if out_path.exists():
                rendered[pn] = out_path
                continue

            tmp_path = epub_file.parent / f"_render_{epub_file.name}"
            try:
                # Inject CSS
                with open(epub_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                content = content.replace('</head>', f'{css_link}\n</head>')
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                url = f"file:///{tmp_path.resolve().as_posix()}"
                page.goto(url, wait_until='load', timeout=15000)
                page.screenshot(path=str(out_path), full_page=True)
                rendered[pn] = out_path

            except Exception as e:
                failed.append((pn, str(e)[:100]))
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()

            if (i + 1) % 50 == 0:
                print(f"  EPUB: {i+1}/{len(epub_files)} "
                      f"[{len(rendered)} ok, {len(failed)} failed]")

        browser.close()

    return rendered, failed


def compare_images(img_path1, img_path2, page_num):
    """Compare two rendered images pixel-by-pixel."""
    img1 = Image.open(img_path1).convert('L')
    img2 = Image.open(img_path2).convert('L')

    tw = max(img1.width, img2.width)
    th = max(img1.height, img2.height)

    def pad(img, w, h):
        p = Image.new('L', (w, h), 255)
        p.paste(img, (0, 0))
        return p

    img1 = pad(img1, tw, th)
    img2 = pad(img2, tw, th)

    arr1 = np.array(img1, dtype=np.float32) / 255.0
    arr2 = np.array(img2, dtype=np.float32) / 255.0

    diff = np.abs(arr1 - arr2)
    mean_diff = float(np.mean(diff))
    similarity = 1.0 - mean_diff
    sig_pixels = float(np.mean(diff > 0.15)) * 100

    # Save side-by-side diff for non-good pages
    if similarity < THRESHOLD_GOOD:
        diff_uint8 = (diff * 255).astype(np.uint8)
        diff_img = Image.fromarray(diff_uint8, mode='L')
        diff_img = Image.eval(diff_img, lambda x: 255 - x)

        gap = 10
        combined = Image.new('L', (tw * 3 + gap * 2, th), 255)
        combined.paste(img1, (0, 0))
        combined.paste(img2, (tw + gap, 0))
        combined.paste(diff_img, (tw * 2 + gap * 2, 0))
        combined.save(str(DIFF_DIR / f"diff_p{page_num}.png"))

    return {
        'similarity': round(similarity, 4),
        'mean_diff': round(mean_diff, 4),
        'significant_pixels_pct': round(sig_pixels, 2),
    }


def classify(sim):
    if sim >= THRESHOLD_GOOD:
        return 'GOOD'
    elif sim >= THRESHOLD_REVIEW:
        return 'REVIEW'
    return 'ISSUE'


def main():
    setup_dirs()

    epub_files = sorted(
        EPUB_DIR.glob('full_book_v7_p*.xhtml'),
        key=lambda f: int(f.stem.split('_p')[1])
    )
    total = len(epub_files)
    print(f"Total pages: {total}")

    # Phase 1: PDF rendering
    print(f"\n--- Phase 1: Rendering PDF pages ---")
    t0 = time.time()
    pdf_renders = render_all_pdf_pages(total)
    print(f"  {len(pdf_renders)} pages in {time.time()-t0:.1f}s")

    # Phase 2: EPUB rendering
    print(f"\n--- Phase 2: Rendering EPUB pages ---")
    t0 = time.time()
    epub_renders, epub_failed = render_all_epub_pages(epub_files)
    print(f"  {len(epub_renders)} pages in {time.time()-t0:.1f}s")
    if epub_failed:
        print(f"  {len(epub_failed)} failed: {epub_failed[:10]}")

    # Phase 3: Comparison
    print(f"\n--- Phase 3: Comparing ---")
    results = []
    for i, ef in enumerate(epub_files):
        pn = int(ef.stem.split('_p')[1])

        if pn not in pdf_renders or pn not in epub_renders:
            results.append({
                'page': pn, 'status': 'ERROR',
                'similarity': 0.0, 'mean_diff': 1.0,
                'significant_pixels_pct': 100.0, 'epub_file': ef.name,
            })
            continue

        comp = compare_images(str(pdf_renders[pn]), str(epub_renders[pn]), pn)
        status = classify(comp['similarity'])
        results.append({'page': pn, 'status': status, 'epub_file': ef.name, **comp})

        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{total}")

    # Save report
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    # Summary
    good = sum(1 for r in results if r['status'] == 'GOOD')
    review = sum(1 for r in results if r['status'] == 'REVIEW')
    issue = sum(1 for r in results if r['status'] == 'ISSUE')
    error = sum(1 for r in results if r['status'] == 'ERROR')
    sims = [r['similarity'] for r in results if r['status'] != 'ERROR']

    print(f"\n{'='*60}")
    print(f"VISUAL VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total:   {len(results)}")
    print(f"GOOD:    {good} (>= {THRESHOLD_GOOD})")
    print(f"REVIEW:  {review} ({THRESHOLD_REVIEW}-{THRESHOLD_GOOD})")
    print(f"ISSUE:   {issue} (< {THRESHOLD_REVIEW})")
    print(f"ERROR:   {error}")

    if sims:
        print(f"\nSimilarity: mean={np.mean(sims):.4f} "
              f"median={np.median(sims):.4f} "
              f"min={np.min(sims):.4f} max={np.max(sims):.4f}")

        print(f"\nDistribution:")
        for t in [0.95, 0.92, 0.90, 0.85, 0.80, 0.70, 0.50]:
            cnt = sum(1 for s in sims if s >= t)
            print(f"  >= {t:.2f}: {cnt:>4} ({cnt*100/len(sims):5.1f}%)")

    non_good = sorted([r for r in results if r['status'] != 'GOOD'],
                       key=lambda r: r['similarity'])
    if non_good:
        print(f"\n{'='*60}")
        print(f"NON-GOOD PAGES (worst 50):")
        print(f"{'='*60}")
        print(f"{'Page':>6} {'Status':>7} {'Sim':>7} {'Diff%':>7} {'SigPx%':>7}")
        for r in non_good[:50]:
            print(f"{r['page']:>6} {r['status']:>7} {r['similarity']:>7.4f} "
                  f"{r['mean_diff']*100:>6.2f}% {r['significant_pixels_pct']:>6.2f}%")

    print(f"\nDiffs: {DIFF_DIR}")
    print(f"Report: {REPORT_PATH}")


if __name__ == '__main__':
    main()
