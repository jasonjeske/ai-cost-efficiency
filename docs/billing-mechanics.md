# Billing Mechanics

The longer explanation behind the one-page standard. Nothing here quotes a price. Mechanics are stable across providers; rates are not, so rates belong on your provider's pricing page, not in a repo.

## 1. The model is stateless; the client fakes memory

An LLM API call is a pure function: tokens in, tokens out. The model retains nothing between calls. The "conversation" you experience is the client's doing: on each turn it assembles a request containing, in order:

1. The system prompt (harness instructions, safety text, your instruction files).
2. The tool catalog (every registered tool's name, description, and input schema).
3. The full message history: every prior user message, assistant message, tool call, and tool result.
4. Your new message.

The model reads all of it, every turn, and you are billed for all of it as input tokens, every turn.

## 2. Why cost is roughly quadratic in session length

Let `F` be the fixed prefix (system prompt plus tool catalog) and `d` the average tokens a turn adds to history (your message, the assistant's reply, tool output). The input billed on turn `n` is about:

```
input(n) = F + (n - 1) * d
```

Summed over an `N`-turn session:

```
total_input(N) = N * F + d * N * (N - 1) / 2
```

The second term is the killer: it grows with `N^2`. Doubling session length roughly quadruples the history component of the bill. This is why the cheapest question you ask is the one asked early in a short session, and why the same question at turn 40 costs a multiple of what it cost at turn 4. `scripts/session-cost.py` computes this with your own numbers, including what splitting the work across fresh sessions changes.

Two practical corollaries:

- **Verbose tool output compounds.** A large tool result lands in history and is re-billed on every remaining turn. Cost of a tool result is roughly `size * remaining_turns`, not `size`.
- **Ending a session is a cost action.** History dies with the session. A written summary carried forward costs its own size per turn, not the transcript's.

## 3. Standing overhead: the tool catalog

Every tool definition registered with the session is serialized into every request. Individual definitions typically run on the order of 100 to 500 tokens depending on description length and schema complexity (order-of-magnitude estimate; your numbers come from `scripts/tool-overhead.py`). This compounds in two directions:

- **Across tools:** community measurements of multi-server MCP setups commonly land in the tens of thousands of tokens of standing catalog, with heavily loaded configurations reported in the 30,000 to 60,000 token range (published-measurement range, not a law; measure your own).
- **Across turns:** standing overhead is paid per turn. A 40,000-token catalog over a 25-turn session is a million input tokens before any work happens.

This is why "just attach all the servers globally" is one of the most expensive defaults in agentic tooling, and why the workspace templates in this repo attach servers per project.

Some harnesses mitigate this with deferred or searchable tool loading (only names resident, schemas fetched on demand). If yours offers it, use it; if not, the audit process in `templates/workspace-config/tool-server-audit.md` is the manual equivalent.

## 4. Prompt caching: the prefix discount

Most major providers discount input tokens that exactly repeat the prefix of a recent request, because they can reuse the internal computation. Details differ (some cache implicitly, some require explicit breakpoints, minimum cacheable sizes and time windows vary), but the shape is universal:

- The discount applies to an **exact, contiguous prefix match**. One changed byte at position `k` invalidates everything after `k`.
- Conversations are naturally cache-friendly: each turn's request is the previous request plus appended messages, so the whole previous request is a matching prefix.
- Therefore: **order context by volatility.** Stable content first (system prompt, instructions, tool catalog), volatile content last (messages). This is already how good harnesses assemble requests, and it is why mid-session configuration changes are expensive: editing an instruction file or registering a tool mutates the early prefix and invalidates the cache for everything after it, for the rest of the session.

Caching softens the quadratic curve substantially; it does not repeal it. Cached tokens are discounted, not free, cache writes can carry their own premium on some platforms, and cache entries expire. Check your provider's documentation for current discount rates, minimums, and lifetimes. `scripts/session-cost.py` models caching with a discount factor you supply.

## 5. Model routing: why "cheaper" often is not

Per-token rates differ sharply between model tiers, which invites a tempting shortcut: route everything to the small model. The failure mode is reliability. If the small model completes a task class in one pass 60% of the time, the other 40% of attempts buy you retries, and retries are not billed at turn-1 prices: they arrive with a grown context (failed attempt, error output, your correction), plus your time. Multiply a "6x cheaper" rate by 3 attempts on a context that doubled and the saving is gone; add the human minutes and it is negative.

The stable rule: **use the lowest-cost model that reliably completes the task class in a single pass, and determine "reliably" empirically.** Frontier models earn their rate on tasks where weaker models retry; small models earn their place on task classes where they genuinely one-shot. The routing table format in `routing/model-routing.md` exists to hold those empirical findings, with the evidence attached and an expiry mindset, because every new model release can flip a row.

## 6. The metric: cost per completed task

Tokens consumed is the wrong objective. Minimizing it rewards not using AI, which is a productivity cut disguised as savings. The right unit:

```
cost per completed task = total spend on a task class / tasks completed to standard
```

"Completed to standard" is defined before measuring (merged without rework, tests pass, reviewer accepted). A change is an improvement only if it lowers this number, or completes more tasks at the same number. The measurement method, a logging template, and a worked example are in `measurement/`.

## 7. What this repo deliberately does not model

- **Exact tokenization.** Tokenizers are model-specific. All scripts use a characters-per-token heuristic, adjustable via `--chars-per-token`, adequate for ranking and budgeting.
- **Subscription plans and rate limits.** Flat-rate plans change the marginal price of a token to zero until you hit a limit, at which point the mechanics above decide what you get done inside the limit. The efficiency practices are identical; the unit changes from dollars to capacity.
- **Provider-specific compaction.** Harnesses summarize or trim history at different thresholds and with different strategies. Compaction reduces the re-read cost of old turns at the price of fidelity; it does not change the incentive to keep sessions short and output compact.
