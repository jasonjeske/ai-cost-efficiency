#!/usr/bin/env python3
"""Audit the standing token overhead of a tool/MCP configuration.

Every registered tool's definition (name, description, input schema) is
resent to the model on every turn, whether or not the tool is called.
This tool reads a config or a tool-definition dump and reports the
estimated standing overhead per turn, plus what it compounds to across
a session.

Accepted inputs (auto-detected):
  1. A server config: {"mcpServers": {...}} or {"servers": {...}}
     (Claude Code .mcp.json, Cursor .cursor/mcp.json, VS Code .vscode/mcp.json).
     Server configs do not contain the tools themselves, so per-server
     overhead is estimated from --tools-per-server and a per-tool token
     range, clearly labeled as an estimate.
  2. A tool-definition dump: a JSON array of tool objects, or
     {"tools": [...]}, where each object has a name/description/schema.
     This is measured directly by serializing each definition.
     If your client can export its registered tools, prefer this input.

Use "-" to read from stdin.

Examples:
  tool-overhead.py .mcp.json
  tool-overhead.py tools-dump.json --turns 30
  tool-overhead.py .cursor/mcp.json --json
"""

import argparse
import json
import os
import re
import sys

# Per-tool token range used when only a server list is available.
# Order-of-magnitude estimate based on typical definition sizes; real
# definitions vary widely. Override with --tokens-per-tool.
DEFAULT_TOOL_TOKENS_LOW = 100
DEFAULT_TOOL_TOKENS_HIGH = 500


DEFAULT_CANDIDATES = (".mcp.json", "mcp.json", ".cursor/mcp.json", ".vscode/mcp.json")


def est_tokens(text, cpt):
    return int(round(len(text) / cpt))


def fmt(n):
    return f"{int(round(n)):,}"


def strip_jsonc(text):
    """Tolerate JSONC. Editor tool configs are routinely .jsonc with comments
    and trailing commas (VS Code and Cursor both ship them that way), so a
    strict JSON parser rejects the very files this tool exists to read.
    Removes // and /* */ comments outside strings, then trailing commas."""
    out, i, n = [], 0, len(text)
    in_str = esc = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
        else:
            out.append(c)
            i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def load(path):
    try:
        raw = sys.stdin.read() if path == "-" else open(path, "r", encoding="utf-8").read()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return json.loads(strip_jsonc(raw))
    except FileNotFoundError:
        # "No config here" is a valid state, not a failure, so say so plainly and
        # show the next command instead of dying with a bare error. This is the
        # useful-no-argument-output rule from standards/tool-design.md applied to
        # this tool itself.
        if path in DEFAULT_CANDIDATES:
            print("No tool or MCP config found in this directory.")
            print("  Looked for: " + ", ".join(DEFAULT_CANDIDATES))
            print()
            print("Point it at a config, or try the bundled example:")
            print("  python3 scripts/tool-overhead.py templates/workspace-config/mcp-servers.example.jsonc")
            print("  python3 scripts/tool-overhead.py /path/to/mcp.json")
            print("  <your-agent> --dump-tools | python3 scripts/tool-overhead.py -")
            sys.exit(0)
        sys.stderr.write(f"error: file not found: {path}\n")
        sys.exit(1)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"error: {path} is not valid JSON: {e}\n")
        sys.exit(1)


def analyze_tool_dump(tools, cpt):
    rows = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        name = t.get("name", "<unnamed>")
        rows.append({"name": name, "tokens": est_tokens(json.dumps(t, separators=(",", ":")), cpt)})
    rows.sort(key=lambda r: r["tokens"], reverse=True)
    return rows


