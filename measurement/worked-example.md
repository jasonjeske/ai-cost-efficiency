# Worked Example

Two small end-to-end examples of the method in `README.md`.

**Every number on this page is illustrative, invented so the arithmetic can be followed and checked.** None of it is a measurement of any real product, model, or team, and the hypothetical rates exist only so the math has units. Substitute your own measurements and your provider's current rates.

## Example 1: An individual baselines standing overhead and session shape

**Baseline (measured with this repo's scripts, numbers illustrative):**

- `instruction-audit.py` on the project: instruction files total ~3,000 estimated tokens. Fine.
- `tool-overhead.py` on the globally attached server config: ~18,000 estimated tokens of standing catalog, from five servers, two of which the developer cannot remember using.
- Harness system prompt assumed at ~4,000 tokens. Standing prefix: **~25,000 tokens per turn.**
- Session logs for a week: typical task runs one session of about 14 turns, with per-turn averages near the `session-cost.py` defaults (user 150, assistant 600, tool output 1,200; so history grows ~1,950 tokens per turn).

**Model the baseline:**

```sh
python3 scripts/session-cost.py --system 7000 --tools 18000 --turns 14
```

Using the closed form (prefix F = 25,000; per-turn history growth d = 1,950; N = 14):

```
total input = N x (F + user) + d x N x (N - 1) / 2
            = 14 x 25,150 + 1,950 x 91
            = 352,100 + 177,450  =  ~529,600 tokens per task
```

Overhead share = 352,100 / 529,600 = **~66% of all input tokens are the standing prefix being re-read.** The biggest lever is not "prompt better," it is configuration.

**Change 1: audit the tool servers** (process in `templates/workspace-config/tool-server-audit.md`). Two unused servers removed, one demoted to a single project: catalog drops from 18,000 to 6,000 tokens; prefix falls to 13,000.

```
total input = 14 x 13,150 + 177,450 = ~361,600 tokens per task   (~32% lower)
```

No behavior change, one afternoon, every future session cheaper.

**Change 2: split at the natural boundary.** The 14-turn sessions turn out to be two tasks back to back. Two fresh 7-turn sessions:

```
per session = 7 x 13,150 + 1,950 x 21 = 133,000;  x2 = ~266,000 tokens  (~26% below change 1)
```

Combined effect: ~529,600 to ~266,000 input tokens for the same work, **roughly half**, before prompt caching discounts are even considered. Both levers were visible only because the baseline was measured.

## Example 2: A routing experiment (why the cheap tier lost)

Task class: "well-specified single-file change with tests that define done." Ten real backlog instances per tier, one attempt each in a fresh session, per the experiment recipe in `routing/model-routing.md`. "Completed to standard" was defined first: tests pass, merged without rework.

**Hypothetical rates, purely for arithmetic** (substitute your provider's current pricing page): mid tier $3.00 per million input tokens, $0.30 cached, $15.00 output; small tier one fifth of each ($0.60 / $0.06 / $3.00).

**Mid tier, 10 tasks:** 9 completed single-pass, 1 on a second attempt; 10 of 10 completed. Totals: 240k fresh input, 810k cached input, 46k output.

```
cost = 0.24 x $3.00 + 0.81 x $0.30 + 0.046 x $15.00 = $1.65
CPCT = $1.65 / 10 completed = ~$0.17 per completed task    single-pass: 90%
```

**Small tier, 10 tasks:** 5 completed single-pass, 1 on a second attempt; 4 never reached standard on the small tier (abandoned after retries) and were redone on mid. The retries are what inflate the totals: each retry restarts with corrections and failed-attempt context, and abandoned sessions still bill. Small-tier totals: 900k fresh input, 4.5M cached input, 180k output. Plus the mid-tier redo of 4 tasks (40% of the mid totals above).

```
small spend = 0.90 x $0.60 + 4.5 x $0.06 + 0.18 x $3.00 = $1.35
mid redo    = 0.096 x $3.00 + 0.324 x $0.30 + 0.0184 x $15.00 = $0.66
CPCT = ($1.35 + $0.66) / 10 completed = ~$0.20 per completed task    single-pass: 50%
```

**Result: the tier with a 5x lower rate card produced a ~20% HIGHER cost per completed task**, plus the unpriced human time spent shepherding retries and re-briefing the redo sessions. This is the normal shape of the outcome whenever single-pass reliability drops steeply between tiers; the cheap tier wins only on task classes it genuinely one-shots (which is exactly what the routing table exists to record).

**Routing decision logged:** this task class routes to mid; the small tier gets re-tested when a new small model ships. Row added to `routing/model-routing.md` with the raw log linked and a review date one quarter out.
