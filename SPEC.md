# Specification: Local Audit, Proposal, and Verification CLI

**Status:** Implementation specification for slice 1
**Normative input:** `PRD.md`
**Runtime:** Python 3.8+ standard library only

## 1. Scope and invariants

Implement a source-checkout package at `ace/` and a single entry point at `scripts/ace.py` with `audit`, `propose`, and `verify` subcommands. The four existing scripts remain byte-for-byte unchanged and directly invokable.

The slice is local and deterministic. It has no network calls, telemetry, services, databases, MCP client, provider API, model call, background process, package installer, npm, Bun, or Node dependency. It never applies a candidate to the selected workspace. Audit and proposal are read-only. Verification applies a candidate only to a `tempfile.TemporaryDirectory` copy and always removes that copy.

Patch scope is recognized workspace instruction files plus proposer-created on-demand Markdown references. Tool configuration is audited and verified, but slice 1 does not infer non-use or automatically remove a server. Application source, generated files, lockfiles, account settings, billing data, global configuration, and paths outside the workspace are never patched.

## 2. Source layout

Create only these implementation areas:

```text
ace/
  __init__.py
  adapters.py       static capability records and detection
  audit.py          inventory and normalized findings
  cli.py            argument parsing, rendering, exit mapping
  legacy.py         ports of the existing measurement semantics
  measurement.py    CSV validation and CPCT aggregation
  patch.py          deterministic proposal and strict unified-diff handling
  redact.py         report-safe values
  schema.py         runtime validation for versioned documents
  verify.py         preconditions, temporary copy, checks, deltas
scripts/
  ace.py            thin entry point that adds the repository root to sys.path
schemas/
  ace-audit-v1.schema.json
  ace-candidate-v1.schema.json
  ace-verification-v1.schema.json
tests/
  __init__.py
  test_acceptance.py
  test_cli.py
  test_legacy_compat.py
  test_measurement.py
  test_patch.py
  test_schema.py
  fixtures/...
```

Do not edit these files. Compatibility tests pin their current SHA-256 values:

| Path | SHA-256 |
|---|---|
| `scripts/context-size.py` | `5b2535fe7296af2f7a8ee17d0ac73f4ff4dcdef5ad09d435580b7b934cda6f67` |
| `scripts/instruction-audit.py` | `bed9a469e991ba4d140851cf6f3f4d1dff634074ebcef8358247aa3b17f32dc5` |
| `scripts/session-cost.py` | `2dd2a780feb84b77559fc5e175a59c98b6a810cb539ad661b5032e8819160ae4` |
| `scripts/tool-overhead.py` | `d7275a5c82768a2c87542c898f4cbe30d9dc3e22f6cce3188d9fe27f6fa9dca7` |

`ace/legacy.py` may port reusable logic, but the four scripts remain the normative compatibility behavior. Preserve their documented flags, defaults, human-output intent, JSON field meanings, and exit behavior through golden subprocess tests.

## 3. CLI contract

The exact grammar is:

```text
python3 scripts/ace.py audit WORKSPACE
  [--adapter auto|claude-code|codex|cursor|vscode-copilot]
  [--tool-config PATH] [--tool-dump PATH]
  [--measurement-csv PATH]
  [--measurement-kind measured|estimated|modeled]
  [--chars-per-token FLOAT] [--warn INT] [--fail-over INT]
  [--top INT] [--turns INT] [--tools-per-server INT]
  [--tokens-per-tool INT]
  [--model-session] [--user INT] [--assistant INT]
  [--tool-output INT] [--cache-discount FLOAT]
  [--price-input FLOAT] [--price-cached FLOAT] [--price-output FLOAT]
  [--json] [--output PATH]

python3 scripts/ace.py propose WORKSPACE --audit PATH
  [--finding FINDING_ID ...] [--json] [--output PATH]

python3 scripts/ace.py verify WORKSPACE --candidate PATH
  [--pre-csv PATH --post-csv PATH --completion-standard PATH
   --harness-id TEXT]
  [--pre-kind measured|estimated|modeled]
  [--post-kind measured|estimated|modeled]
  [--json] [--output PATH]
```

