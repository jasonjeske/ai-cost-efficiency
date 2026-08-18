#!/usr/bin/env python3
"""Estimate the token cost of reading files or directories into a model context.

Answers "what would an agent pay to read this?" for any file set: a repo,
a docs tree, a single large file you are about to paste. Walks the given
paths, skips binaries and common junk directories, and reports estimated
tokens per file and in total.

Token estimates use a characters-per-token heuristic (default 4.0), which
is adequate for ranking and budgeting, not exact billing.

Examples:
  context-size.py                    # current directory
  context-size.py src/ docs/README.md
  context-size.py ~/project --top 25 --json
"""

import argparse
import json
import os
import sys

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", ".venv", "venv",
    "__pycache__", "dist", "build", "out", ".next", "target", "coverage",
    ".cache", ".idea", ".vscode",
}

# Extensions treated as binary without opening the file.
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".tar", ".bz2", ".xz", ".7z", ".mp3", ".mp4", ".mov", ".avi", ".wav",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".so", ".dylib", ".dll",
    ".exe", ".bin", ".sqlite", ".db", ".parquet", ".pyc", ".class", ".jar",
}


def is_binary(path):
    if os.path.splitext(path)[1].lower() in BINARY_EXTS:
        return True
    try:
        with open(path, "rb") as f:
            return b"\0" in f.read(8192)
    except OSError:
        return True


def file_stats(path, cpt):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return None
    return {"path": path, "bytes": os.path.getsize(path),
            "est_tokens": int(round(len(text) / cpt))}


def walk(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p
        elif os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".git")]
                for name in files:
                    yield os.path.join(root, name)
        else:
            sys.stderr.write(f"error: no such file or directory: {p}\n")
            sys.exit(1)


def fmt(n):
    return f"{int(round(n)):,}"


def main():
    ap = argparse.ArgumentParser(
        prog="context-size.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("paths", nargs="*", default=["."],
                    help="files or directories to measure (default: current directory)")
    ap.add_argument("--top", type=int, default=15,
                    help="how many largest files to list (default 15)")
    ap.add_argument("--chars-per-token", type=float, default=4.0,
                    help="estimation heuristic (default 4.0)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    if args.chars_per_token <= 0:
        ap.error("--chars-per-token must be positive")

    rows = []
    skipped_binary = 0
    for path in walk(args.paths):
        if is_binary(path):
            skipped_binary += 1
            continue
        st = file_stats(path, args.chars_per_token)
        if st:
            rows.append(st)

    rows.sort(key=lambda r: r["est_tokens"], reverse=True)
    total_tokens = sum(r["est_tokens"] for r in rows)
    total_bytes = sum(r["bytes"] for r in rows)

    result = {
        "note": "estimates via chars/token heuristic, not exact tokenizer counts",
        "paths": args.paths,
        "text_files": len(rows),
        "binary_files_skipped": skipped_binary,
        "total_bytes": total_bytes,
        "total_est_tokens": total_tokens,
        "largest": rows[: args.top],
        "truncated": max(0, len(rows) - args.top),
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"Context size estimate for: {' '.join(args.paths)}")
    print(f"  Text files: {len(rows)}   Binary skipped: {skipped_binary}")
    print(f"  Total: ~{fmt(total_tokens)} tokens ({fmt(total_bytes)} bytes)")
    print()
    print(f"  Largest {min(args.top, len(rows))} files:")
    for r in rows[: args.top]:
        print(f"  {fmt(r['est_tokens']):>10}  {r['path']}")
    if len(rows) > args.top:
        print(f"  ... {len(rows) - args.top} more (use --top to widen)")
    print()
    print("  Reference points: frontier-model context windows are commonly in the")
    print("  hundreds of thousands of tokens, and everything read into a session is")
    print("  re-read (and re-billed) on every subsequent turn of that session.")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
