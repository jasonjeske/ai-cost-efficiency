# Product Requirements: Local Agentic Cost Audit and Verification

**Status:** Ratified product contract for slice 1
**Workflow:** audit -> proposed patch -> measured verification
**Ratification note:** The owner ratified the slice 1 decisions and thresholds on 2026-08-18.

## 1. Product contract

The product turns this repository's guidance and standalone estimators into one local operational loop. It audits a coding-agent workspace, explains cost findings with evidence, proposes a reviewable patch, and verifies the candidate against the same baseline. It must distinguish measured, estimated, and modeled results and must not claim cost-per-completed-task improvement without post-change task evidence and passing quality guardrails.

### Value

- Make the largest avoidable agent-cost drivers visible without sending private work data elsewhere.
- Convert findings into a concrete candidate change rather than advice alone.
- Show whether the candidate reduces cost while preserving task completion quality.
- Keep the method portable across agent vendors and usable in locked-down environments.

### Users

1. Individual developers who want a safer, cheaper local agent setup.
2. Repository maintainers who own instruction and workspace configuration.
3. Developer-platform teams evaluating repeatable policy for multiple repositories.

The slice is optimized for one operator auditing one local workspace. Fleet governance is not a slice 1 use case.

## 2. Repository facts

- Four Python 3.8+ standard-library CLIs exist at `scripts/context-size.py`, `scripts/instruction-audit.py`, `scripts/session-cost.py`, and `scripts/tool-overhead.py`.
- The scripts expose bounded human output and `--json`. Their token counts use an adjustable characters-per-token estimate, defaulting to 4.0, rather than an exact tokenizer.
- `instruction-audit.py` discovers common agent instruction files, Cursor rules, and GitHub Copilot instructions.
- `tool-overhead.py` reads JSON or JSONC server configurations used by Claude Code, Cursor, and VS Code, plus tool-definition dumps. Server-list results are estimated; serialized tool-definition results are more direct measurements but are still tokenizer estimates.
- `measurement/session-log.template.csv` already defines task-level fields for model tier, sessions, turns, attempts, token usage, completion, and cost. `measurement/README.md` defines cost per completed task by task class and requires abandoned attempts to remain in the numerator.
- Existing documentation names Claude Code, Codex, Cursor, and VS Code with GitHub Copilot, but there is no unified audit command, adapter layer, patch generator, verification workflow, or Codex-specific integration in the current tree.
- Existing guidance rejects built-in vendor prices and treats provider behavior, prices, exact tokenization, and model routing as variable evidence rather than universal truth.

## 3. Ratified decisions

1. Slice 1 is the operational `audit -> proposed patch -> measured verification` path.
2. The reference implementation is Python.
3. Every existing script path remains a legacy compatibility entry point.
4. The core is vendor-neutral, with adapters for Claude Code, Codex, Cursor, and VS Code with GitHub Copilot.
5. Processing is local-first. Prompt content, source content, and tool-output content are not exported.
6. Proposed patches are dry-run by default.
7. The primary outcome metric is cost per completed task, protected by completion-quality guardrails.
8. Slice 1 has no Bun requirement and no npm work.

## 4. First vertical slice

### Input

- A local workspace path.
- An explicitly selected or unambiguously detected supported adapter.
- Optional local tool-definition dumps, session metadata, task logs in the existing CSV shape, and user-supplied rates.
- A completion-to-standard definition declared before outcome comparison.

### Audit

The audit must:

1. Inventory supported instruction files and project tool configuration, recording the adapter and source path for each item.
2. Reuse the current estimation semantics for instruction size, context size, tool overhead, and session cost.
3. Normalize available local session and task metadata without copying prompt, source, or tool-output bodies into the normalized record.
4. Report each finding with baseline value, unit, provenance, confidence, and whether it is measured, estimated, or modeled.
5. Identify only evidence-backed opportunities. Lack of accessible usage data must be reported as unknown, not interpreted as non-use.

### Proposed patch

The product must produce a human-reviewable candidate diff and a rationale for each hunk. Each rationale must state the evidence, expected metric effect, quality risk, and any human judgment still required. By default, the audited workspace is not modified.

Slice 1 patch candidates are limited to agent-facing instruction and workspace/tool configuration. Product source code, generated files, lockfiles, secrets, billing records, and provider account settings are outside patch scope.

### Measured verification

