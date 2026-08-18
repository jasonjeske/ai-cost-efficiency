# Tool Design Standard

The output contract every agent-facing tool must meet. "Tool" here means anything an agent calls: an MCP server tool, a CLI the agent runs, an internal script, a wrapped API.

## Why this is a cost standard, not a style guide

A tool touches the bill twice:

1. **Its definition is standing overhead.** The name, description, and input schema of every registered tool are serialized into every request, every turn, whether the tool is called or not. A typical definition runs on the order of 100 to 500 tokens (estimate; measure yours with `scripts/tool-overhead.py`). Multiply by tool count and by turn count.
2. **Its output becomes permanent history.** Whatever a tool returns is appended to the conversation and re-read, and re-billed, on every subsequent turn of the session. A 5,000-token response on turn 3 of a 30-turn session is paid for roughly 27 more times. Verbose output is not a one-time cost; it is a subscription the session cannot cancel.

A tool that dumps raw data is therefore expensive even when it is free to execute.

## The contract

Every agent-facing tool MUST:

### 1. Return the minimum that answers the question
Default output is a compact result, not a raw payload. Return the answer, the identifiers needed to drill down, and nothing else. If the underlying data is large, return a summary plus a handle (path, ID, URL) the agent can use to fetch detail on request.

### 2. Bound its output
Hard-cap default output at a small, documented size. Good defaults: 10 to 50 items for lists, a few thousand characters for text. Paginate or truncate beyond the cap, and say so explicitly in the output ("showing 20 of 1,340; use offset/limit"), so the agent knows truncation happened and can ask for more instead of hallucinating completeness.

### 3. Fail small and loud
Errors are one to three lines: what failed, why, what to try. Never return a stack trace, a full request/response dump, or the entire input back. An error message is history too.

### 4. Offer a verbose path, off by default
A `verbose` or `full` parameter may exist for the rare case the agent genuinely needs raw detail. The default must be the compact form. Design rule: the expensive path is opt-in, never opt-out.

### 5. Keep the definition lean
- Description: one to three sentences saying what the tool does and when to use it. Cut sales language, restated parameter lists, and examples the schema already implies. Keep a "when NOT to use" clause only if agents demonstrably misuse the tool without it.
- Schema: only parameters agents actually set. Every optional parameter with a long description is standing overhead on every turn of every session in every workspace that loads the server.

### 6. Prefer one capable tool over many narrow ones
Ten single-purpose tools cost ten definitions of standing overhead. One tool with a mode parameter costs one. Split tools only when the schemas genuinely diverge or when merging would force a confusing interface, since a confused agent burns turns, and turns are the most expensive thing in the system.

### 7. Return text shaped for a reader, not a parser
Agents read output as language. Compact tables, labeled fields, and plain sentences beat deeply nested JSON with long keys. If structured output is required, keep keys short and omit null/empty fields.

## Review checklist

Use in code review for any new or changed agent-facing tool. All answers should be yes.

- [ ] Is the default output bounded, with the bound documented?
- [ ] Does truncated output say it was truncated and how to get more?
- [ ] Is the compact form the default and verbose opt-in?
- [ ] Are errors under ~3 lines with an actionable message?
- [ ] Is the description under ~3 sentences, with no content the schema already carries?
- [ ] Could this tool merge with an existing one instead of adding a definition?
- [ ] Was the definition's token cost measured (`scripts/tool-overhead.py`) and recorded in the PR?

## For organizations

Make this contract a merge gate for internal MCP servers and agent tools, and re-audit the deployed catalog quarterly: catalogs only ever grow, and every unused registered tool is overhead on every turn of every user's session. The audit process and an approved-list template live in `templates/workspace-config/`.
