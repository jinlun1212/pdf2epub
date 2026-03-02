#!/usr/bin/env python3
"""
First-20-page Pages validation pipeline.

Steps:
1. Render PDF pages 1-20 to reference PNGs.
2. Extract text page-by-page and build one DOCX per page.
3. Open each DOCX in Pages, take UI screenshot, export to PDF, close.
4. Render exported PDF first page to PNG.
5. Compute visual diff metric against reference PNG.
6. Emit summary report.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List

import fitz


ROOT = Path("/Users/lunjin/Desktop/pdf2epub")
PDF_PATH = ROOT / "options_futures_and_other_derivatives_11th.pdf"
OUT_BASE = ROOT / "output"

REF_DIR: Path
DOCX_DIR: Path
UI_DIR: Path
PAGES_PDF_DIR: Path
PAGES_PNG_DIR: Path
REPORT: Path
SUMMARY_MD: Path


def run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def safe_text(s: str) -> str:
    s = s.replace("\x0c", " ")
    s = s.replace("\ufffd", " ")
    s = re.sub(r"\s+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = s.strip()
    return s


def prep_dirs(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    for d in [REF_DIR, DOCX_DIR, UI_DIR, PAGES_PDF_DIR, PAGES_PNG_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def render_pdf_refs(doc: fitz.Document, start: int = 1, end: int = 20, dpi: int = 170) -> None:
    m = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    for p in range(start, end + 1):
        pix = doc[p - 1].get_pixmap(matrix=m, alpha=False)
        pix.save((REF_DIR / f"page-{p:04d}.png").as_posix())


def build_docx_per_page_text(doc: fitz.Document, start: int = 1, end: int = 20) -> None:
    for p in range(start, end + 1):
        text = safe_text(doc[p - 1].get_text("text"))
        md = DOCX_DIR / f"page-{p:04d}.md"
        docx = DOCX_DIR / f"page-{p:04d}.docx"
        md.write_text(f"# PDF Page {p}\n\n{text}\n", encoding="utf-8")
        run(["pandoc", md.as_posix(), "-o", docx.as_posix()])


def build_docx_per_page_image(start: int = 1, end: int = 20) -> None:
    for p in range(start, end + 1):
        md = DOCX_DIR / f"page-{p:04d}.md"
        docx = DOCX_DIR / f"page-{p:04d}.docx"
        ref = REF_DIR / f"page-{p:04d}.png"
        md.write_text(f"![PDF Page {p}]({ref.as_posix()})\n", encoding="utf-8")
        run(["pandoc", md.as_posix(), "-o", docx.as_posix()])


def pages_open_export_screenshot(docx: Path, ui_png: Path, out_pdf: Path) -> None:
    script = f'''
tell application "Pages"
    activate
    open POSIX file "{docx.as_posix()}"
    delay 1.2
end tell
'''
    run(["osascript", "-e", script])

    # full-screen capture includes Pages UI state for validation trail
    run(["screencapture", "-x", ui_png.as_posix()])

    script2 = f'''
tell application "Pages"
    export front document to POSIX file "{out_pdf.as_posix()}" as PDF
    close front document saving no
end tell
'''
    run(["osascript", "-e", script2])


def render_export_pdf_first_page(in_pdf: Path, out_png: Path, dpi: int = 170) -> None:
    d = fitz.open(in_pdf.as_posix())
    try:
        pix = d[0].get_pixmap(matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0), alpha=False)
        pix.save(out_png.as_posix())
    finally:
        d.close()


def compare_rmse(ref_png: Path, pages_png: Path) -> str:
    # Returns ImageMagick compare RMSE summary token like "0.51234 (0.00782)"
    proc = subprocess.run(
        ["/opt/local/bin/compare", "-metric", "RMSE", ref_png.as_posix(), pages_png.as_posix(), "null:"],
        text=True,
        capture_output=True,
    )
    # compare writes metric to stderr; non-zero exit is normal for difference
    metric = (proc.stderr or "").strip()
    return metric if metric else "N/A"


def parse_rmse(metric: str) -> float:
    # format usually: "12345.6 (0.1883)"
    m = re.search(r"\(([\d.]+)\)", metric)
    if not m:
        return 999.0
    return float(m.group(1))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Pages first20 pipeline")
    parser.add_argument("--mode", choices=["text", "image"], default="text")
    args = parser.parse_args()

    out = OUT_BASE / f"first20_pages_pipeline_{args.mode}"

    global REF_DIR, DOCX_DIR, UI_DIR, PAGES_PDF_DIR, PAGES_PNG_DIR, REPORT, SUMMARY_MD
    REF_DIR = out / "pdf_ref_png"
    DOCX_DIR = out / "pages_docx"
    UI_DIR = out / "pages_ui_screens"
    PAGES_PDF_DIR = out / "pages_export_pdf"
    PAGES_PNG_DIR = out / "pages_export_png"
    REPORT = out / "report.json"
    SUMMARY_MD = out / "summary.md"

    prep_dirs(out)
    doc = fitz.open(PDF_PATH.as_posix())
    try:
        render_pdf_refs(doc, 1, 20, 170)
        if args.mode == "text":
            build_docx_per_page_text(doc, 1, 20)
        else:
            build_docx_per_page_image(1, 20)
    finally:
        doc.close()

    rows: List[Dict[str, object]] = []
    for p in range(1, 21):
        stem = f"page-{p:04d}"
        docx = DOCX_DIR / f"{stem}.docx"
        ui = UI_DIR / f"{stem}.png"
        exp_pdf = PAGES_PDF_DIR / f"{stem}.pdf"
        exp_png = PAGES_PNG_DIR / f"{stem}.png"
        ref_png = REF_DIR / f"{stem}.png"

        pages_open_export_screenshot(docx, ui, exp_pdf)
        render_export_pdf_first_page(exp_pdf, exp_png, 170)
        metric = compare_rmse(ref_png, exp_png)
        rows.append(
            {
                "page": p,
                "docx": docx.as_posix(),
                "ui_screenshot": ui.as_posix(),
                "pages_export_pdf": exp_pdf.as_posix(),
                "pages_export_png": exp_png.as_posix(),
                "pdf_ref_png": ref_png.as_posix(),
                "rmse_metric": metric,
                "rmse_norm": parse_rmse(metric),
            }
        )

    rows_sorted = sorted(rows, key=lambda r: float(r["rmse_norm"]), reverse=True)
    avg = sum(float(r["rmse_norm"]) for r in rows) / len(rows)
    report = {
        "pdf": PDF_PATH.as_posix(),
        "mode": args.mode,
        "pages_processed": 20,
        "avg_rmse_norm": avg,
        "worst_pages": rows_sorted[:5],
        "rows": rows,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# First 20 Pages Pipeline Summary",
        "",
        f"- PDF: `{PDF_PATH}`",
        f"- Mode: `{args.mode}`",
        f"- Pages processed: `20`",
        f"- Average normalized RMSE (lower is better): `{avg:.4f}`",
        "",
        "## Worst 5 Pages",
        "",
    ]
    for w in rows_sorted[:5]:
        lines.append(
            f"- Page {w['page']}: RMSE `{w['rmse_metric']}` | UI `{w['ui_screenshot']}`"
        )
    lines.append("")
    lines.append("## Output Folders")
    lines.append(f"- PDF refs: `{REF_DIR}`")
    lines.append(f"- DOCX input to Pages: `{DOCX_DIR}`")
    lines.append(f"- Pages UI screenshots: `{UI_DIR}`")
    lines.append(f"- Pages exported PDFs: `{PAGES_PDF_DIR}`")
    lines.append(f"- Pages exported PNGs: `{PAGES_PNG_DIR}`")
    lines.append(f"- Full JSON report: `{REPORT}`")
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"Done. Summary: {SUMMARY_MD}")
    print(f"Report: {REPORT}")


if __name__ == "__main__":
    main()
