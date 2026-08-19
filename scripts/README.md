# Scripts

Python 3.8+, standard library only, zero dependencies. `ace.py` is the local audit, proposal, and verification CLI. The four legacy estimator scripts remain directly runnable with their existing flags and behavior.

## Five-minute ACE workflow

ACE is review-only: audit and proposal do not modify the workspace, and verification uses a removed temporary copy. Keep output outside the workspace.

```sh
mkdir -p /tmp/ace-results
python3 scripts/ace.py audit /path/to/workspace --adapter cursor --json --output /tmp/ace-results/audit.json
python3 scripts/ace.py propose /path/to/workspace --audit /tmp/ace-results/audit.json --json --output /tmp/ace-results/candidate.json
python3 scripts/ace.py verify /path/to/workspace --candidate /tmp/ace-results/candidate.json --json --output /tmp/ace-results/verification.json
```

The versioned JSON documents are the supported chaining interface. Select `claude-code`, `codex`, `cursor`, or `vscode-copilot`; use `auto` only for an unambiguous workspace. Read the candidate diff before verification and never auto-apply it. A `no_candidate` result exits 0.

Exit codes are: `0` completed operation, `1` completed negative result, `2` usage, `3` input/output, `4` safety or precondition failure, and `5` unexpected error. See [`RUNBOOK.md`](../RUNBOOK.md) for troubleshooting. Verification confirms static and isolated checks, not observed CPCT improvement. CPCT needs comparable post-change task data and quality guardrails.

## Legacy estimators

The legacy tools produce useful bounded output with no arguments, support `--help` and `--json`, and retain their historical exit behavior. Their usual successful exit is `0`; consult each tool's help for its specific error and gating behavior.

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
