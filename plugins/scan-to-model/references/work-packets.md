# Reusable work packets

Use this reference to give a bounded worker or reviewer enough context to produce a reusable project record. It is a prompt pattern, not a queue format or executor. Keep the job-specific room, source, model, paths and decisions in the private project.

## Shared brief

```text
Work item: <stable project ID and one-sentence decision>
Role: <the agent executing this work item: planner/PM, source examiner, geometry builder, or independent reviewer>
Dependencies / accepted scope: <records, accepted transforms, and prerequisite review that must remain valid>
Readiness: <ready to dispatch, or planning-only with the missing prerequisites>
Parent milestone: <the larger project milestone; do not treat this work item as the milestone itself>
Investigation outcome: <what this bounded item can establish, or the explicit unknown it may preserve>
Inputs: <absolute or project-relative paths, source IDs, model/transform IDs, and SHA256 values>
Allowed outputs: <fresh output directory and the exact records/artifacts it may contain>
Scope: <one room, connection, source route, or review contract>
Required return: <source observations, measurements, candidate diff, review receipt, or a stated no-result>
Next gate: <the concrete evidence or review required before the next stage>
Stop/escalate when: <identity, scope, conflicting control, accepted-geometry, or validation condition that needs an operator>
```

The `Role` names the agent executing the work item, not the person or agent who authored the brief. Bind immutable inputs before work and write only to fresh allowed outputs. Report what was actually opened or measured, preserve rejected alternatives and unresolved limits, and distinguish a finished investigation from a finished project milestone. A reviewer must be able to follow each claim to the project records and source components. Use [project-records.md](project-records.md) as the record authority and [evidence-workflow.md](evidence-workflow.md) for provenance and uncertainty rules. A discovery job binds its starting index or input set and may return newly identified frame or source bindings; it does not require undiscovered frame IDs as prerequisites. Mark the packet planning-only when a required accepted scope or input is still missing.

## Planner or PM

```text
Choose one bounded next increment from the project's coverage atlas and register. Prioritize coordinate ties, levels and envelope; then major surfaces and connections; then fixed assemblies and contents; then fine details. Stable regions may advance independently. Name the exact source and expected decision, retain the parent milestone separately, and state a finite success condition and stop condition. Return a small machine-readable or Markdown work brief with inputs, allowed output paths, dependencies, next gate and unresolved obligations. Do not count indexed, reviewed, or partially reconciled work as accepted geometry without the project's acceptance record. After an exhausted bounded attempt, repeat only for a genuinely different source or question.
```

Use [scan-to-model](../skills/scan-to-model/SKILL.md) for routing and [project-records.md](project-records.md) for coverage, handoff and bounded completion.

## Source examiner

```text
Inspect the named original photos or native frames and preserve their hashes and display/native mapping. Record visible physical facts, candidate identity, endpoint meaning, chronology and uncertainty separately. Return exact opened-source records, marked review artifacts and a finite result or no-result. Route native depth and surface support through the depth-inspect skill, and rigid correspondence questions through the scan-register skill. Escalate an ambiguous physical identity, conflicting fixed control or unsupported endpoint instead of inventing a match or placement.
```

Use [source-observe](../skills/source-observe/SKILL.md), [formats.md](formats.md), and [source-observations.md](source-observations.md) for the source record and review contract. Route native depth and surface support to [depth-inspect](../skills/depth-inspect/SKILL.md), and rigid correspondence questions to [scan-register](../skills/scan-register/SKILL.md).

## Geometry builder

```text
Build only the named candidate increment in a fresh candidate/output path. Preserve unrelated architecture, current finishes, contents, historical construction and observed services as separate categories. Bind source records and accepted transforms before using coordinates; keep diagnostic or provisional results out of physical contacts. Return the candidate hash, changed object IDs, input bindings, unresolved dimensions, inventory comparison and reviewed renders. Escalate any proposed change to accepted geometry, transform scope or physical identity that lacks the required independent record.
```

Use [blender-reconstruct](../skills/blender-reconstruct/SKILL.md), [blender-review.md](blender-review.md), and [manufactured-shapes.md](manufactured-shapes.md) for candidate, component and saved-file contracts.

## Independent reviewer

```text
Review the supplied candidate or evidence packet against its declared scope and immutable input hashes. Preserve the evidence packet itself, including failed attempts and retained inputs. Use a fresh review output directory; retain command, runtime, failure and receipt details. Archived producers may write beside their scripts, so inspect write behavior before rerunning and use frozen input copies or an explicit fresh output path. Check source identity, accepted versus diagnostic roles, preservation of unrelated content, model membership and visual evidence. Return pass, bounded pass, or fail with exact findings and the next gate. Do not repair the candidate, promote geometry, or treat a valid tool receipt as proof of depicted pixels or physical acceptance.
```

Use [blender-review.md](blender-review.md) for saved-scene and presentation review. For scripted presentations, validate the contract and hash-bound sample receipt with `scripts/presentation.py`, then inspect the actual sample images.

## Reusable-tool learning loop

When a recurring mechanical operation is demonstrated, capture it as a tested script or fixture. Capture stable interpretation rules as a skill or reference. Capture repeated worker/reviewer boundaries as this prompt pattern. Keep publishing authorization project-owned, and keep private scans, models, addresses and owner observations out of the plugin.
