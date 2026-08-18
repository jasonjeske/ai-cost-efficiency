# Editor Setup: Cursor and VS Code with GitHub Copilot

The short answer to "does this actually work in my editor": yes, and the parts
that depend on your editor reading a file are documented by the vendors
themselves. This page names the exact filenames each editor reads, cites the
vendor documentation for each claim, and ends with a five minute walkthrough you
can run in front of someone to prove it.

Nothing here is a plugin or an install. Everything is a file your editor already
looks for, or a script that runs on its own.

## What is portable, and what is editor-specific

| Part of this repo | Works where | Depends on the editor? |
|---|---|---|
| `scripts/` | Any terminal with Python 3.8+ | No. Runs standalone. |
| `standards/`, `measurement/`, `routing/` | Anywhere | No. These are practices and methods. |
| `templates/AGENTS.md` | Cursor, Copilot, and other agents | Yes, and both vendors document support. |
| `templates/workspace-config/` | Cursor and VS Code | Yes, uses stock editor settings. |
| `skills/` | Any agent that supports on-demand procedure files | Partly. See the note below. |

## Cursor

Cursor reads three kinds of instruction file:

- **`AGENTS.md`** in the project root. Cursor's documentation describes it as
  "agent instructions in markdown format" and a "simple alternative to
  `.cursor/rules`", supported in the project root and in subdirectories, where a
  nested file takes precedence over its parent. This is the file to start with.
- **`.cursor/rules/*.mdc`** for rules that should only load when certain files
  are in play. These use frontmatter to declare globs, so they are scoped rather
  than always-on. A plain `.md` file in that directory is ignored, because there
  is no frontmatter to scope it.
- **User rules**, set in Cursor's settings, applied across every project.

Two other files matter for cost:

- **`.cursorignore`** in the project root, same syntax as `.gitignore`, keeps
  paths out of indexing and context gathering entirely. See
  `templates/workspace-config/cursorignore.example`.
- **`.cursor/mcp.json`** per project for tool servers. Keep the global
  `~/.cursor/mcp.json` near empty, because a globally attached server is standing
  overhead in every session of every project.

Source: Cursor documentation, Rules, https://cursor.com/docs/rules

## VS Code with GitHub Copilot

GitHub's documentation lists these repository instruction files:

- **`AGENTS.md`** (and equivalently `CLAUDE.md` or `GEMINI.md`), which GitHub
  documents as agent instructions that can be stored anywhere in the repository,
  with the nearest file taking precedence, or as a single file in the repository
  root.
- **`.github/copilot-instructions.md`**, which applies to all requests made in
  the context of the repository.
- **`.github/instructions/NAME.instructions.md`**, which use glob patterns in
  frontmatter to apply only to matching paths. This is the Copilot equivalent of
  scoped rules.

Tool servers are configured per workspace in **`.vscode/mcp.json`**.

Source: GitHub Docs, adding repository custom instructions for GitHub Copilot,
https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot

## The practical consequence

Because both editors read `AGENTS.md`, one instruction file covers both. That is
the whole reason this repo standardizes on it rather than maintaining a separate
file per vendor. Scoped rules still differ (`.mdc` for Cursor,
`.instructions.md` for Copilot), so keep the always-loaded content in `AGENTS.md`
and push conditional content into whichever scoped format your editor uses.

Keeping one always-loaded file instead of several is itself the cost argument in
miniature: that file is re-read on every turn, so duplicating it per vendor means
paying for the duplicate forever.

## A note on `skills/`

On-demand procedure files are not a cross-vendor standard the way `AGENTS.md` is.
Some agents load them natively; others do not. The portable version of the idea
works everywhere: keep the procedure in a file, and put a one line pointer to it
in `AGENTS.md`. The agent reads the procedure only in the session that needs it,
which is the entire point. If your agent supports a native skill mechanism, use
it; if not, the pointer costs one line.

## Prove it in five minutes

Run this in front of whoever is asking. Every step produces a number.

```sh
# 1. Standing cost of your tool servers, per turn, whether or not you call them.
python3 scripts/tool-overhead.py .cursor/mcp.json
python3 scripts/tool-overhead.py .vscode/mcp.json

# 2. What your instruction files cost on every single turn.
python3 scripts/instruction-audit.py .

# 3. What an agent pays to read a given file set.
python3 scripts/context-size.py src/

# 4. The re-read mechanic, with the session length you actually work at.
python3 scripts/session-cost.py --turns 30
python3 scripts/session-cost.py --turns 30 --split 3
```

Step 4 is the one that lands. It shows the same work costing materially less when
split into shorter sessions, which is a habit change with no tooling, no budget,
and no approval required.

Then make one change and re-measure: detach a tool server you never call, or cut
your instruction file down, and run steps 1 and 2 again. The delta is the proof.

## Honest limits

- Token figures from these scripts are estimates using a characters per token
  heuristic, not exact tokenizer counts. They are accurate enough to rank and to
  decide, not to reconcile an invoice.
- A server config lists servers, not the tools inside them, so per server figures
  are estimated from a tool count assumption. If your client can export its
  registered tool definitions, feed that dump instead and the numbers become
  measured rather than estimated.
- Editor behavior changes between releases. The filenames above are cited to
  vendor documentation, and vendor documentation is the thing to check if
  something does not load.
