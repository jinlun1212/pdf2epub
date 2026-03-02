import sys

# Require Python 3: provide a clear error if user runs with Python 2 `python` command.
if sys.version_info[0] < 3:
    print("This script requires Python 3. Run it with 'python3 epub_extract.py'.")
    sys.exit(1)

import argparse
import zipfile
import os
import shutil
import tempfile
import re
from pathlib import Path
from typing import List, Tuple

def extract_epub(epub_path: str, extract_dir: str) -> None:
    with zipfile.ZipFile(epub_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

def modify_xhtml_files(root_dir, old_text, new_text):
    for path in Path(root_dir).rglob("*.xhtml"):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        content = content.replace(old_text, new_text)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
def modify_files(root_dir: str,
                 replacements: List[Tuple[str, str]],
                 use_regex: bool = False,
                 extensions: List[str] = None,
                 dry_run: bool = False) -> List[Tuple[Path, List[Tuple[str, str]]]]:
    """Apply replacements to files under root_dir.

    Returns a list of (file_path, list_of_successful_replacements) for reporting.
    """
    if extensions is None:
        extensions = [".xhtml", ".html", ".htm", ".css", ".svg"]

    modified = []
    for ext in extensions:
        for path in Path(root_dir).rglob(f"*{ext}"):
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                text = path.read_text(encoding="utf-8", errors="replace")

            file_changes = []
            new_text = text
            for old, new in replacements:
                if use_regex:
                    result, count = re.subn(old, new, new_text)
                    if count:
                        file_changes.append((old, f"{count} matches"))
                        new_text = result
                else:
                    if old in new_text:
                        count = new_text.count(old)
                        new_text = new_text.replace(old, new)
                        file_changes.append((old, f"{count} occurrences"))

            if file_changes:
                modified.append((path, file_changes))
                if not dry_run:
                    path.write_text(new_text, encoding="utf-8")

    return modified

def create_epub(output_path, source_dir):
    # Ensure mimetype exists and is written first without compression
    mimetype_path = os.path.join(source_dir, "mimetype")
    if not os.path.isfile(mimetype_path):
        raise FileNotFoundError("mimetype file missing in EPUB source directory")

    with zipfile.ZipFile(output_path, 'w') as epub:
        epub.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)

        for foldername, subfolders, filenames in os.walk(source_dir):
            for filename in filenames:
                full_path = os.path.join(foldername, filename)
                rel_path = os.path.relpath(full_path, source_dir)

                if rel_path == "mimetype":
                    continue

                epub.write(full_path, rel_path, compress_type=zipfile.ZIP_DEFLATED)

def parse_replacements(arg_list: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    # arg_list is a list of (old, new) tuples
    return arg_list or []

def main():
    parser = argparse.ArgumentParser(description="Extract, modify, and rebuild EPUB files.")
    parser.add_argument("input", help="Input EPUB file")
    parser.add_argument("-o", "--output", help="Output EPUB file (default: input_modified.epub)")
    parser.add_argument("--temp-dir", help="Temporary extraction directory (default: auto)")
    parser.add_argument("--replace", nargs=2, action='append', metavar=("OLD", "NEW"),
                        help="Replace OLD with NEW in matching files. Can be repeated.")
    parser.add_argument("--regex", action='store_true', help="Treat replacement patterns as regexes.")
    parser.add_argument("--extensions", nargs='+', help="File extensions to process (default: .xhtml .html .htm .css .svg)")
    parser.add_argument("--list-files", action='store_true', help="List files inside the EPUB and exit")
    parser.add_argument("--extract-only", action='store_true', help="Only extract the EPUB and exit")
    parser.add_argument("--dry-run", action='store_true', help="Show what would change without modifying files")
    parser.add_argument("--inplace", action='store_true', help="Overwrite the input EPUB with the modified EPUB")

    args = parser.parse_args()

    input_epub = args.input
    output_epub = args.output or (os.path.splitext(input_epub)[0] + "_modified.epub")

    # Prepare temp dir
    if args.temp_dir:
        temp_dir = args.temp_dir
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
    else:
        temp_dir = tempfile.mkdtemp(prefix="epub_edit_")

    try:
        print("Extracting EPUB...")
        extract_epub(input_epub, temp_dir)

        if args.list_files:
            for root, _, files in os.walk(temp_dir):
                for f in files:
                    print(os.path.relpath(os.path.join(root, f), temp_dir))
            return

        if args.extract_only:
            print("Extracted to:", temp_dir)
            return

        replacements = parse_replacements(args.replace)
        extensions = args.extensions if args.extensions else None

        if not replacements:
            print("No replacements specified. Nothing to do. Use --replace OLD NEW to specify changes.")
        else:
            print("Modifying files...")
            modified = modify_files(temp_dir, replacements, use_regex=args.regex, extensions=extensions, dry_run=args.dry_run)
            if not modified:
                print("No files were changed.")
            else:
                for path, changes in modified:
                    print(f"Modified: {path} -> {changes}")

        if args.dry_run:
            print("Dry run complete. No files were written.")
            return

        print("Rebuilding EPUB...")
        create_epub(output_epub, temp_dir)

        if args.inplace:
            shutil.move(output_epub, input_epub)
            print("Overwrote input EPUB with modified EPUB.")
        else:
            print("Done! Created:", output_epub)

    finally:
        if not args.temp_dir:
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    main()