def main():
    ap = argparse.ArgumentParser(
        prog="tool-overhead.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("config", nargs="?", default=None,
                    help="path to a tool/MCP config or tool-definition dump "
                         "(default: first of " + ", ".join(DEFAULT_CANDIDATES)
                         + " found in the current directory; '-' for stdin)")
    ap.add_argument("--turns", type=int, default=20,
                    help="session length used to show compounded overhead (default 20)")
    ap.add_argument("--tools-per-server", type=int, default=10,
                    help="assumed tool count per server when only a server list is "
                         "available (default 10; check each server's docs for the real count)")
    ap.add_argument("--tokens-per-tool", type=int, default=None,
                    help="override the per-tool token estimate with a single value "
                         f"(default: a {DEFAULT_TOOL_TOKENS_LOW}-{DEFAULT_TOOL_TOKENS_HIGH} range)")
    ap.add_argument("--top", type=int, default=15,
                    help="max tools listed individually in dump mode (default 15)")
    ap.add_argument("--chars-per-token", type=float, default=4.0,
                    help="estimation heuristic (default 4.0)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    if args.turns < 1:
        ap.error("--turns must be >= 1")

    config = args.config
    if config is None:
        # No path given: actually try each default candidate, so the
        # "Looked for" message in load() matches real behavior.
        config = next((c for c in DEFAULT_CANDIDATES if os.path.exists(c)),
                      DEFAULT_CANDIDATES[0])

    data = load(config)
    cpt = args.chars_per_token
    result = {"source": config, "mode": None,
              "note": "token figures are estimates (chars/token heuristic), not exact tokenizer counts"}

    # Detect shape
    tools = None
    servers = None
    if isinstance(data, list):
        tools = data
    elif isinstance(data, dict):
        if isinstance(data.get("tools"), list):
            tools = data["tools"]
        elif isinstance(data.get("mcpServers"), dict):
            servers = data["mcpServers"]
        elif isinstance(data.get("servers"), dict):
            servers = data["servers"]

    if tools is not None:
        result["mode"] = "tool-definition dump (measured)"
        rows = analyze_tool_dump(tools, cpt)
        total = sum(r["tokens"] for r in rows)
        result["tool_count"] = len(rows)
        result["standing_tokens_per_turn"] = total
        result["compounded_tokens"] = {"turns": args.turns, "total": total * args.turns}
        result["tools"] = rows[: args.top]
        result["tools_truncated"] = max(0, len(rows) - args.top)
        if args.json:
            print(json.dumps(result, indent=2))
            return
        print(f"Tool catalog: {len(rows)} definitions ({config})")
        for r in rows[: args.top]:
            print(f"  {fmt(r['tokens']):>8}  {r['name']}")
        if len(rows) > args.top:
            print(f"  ... {len(rows) - args.top} more (use --top to widen)")
        print(f"\n  Standing overhead: ~{fmt(total)} tokens resent EVERY turn, called or not.")
        print(f"  Over a {args.turns}-turn session: ~{fmt(total * args.turns)} input tokens "
              f"before any work happens.")
        print("  (Prompt caching discounts repeats; see docs/billing-mechanics.md.)")
        return

    if servers is not None:
        result["mode"] = "server config (estimated)"
        low_pt = args.tokens_per_tool or DEFAULT_TOOL_TOKENS_LOW
        high_pt = args.tokens_per_tool or DEFAULT_TOOL_TOKENS_HIGH
        rows = []
        for name in sorted(servers):
            rows.append({
                "server": name,
                "assumed_tools": args.tools_per_server,
                "tokens_low": args.tools_per_server * low_pt,
                "tokens_high": args.tools_per_server * high_pt,
            })
        total_low = sum(r["tokens_low"] for r in rows)
        total_high = sum(r["tokens_high"] for r in rows)
        result["server_count"] = len(rows)
        result["assumptions"] = {"tools_per_server": args.tools_per_server,
                                 "tokens_per_tool_low": low_pt, "tokens_per_tool_high": high_pt}
        result["standing_tokens_per_turn"] = {"low": total_low, "high": total_high}
        result["compounded_tokens"] = {"turns": args.turns,
                                       "low": total_low * args.turns,
                                       "high": total_high * args.turns}
        result["servers"] = rows
        if args.json:
            print(json.dumps(result, indent=2))
            return
        print(f"Server config: {len(rows)} server(s) ({config})")
        print(f"  Estimate basis: {args.tools_per_server} tools/server at "
              f"{low_pt}-{high_pt} tokens/tool (rough; feed a tool dump for measured numbers)")
        for r in rows:
            print(f"  {r['server']:<28} ~{fmt(r['tokens_low'])}-{fmt(r['tokens_high'])} tokens/turn")
        print(f"\n  Standing overhead: ~{fmt(total_low)}-{fmt(total_high)} tokens "
              f"resent EVERY turn, called or not.")
        print(f"  Over a {args.turns}-turn session: ~{fmt(total_low * args.turns)}-"
              f"{fmt(total_high * args.turns)} input tokens before any work happens.")
        print("  Audit process: templates/workspace-config/tool-server-audit.md")
        return

    sys.stderr.write(
        "error: unrecognized config shape. Expected {'mcpServers': {...}}, "
        "{'servers': {...}}, {'tools': [...]}, or a JSON array of tool definitions.\n")
    sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
