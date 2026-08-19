---
name: agentic-cost-optimization
description: Audit a local coding-agent workspace, create a review-only ACE candidate, verify it in isolation, and evaluate CPCT evidence. Use when asked to reduce agent standing overhead safely.
---

# Agentic Cost Optimization

Use the local ACE loop: audit -> propose -> verify. It is offline and never applies a patch to the selected workspace.

## Procedure

1. Choose an authorized local workspace and select an adapter explicitly when detection is ambiguous: `claude-code`, `codex`, `cursor`, or `vscode-copilot`. Do not inspect global configuration unless the user explicitly supplies it.
2. Create an output directory outside the workspace. Run an audit and retain its JSON document:
   ```sh
   python3 scripts/ace.py audit <workspace> --adapter <adapter> --json --output <outside-workspace>/audit.json
   ```
   Add only local inputs that are available and authorized, such as `--tool-config`, `--tool-dump`, or `--measurement-csv`. Missing usage data is unknown, not zero.
3. Read the findings and classifications. Prioritize evidence-backed standing-overhead findings. Treat file-byte data as measured, character-derived token counts as estimated, and session projections as modeled.
4. Produce, but do not apply, a candidate:
   ```sh
   python3 scripts/ace.py propose <workspace> --audit <outside-workspace>/audit.json --json --output <outside-workspace>/candidate.json
   ```
   A `no_candidate` result is successful. If a candidate exists, review every diff hunk, rationale, quality risk, and on-demand reference before continuing. Ask the workspace owner to decide whether moved guidance remains appropriate on demand.
5. Verify the reviewed candidate without modifying the workspace:
   ```sh
   python3 scripts/ace.py verify <workspace> --candidate <outside-workspace>/candidate.json --json --output <outside-workspace>/verification.json
   ```
   Verification uses a temporary local copy. A stale precondition or failed check means stop, re-audit, and do not hand-edit the candidate.
6. Evaluate outcome evidence separately. For CPCT, supply all of `--pre-csv`, `--post-csv`, `--completion-standard`, and `--harness-id` after comparable task cohorts exist. CPCT includes failed and abandoned attempts. Do not call a smaller prefix, a verification delta, or a model projection an observed CPCT improvement.

## Rules

- Never auto-apply, commit, publish, or overwrite a candidate. The user applies an accepted diff with their normal review process.
- Keep reports local. Do not transmit prompt bodies, source bodies, tool output, secrets, or task notes.
- Preserve task class, completion standard, harness, and model tier across cohorts where possible. Missing, confounded, or insufficient evidence remains pending.
- Treat exit code 0 as completed operation, not proof of outcome improvement. See `RUNBOOK.md` for all exit codes and recovery.
