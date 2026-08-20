# Agent Integration

ACE is a local Python CLI. It does not install editor extensions, modify vendor settings, start a service, or connect to a vendor account. Run it from this checkout with `python3 scripts/ace.py`; use an output path outside the workspace.

## Common pattern

Keep the always-loaded project instruction short and point deeper work to the on-demand skill:

```md
For local agent-cost work, read skills/agentic-cost-optimization/SKILL.md.
```

Then run the explicit, review-only chain from a terminal:

```sh
mkdir -p /tmp/ace-results
python3 scripts/ace.py audit /path/to/workspace --adapter <adapter> --json --output /tmp/ace-results/audit.json
python3 scripts/ace.py propose /path/to/workspace --audit /tmp/ace-results/audit.json --json --output /tmp/ace-results/candidate.json
python3 scripts/ace.py verify /path/to/workspace --candidate /tmp/ace-results/candidate.json --json --output /tmp/ace-results/verification.json
```

Replace `<adapter>` with `claude-code`, `codex`, `cursor`, or `vscode-copilot`. `--adapter auto` succeeds only when the detected markers resolve to exactly one supported adapter. Multiple markers for that same adapter are valid. Review the candidate before verification and apply nothing automatically.

## Claude Code

Use the project instruction mechanism configured for the Claude Code version in use, commonly `CLAUDE.md`; ACE also inventories `AGENTS.md`, `CLAUDE.md`, `CLAUDE.local.md`, and a workspace `.mcp.json` when selected as `claude-code`. Put a short pointer to the skill in the project guidance rather than copying the procedure into every session. Invoke ACE from Claude Code's terminal or another terminal in the checkout. Supply a tool-definition dump only when you have one locally.

## Codex

Keep repository guidance in `AGENTS.md` where that fits the Codex workflow, with the same short pointer to the skill. Select `--adapter codex` and invoke the CLI from a terminal. In this slice, Codex workspace tool configuration and local session usage remain unavailable capabilities. A measurement CSV or explicit tool-definition dump can provide separate evidence, but does not change those adapter capability states. Do not assume an automatic skill loader or installer.

## Cursor

Cursor documents root and nested `AGENTS.md` files and scoped `.cursor/rules/*.mdc` rules. Keep the ACE pointer in concise project guidance and use scoped rules for conditional instructions. Select `--adapter cursor`; ACE can inventory `.cursor/mcp.json`, but it does not change it. See [editor setup](editor-setup.md) for the documented filenames and Cursor reference.

## VS Code with GitHub Copilot

GitHub documents repository guidance such as `AGENTS.md`, `.github/copilot-instructions.md`, and scoped `.github/instructions/*.instructions.md`. Put the short pointer in the guidance file your workspace uses, then run ACE in the integrated terminal or another terminal. Select `--adapter vscode-copilot`; ACE can inventory `.vscode/mcp.json` but does not install, alter, or activate it. See [editor setup](editor-setup.md) for documented filenames and the GitHub reference.

## Boundaries

The CLI is local-first and deterministic. It does not make network calls, read billing accounts, infer task completion from chats, or apply candidates to the workspace. Tool and instruction reductions can be verified immediately as configuration changes, but CPCT requires comparable post-change task evidence and quality guardrails.
