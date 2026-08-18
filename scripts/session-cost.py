#!/usr/bin/env python3
"""Model the cost of an agent session, including the re-read mechanic.

An LLM is stateless: every turn resends the fixed prefix (system prompt +
instruction files + tool catalog) plus the entire accumulated history. This
tool computes billed input/output tokens across a session, shows the roughly
quadratic growth, models prompt caching with a discount factor you supply,
and compares against splitting the same work into multiple fresh sessions.

All token figures are estimates in tokens, not dollars. To see money, pass
your provider's current rates (from their pricing page) via --price-input /
--price-cached / --price-output, in dollars per million tokens.

Examples:
  session-cost.py                          # default illustrative scenario
  session-cost.py --turns 40 --tools 30000
  session-cost.py --turns 30 --split 3     # same work, 3 fresh sessions
  session-cost.py --turns 30 --json
"""

import argparse
import json
import sys


def simulate(turns, system, tools, user, assistant, tool_output, cache_discount):
    """Simulate one session. Returns totals and per-turn samples.

    Caching model: on turn i, the previous request is an exact prefix of the
    current one, so everything except the newly appended tokens (previous
    turn's assistant reply + tool output, plus the new user message) reads
    from cache. Cached tokens are billed at input * cache_discount.
    """
    fixed = system + tools
    history = 0
    total_input = 0
    total_output = 0
    total_fresh = 0
    total_cached = 0
    per_turn = []
    for i in range(1, turns + 1):
        turn_input = fixed + history + user
        if i == 1:
            fresh = turn_input
        else:
            fresh = user + assistant + tool_output
        cached = turn_input - fresh
        per_turn.append({"turn": i, "input": turn_input, "fresh": fresh, "cached": cached})
        total_input += turn_input
        total_output += assistant
        total_fresh += fresh
        total_cached += cached
        history += user + assistant + tool_output
    effective_input = total_fresh + total_cached * cache_discount
    return {
        "turns": turns,
        "fixed_prefix_tokens": fixed,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "fresh_input_tokens": total_fresh,
        "cached_input_tokens": total_cached,
        "cache_discount": cache_discount,
        "effective_input_tokens_with_cache": int(round(effective_input)),
        "per_turn": per_turn,
    }


def split_sessions(total_turns, k):
    """Distribute total_turns across k sessions as evenly as possible."""
    base, extra = divmod(total_turns, k)
    return [base + (1 if s < extra else 0) for s in range(k)]


def fmt(n):
    return f"{int(round(n)):,}"


def sample_rows(per_turn, max_rows=10):
    n = len(per_turn)
    if n <= max_rows:
        return per_turn
    idx = sorted({round(i * (n - 1) / (max_rows - 1)) for i in range(max_rows)})
    return [per_turn[i] for i in idx]


def money(tokens_in_fresh, tokens_in_cached, tokens_out, args):
    if args.price_input is None:
        return None
    p_in = args.price_input
    p_cached = args.price_cached if args.price_cached is not None else p_in
    p_out = args.price_output if args.price_output is not None else p_in
    return (tokens_in_fresh * p_in + tokens_in_cached * p_cached + tokens_out * p_out) / 1_000_000


