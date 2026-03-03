"""
Record a completed page audit entry in page_audit_status.json.

Usage:
    python scripts/record_page_audit.py \\
        --page 28 \\
        --agent codex \\
        --pdf-observation "PDF shows Table 1.1 as a compact 3-column table." \\
        --epub-observation "EPUB now renders Table 1.1 as a compact table." \\
        --comparison-summary "Caption, row structure, and notes match." \\
        --issue "Mashed paragraph text replaced the table." \\
        --fix "Rebuilt Table 1.1 as HTML table markup."

Multiple --issue and --fix flags are supported.
"""
import sys
import io
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.parent.resolve()
TRACKER_PATH = BASE_DIR / "page_audit_status.json"
PDF_RENDER_DIR = BASE_DIR / "output" / "pdf_renders"
EPUB_RENDER_DIR = BASE_DIR / "output" / "epub_renders"


def load_tracker():
    """Load the audit tracker, or create a new one."""
    if TRACKER_PATH.exists():
        return json.loads(TRACKER_PATH.read_text(encoding='utf-8'))
    return {"pages": {}}


def save_tracker(data):
    """Save the audit tracker."""
    TRACKER_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8'
    )


def main():
    parser = argparse.ArgumentParser(description='Record a page audit entry')
    parser.add_argument('--page', type=int, required=True, help='Page number')
    parser.add_argument('--agent', type=str, default='claude', help='Agent name')
    parser.add_argument('--pdf-observation', type=str, required=True,
                        help='What the PDF render shows')
    parser.add_argument('--epub-observation', type=str, required=True,
                        help='What the final EPUB render shows')
    parser.add_argument('--comparison-summary', type=str, required=True,
                        help='Why the EPUB now matches the PDF')
    parser.add_argument('--issue', action='append', default=[],
                        help='Issue found (repeatable)')
    parser.add_argument('--fix', action='append', default=[],
                        help='Fix applied (repeatable)')
    parser.add_argument('--status', type=str, default='completed',
                        choices=['completed', 'pending', 'needs_review'],
                        help='Audit status (default: completed)')
    args = parser.parse_args()

    pn = args.page

    # Check render files exist
    pdf_render = PDF_RENDER_DIR / f"page_{pn:04d}.png"
    epub_render = EPUB_RENDER_DIR / f"page_{pn:04d}.png"

    errors = []
    if not pdf_render.exists():
        errors.append(f"PDF render missing: {pdf_render}")
    if not epub_render.exists():
        errors.append(f"EPUB render missing: {epub_render}")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print("Both render images must exist before recording an audit.", file=sys.stderr)
        sys.exit(1)

    # Build audit entry
    entry = {
        "status": args.status,
        "agent": args.agent,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pdf_observation": args.pdf_observation,
        "epub_observation": args.epub_observation,
        "comparison_summary": args.comparison_summary,
        "issues": args.issue,
        "fixes": args.fix,
        "pdf_render": str(pdf_render.relative_to(BASE_DIR)),
        "epub_render": str(epub_render.relative_to(BASE_DIR)),
    }

    tracker = load_tracker()
    tracker["pages"][str(pn)] = entry
    save_tracker(tracker)

    print(f"Recorded audit for page {pn} ({args.status})")


if __name__ == '__main__':
    main()
