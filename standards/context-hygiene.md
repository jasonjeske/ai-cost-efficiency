# Context Hygiene

The individual practices. Deliberately one page: this file is meant to be internalized, not referenced. Everything here follows from one fact: **the model re-reads the entire conversation, including all standing overhead, on every turn.**

## Session discipline

1. **One task, one session.** Start a fresh session per task. Carrying task B on top of task A's history means paying to re-read A's context on every turn of B, for zero benefit. Fresh context is the single cheapest optimization that exists.

2. **End sessions at the natural boundary, not at the context limit.** When the task completes, stop. If a follow-up task needs some of the outcome, carry forward a written summary (a file, a commit message, a handoff note), not the conversation. A 200-word summary re-read each turn is cheap; a 40-turn transcript re-read each turn is not.

3. **Front-load the brief.** State the goal, constraints, relevant file paths, and acceptance criteria in the first message. A complete first message that succeeds in 3 turns beats a vague one that succeeds in 12, and not linearly: later turns re-pay for all earlier ones, so cutting session length from 12 turns to 3 cuts cost far more than 4x.

4. **Do not paste what the agent can read.** Pasting a whole file into the chat puts it in history forever, re-billed every turn. Naming the path lets the agent read what it needs, once, and lets compaction drop it later.

5. **Restart when the session sours.** If the agent is confused, a long argument with a confused context costs more than a clean restart with a better brief. The sunk transcript is not an asset; it is a per-turn liability.

## Standing overhead discipline

6. **Instruction files are billed every turn. Budget them.** Keep always-loaded instructions (`AGENTS.md`, `CLAUDE.md`, rules files) to durable, high-frequency rules. A line that matters once a month belongs in an on-demand document or skill, not in the standing file. Audit with `scripts/instruction-audit.py`.

7. **Carry only the tool servers the workspace actually uses.** Every registered tool's definition is resent every turn, called or not. Attach tool servers per project, not globally; disable what a project does not need. Audit with `scripts/tool-overhead.py`. The process for keeping an approved list is in `templates/workspace-config/`.

8. **Keep the prefix stable.** Prompt caching discounts a repeated request prefix. Do not edit instruction files, add tool servers, or change system-level settings mid-session; each such change invalidates the cache for the rest of the session. Make configuration changes between sessions.

## Output discipline

9. **Constrain tool and command output.** Ask for `--quiet` flags, head/tail limits, and summaries. A verbose test run or a full log dump enters history once and is then re-read every remaining turn. When you build tools, the contract in `standards/tool-design.md` applies.

10. **Prefer references over transcripts in handoffs.** When work moves between sessions, agents, or people, hand over paths, diffs, and summaries. Never replay a conversation into another conversation.

## Model discipline

11. **Route by task class, empirically.** Use the lowest-cost model that reliably completes the task class in a single pass. Reliability is measured, not assumed: a cheap model that needs multiple attempts usually costs more than a stronger one that finishes first try, because retries arrive with a grown context. See `routing/model-routing.md`.

12. **Judge cost per completed task, never tokens.** A session that used fewer tokens and did not finish the task saved nothing. Method in `measurement/`.
