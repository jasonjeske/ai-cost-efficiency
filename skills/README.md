# Skills

Packaged procedures an agent loads **on demand**, instead of carrying them in always-loaded instruction files.

## Why skills are a cost primitive

An instruction file is re-read every turn of every session; its cost is `size x turns x sessions`. A skill file costs nothing until the one session that needs it, where it costs `size x remaining turns of that session`. Any procedure that is long, detailed, and rarely needed (a release checklist, an audit process, a migration recipe) is strictly cheaper as a skill, and usually better too, because it can afford to be thorough without taxing every unrelated session.

Rule of thumb: **standing instructions hold behavior that applies to most turns; skills hold procedures that apply to some sessions.** If a section of your `AGENTS.md` starts with "when doing X...", it is probably a skill wearing the wrong file name.

## Format

Each skill is a directory containing a `SKILL.md` with a small frontmatter block (name, one-sentence description) and a procedure body. This layout is natively loadable by harnesses that support skill directories (Claude Code and compatible tools); for any other agent, the skill is just a markdown file the agent is pointed at ("follow skills/tool-catalog-audit/SKILL.md"), which works everywhere. The frontmatter description matters: in skill-aware harnesses it is the only part that is always loaded, so it should say precisely when to load the rest.

## Skills in this repo

| Skill | Procedure it packages |
|---|---|
| `cost-baseline/` | Baseline a project's standing overhead and session shape using the scripts, and report the four key numbers. |
| `tool-catalog-audit/` | Run the tool-server audit end to end and produce the approved-list table. |
| `session-postmortem/` | Analyze why a finished session was expensive and name the levers that would have cut it. |

Each one exists twice over: as a usable procedure, and as a demonstration of the pattern to copy for your own recurring procedures.
