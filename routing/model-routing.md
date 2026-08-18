# Model Routing

Task class to model tier, maintained as an empirical table. Two warnings before the table:

1. **This table is empirical and goes stale.** Every model release can flip a row. A row without a recent review date is a hypothesis, not a policy. Treat the format as the durable asset and the contents as perishable.
2. **This repo cannot fill it in for you.** Which model one-shots which task class depends on your codebase, your prompts, and the models available to you this quarter. The seed rows below are illustrative placeholders showing the format; replace them with your own measured rows.

## The routing rule

> **Use the lowest-cost model tier that reliably completes the task class in a single pass. Determine "reliably" empirically, never by price list.**

Why "cheaper model" backfires so often: a weaker model that fails buys you retries, and retries are billed on a grown context (the failed attempt, its output, your correction, all re-read every subsequent turn), plus your time supervising. A model with a 6x lower per-token rate that averages three attempts on a doubled context is not cheaper, and that is before counting the human minutes. Conversely, routing genuinely easy, mechanical task classes to a frontier model pays a premium for headroom that goes unused. Both errors come from routing by rate instead of by measured single-pass reliability.

Tiers, not model names: model names churn monthly. Define tiers once ("frontier" = your strongest available, "mid" = the capable default, "small" = the fast/cheap one) and map current model names to tiers in one place, so the table survives releases.

## The table

Columns are mandatory, especially Evidence: a row without evidence is deleted on the next review.

| Task class | Tier | Single-pass success (measured) | Evidence (experiment link/date/n) | Reviewed | Next review |
|---|---|---|---|---|---|
| *(seed example)* Mechanical edits: rename across files, apply a known codemod, format migrations | small | *(fill in)* | *(link your experiment; n>=10)* | YYYY-MM-DD | +3 months |
| *(seed example)* Well-specified single-file changes with tests that define done | mid | *(fill in)* | *(link)* | YYYY-MM-DD | +3 months |
| *(seed example)* Multi-file features, cross-cutting refactors, unfamiliar codebases | frontier | *(fill in)* | *(link)* | YYYY-MM-DD | +3 months |
| *(seed example)* Debugging with an unclear reproduction | frontier | *(fill in)* | *(link)* | YYYY-MM-DD | +3 months |
| *(seed example)* Commit messages, PR descriptions, changelog entries | small | *(fill in)* | *(link)* | YYYY-MM-DD | +3 months |

The seed rows reflect a common pattern (mechanical work routes down, ambiguous work routes up), but "common pattern" is exactly the kind of claim this table exists to replace with your data.

## How to add a row (the experiment)

1. **Define the task class** tightly enough that instances are interchangeable: "rename a public function and update call sites, repo under 50k lines" is a class; "backend work" is not.
2. **Collect 10+ real instances** from your actual backlog. Synthetic tasks flatter small models.
3. **Run each instance once per candidate tier** with the same brief, in a fresh session. One attempt. No coaching. Record: completed to standard, yes or no (define "standard" first: tests pass, no rework needed).
4. **Compute single-pass success per tier** and the cost per completed task per tier using the method in `measurement/`. Tokens per attempt matter less than attempts per completion.
5. **Route to the cheapest tier whose single-pass rate clears your bar** (0.9 is a sensible default bar; below that, retry costs dominate).
6. **Write the row** with the numbers, the date, sample size, and a link to the raw log. Set a review date no more than one quarter out.

## Escalation policy (the safety valve)

Routing is a default, not a cage. Two standing rules make a routing table safe to follow:

- **Escalate on first failure.** If the routed tier fails an instance once, re-run the task on the next tier up in a fresh session rather than iterating with the failed model on a polluted context. One clean escalation is almost always cheaper than a retry loop.
- **Log every escalation.** Escalations are the signal that a row has gone stale. A row that escalates more than roughly one time in ten is due for re-measurement, early.

## Review cadence

Re-review each row quarterly, and immediately when: a new model version ships in a tier you use, your harness changes how it compacts context or loads tools, or the escalation log flags a row. Delete rows for task classes you no longer perform; a stale table is worse than a short one.
