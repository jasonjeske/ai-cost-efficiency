# Measurement: Baseline Consumption and Cost per Completed Task

A concrete, copy-pasteable method. The point of measuring is to make one number visible and drive it down:

```
cost per completed task (CPCT) = spend attributed to a task class / tasks completed to standard
```

Not tokens consumed. Tokens-consumed as a target rewards using AI less, which quietly cuts productivity while reporting "savings." CPCT rewards completing the same work for less, which is the actual goal.

## Step 0: Define "completed to standard" first

Write the definition down before collecting any data, per task class. Examples that work: "merged without follow-up fixes within 3 days," "tests pass and reviewer approved without requesting rework," "document accepted by requester as-is." If a task needed a human to redo the work, it was not completed by the AI, whatever the transcript looks like. Deciding this after seeing the data is how measurement becomes theater.

## Step 1: Instrument (choose the best source you have)

In descending order of quality:

1. **Provider/API usage export.** If you run through an API key or gateway, the provider's usage dashboard or export gives exact input/output/cached token counts, often taggable per key. Best source; use one key or tag per project or team.
2. **Harness session data.** Most agent CLIs and IDE agents expose per-session token or cost readouts (a cost command, a status line, session logs on disk). Record the session total when you close the session.
3. **Estimates from this repo's scripts.** If you can see none of the above (some subscription plans hide token counts), model it: measure your standing overhead with `tool-overhead.py` and `instruction-audit.py`, then use `session-cost.py` with your observed turn counts. Label everything downstream as estimated.

On flat-rate subscription plans, dollars are invisible but capacity is not: use tokens (or the plan's own utilization metric) as the spend numerator. CPCT works in any consistent unit.

## Step 2: Log per task, not per session

One row per task in `session-log.template.csv` (copy it; the `.gitignore` here keeps filled logs out of the repo because logs can leak paths and prompt fragments). A task may span several sessions; sum them into the row. The columns that matter and why:

- `task_class`: the unit of routing and comparison. Use the same class names as your routing table.
- `model_tier`: what actually ran, so tiers can be compared.
- `sessions`, `turns_total`: session-shape data; the levers in `standards/context-hygiene.md` move these.
- `input_tokens`, `cached_input_tokens`, `output_tokens`: from your source in step 1. Estimated is fine if labeled.
- `attempts`: how many independent tries (including abandoned sessions) the task took. This is the number that exposes false economies of weak models.
- `completed_to_standard`: y/n against the step 0 definition.
- `cost_usd`: only if you have real rates; otherwise leave empty and work in tokens.

Discipline note: log abandoned attempts. The failed session that got thrown away is exactly the cost that makes "the cheap model is cheaper" false, and it is the first thing informal accounting forgets.

## Step 3: Baseline for two weeks, then compute

Two weeks of normal work, no behavior changes yet. Then, per task class:

```
CPCT           = sum(spend) / count(completed_to_standard = y)
single-pass %  = count(attempts = 1 AND completed) / count(all tasks)
avg turns      = mean(turns_total)
overhead share = (standing prefix tokens x total turns) / total input tokens
```

The four numbers point at the four levers: routing (CPCT by tier), briefing quality (single-pass %), session discipline (avg turns), and configuration (overhead share).

## Step 4: Change one thing, re-measure

Pick the worst number, apply the matching practice from this repo, run another two weeks, compare CPCT. One change at a time, or the comparison means nothing. Typical first moves, in order of effort:

1. Overhead share high: cut tool servers and instruction files (an afternoon, no behavior change needed).
2. Avg turns high: enforce one-task-one-session and front-loaded briefs.
3. Single-pass % low on a cheap tier: escalate that task class one tier and compare CPCT, not rate cards.

## Step 5 (organizations): roll up honestly

- Aggregate by task class, never a single blended number: a blended CPCT hides a cheap class subsidizing an expensive one.
- Report CPCT next to completion volume. CPCT falling while completions fall is not a win; that is the tokens-consumed trap wearing a better metric.
- Keep the raw logs; publish the method with the numbers. A CPCT figure nobody can audit will be gamed within a quarter.

A worked end-to-end example with (clearly labeled, illustrative) numbers: `worked-example.md`.