Defaults match existing scripts where applicable: adapter `auto`, characters per token `4.0`, warning `2500`, top `15`, turns `20`, tools per server `10`, tool token range `100..500`, user `150`, assistant `600`, tool output `1200`, and cache discount `0.1`. Measurement kind defaults to `estimated`. Validate positive counts and rates and cache discount in `0..1`.

`--json` selects the versioned JSON document. Otherwise output is bounded human text, with at most `--top` item rows; proposal human output includes the complete diff because it is the review artifact. Without `--output`, the selected representation goes to stdout. With `--output`, write it atomically to that explicit local path and print only a path/status line to stdout. Reject an output path inside `WORKSPACE`, since that would violate read-only operation. Errors go to stderr. JSON is UTF-8, LF-terminated, indented by two spaces, key-sorted, and contains no time, host, process, random, or temporary-path fields.

For chaining, the supported path is:

```text
ace.py audit WORKSPACE --adapter ID --json --output /local/audit.json
ace.py propose WORKSPACE --audit /local/audit.json --json --output /local/candidate.json
ace.py verify WORKSPACE --candidate /local/candidate.json --json --output /local/verification.json
```

### Command behavior

- `audit` validates the workspace, resolves exactly one adapter, inventories sources, computes applicable metrics, emits findings and explicit unknowns, and changes nothing.
- `propose` accepts only an `ace.audit` v1 document, rechecks its measured-input manifest, creates zero or more deterministic candidates, and changes nothing. No eligible change is a successful `no_candidate` result.
- `verify` accepts only an `ace.candidate` v1 document, checks every precondition against the original workspace, copies the whole workspace without following symlinks, applies the strict diff in the temporary copy, reruns the same audit assumptions there, validates changed artifacts and introduced references, computes deltas, optionally compares CPCT cohorts, and removes the copy in `finally`.

## 4. Adapter contract

There are exactly four immutable capability records. Common instruction discovery still uses every name and directory pattern recognized by `scripts/instruction-audit.py`; `native_patterns` below explains adapter relevance rather than narrowing that common inventory. A user-supplied `--tool-config` may use any shape already accepted by `tool-overhead.py`.

```json
[
  {
    "id": "claude-code",
    "detection_markers": ["CLAUDE.md", "CLAUDE.local.md", ".mcp.json"],
    "instruction_inventory": {"state": "available", "native_patterns": ["AGENTS.md", "CLAUDE.md", "CLAUDE.local.md"]},
    "workspace_tool_config": {"state": "available", "paths": [".mcp.json"], "root_keys": ["mcpServers"]},
    "tool_definition_dump": {"state": "available", "source": "explicit_input"},
    "local_session_usage": {"state": "unavailable", "fallback": "measurement_csv"},
    "task_outcomes": {"state": "unavailable", "fallback": "measurement_csv"}
  },
  {
    "id": "codex",
    "detection_markers": [".codex/"],
    "instruction_inventory": {"state": "available", "native_patterns": ["AGENTS.md"]},
    "workspace_tool_config": {"state": "unavailable", "reason": "no supported JSON or JSONC project artifact in slice 1"},
    "tool_definition_dump": {"state": "available", "source": "explicit_input"},
    "local_session_usage": {"state": "unavailable", "fallback": "measurement_csv"},
    "task_outcomes": {"state": "unavailable", "fallback": "measurement_csv"}
  },
  {
    "id": "cursor",
    "detection_markers": [".cursor/", ".cursorrules"],
    "instruction_inventory": {"state": "available", "native_patterns": ["AGENTS.md", ".cursorrules", ".cursor/rules/*"]},
    "workspace_tool_config": {"state": "available", "paths": [".cursor/mcp.json"], "root_keys": ["mcpServers"]},
    "tool_definition_dump": {"state": "available", "source": "explicit_input"},
    "local_session_usage": {"state": "unavailable", "fallback": "measurement_csv"},
    "task_outcomes": {"state": "unavailable", "fallback": "measurement_csv"}
  },
  {
    "id": "vscode-copilot",
    "detection_markers": [".github/copilot-instructions.md", ".github/instructions/", ".vscode/mcp.json"],
    "instruction_inventory": {"state": "available", "native_patterns": ["AGENTS.md", ".github/copilot-instructions.md", ".github/instructions/*.instructions.md"]},
    "workspace_tool_config": {"state": "available", "paths": [".vscode/mcp.json"], "root_keys": ["servers"]},
    "tool_definition_dump": {"state": "available", "source": "explicit_input"},
    "local_session_usage": {"state": "unavailable", "fallback": "measurement_csv"},
    "task_outcomes": {"state": "unavailable", "fallback": "measurement_csv"}
  }
]
```

