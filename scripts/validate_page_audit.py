"""
Validate page audit entries in page_audit_status.json.

Usage:
    python scripts/validate_page_audit.py               # validate all entries
    python scripts/validate_page_audit.py --page 28      # validate single page
    python scripts/validate_page_audit.py --summary      # show progress summary

Checks:
1. Both render images exist (pdf_renders/ and epub_renders/).
2. Required fields are present and non-empty.
3. Status is a valid value.
"""
import sys
import io
import json
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.parent.resolve()
TRACKER_PATH = BASE_DIR / "page_audit_status.json"
PDF_RENDER_DIR = BASE_DIR / "output" / "pdf_renders"
EPUB_RENDER_DIR = BASE_DIR / "output" / "epub_renders"

REQUIRED_FIELDS = [
    "status", "agent", "pdf_observation", "epub_observation", "comparison_summary"
]
VALID_STATUSES = {"completed", "pending", "needs_review"}


def load_tracker():
    if TRACKER_PATH.exists():
        return json.loads(TRACKER_PATH.read_text(encoding='utf-8'))
    return {"pages": {}}


def validate_page(pn, entry):
    """Validate a single page entry. Returns list of error strings."""
    errors = []

    # Check required fields
    for field in REQUIRED_FIELDS:
        val = entry.get(field)
        if not val or (isinstance(val, str) and not val.strip()):
            errors.append(f"Missing or empty field: {field}")

    # Check status value
    status = entry.get("status", "")
    if status not in VALID_STATUSES:
        errors.append(f"Invalid status: '{status}' (must be one of {VALID_STATUSES})")

    # Check render files
    pdf_render = PDF_RENDER_DIR / f"page_{pn:04d}.png"
    epub_render = EPUB_RENDER_DIR / f"page_{pn:04d}.png"

    if not pdf_render.exists():
        errors.append(f"PDF render missing: {pdf_render.name}")
    if not epub_render.exists():
        errors.append(f"EPUB render missing: {epub_render.name}")

    # If completed, observations should be substantive (>10 chars)
    if status == "completed":
        for field in ["pdf_observation", "epub_observation", "comparison_summary"]:
            val = entry.get(field, "")
            if len(val) < 10:
                errors.append(f"Field '{field}' too short for completed page ({len(val)} chars)")

    return errors


def main():
    parser = argparse.ArgumentParser(description='Validate page audit entries')
    parser.add_argument('--page', type=int, help='Validate a specific page')
    parser.add_argument('--summary', action='store_true', help='Show progress summary')
    args = parser.parse_args()

    tracker = load_tracker()
    pages = tracker.get("pages", {})

    if args.summary:
        total_pages = 880
        completed = sum(1 for e in pages.values() if e.get("status") == "completed")
        pending = sum(1 for e in pages.values() if e.get("status") == "pending")
        needs_review = sum(1 for e in pages.values() if e.get("status") == "needs_review")
        not_started = total_pages - len(pages)

        print(f"Page Audit Progress")
        print(f"{'='*40}")
        print(f"Total pages:    {total_pages}")
        print(f"Completed:      {completed}")
        print(f"Pending:        {pending}")
        print(f"Needs review:   {needs_review}")
        print(f"Not started:    {not_started}")
        print(f"{'='*40}")
        pct = (completed / total_pages) * 100
        print(f"Progress:       {pct:.1f}%")
        return

    if args.page:
        pn = args.page
        entry = pages.get(str(pn))
        if not entry:
            print(f"FAIL: Page {pn} has no audit entry.", file=sys.stderr)
            sys.exit(1)
        errors = validate_page(pn, entry)
        if errors:
            print(f"FAIL: Page {pn} has {len(errors)} validation error(s):")
            for e in errors:
                print(f"  - {e}")
            sys.exit(1)
        else:
            print(f"PASS: Page {pn} audit entry is valid.")
            sys.exit(0)

    # Validate all entries
    total_errors = 0
    for pn_str, entry in sorted(pages.items(), key=lambda x: int(x[0])):
        pn = int(pn_str)
        errors = validate_page(pn, entry)
        if errors:
            total_errors += len(errors)
            print(f"Page {pn}: {len(errors)} error(s)")
            for e in errors:
                print(f"  - {e}")

    if total_errors == 0:
        print(f"All {len(pages)} audit entries are valid.")
    else:
        print(f"\n{total_errors} total errors across {len(pages)} entries.")
        sys.exit(1)


if __name__ == '__main__':
    main()