Verification applies the candidate only in an isolated local copy or equivalent non-mutating view, then repeats the same applicable audit measurements. The report must include:

- Baseline and candidate values with reproducible arithmetic.
- Absolute and percentage deltas using the same units and assumptions.
- Parse and structural validity for changed supported configuration.
- Broken or missing on-demand references introduced by the candidate.
- Patch precondition failures when the source has changed since audit.
- A clear distinction among immediate configuration verification, modeled session impact, and observed task outcomes.

A smaller standing prefix is not, by itself, proof of lower cost per completed task. Until enough post-change tasks exist, the outcome status must remain pending. When comparable pre-change and post-change task data exist, the product computes cost per completed task by task class, includes all attempts and abandoned work in spend, and evaluates the declared quality guardrails.

## 5. Supported and unsupported boundaries

### Supported in slice 1

- Local, user-readable workspaces and local adapter artifacts.
- Claude Code, Codex, Cursor, and VS Code Copilot through a shared normalized capability contract.
- Common instruction-file discovery already recognized by `instruction-audit.py`.
- MCP server configurations and tool-definition dumps in shapes already recognized by `tool-overhead.py`.
- JSON, JSONC, Markdown, unified diffs, and the existing measurement CSV shape.
- Dollar CPCT when the user supplies current rates, or token/capacity CPCT when dollars are unavailable.
- Honest partial support: an adapter may report a capability as unavailable when its product does not expose the required local metadata.

"Supported adapter" means the product can identify the adapter, inventory its documented local artifacts, normalize every available supported metric, and explicitly report unavailable capabilities. It does not mean all vendors expose equivalent usage or completion data.

### Unsupported in slice 1

- Remote repository auditing, hosted dashboards, telemetry, or fleet-wide control planes.
- Reading provider billing accounts or calling vendor APIs to fill missing data.
- Exact invoice reconciliation, bundled price tables, or claims of exact tokenization from character estimates.
- Automatic model routing, model benchmarking, or universal recommendations about a vendor or model.
- Editing application source code or generating cost-saving code changes.
- Inferring task completion from conversation text. Completion comes from a predeclared local signal or user-provided task log.
- Automatic publication, pull-request creation, commit creation, or unattended application of a patch.
- Bun, npm packages, Node-based build steps, or IDE user interfaces.

## 6. Privacy and safety constraints

1. The core and adapters must complete their supported path with network access disabled. No telemetry, update check, crash upload, or vendor API call is allowed.
2. Local files may be inspected only for the selected audit. Raw prompt bodies, application source bodies, and tool-output bodies must not be copied into normalized metrics or verification reports.
3. Local audit and candidate artifacts contain workspace-relative filenames, and candidate diffs contain instruction or configuration content. Treat every raw artifact as source code: protect it locally and never centrally aggregate it. It is emitted only to the terminal or a user-selected local path and is never transmitted by the product.
4. Secret values found in configuration, environment references, paths, or command arguments must be redacted from reports. This redaction does not make raw local artifacts safe to aggregate. The product must never require credentials for slice 1.
5. Temporary verification material stays local, is access-restricted, and is removed after the run unless the user explicitly asks to retain it.
6. Dry-run must preserve tracked and untracked workspace content, permissions, and Git state. Ambiguous adapter detection or an unsafe path must fail closed with an actionable explanation.

## 7. Legacy compatibility

The following paths remain directly invokable:

- `scripts/context-size.py`
- `scripts/instruction-audit.py`
- `scripts/session-cost.py`
- `scripts/tool-overhead.py`

Compatibility includes existing documented flags, defaults, exit-code meanings, human-output intent, and JSON field meanings. A new core may be shared behind these entry points, but users and automation must not need to change commands. Additive fields are allowed only when they do not break documented consumers; removals, renames, or semantic changes require a separately ratified compatibility plan.

## 8. Metrics and success

### Metric definitions

```text
CPCT = total spend for a task class, including failed and abandoned attempts
       / tasks completed to the predeclared standard
```

- Spend is dollars when exact usage and user-supplied rates exist. Otherwise it is a clearly labeled consistent token or capacity unit.
- Results are grouped by task class. A blended cross-class CPCT must not be presented as the primary result.
- Required quality guardrails are completion-to-standard rate and completion volume. Single-pass completion rate is a diagnostic guardrail.
- A change is not labeled improved when completion evidence is missing, a guardrail fails, or the comparison is materially confounded by a changed task class, model tier, harness, or completion definition.