Auto-detection uses only these workspace-relative markers. One match selects it. Zero or multiple matching adapter IDs fail closed with exit 4 and list only adapter IDs, not source content. Explicit selection bypasses detection but not workspace and artifact validation. Missing artifacts are reported as unavailable, never as zero use.

## 5. Audit semantics

The existing scripts are normative for regular-file calculations:

- Context uses the same skip directories, binary extensions, 8 KiB NUL check, UTF-8 replacement behavior, per-file rounding, sort order, and top truncation as `context-size.py`.
- Instructions use the exact known names, scoped patterns, hidden-directory behavior, strict `tokens > threshold` comparison, sorting, and combined standing-token sum from `instruction-audit.py`.
- Tool configuration uses the same JSON then JSONC parsing, shape precedence, compact serialization for definitions, server assumptions, ranges, and compounded-turn arithmetic as `tool-overhead.py`.
- Session modeling is absent unless `--model-session` is supplied. When requested, use `session-cost.py` arithmetic. The fixed prefix is the instruction total plus the tool total; a server range produces low and high scenarios. Prices appear only when supplied by the user and are never built in.

Safety overrides legacy traversal: do not follow symlinks, sockets, devices, or FIFOs. Record them as unknown. A required explicit input that is unreadable or malformed is an input error; an incidental unreadable workspace file is an unknown.

Every metric record contains `name`, integer or decimal-string `value`, `unit`, `classification` (`measured`, `estimated`, or `modeled`), `confidence` (`high`, `medium`, or `low`), `source_ids`, and a plain arithmetic `calculation`. Character-based token counts are `estimated`, including counts from serialized tool definitions. File byte counts are `measured`. Session projections are `modeled`. Findings reference metric IDs and include baseline, evidence, impact, and action boundary. Unknown capability data remains `null` with a reason and fallback.

The audit stores a sorted manifest of workspace-relative paths, raw-byte SHA-256 values, file modes, and source roles for every input used by a metric. It stores no file body. Its manifest digest and canonical assumptions produce a deterministic `audit_id`.

## 6. Versioned JSON documents

All documents have these required top-level fields:

```text
document_type   one of ace.audit, ace.candidate, ace.verification
schema_version  integer 1
id              sha256:<lowercase hex> over canonical content excluding id
status           command-specific enum
```

The checked-in schemas are the public v1 contract. Runtime validation is implemented with standard-library code in `ace/schema.py`; JSON Schema files are documentation and fixture validation targets, not a reason to add a dependency. Unknown top-level fields are rejected when consuming audit or candidate documents. A breaking field or semantic change requires schema version 2. Additive human text is not part of the machine contract.

Required command payloads are:

- `ace.audit`: selected adapter record, assumptions, manifest and digest, source metadata, metrics, findings, unknowns, and optional aggregate measurement. No raw prompt, source, tool output, task notes, task IDs, command arguments, environment values, or configuration values.
- `ace.candidate`: complete baseline audit, selected finding IDs, sorted file bindings, one canonical unified diff, per-hunk rationales, expected metric deltas, and `candidate_id`. It contains no absolute workspace path.
- `ace.verification`: candidate ID, baseline and candidate metric records, deltas, ordered check results, optional CPCT comparison, explicit outcome-claim status, and failure reasons. It does not repeat the diff.

