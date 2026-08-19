# Local ACE Runbook

ACE runs directly from this checkout with Python 3.8+ and the standard library. It has no installer, deployment, daemon, service, account connection, or network requirement.

## Normal operation

Read current options first:

```sh
python3 scripts/ace.py --help
python3 scripts/ace.py audit --help
```

Keep JSON artifacts outside the workspace because `--output` paths inside it are rejected:

```sh
mkdir -p /tmp/ace-results
python3 scripts/ace.py audit /path/to/workspace --adapter codex --json --output /tmp/ace-results/audit.json
python3 scripts/ace.py propose /path/to/workspace --audit /tmp/ace-results/audit.json --json --output /tmp/ace-results/candidate.json
python3 scripts/ace.py verify /path/to/workspace --candidate /tmp/ace-results/candidate.json --json --output /tmp/ace-results/verification.json
```

Use an explicit adapter when auto-detection is ambiguous. Review the proposal diff and rationales. ACE never applies it to the selected workspace; verification uses and removes a temporary local copy.

For outcome evidence, provide all cohort inputs together:

```sh
python3 scripts/ace.py verify /path/to/workspace --candidate /tmp/ace-results/candidate.json \
  --pre-csv pre.csv --post-csv post.csv \
  --completion-standard completion-standard.md --harness-id declared-harness
```

CPCT includes failed and abandoned attempts. A passing structural verification or modeled delta is not a measured CPCT result.

## Exit codes

| Code | Meaning | Response |
|---|---|---|
| 0 | Operation completed, including no candidate or pending outcome evidence. | Read the report status. |
| 1 | Negative completed result, including failed verification or quality guardrail regression. | Do not apply. Resolve the reported check or evidence issue. |
| 2 | Invalid command usage or argument domain. | Run `--help` and correct arguments. |
| 3 | Missing, unreadable, or malformed input or output failure. | Check local paths, permissions, and JSON or CSV shape. |
| 4 | Safety or precondition failure. | Stop. Re-audit after resolving ambiguity, unsafe paths, or source drift. |
| 5 | Unexpected internal error. | Preserve the redacted error and reproduce with the same local inputs. |

## Troubleshooting

- **Multiple adapters detected:** pass `--adapter` with one supported ID. Do not rely on a guessed adapter.
- **Proposal says `no_candidate`:** this is a valid result. The conservative proposer only moves eligible trailing Markdown sections from oversized instruction files.
- **Verification reports stale preconditions:** the workspace changed after audit. Do not edit hashes or the candidate. Run audit and proposal again.
- **Output path rejected:** choose a path outside the selected workspace.
- **Missing usage or outcome data:** provide authorized local CSV data in the documented shape, or leave the capability unknown. Do not substitute chat interpretation.
- **Configuration or reference check fails:** repair the proposed source through a new audit/proposal cycle. Never patch the temporary copy.

## Rollback

There is normally nothing for ACE to roll back: audit and proposal are read-only, and verification deletes its temporary copy. If a human later applies a reviewed candidate, roll it back with the repository's normal version-control revert or by restoring the reviewed preimage, then run a fresh audit. Do not reuse a candidate after source drift.

The legacy scripts remain independently runnable: `context-size.py`, `instruction-audit.py`, `session-cost.py`, and `tool-overhead.py`. See `scripts/README.md` for their direct workflows.