### Ratified slice 1 success thresholds

1. **Safety:** 100% of dry-run acceptance fixtures leave the audited workspace byte-for-byte and Git-state unchanged, with zero attempted network connections and zero unredacted seeded secrets.
2. **Coverage:** all four adapters complete the common audit on maintained fixtures and explicitly identify any unavailable vendor capability.
3. **Correctness:** repeated runs on unchanged fixtures produce identical findings and deltas; metric arithmetic matches fixture expectations exactly, apart from documented rounding.
4. **Usability:** at least 8 of 10 pilot users can reach a verified candidate report from a supported workspace without manually assembling script output.
5. **Outcome:** among adopted candidates with comparable data, median CPCT falls by at least 10% within the same task class, with no decline in completion-to-standard rate and no decline in completion volume. No outcome claim is made with fewer than 10 attempted tasks in either comparison cohort.

## 9. Acceptance claims

Slice 1 is acceptable only when each claim is demonstrated by an automated fixture or a documented pilot result:

1. **Offline end-to-end:** each named adapter can drive one local audit, candidate patch, and isolated verification path with the network disabled.
2. **Evidence traceability:** every reported number names its source, unit, calculation, and measured/estimated/modeled status. Missing data stays missing.
3. **Safe proposal:** default execution changes no audited file. The candidate is a valid, reviewable diff scoped to supported files and tied to the audited preimage.
4. **Repeatable verification:** the candidate is evaluated against the same inputs and assumptions as the baseline, invalid configurations fail verification, and the reported delta can be independently recalculated.
5. **No false outcome claim:** static or modeled savings cannot produce a CPCT-success label. That label requires comparable task cohorts and passing guardrails.
6. **Privacy:** network-denied tests pass, content canaries do not appear in outbound traffic or normalized reports, and secret canaries are redacted from all output.
7. **Adapter honesty:** when a vendor artifact or metric is unavailable, the adapter reports the gap and the fallback input needed rather than fabricating a value.
8. **Legacy continuity:** the four legacy script paths pass compatibility fixtures covering help, default invocation, JSON mode, documented options, and exit behavior.
9. **Runtime boundary:** the slice installs and runs without Bun, npm, or Node tooling.

## 10. Assumptions

- Users have authority to inspect the selected workspace and any local agent metadata they provide.
- At least one local metadata or manual-log path can supply task-level spend and completion evidence; some vendors will require the existing CSV fallback.
- Instruction and tool-configuration overhead is a useful immediate optimization signal, but outcome causality still requires post-change task data.
- Adapter behavior and artifact locations will need versioned fixtures because vendor clients change over time.

## 11. Ratified implementation defaults

1. The interface is one new `ace` CLI with human output plus versioned JSON, while retaining the four old entry points.
2. Slice 1 does not apply patches. Verification uses an isolated copy, and users apply an accepted diff with their existing tools.
3. Slice 1 supports macOS and Linux with Python 3.8+ and standard-library-only runtime dependencies. Windows waits for path and permission fixtures.
4. Global configuration may be audited when explicitly supplied, but generated patches are limited to files inside the selected workspace.
5. Outcome claims require the repository's two-week measurement method and at least 10 attempted tasks per pre/post cohort.
6. Quality allows no decline in completion-to-standard rate or completion volume, with no statistical-tolerance band in slice 1.
7. The product makes no external LLM calls. A coding agent may invoke the local CLI, but the core remains deterministic and offline.
8. Reports and diffs go to stdout by default. Persistence requires an explicit user-selected local path. The machine-readable schema is versioned from its first release.

## 12. Deferred beyond slice 1

- Explicit patch apply, rollback, commits, pull requests, and approval workflows.
- Fleet aggregation, central policy, hosted storage, dashboards, and remote administration.
- Additional vendors, IDE interfaces, continuous background monitoring, and automatic updates.
- Provider billing integrations, live price synchronization, and model-specific tokenizers.
- Statistical experiment design beyond the minimum cohort rule, including significance tests and matched-task sampling.
- Automatic task classification, completion inference, model routing, and cross-vendor model comparison.
- Changes to application source, tool-server implementations, or agent prompts beyond local instruction/configuration hygiene.
- Any Bun or npm-based packaging. Future JavaScript work would require separate ratification.