Paths in reports are normalized workspace-relative POSIX paths. Explicit external inputs receive opaque labels such as `external-tool-dump` plus a content hash, never their absolute paths.

## 7. Candidate generation and source binding

Proposal is deliberately conservative and deterministic. For each selected oversized UTF-8 Markdown instruction finding:

1. Parse ATX level-2 headings at column zero while ignoring fenced code blocks.
2. Select the shortest trailing sequence of complete level-2 sections whose replacement makes that instruction file no greater than its audited warning threshold. If no such sequence exists, emit no candidate for that file.
3. Move the selected bytes to `docs/agent-reference/<path-slug>-<path-sha256-first-12>.md`. Do not overwrite an existing path.
4. Replace the moved suffix with one `## On-demand reference` section linking by a relative Markdown link to the new file and listing the moved level-2 heading titles.
5. Emit the candidate only if recalculation shows a strict reduction in estimated standing instruction tokens.

The new reference starts with a title and provenance sentence, followed by the moved sections verbatim. No whitespace-only rewrite, semantic summarization, tool-server removal, or config rewrite is allowed. Default proposal includes all eligible findings; repeated `--finding` limits it to those exact audit finding IDs.

The canonical patch is a UTF-8 unified diff with `a/<path>` and `b/<path>`, three context lines, LF diff framing, and `/dev/null` for new files. Paths containing control characters, absolute paths, `..`, or non-normalized segments are rejected. Each changed existing file has a binding with raw preimage SHA-256, mode, and postimage SHA-256. Each new file has `must_be_absent: true`, mode `0644`, and a postimage hash. Bindings are sorted by path.

Each diff hunk has exactly one rationale keyed by path and 1-based hunk index. It states the source metric and finding, expected standing-token delta, quality risk, and required human judgment. The diff is the source of truth. `verify` uses a strict parser for this generated subset, checks that parsed outputs exactly match all postimage hashes, and rejects extra, duplicate, or unbound hunks.

A candidate is review material, not approval. Moving a valid always-on rule can reduce tokens and still harm quality; verification cannot settle that human judgment.

## 8. Verification

Before creating a temporary directory, verification validates schema, candidate ID, audit ID, workspace identity, the full measured-input manifest, all preimage hashes and modes, all `must_be_absent` bindings, and path safety. Any drift is a stale precondition failure. No partial application is attempted.

Copy the entire workspace into a mode-`0700` temporary directory using standard-library copy operations, preserving regular-file metadata and symlinks without following them. Reject special files and any changed path whose parent is or becomes a symlink. Apply only in the copy. On success or failure, remove it in `finally`; never emit its path.

Run these ordered checks and report each as pass, fail, or unavailable:

1. `preconditions`
2. `isolated_apply`
3. `postimage_hashes`
4. `supported_config_parse`
5. `supported_config_structure`
6. `introduced_reference_targets`
7. `repeat_audit`
8. `metric_delta`
9. `quality_guardrails` when CSVs are supplied
10. `temporary_cleanup`

Changed JSON/JSONC tool configuration must parse with the existing tolerant parser and contain the selected adapter's required root dictionary. Server entries must be dictionaries. Introduced relative Markdown links must resolve to regular files inside the copy; absolute, escaping, missing, and symlink targets fail. Repeat audit with the baseline adapter and assumptions. For each common metric, emit baseline, candidate, absolute delta, and percentage delta; zero baselines produce a `null` percentage with a reason. Never reinterpret static or modeled savings as observed CPCT improvement.

## 9. Optional CPCT comparison

`--pre-csv`, `--post-csv`, `--completion-standard`, and `--harness-id` are all-or-none. The completion-standard file must be readable before either CSV is parsed; only its SHA-256 is reported. The harness ID is a predeclared assertion that both cohorts used the same harness and is reported in redacted form. Compare model-tier sets from the rows and flag a mismatch as a confounder.

