# Contributing

Thanks for considering a contribution. This repo has a narrow purpose: teach and operationalize the cost mechanics of agentic AI. Contributions are judged against that purpose.

## What is most welcome

1. **Corrections to mechanics, with evidence.** If a claim in `docs/billing-mechanics.md`, the standards, or the README is wrong or has gone stale (providers do change behavior), open an issue with a link to the provider documentation or a reproducible measurement.
2. **Routing table rows.** New task classes for `routing/model-routing.md`, but only with the experiment attached: task definition, models compared, pass criteria, sample size, and date. Rows without evidence are not merged. See the "How to add a row" section in that file.
3. **Script improvements.** Bug fixes, better config-format detection in `tool-overhead.py`, additional instruction-file patterns in `instruction-audit.py`. Keep the constraints below.
4. **New skills** under `skills/`, if they package a genuinely recurring procedure and follow the format in `skills/README.md`.

## What will be declined

- **Vendor advocacy.** Naming vendors as examples is fine; ranking them, endorsing them, or adding vendor-specific marketing language is not.
- **Quoted prices.** Prices go stale in weeks. Describe mechanics; link to pricing pages; accept rates as script arguments.
- **Invented benchmark numbers.** Any figure must be labeled as an order-of-magnitude estimate or link to a published measurement.
- **Third-party dependencies in `scripts/`.** The scripts are Python 3 standard library only, on purpose. Anyone must be able to run them immediately, including in locked-down environments.
- **Growth for its own sake.** This repo practices what it preaches: every page has a cost to the reader. A contribution that doubles a document's length must more than double its value.

## Ground rules for text

- US English spelling (organization, behavior, optimize, artifact).
- No em dashes or en dashes. Use commas, colons, or periods.
- Estimates are labeled as estimates. Claims about provider behavior link to provider docs.
- Vendor-neutral tone. When one vendor is named as an example, name at least one alternative.

## Ground rules for scripts

- Python 3.8+, standard library only, single file per tool.
- `--help` and `--json` on every tool.
- Useful output with no arguments where that makes sense; bounded default output always.
- Exit codes: `0` success, `1` runtime failure (bad input file, unreadable path), `2` usage error (argparse handles this). Threshold-gate flags like `--fail-over` document their own exit behavior.
- Unknown flags fail loudly (argparse default). Never silently ignore an argument.

## Process

Fork, branch, open a pull request with a description of what changed and why. For anything touching a factual claim, include your source in the PR description. Small PRs merge faster than large ones.
