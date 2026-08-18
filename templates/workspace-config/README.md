# Workspace Configuration Baseline

Editor-level defaults that keep standing overhead down. Two principles drive everything in this directory:

1. **Attach per project, not globally.** Tool servers, rules files, and context sources configured globally are paid for in every session of every project, including the ones that never use them. The default posture is: global config is nearly empty; each project declares what it needs.
2. **Exclude what the agent should never index.** Build output, dependency trees, lockfiles, and generated code inflate every context-gathering operation. Excluding them makes retrieval cheaper AND better, since junk files also pollute search results and confuse the agent.

## Files here

| File | Use |
|---|---|
| `vscode-settings.jsonc` | Baseline workspace settings for VS Code (with GitHub Copilot or any agent extension). Copy the relevant keys into `.vscode/settings.json`. |
| `cursor-settings.jsonc` | Same baseline for Cursor (a VS Code fork, same settings format). |
| `cursorignore.example` | Example `.cursorignore` to keep noise out of Cursor's context gathering. |
| `mcp-servers.example.jsonc` | An annotated example of a minimal, per-project tool-server config. |
| `tool-server-audit.md` | The process and template for maintaining an audited tool-server list, for individuals and for org fleets. |

Note on file names: the `.jsonc` files here contain comments for annotation. VS Code and Cursor settings files tolerate comments; strict JSON consumers do not. Strip comments if your target file is plain JSON (`mcp.json` in some clients is strict).

## Where tool-server configs live (as of this writing; verify against your tool's docs)

- **Claude Code:** `.mcp.json` at the project root (project scope), `mcpServers` key. Also supports user scope; prefer project scope.
- **Cursor:** `.cursor/mcp.json` per project, `mcpServers` key; a global `~/.cursor/mcp.json` exists and is exactly the thing to keep near-empty.
- **VS Code:** `.vscode/mcp.json` per workspace, `servers` key; user-level configuration exists and the same near-empty rule applies.

These paths and key names change occasionally. The principle does not: **the per-project file is the right home for tool servers.**

## Quick checks

```sh
# What is the standing token cost of this project's tool config?
python3 ../../scripts/tool-overhead.py .mcp.json          # or .cursor/mcp.json, .vscode/mcp.json

# Are this project's instruction files oversized?
python3 ../../scripts/instruction-audit.py .
```