Both CSVs must have exactly the existing header from `measurement/session-log.template.csv`. Validate dates, nonempty task class, positive sessions/turns/attempts, nonnegative integer token fields, `y|n`, and nonnegative decimal `cost_usd` when present. Never copy `task_id` or `notes` to output.

Aggregate separately by task class over every row, including failed and abandoned work:

```text
completed volume = count(completed_to_standard = y)
completion rate = completed volume / row count
single-pass rate = count(completed and attempts = 1) / row count
token spend = sum(input_tokens + output_tokens)
CPCT = spend / completed volume
```

`cached_input_tokens` is a diagnostic subset of `input_tokens` and is not added again. Use USD only when every row in both cohorts for that task class has `cost_usd`; otherwise use tokens. A zero denominator produces `null`, not zero. Use `decimal.Decimal` for USD and ratios, serialize exact decimal strings without exponent notation, and sort by task class. The aggregate classification is the less-direct of the declared pre/post kinds.

Report CPCT direction and the factual guardrails. A post completion rate below pre or post completion volume below pre fails `quality_guardrails` and makes verification exit 1. Missing classes, zero denominators, model-tier mismatch, or missing evidence make the outcome pending rather than improved.

The owner ratified a minimum of 10 attempted tasks per cohort, a two-week evidence window, a CPCT reduction target of at least 10 percent, and no decline in completion rate or completion volume. Emit `outcome_claim: "improved"` only when all thresholds pass, the harness and model-tier sets match, both CPCT denominators are nonzero, and there are no missing classes or other confounders. Otherwise emit `pending_insufficient_evidence`, `not_improved`, or `regressed` with factual reasons.

## 10. Redaction, ownership, and safety

There is no application authentication or authorization layer. The invoking OS user owns all inputs and outputs; existing filesystem permissions are the authorization boundary. Never elevate privileges, read credential stores, inspect home/global configuration implicitly, or bypass a permission error.

Normalized reports never emit configuration values, environment references, command arrays, prompt/source/tool-output bodies, CSV notes, task IDs, usernames, home prefixes, or absolute paths. Tool/server names are emitted as deterministic opaque IDs derived from their names, not as names. Apply case-insensitive detection for common credential assignments and token formats before rendering any remaining free text; replace matches with `<redacted>`. Redact stderr through the same path. A source containing a suspected secret can still be measured, but findings and verification reports expose only its relative path, hash, counts, and redacted labels. The local candidate diff is the sole content-bearing artifact allowed by the PRD and is written only to stdout or an explicit local path.

Audit and proposal perform no writes below the workspace. Verification performs none below the workspace because all patch writes target the temporary copy. Output files use create-or-replace atomic rename, mode `0600`, and no implicit default location. Fail closed for an ambiguous adapter, unsafe path, workspace root symlink, source drift, malformed artifact, or attempted path escape.

## 11. Exit codes and failure modes

| Code | Meaning |
|---|---|
| `0` | Operation completed. Audit findings, unavailable capabilities, pending CPCT, or no candidate are not process errors. |
| `1` | Completed negative result: `--fail-over` exceeded, isolated verification check failed, or supplied quality guardrail regressed. |
| `2` | CLI usage or argument-domain error, including incomplete pre/post options. |
| `3` | Input/output error: missing, unreadable, malformed JSON/JSONC/CSV/schema, or atomic output failure. |
| `4` | Safety or precondition failure: ambiguous adapter, unsafe workspace/path/symlink, manifest drift, hash mismatch, or unexpected existing new-file target. |
| `5` | Unexpected internal error. Emit a redacted stable error class, no traceback by default. |

New `scripts/ace.py` broken pipes exit 0. The four immutable legacy entry points retain their historical observed pipe behavior as part of compatibility. Errors use stable `ACE[E<code>]: <message>` prefixes. Reports include stage results and source hashes for local diagnosis. There are no logs, telemetry, tracing exporters, update checks, or retained temporary artifacts.

## 12. Tests and fixtures

Use only `unittest`, `tempfile`, `unittest.mock`, and other standard-library modules. Fixture layout is fixed:

