#!/usr/bin/env python3
import csv
import sys
from pathlib import Path

if len(sys.argv) < 4:
    print("Usage: init_epub_screen_tracker.py <screens_dir> <output_csv> <epub_file>")
    raise SystemExit(1)

screens_dir = Path(sys.argv[1])
out_csv = Path(sys.argv[2])
epub_file = Path(sys.argv[3])

screens = sorted(p for p in screens_dir.glob("screen_*.png") + list(screens_dir.glob("screen_*.jpg")))
out_csv.parent.mkdir(parents=True, exist_ok=True)

with out_csv.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow([
        "epub_file",
        "epub_screen",
        "status",
        "issue_categories",
        "notes",
        "books_screenshot",
        "validated_at",
    ])
    for i, p in enumerate(screens, start=1):
        w.writerow([
            str(epub_file),
            i,
            "pending",
            "",
            "",
            str(p),
            "",
        ])

print(f"Wrote {len(screens)} rows to {out_csv}")
