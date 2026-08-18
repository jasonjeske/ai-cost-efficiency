---
name: session-postmortem
description: Analyze a finished (or dying) agent session for why it got expensive, attribute cost to its causes, and name the levers that would have cut it. Use when a session felt expensive or slow, hit context limits, or when asked why costs spiked.
---

# Session Postmortem

Turn "that session felt expensive" into an attributed cause and a concrete change. Input: the session transcript, the harness's session stats, or failing both, the user's account of what happened.

## Procedure

1. **Reconstruct the shape.** Establish: turn count, standing prefix size (instructions + tool catalog; measure with the scripts if configs are available), the largest single items in history (big tool outputs, pasted files, long error dumps), and whether the session covered one task or several.

2. **Attribute the cost** across the four standard buckets, roughly quantified with `session-cost.py` using the reconstructed numbers:
   - **Standing overhead:** prefix x turns.
   - **History re-read:** the quadratic term; driven by turn count.
   - **Payload events:** individual large insertions (a dumped log, a pasted file), each costing its size times the turns that followed it.
   - **Retry loops:** turns spent re-attempting after failures, including model-capability misses.

3. **Name the dominant bucket** and map it to its lever:
   - Standing overhead dominant: tool-catalog audit, instruction diet (`skills/tool-catalog-audit`, `templates/AGENTS.md`).
   - Re-read dominant: session should have been split at the task boundary; or the brief was thin and turns were spent negotiating scope (`standards/context-hygiene.md` items 1 to 3).
   - Payload dominant: the specific tool or habit that dumped it, fixed by output bounding (`standards/tool-design.md`) or by referencing paths instead of pasting.
   - Retry dominant: routing question; the task class may need a stronger tier, or a clean escalation instead of iterating on a polluted context (`routing/model-routing.md`).

4. **Deliver** a short report: shape summary (3 lines), cost attribution (4 buckets, estimated shares), the one dominant cause, the one change that would have cut the most, and the modeled saving if that change had been in place (re-run `session-cost.py` with the change applied).

## Rules

- Estimated shares are labeled as estimates; do not present modeled numbers as billing data.
- One dominant cause, one primary recommendation. A postmortem that recommends five things changes nothing.
- If the honest finding is "the session was fine, the task was just large," say exactly that. Not every expensive session is a defect, and false findings erode trust in the method.
