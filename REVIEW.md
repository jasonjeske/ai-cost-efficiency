# Source-checkout release review

## Decision

**Conditional GO for human review. STOP before commit, push, pull request, merge, tag, release, or publication.**

The local implementation verifier and launch-adversary pass are both PASS. Production-like GitHub Actions execution and human approval are still outstanding. This repository has no application deployment path: the release runs directly from a source checkout with `python3 scripts/ace.py`.

## Verified facts

- Review target: branch `feature/agentic-audit-verify` at `221722f`, based directly on local `origin/main` at inspection time.
- The feature and release-preparation work are uncommitted. No commit, push, pull request, merge, tag, release upload, or deployment was performed.
- Runtime path: `python3 scripts/ace.py`, importing the standard-library-only `ace/` package from the checkout.
- Supported release matrix in `.github/workflows/ci.yml`: Linux and macOS across Python 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, and 3.14, for 14 jobs.
- CI performs `py_compile`, full `unittest` discovery, and `git diff --check`. It has no pip, npm, Bun, package build, package install, artifact upload, release, or deploy step.
- Workflow permissions are limited to `contents: read`; checkout credential persistence is disabled. The workflow does not reference repository secrets.
- The four legacy scripts retain the SHA-256 values required by `SPEC.md`.
- No package manifest, installer, daemon, service, database, container, migration, or deployment manifest exists.
- The maintained VS Code fixture is now explicitly exempted from the repository-wide `.vscode/` ignore rule and is visible to a future source checkout.
- A launch-adversary probe reproduced acceptance of a workspace-root symlink through the public CLI. `ace/cli.py` now rejects it with safety exit code 4, and `tests/test_audit.py` contains the passing regression test.

## Implementation scope

The source-checkout feature under review contains:

- `ace/` audit, adapter, proposal, measurement, schema, redaction, and isolated-verification implementation.
- `scripts/ace.py`, versioned schemas, fixtures, unit and acceptance tests.
- Product, specification, runbook, integration, enterprise-adoption, README, and skill documentation.
- Release preparation in `.github/workflows/ci.yml` and this `REVIEW.md`.
- A narrow `.gitignore` exception for `tests/fixtures/adapters/vscode-copilot/workspace/.vscode/mcp.json`.
- A workspace-root symlink safety fix and regression test found during adversarial release review.

Out of scope and absent: package installation, wheels, PyPI, Homebrew, npm, Bun, Node, containers, hosted services, telemetry, databases, remote APIs, automatic patch application, release uploads, and production deployment.

## Independent verifier: PASS

A separate verification pass in this working session re-read `PRD.md`, `SPEC.md`, `RUNBOOK.md`, the tests, the runtime entry point, verification path, output handling, and Git state, then ran the normative probes. This is independent evidence execution, not an independent human approval or a second host.

Verified claims:

- All four adapters complete offline audit, proposal, and isolated verification.
- Audit, proposal, and verification preserve fixture bytes and Git state.
- Deterministic JSON, redaction, stale-input rejection, forged-candidate rejection, temporary cleanup, exact CPCT arithmetic, schema documents, legacy compatibility, and the stdlib/runtime boundary pass.
- Full discovery passes 33 tests after the release safety regression was added.
- The exact legacy script digests match `SPEC.md`.

## Launch-adversary: PASS

Adversarial checks covered:

- Network denial and forbidden runtime/process APIs.
- Seeded secret and absolute-home-path redaction.
- Read-only workspace behavior and temporary-copy cleanup.
- Candidate authenticity, stale hashes, path traversal, symlink handling, special-file handling, output symlink retargeting, and workspace-root symlink rejection.
- CI privilege and release surface: read-only contents permission, no persisted checkout credentials, no secret references, no package manager, no artifact upload, and no publish or deploy trigger.
- Source-checkout completeness for the previously ignored VS Code fixture.

The pass means the checked local probes found no remaining release-blocking defect. It does not replace hosted CI, repository-settings review, or human review.

## Exact local evidence

Validated on `2026-08-18T20:22:18Z` using macOS 26.5.2, Python 3.9.6, and Git 2.50.1.

Every exact acceptance command listed in `SPEC.md` exited 0:

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

Final full-discovery result:

```text
Ran 33 tests in 5.693s
OK
```

Additional release probes:

```text
python3 -m py_compile ace/*.py scripts/*.py tests/*.py: PASS
ruby YAML.parse_file(.github/workflows/ci.yml): PASS
workflow static policy check: PASS, 14 jobs, 0 secret references, 0 package installs, 0 publish steps
git diff --check: PASS
VS Code fixture source-checkout visibility: PASS
workspace-root symlink regression: PASS, safety exit code 4
```

Local YAML validation is syntax-level because `actionlint` and `yamllint` are not installed. Hosted GitHub Actions validation has not run.

## Prerequisites and configuration dependencies

Required before merge:

1. Review the complete intended diff, including all currently untracked feature files.
2. Commit and push the intended files on `feature/agentic-audit-verify`, then open a pull request. These actions are deliberately not performed here.
3. Confirm GitHub Actions is enabled and permits `actions/checkout@v4` and `actions/setup-python@v5`.
4. Obtain green results for all 14 Linux/macOS and Python 3.8 through 3.14 matrix jobs.
5. Confirm branch-protection and required-check settings in GitHub. They were not accessible from the local checkout.
6. Obtain explicit owner approval for the formal macOS/Linux support statement and merge.

Additional prerequisites before publication:

1. Select a release version and immutable tag. The repository currently has no tags and no requested release identifier.
2. Identify the exact reviewed commit on `main` from which the source checkout will be published.
3. Prepare and review release notes that state source-checkout-only operation and no package or production deployment.
4. Obtain a separate explicit publication approval using the wording below.

Runtime configuration dependencies:

- Python 3.8 or newer on macOS or Linux.
- Local filesystem read access to the selected workspace and write access only to an explicitly selected output directory outside that workspace.
- No credentials, environment variables, provider account access, network, package installation, Node, npm, or Bun.
- Git is required by acceptance tests that create fixture repositories, but not by normal ACE CLI operation.

CI configuration dependencies:

- GitHub-hosted Linux and macOS runner availability.
- GitHub access to the two declared actions and the requested Python runtime versions.
- The automatically minted GitHub token is restricted to read-only repository contents and is not persisted by checkout.

## Migrations, health checks, alerts, and secrets

- **Migrations:** none. There is no persistent state, database, schema migration process, installer, or service configuration to migrate.
- **Pre-merge health check:** all 14 CI matrix jobs must pass, including compile, full discovery, and patch-whitespace checks.
- **Post-publication smoke check:** from a fresh checkout of the approved tag, run `python3 scripts/ace.py --help`, full unittest discovery, and one fixture-backed `audit -> propose -> verify` chain with output outside the workspace.
- **Runtime health check:** none is needed because there is no long-running process. CLI exit codes and verification check records are the health signal.
- **Alerts:** no runtime alerting dependency exists. GitHub check notifications are sufficient for CI failures; release defects require normal repository issue handling. No alert endpoint or credential should be added for this source-only release.
- **Secret boundary:** the invoking OS user's filesystem permissions are the runtime authorization boundary. ACE must not elevate privileges, inspect credential stores, infer global configuration, or transmit data. Candidate diffs are content-bearing source artifacts and must stay local unless deliberately reviewed for source control. CI references no repository or production secret.

## Known limitations and assumptions

Verified limitations:

- Local execution covered only Python 3.9.6 on one macOS host. The other 13 matrix combinations remain pending hosted CI.
- Workflow validation was local YAML parsing and static inspection only. GitHub expression and runner validation remain pending.
- Windows is unsupported and untested.
- Token counts are estimates unless direct local evidence is supplied; static verification does not prove CPCT improvement.
- No independent human or second-host verifier has approved this release.
- `SPEC.md` names `tests/test_cli.py`, while the current CLI audit coverage lives in `tests/test_audit.py`. Test discovery and acceptance behavior pass, but the filename differs from the documented illustrative source layout.

Assumptions requiring owner or GitHub confirmation:

- Python 3.8 through 3.14 are the intended currently supported versions under the ratified `Python 3.8+` contract.
- GitHub-hosted macOS runners can provision every declared Python version through `actions/setup-python@v5`.
- Major action tags `actions/checkout@v4` and `actions/setup-python@v5` satisfy repository supply-chain policy. Immutable action SHA requirements, if any, are unknown.
- No unpublished repository rules, legal gate, signing requirement, or release naming convention exists beyond files visible in this checkout.

## Rollout and rollback

Rollout is intentionally direct:

1. Satisfy every merge prerequisite.
2. Merge only after explicit approval.
3. Select and approve a tag from the reviewed `main` commit.
4. Publish only source-checkout metadata and source archives. Do not upload packages or deploy a service.
5. Run the fresh-checkout smoke check.

Rollback actions:

- Before merge: close or abandon the branch or remove the rejected changes. No external rollback is required.
- After merge but before publication: revert the merge commit through normal reviewed Git history.
- After publication: mark the release withdrawn, revert the merge on `main`, and publish a new corrective tag if needed. Do not silently move or reuse an immutable public tag.
- If a human separately applies an ACE candidate to another workspace: restore its reviewed preimage or revert that workspace's commit, then run a fresh audit. Never reuse a stale candidate.

## Explicit stop gate and exact approval request

**STOP. This document does not authorize commit, push, pull request creation, merge, tag creation, release publication, package upload, or production deployment.**

After the complete diff is reviewed and all 14 CI jobs pass, the owner must reply exactly:

```text
APPROVE MERGE: feature/agentic-audit-verify -> main, contingent on the reviewed diff matching REVIEW.md and all 14 CI jobs passing.
```

After merge, replace `<TAG>` with the selected release tag and obtain a separate reply exactly:

```text
APPROVE PUBLISH: create source-checkout release <TAG> from the reviewed main commit, with macOS/Linux Python 3.8-3.14 scope, no package upload, and no production deployment.
```

Without both applicable approvals, stop.