```text
tests/fixtures/
  adapters/
    claude-code/workspace/{CLAUDE.md,.mcp.json}
    codex/workspace/{AGENTS.md,.codex/}
    cursor/workspace/{AGENTS.md,.cursor/mcp.json,.cursor/rules/example.mdc}
    vscode-copilot/workspace/{AGENTS.md,.vscode/mcp.json,.github/copilot-instructions.md}
  tool-dumps/measured.json
  measurement/{pre.csv,post.csv,pre-usd.csv,post-usd.csv,completion-standard.txt}
  safety/{secret-workspace,symlink-workspace,special-file-description.txt}
  verification/{stale-candidate.json,invalid-config-candidate.json,broken-link-candidate.json}
  legacy/{context,repo,mcp.jsonc,tools.json}
  expected/{audit,proposal,verification,legacy}/
```

Each adapter fixture has an oversized, sectioned instruction file that produces one deterministic on-demand-reference candidate. Codex explicitly reports workspace tool configuration and local usage unavailable. Seed `ACE_SECRET_CANARY`, a fake `sk-...` token, an environment reference, and an absolute home path in safety config values and CSV notes.

The token CPCT fixture has one `single-file-change` class: pre has 10 rows, 8 completed, and 110 spend tokens per row, so CPCT is `137.5`; post has 10 rows, 9 completed, and 90 spend tokens per row, so CPCT is `100`. At least one failed row has attempts greater than one, proving its spend remains in the numerator. Expected JSON fixtures contain no volatile values.

Legacy compatibility covers help, controlled default invocation, JSON mode, every documented option, stdin for `tool-overhead.py`, instruction `--fail-over`, missing paths/configs, invalid argument domains, malformed/unrecognized JSON, no-default-config success, and broken pipe. Compare exit code, stdout JSON fields or normalized human output, and stderr against checked-in golden results. The pinned hashes ensure compatibility is not obtained by changing the old scripts.

### Exact acceptance probes

Run from the repository root. Every command below must exit 0:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_acceptance.AcceptanceTests.test_offline_e2e_all_four_adapters
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_acceptance.AcceptanceTests.test_workspace_and_git_bytes_unchanged
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_acceptance.AcceptanceTests.test_deterministic_json_and_redaction
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_acceptance.AcceptanceTests.test_stale_hash_fails_before_temp_copy
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_acceptance.AcceptanceTests.test_verify_uses_and_removes_temp_copy
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_acceptance.AcceptanceTests.test_forged_candidates_fail_before_temp_copy
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_measurement.MeasurementTests.test_cpct_exact_and_abandoned_spend_included
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_measurement.MeasurementTests.test_improved_claim_requires_ratified_thresholds
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_legacy_compat.LegacyCompatibilityTests
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_schema.SchemaTests.test_v1_golden_documents
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_acceptance.AcceptanceTests.test_stdlib_only_no_node_bun_network_or_services
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
```

The offline E2E test patches socket creation and connection functions to raise and invokes the real `scripts/ace.py` entry point in-process for `audit -> propose -> verify`; any attempted connection fails the test. The unchanged test snapshots every fixture regular-file byte string, mode, symlink target, and `.git` byte before and after all three commands. The tempfile test spies on `tempfile.TemporaryDirectory`, proves all writes occur below it, and proves removal after both pass and failure. The forged-candidate test proves changed source paths, hooks, findings, rationales, and diffs fail before a copy exists. The runtime-boundary test parses imports and runtime calls to reject non-stdlib dependencies, Node/Bun commands, subprocess-based services, and network modules.

## 13. Deployment and ratification gates

Run directly from a checkout with `python3 scripts/ace.py`; there is no installer or daemon. The implementation target follows the repository's existing Python 3.8+, macOS/Linux convention. A formal platform support promise remains an owner release decision, so do not claim Windows support or publish a macOS/Linux SLA from this spec.

The owner ratified the cohort minimum and duration, CPCT target, quality tolerance, and confound policy. Release still requires independent verification and explicit owner approval before merge or publication.