def main():
    ap = argparse.ArgumentParser(
        prog="session-cost.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--turns", type=int, default=20, help="turns in the session (default 20)")
    ap.add_argument("--system", type=int, default=5000,
                    help="system prompt + instruction file tokens (default 5000, illustrative)")
    ap.add_argument("--tools", type=int, default=15000,
                    help="tool catalog tokens (default 15000, illustrative; measure yours with tool-overhead.py)")
    ap.add_argument("--user", type=int, default=150, help="avg user message tokens per turn (default 150)")
    ap.add_argument("--assistant", type=int, default=600, help="avg assistant reply tokens per turn (default 600)")
    ap.add_argument("--tool-output", type=int, default=1200,
                    help="avg tool-result tokens entering history per turn (default 1200)")
    ap.add_argument("--cache-discount", type=float, default=0.1,
                    help="price multiplier for cached input tokens, 0..1 (default 0.1; "
                         "check your provider's pricing page, some providers do not cache at all: use 1.0)")
    ap.add_argument("--split", type=int, metavar="K",
                    help="also model the same total turns split across K fresh sessions")
    ap.add_argument("--price-input", type=float, help="your rate: dollars per million fresh input tokens")
    ap.add_argument("--price-cached", type=float, help="your rate: dollars per million cached input tokens")
    ap.add_argument("--price-output", type=float, help="your rate: dollars per million output tokens")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    if args.turns < 1:
        ap.error("--turns must be >= 1")
    if not (0.0 <= args.cache_discount <= 1.0):
        ap.error("--cache-discount must be between 0 and 1")
    if args.split is not None and not (2 <= args.split <= args.turns):
        ap.error("--split must be between 2 and --turns")

    base = simulate(args.turns, args.system, args.tools, args.user,
                    args.assistant, args.tool_output, args.cache_discount)

    result = {
        "note": "token figures are model estimates, not measurements; "
                "defaults are illustrative round numbers",
        "assumptions": {
            "system_tokens": args.system, "tool_catalog_tokens": args.tools,
            "user_per_turn": args.user, "assistant_per_turn": args.assistant,
            "tool_output_per_turn": args.tool_output,
            "cache_discount": args.cache_discount,
        },
        "single_session": {k: v for k, v in base.items() if k != "per_turn"},
        "per_turn_samples": sample_rows(base["per_turn"]),
    }

    split = None
    if args.split:
        sessions = [simulate(t, args.system, args.tools, args.user,
                             args.assistant, args.tool_output, args.cache_discount)
                    for t in split_sessions(args.turns, args.split)]
        split = {
            "sessions": args.split,
            "turns_per_session": split_sessions(args.turns, args.split),
            "total_input_tokens": sum(s["total_input_tokens"] for s in sessions),
            "total_output_tokens": sum(s["total_output_tokens"] for s in sessions),
            "fresh_input_tokens": sum(s["fresh_input_tokens"] for s in sessions),
            "cached_input_tokens": sum(s["cached_input_tokens"] for s in sessions),
            "effective_input_tokens_with_cache":
                sum(s["effective_input_tokens_with_cache"] for s in sessions),
        }
        result["split_scenario"] = split

    cost_single = money(base["fresh_input_tokens"], base["cached_input_tokens"],
                        base["total_output_tokens"], args)
    if cost_single is not None:
        result["single_session"]["estimated_cost_dollars"] = round(cost_single, 4)
        if split:
            cost_split = money(split["fresh_input_tokens"], split["cached_input_tokens"],
                               split["total_output_tokens"], args)
            result["split_scenario"]["estimated_cost_dollars"] = round(cost_split, 4)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    b = result["single_session"]
    print(f"Session model: {args.turns} turns "
          f"(fixed prefix {fmt(b['fixed_prefix_tokens'])} tokens per turn)")
    print(f"  Assumptions per turn: user {args.user}, assistant {args.assistant}, "
          f"tool output {args.tool_output} tokens. Illustrative defaults; override with flags.")
    print()
    print(f"  {'turn':>5} {'input tokens':>14} {'fresh':>10} {'cached':>12}")
    for row in result["per_turn_samples"]:
        print(f"  {row['turn']:>5} {fmt(row['input']):>14} {fmt(row['fresh']):>10} {fmt(row['cached']):>12}")
    print()
    print(f"  Total billed input:  {fmt(b['total_input_tokens'])} tokens "
          f"({fmt(b['fresh_input_tokens'])} fresh + {fmt(b['cached_input_tokens'])} cached)")
    print(f"  Total billed output: {fmt(b['total_output_tokens'])} tokens")
    print(f"  Effective input at cache discount {args.cache_discount}: "
          f"{fmt(b['effective_input_tokens_with_cache'])} tokens")
    if "estimated_cost_dollars" in b:
        print(f"  Estimated cost at your rates: ${b['estimated_cost_dollars']:.4f}")
    first = base["per_turn"][0]["input"]
    last = base["per_turn"][-1]["input"]
    if first > 0:
        print(f"  Growth: turn {args.turns} costs {last / first:.1f}x turn 1. "
              f"History re-read grows with turns squared.")
    if split:
        s = result["split_scenario"]
        saved = b["total_input_tokens"] - s["total_input_tokens"]
        pct = 100.0 * saved / b["total_input_tokens"] if b["total_input_tokens"] else 0
        print()
        print(f"  Split into {args.split} fresh sessions ({s['turns_per_session']} turns):")
        print(f"    Total billed input: {fmt(s['total_input_tokens'])} tokens "
              f"({pct:.0f}% less raw input than one long session)")
        print(f"    Effective input with cache: {fmt(s['effective_input_tokens_with_cache'])} tokens")
        if "estimated_cost_dollars" in s:
            print(f"    Estimated cost at your rates: ${s['estimated_cost_dollars']:.4f}")
        print("    Caveat: splitting only wins when each fresh session gets a good brief;")
        print("    re-explaining lost context has its own cost. See standards/context-hygiene.md.")
    print()
    print("  Note: pass --price-input/--price-cached/--price-output (per million tokens,")
    print("  from your provider's pricing page) to see dollar figures. No prices are built in.")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
