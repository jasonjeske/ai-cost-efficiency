---
name: cost-baseline
description: Baseline a project's AI cost profile, standing overhead plus session shape, and report the four key numbers with the biggest lever named. Use when asked to measure, baseline, or explain what agent sessions in a project cost.
---

# Cost Baseline

Produce a project's cost profile in one pass. Requires only this repo's scripts (Python 3, no dependencies).

## Procedure

1. **Measure instruction overhead.**
   ```sh
   python3 scripts/instruction-audit.py <project-root>
   ```
   Record the combined estimated tokens and any file flagged REVIEW.

2. **Measure tool-catalog overhead.** Locate every tool config that loads in this project (project files like `.mcp.json`, `.cursor/mcp.json`, `.vscode/mcp.json`, AND user-global configs). For each:
   ```sh
   python3 scripts/tool-overhead.py <config>
   ```
   Sum the standing estimates. If the harness can dump actual registered tools, use the dump for measured numbers.

3. **Establish session shape.** From harness logs, history, or the user's description, estimate: typical turns per session, and average tokens per turn for user messages, assistant replies, and tool output. If unknown, state that the `session-cost.py` defaults are being used as placeholders.

4. **Model the session.**
   ```sh
   python3 scripts/session-cost.py --system <instr+system> --tools <catalog> --turns <N>
   ```
   Also run the two levers for comparison: `--split 2` (or 3), and the same command with the tool catalog halved.

5. **Report** in this exact shape:
   - **Standing prefix:** X tokens/turn (instructions A + catalog B + assumed system C).
   - **Session shape:** ~N turns typical; ~D tokens/turn of history growth.
   - **Modeled cost per task:** total input and output tokens, with the overhead share percentage.
   - **Biggest lever:** exactly one of: cut the catalog, shrink instructions, split sessions, constrain tool output, with the modeled saving from step 4.
   - **Caveat line:** all figures are chars/token estimates; exact numbers come from the provider dashboard.

## Rules

- Never present the estimates as measurements. Label them.
- Do not recommend more than one lever; name the biggest and stop. The others go in a "next" line.
- If the standing prefix exceeds roughly half of modeled per-task input, configuration is the finding; say so before any behavioral advice.
