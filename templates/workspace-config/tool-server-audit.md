# Tool-Server Audit

The process for deciding which tool servers (MCP or otherwise) earn a place in a workspace, and for keeping that decision honest over time. Works at two scales: a single developer auditing their own setup in ten minutes, and an organization maintaining an approved list for a fleet.

## Why an audit exists

Tool catalogs are resent on every turn, called or not. Catalogs also only ever grow: adding a server takes one config line and feels free; nothing ever prompts removal. Without a periodic audit, standing overhead ratchets upward forever. The audit is the counter-ratchet.

## The audit, step by step

1. **Inventory.** Collect every tool config in scope: global client configs AND per-project files. The global ones matter most; anything there taxes every project.

2. **Measure.** For each config:
   ```sh
   python3 scripts/tool-overhead.py <path-to-config>
   ```
   Record the estimated standing tokens per server. If your client can dump actual registered tool definitions, feed that dump to the same script for a tighter estimate.

3. **Interrogate each server** with four questions:
   - **Usage:** was any tool from this server called in the last two weeks? (Most clients have logs or history; when in doubt, remove it and see who notices.)
   - **Frequency:** daily, weekly, or rarer? Rare-use servers should be attached for the session that needs them, not resident.
   - **Scope:** is it globally attached but only relevant to one project? Move it to that project's config.
   - **Substitutability:** does a plain CLI do the same job? A CLI the agent invokes costs tokens only when used; a resident tool server costs tokens always. For infrequent operations the CLI is almost always cheaper.

4. **Disposition.** Each server gets one of: **keep** (in the narrowest scope that covers real usage), **demote** (global to per-project, or resident to attach-on-demand), or **remove**.

5. **Record.** Fill the table below and date it. The table IS the approved list; a server not in the table is not in the config.

## The approved-list table

Keep this table next to the config it governs (repo root for a project, a shared doc for an org fleet).

| Server | Scope | Est. standing tokens | Used in last 14 days | Justification | Disposition | Reviewed |
|---|---|---|---|---|---|---|
| example: github | this project | (from tool-overhead.py) | yes, daily | PR and issue workflow | keep | YYYY-MM-DD |
| example: browser-automation | frontend repo only | (measure) | yes, weekly | UI verification | keep, per-project | YYYY-MM-DD |
| example: database-admin | none (attach on demand) | (measure) | once this month | monthly migration task | demote | YYYY-MM-DD |
| example: notes-connector | removed | (measure) | no | none found | remove | YYYY-MM-DD |

## Cadence

- **Individual:** audit when a session feels slow or expensive, and at minimum quarterly.
- **Organization:** quarterly, owned by whoever owns the developer platform. Publish the approved list; treat additions like dependency additions (a request with a justification, not a self-serve default). Pair the list with the merge-gate contract in `standards/tool-design.md` so internal servers are lean before they are ever approved.

## Red flags that fail an audit on sight

- A server present globally "just in case."
- A server nobody on the team can name a recent use for.
- A single server contributing a five-figure token estimate (common for large connector suites); demand deferred loading, a slimmed tool subset, or per-project scoping.
- Overlapping servers offering the same capability twice: the agent pays for both catalogs and picks between them by guesswork.
