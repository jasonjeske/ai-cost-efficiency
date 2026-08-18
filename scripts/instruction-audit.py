#!/usr/bin/env python3
"""Scan a repository for agent instruction files and flag oversized ones.

Instruction files (AGENTS.md, CLAUDE.md, rules files, and equivalents) are
loaded into every request and re-read by the model on every turn. Their size
is a standing per-turn cost in every session opened in the project. This tool
finds them, estimates their token cost, and flags files over a threshold.

Exit codes: 0 on success; 1 if --fail-over is set and any file exceeds it
(useful as a CI gate); 2 on usage errors.

Examples:
  instruction-audit.py                  # scan current directory
  instruction-audit.py ~/project
  instruction-audit.py . --warn 2000 --json
  instruction-audit.py . --fail-over 4000   # CI gate
"""

import argparse
import fnmatch
import json
import os
import sys

# Known instruction-file names (checked anywhere in the tree).
KNOWN_NAMES = {
    "AGENTS.md", "AGENT.md", "CLAUDE.md", "CLAUDE.local.md", "GEMINI.md",
    ".cursorrules", ".windsurfrules", ".clinerules",
    "copilot-instructions.md",
}

# Directory-scoped patterns: (directory suffix, filename glob).
DIR_PATTERNS = [
    (os.path.join(".cursor", "rules"), "*"),
    (os.path.join(".github", "instructions"), "*.instructions.md"),
]

SKIP_DIRS = {
    ".git", "node_modules", "vendor", ".venv", "venv", "__pycache__",
    "dist", "build", "out", ".next", "target", "coverage",
}


def est_tokens(path, cpt):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return int(round(len(f.read()) / cpt))
    except OSError:
        return None


def find_instruction_files(root):
    hits = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs
                   if d not in SKIP_DIRS and (not d.startswith(".") or d in {".cursor", ".github"})]
        for name in files:
            full = os.path.join(dirpath, name)
            if name in KNOWN_NAMES:
                hits.append(full)
                continue
            for dir_suffix, pattern in DIR_PATTERNS:
                if dirpath.endswith(dir_suffix) and fnmatch.fnmatch(name, pattern):
                    hits.append(full)
                    break
    return sorted(set(hits))


def fmt(n):
    return f"{int(round(n)):,}"


def main():
    ap = argparse.ArgumentParser(
        prog="instruction-audit.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("root", nargs="?", default=".",
                    help="repository root to scan (default: current directory)")
    ap.add_argument("--warn", type=int, default=2500,
                    help="estimated-token threshold that flags a file for review (default 2500)")
    ap.add_argument("--fail-over", type=int, metavar="N",
                    help="exit 1 if any file exceeds N estimated tokens (CI gate)")
    ap.add_argument("--chars-per-token", type=float, default=4.0,
                    help="estimation heuristic (default 4.0)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        sys.stderr.write(f"error: not a directory: {args.root}\n")
        sys.exit(1)

    rows = []
    for path in find_instruction_files(args.root):
        tokens = est_tokens(path, args.chars_per_token)
        if tokens is None:
            continue
        status = "REVIEW" if tokens > args.warn else "OK"
        if args.fail_over is not None and tokens > args.fail_over:
            status = "FAIL"
        rows.append({"path": os.path.relpath(path, args.root),
                     "est_tokens": tokens, "status": status})
    rows.sort(key=lambda r: r["est_tokens"], reverse=True)
    total = sum(r["est_tokens"] for r in rows)
    failed = [r for r in rows if r["status"] == "FAIL"]

    result = {
        "note": "estimates via chars/token heuristic; instruction files are "
                "re-read every turn, so totals here are per-turn standing cost",
        "root": args.root,
        "files": rows,
        "total_est_tokens": total,
        "warn_threshold": args.warn,
        "fail_over": args.fail_over,
        "failures": len(failed),
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if not rows:
            print(f"No instruction files found under {args.root}.")
            print("Looked for: " + ", ".join(sorted(KNOWN_NAMES))
                  + ", .cursor/rules/*, .github/instructions/*.instructions.md")
            return
        print(f"Instruction files under {args.root} "
              f"(warn threshold: {fmt(args.warn)} est. tokens):")
        for r in rows:
            print(f"  {r['status']:<7} {fmt(r['est_tokens']):>9}  {r['path']}")
        print(f"\n  Combined standing cost if all load together: ~{fmt(total)} tokens per turn.")
        review = [r for r in rows if r["status"] in ("REVIEW", "FAIL")]
        if review:
            print(f"  {len(review)} file(s) over threshold. The usual fix: move reference")
            print("  material behind on-demand pointers. See templates/AGENTS.md.")

    if failed:
        sys.stderr.write(f"FAIL: {len(failed)} file(s) exceed --fail-over "
                         f"{fmt(args.fail_over)} tokens\n")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
