---
name: tool-catalog-audit
description: Run the tool-server audit end to end, measure standing overhead per server, interrogate usage, and produce the approved-list table with keep/demote/remove dispositions. Use when asked to audit, clean up, or justify MCP servers or agent tool configs.
---

# Tool Catalog Audit

Execute the audit defined in `templates/workspace-config/tool-server-audit.md` and deliver the filled table. This skill is the runbook; that document is the policy.

## Procedure

1. **Inventory every config in scope.** Check, at minimum: project-level `.mcp.json`, `.cursor/mcp.json`, `.vscode/mcp.json`, and the user-global equivalents. Global configs are the priority: they tax every project.

2. **Measure each config.**
   ```sh
   python3 scripts/tool-overhead.py <config> --json
   ```
   Prefer a tool-definition dump if the harness can produce one (measured beats estimated). Record per-server figures.

3. **Interrogate each server** (ask the user what cannot be read from logs):
   - Called in the last 14 days? By what workflow?
   - Daily, weekly, or rarer?
   - Relevant to all projects or one?
   - Could a plain CLI invocation replace it?

4. **Assign dispositions:** keep (narrowest sufficient scope), demote (global to per-project, or resident to attach-on-demand), remove. Default for "nobody can name a recent use" is remove; the config is version-controlled and reversible.

5. **Deliver:**
   - The filled approved-list table (columns: server, scope, est. standing tokens, used in last 14 days, justification, disposition, reviewed date).
   - Before/after standing overhead totals, and the per-session difference at the user's typical turn count.
   - The exact config edits to apply (but do not apply them without confirmation; changing tool configs mid-session also invalidates prompt caches, so recommend applying between sessions).

## Rules

- Never remove a server silently; every removal appears in the table with its justification.
- Flag overlapping servers (two providing the same capability) even when both are used.
- If a single server dominates the total, say so explicitly and check whether the harness supports deferred tool loading before recommending removal.
