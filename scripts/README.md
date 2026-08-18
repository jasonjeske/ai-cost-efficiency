# Scripts

Four runnable CLI tools. Python 3.8+, standard library only, zero dependencies, single file each. Every tool supports `--help` and `--json`, produces useful bounded output with no arguments, exits `0` on success, `1` on runtime failure, `2` on usage errors, and rejects unknown flags loudly.

All token figures are estimates from a characters-per-token heuristic (default 4.0, tunable with `--chars-per-token`). Good enough for ranking and budgeting; use your provider's usage dashboard for exact billing.

| Tool | Question it answers |
|---|---|
| `context-size.py` | What would an agent pay to read this file set? |
| `tool-overhead.py` | What standing tool-catalog overhead does this config add to every turn? |
| `session-cost.py` | What does the re-read mechanic do to my session, and what would splitting it save? |
| `instruction-audit.py` | Which instruction files in this repo are oversized per-turn costs? |

## Typical workflow

```sh
# 1. Baseline the standing overhead of a project you work in daily.
python3 scripts/instruction-audit.py ~/work/project
python3 scripts/tool-overhead.py ~/work/project/.mcp.json

# 2. Feed those measured numbers into the session model.
python3 scripts/session-cost.py --system 3000 --tools 22000 --turns 30

# 3. Test the two big levers: shorter sessions, leaner catalog.
python3 scripts/session-cost.py --system 3000 --tools 22000 --turns 30 --split 3
python3 scripts/session-cost.py --system 3000 --tools 8000  --turns 30

# 4. Gate regressions in CI.
python3 scripts/instruction-audit.py . --fail-over 4000
```

## Notes

- `tool-overhead.py` gives measured numbers when fed a tool-definition dump and labeled estimates when fed only a server list, because server configs do not contain the tool schemas. If your client can export registered tools, use the dump.
- `session-cost.py` contains no built-in prices. Pass your provider's current rates (`--price-input`, `--price-cached`, `--price-output`, dollars per million tokens) to see money.
- macOS and most Linux distributions ship a suitable Python 3. The scripts have no other requirements.
