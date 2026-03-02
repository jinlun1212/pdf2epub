#!/usr/bin/env python3
"""
Create a fixed-layout EPUB from a PDF page range.

Each PDF page is rendered to an image and placed on one pre-paginated EPUB page.
This maximizes visual fidelity to the source PDF.
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import List, Tuple

import fitz  # PyMuPDF
from ebooklib import epub


def render_pdf_pages(
    pdf_path: Path,
    start_page: int,
    end_page: int,
    dpi: int,
    out_dir: Path,
) -> List[Tuple[int, str, int, int]]:
    doc = fitz.open(pdf_path.as_posix())
    try:
        if start_page < 1 or end_page < start_page or end_page > len(doc):
            raise ValueError(f"Invalid page range {start_page}-{end_page} for PDF of {len(doc)} pages.")

        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        rendered: List[Tuple[int, str, int, int]] = []
        for page_num in range(start_page, end_page + 1):
            page = doc[page_num - 1]
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            name = f"page-{page_num:04d}.jpg"
            path = out_dir / name
            pix.save(path.as_posix(), jpg_quality=88)
            rendered.append((page_num, name, pix.width, pix.height))
        return rendered
    finally:
        doc.close()


def build_fixed_epub(
    rendered_pages: List[Tuple[int, str, int, int]],
    image_dir: Path,
    out_epub: Path,
    title: str,
    identifier: str,
    language: str = "en",
) -> None:
    book = epub.EpubBook()
    book.set_identifier(identifier)
    book.set_title(title)
    book.set_language(language)
    book.add_author("John C. Hull")
    book.add_metadata("DC", "description", "Fixed-layout EPUB generated from PDF pages")
    book.add_metadata(None, "meta", "pre-paginated", {"property": "rendition:layout"})
    book.add_metadata(None, "meta", "auto", {"property": "rendition:orientation"})
    book.add_metadata(None, "meta", "auto", {"property": "rendition:spread"})

    page_items = []
    for page_num, img_name, width, height in rendered_pages:
        img_path = image_dir / img_name
        image_item = epub.EpubImage(
            uid=f"img-{page_num}",
            file_name=f"images/{img_name}",
            media_type="image/jpeg",
            content=img_path.read_bytes(),
        )
        book.add_item(image_item)

        xhtml = (
            "<html>"
            "<head>"
            '<meta charset="utf-8" />'
            f'<meta name="viewport" content="width={width},height={height}" />'
            "</head>"
            '<body style="margin:0;padding:0;width:100%;height:100%;">'
            f'<img src="../images/{img_name}" alt="Page {page_num}" style="display:block;width:100%;height:100%;object-fit:contain;" />'
            "</body>"
            "</html>"
        )
        page_item = epub.EpubHtml(
            title=f"Page {page_num}",
            file_name=f"pages/page-{page_num:04d}.xhtml",
            lang=language,
        )
        page_item.content = xhtml.encode("utf-8")
        page_item.properties.append("svg")
        book.add_item(page_item)
        page_items.append(page_item)

    book.toc = tuple(page_items)
    book.spine = ["nav"] + page_items
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(out_epub.as_posix(), book, {})


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create fixed-layout EPUB from PDF pages.")
    p.add_argument("--pdf", required=True, help="Source PDF path")
    p.add_argument("--start", type=int, required=True, help="Start page (1-based)")
    p.add_argument("--end", type=int, required=True, help="End page (1-based)")
    p.add_argument("--dpi", type=int, default=170, help="Render DPI")
    p.add_argument("--title", required=True, help="Book title")
    p.add_argument("--out", required=True, help="Output EPUB path")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    pdf_path = Path(args.pdf).expanduser()
    out_path = Path(args.out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="fixed_epub_"))
    try:
        image_dir = tmp_dir / "images"
        image_dir.mkdir(parents=True, exist_ok=True)
        rendered = render_pdf_pages(
            pdf_path=pdf_path,
            start_page=args.start,
            end_page=args.end,
            dpi=args.dpi,
            out_dir=image_dir,
        )
        build_fixed_epub(
            rendered_pages=rendered,
            image_dir=image_dir,
            out_epub=out_path,
            title=args.title,
            identifier=f"fixed-{uuid.uuid4().hex[:12]}",
            language="en",
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"Done: {out_path}")


if __name__ == "__main__":
    main()
