#!/usr/bin/env python3
import argparse
import hashlib
import subprocess
import time
from pathlib import Path


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def osascript(script: str):
    run(["osascript", "-e", script])


def activate_books():
    osascript('tell application "Books" to activate')


def go_home():
    osascript('tell application "System Events" to key code 115')


def right_arrow():
    osascript('tell application "System Events" to key code 124')


def capture(path: Path, img_type: str):
    run(["screencapture", "-x", "-t", img_type, str(path)])


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epub", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-screens", type=int, default=2000)
    ap.add_argument("--start-delay", type=float, default=7.0)
    ap.add_argument("--step-delay", type=float, default=0.8)
    ap.add_argument("--repeat-stop", type=int, default=3)
    ap.add_argument("--img-type", choices=["jpg", "png"], default="jpg")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    run(["open", "-a", "Books", args.epub])
    time.sleep(args.start_delay)
    activate_books()
    time.sleep(0.8)
    go_home()
    time.sleep(1.0)

    prev = None
    repeat_count = 0
    captured = 0

    for i in range(1, args.max_screens + 1):
        ext = "jpg" if args.img_type == "jpg" else "png"
        p = out / f"screen_{i:04d}.{ext}"
        capture(p, args.img_type)
        d = digest(p)

        if prev == d:
            repeat_count += 1
        else:
            repeat_count = 0
        prev = d

        captured = i
        print(f"captured {i}: {p.name} repeat_count={repeat_count}")

        if repeat_count >= args.repeat_stop:
            print("Reached repeated end screens; stopping.")
            break

        right_arrow()
        time.sleep(args.step_delay)

    print(f"Saved {captured} screens to {out}")


if __name__ == "__main__":
    main()
