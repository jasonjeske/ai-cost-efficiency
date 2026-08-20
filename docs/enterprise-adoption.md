# Enterprise Adoption

ACE is an advisory, local workspace tool. It is not a fleet service, telemetry product, or automatic enforcement engine. Adopt it as a small evidence practice before considering any policy gate.

## Rollout path

1. **Advisory pilot.** Let volunteers run `audit -> propose -> verify` on authorized local workspaces. Keep candidate diffs review-only. Record only aggregate policy reporting, not raw local JSON, prompt content, source content, filenames, or diffs.
2. **Shared practice.** Publish a short project pointer to `skills/agentic-cost-optimization/SKILL.md`, an approved completion standard, and a versioned policy document. Use the existing task-log CSV for outcome evidence when local usage data is unavailable.
3. **Review expectation.** Require human review of candidate rationales, quality risk, and task-class comparability for participating repositories. Treat unavailable data as unavailable.
4. **Narrow enforcement.** Only after a pilot demonstrates value, gate a stable, low-risk structural condition, such as an instruction-size threshold using the legacy `instruction-audit.py --fail-over` command. Keep exceptions, an owner, a review date, and a rollback path. Do not gate on estimated savings or CPCT without the required evidence.

Enforcement remains an organizational integration outside this slice. ACE itself does not apply patches, change settings, collect centrally, or contact a service.

## Privacy and anti-surveillance

- Audit only workspaces and optional local inputs the operator is authorized to inspect.
- Keep all raw ACE artifacts local and protect them like source code. Audit and candidate artifacts contain workspace-relative filenames, and candidate diffs intentionally contain instruction content. Audit and verification reports exclude prompt bodies, source bodies, tool-output bodies, task IDs, notes, configuration values, and secrets, but that redaction does not authorize central aggregation of raw JSON.
- Do not collect per-person rankings, keystrokes, conversation transcripts, hidden productivity scores, or usage quotas from this process.
- Stable hashes are linkable pseudonyms, not anonymous identifiers. Use them only for local evidence correlation. In any external organizational reporting, report at task-class or repository-practice level and suppress or coarsen small cohorts as insufficient evidence.
- Separate cost stewardship from performance management. An operator's use of a tool or model is not evidence of individual performance.
- Retain only the minimum local evidence needed for a stated review period. Access is governed by existing filesystem permissions and the organization's data policy. Aggregate policy reporting must be derived without centralizing raw audit, candidate, verification, or measurement JSON.

## Versioned policy direction

Maintain policy as a reviewed, versioned document rather than a mutable convention. Each version should state its effective date, owner, scope, evidence required, thresholds, exceptions, review date, and rollback trigger. Start with guidance. Any later gate must name the exact command and threshold, preserve legacy CLI behavior, and be reversible by removing the external gate or reverting the policy version.

Do not turn vendor assumptions into policy. Adapter artifacts and capabilities change, so pin policy to observed local behavior and periodically revalidate it against current documentation and fixtures.

## Evidence classes

| Classification | Meaning | Allowed decision use |
|---|---|---|
| Measured | Direct local observation, such as file bytes or supplied usage data. | Baseline and verification facts. |
| Estimated | A reproducible approximation, such as character-derived tokens or server-list tool assumptions. | Ranking and advisory prioritization. |
| Modeled | A projection from stated assumptions, such as session-cost impact. | Scenario planning only. |
| Observed outcome | Comparable pre/post task evidence with a declared completion standard and quality guardrails. | CPCT outcome claim only. |
| Unknown or unavailable | Data was not accessible or supported. | No savings or non-use inference. |

A verified candidate proves only immediate configuration and structural checks. It is not an observed CPCT improvement. Label outcome as pending until comparable cohorts meet the declared standard, preserve completion quality and volume, and include failed and abandoned spend.
