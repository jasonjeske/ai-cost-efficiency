# AGENTS.md Template (Annotated)

This file is two things at once: a copy-pasteable template for a project instruction file (`AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, or equivalent), and an explanation of why each section earns its place.

**The economics of this file:** an instruction file is loaded into every request and re-read by the model on every turn, in every session, forever. At a rough 4 characters per token, every 400 characters you write costs about 100 tokens per turn. A 20-turn session pays that 20 times; a team of 30 developers pays it in every session of every day. Brevity here is not style, it is a standing cost decision. The test for every line: **will this line change agent behavior often enough to justify being re-read thousands of times?** If a rule matters rarely, put it in a linked document or a skill (`skills/`) that gets loaded on demand, and leave only the pointer here.

Sizing guidance: a strong instruction file usually lands well under 2,500 estimated tokens (check with `scripts/instruction-audit.py`). If yours is larger, it almost certainly contains reference material that should be on-demand instead of resident.

Everything below the rule is the template. Text in `> WHY:` blockquotes is annotation: delete every blockquote when you adopt it.

---

# Project: <name>

<One sentence: what this codebase is. One sentence: what the agent is usually asked to do here.>

> WHY: Orientation prevents the most expensive failure mode, a wrong first guess about what kind of project this is, which burns turns to unwind. Two sentences is the budget. The agent can read the README if it needs the story.

## Commands

```sh
<build command>            # build
<test command>             # run tests (use this before claiming done)
<lint/format command>      # lint and format
<run command>              # run locally
```

> WHY: This section has the best cost-benefit ratio in the file. Without it, the agent rediscovers commands by trial and error, and every failed guess plus its error output enters history and is re-billed each remaining turn. Four to eight lines here routinely saves multiples of their cost in the first session alone. Keep it to the commands the agent actually needs, not the full task catalog.

## Architecture in one breath

<3 to 6 bullets. Only what cannot be inferred by reading the code for two minutes: the load-bearing directories, where entry points live, the one pattern everything follows.>

- `src/<x>/` : <what lives here>
- `src/<y>/` : <what lives here>
- <the one non-obvious pattern, e.g. "all DB access goes through repositories in src/db, never inline SQL">

> WHY: Earns its place only for what is genuinely non-obvious. Do not describe what `ls` and a README reveal; the agent reads those once, on demand, which is cheaper than you re-billing a paraphrase every turn. The non-obvious pattern line is the valuable one: it prevents the agent from writing code that works but violates the house pattern, which triggers review rework, which triggers another session.

## Hard rules

<3 to 10 bullets maximum. Only rules that are (a) violated by default agent behavior and (b) expensive when violated.>

- <e.g. "Never edit files under generated/ ; regenerate with <command>">
- <e.g. "All user-facing strings go through the i18n layer">
- <e.g. "Do not add dependencies without asking">

> WHY: The word "hard" is the filter. A rule belongs here only if agents actually break it without the rule AND breaking it costs real rework. Style preferences the linter already enforces do not belong: the linter is free, this file is not. Worked example of the distinction:
>
> - Earns its place: "Never edit `generated/`; regenerate with `make gen`." Agents will absolutely edit generated files, and the damage surfaces two sessions later.
> - Does not earn its place: "Use meaningful variable names." The model already does this; the line is pure overhead.
> - Does not earn its place: "Follow PEP 8." The formatter enforces it for free.

## Verification

<How the agent proves work is done. One short list.>

1. <test command> passes
2. <lint command> clean
3. <any project-specific check, e.g. "migration up AND down tested">

> WHY: A definition of done cuts the longest sessions short. Without it, "done" is negotiated over several turns of show-and-check, and each of those turns re-reads the whole session. With it, the agent self-verifies and stops.

## On-demand references

<Pointers only. One line each. The agent reads these when relevant, and their content stays out of the per-turn bill.>

- Deploy procedure: `docs/deploy.md`
- API conventions: `docs/api-style.md`
- Release checklist: `skills/release/SKILL.md`

> WHY: This section is the pressure valve that keeps the whole file small. Anything long, rare, or reference-shaped goes behind a pointer: the pointer costs ~10 tokens per turn, the document costs nothing until the one session that needs it. Moving a 1,500-token deploy procedure from the body to a pointer saves ~1,490 tokens per turn in every session that is not a deploy. This is the single highest-leverage edit most oversized instruction files can make.

---

## Anti-patterns (delete this section too when adopting)

Seen repeatedly in real instruction files, all of them per-turn money on fire:

- **The pasted style guide.** Multi-page coding standards inline. Link it instead; better, enforce it with a linter and delete it.
- **The changelog.** "2025-10-12: fixed the auth bug by..." History belongs in git. Instruction files are for standing behavior.
- **The duplicate README.** Project marketing, feature lists, badges. The agent needs orientation, not persuasion.
- **The defensive essay.** Ten lines explaining why a rule exists. State the rule; put the rationale in a linked doc if anyone ever asks.
- **The kitchen-sink command list.** Every make target ever written. List the five the agent uses.
- **The stale rule.** Rules for code that was deleted last quarter. Stale rules are worse than missing ones: the agent obeys them, and you pay to transmit them every turn. Audit this file on a schedule (see `scripts/instruction-audit.py`), treat it like code.
