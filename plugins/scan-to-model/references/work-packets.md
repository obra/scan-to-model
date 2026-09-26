# Reusable work packets

Use this reference to give a bounded worker or reviewer enough context to produce a reusable project record. It is a prompt pattern, not a queue format or executor. Keep the job-specific room, source, model, paths and decisions in the private project. Pair it with [goals.md](goals.md) when the work item belongs to a larger completion goal.

## Outcome-first execution

- Finish an existing candidate's acceptance and delivery before growing the geometry queue. Default to one active geometry increment, including review, correction and delivery, plus one independent source/records lane. From a backlog, select one candidate to finish; leave the others queued rather than sending the entire batch for review. Additional parallel work needs named independent acceptance owners with demonstrated capacity, not just available builders or reviewers. The coordinator remains a bottleneck when every result still requires its judgment.
- Bound each attempt by a named source selection, candidate or decision and a finite stop condition. A no-result is a valid investigation outcome, not physical completion. Park the item with its exact missing fact and continue supported independent work. Before reopening, name new evidence, a corrected invalid method or a materially different question, and explain how it could change the decision. More samples of the same occluded edge, a renamed packet or a fresh reviewer alone do not qualify.
- Give a worker a complete brief and return contract, then review the returned result. Batch findings into one actionable review. Further cycles address named defects or changed evidence, not repeated status requests; escalate a repeated unresolved identity or scope decision instead of sending the same work around again. Necessary failed checks still block acceptance.
- Review physical meaning before presentation polish. Compare the affected assembly's extent, placement and contacts with available source views and owner corrections; hashes and rendered coverage cannot establish those relationships. Hold affected final sheets when a visible source conflict remains. Clearly labeled diagnostic or historical sheets may be retained without counting as final acceptance.
- Reuse valid checks bound to immutable inputs. A changed model, producer, relevant runtime or failed check justifies targeted revalidation; copying byte-identical artifacts to a verified destination does not by itself require rendering again. Preserve source bindings, saved-file checks, failures and delivery verification, but update the existing authoritative records together once at the end of the increment. Do not add a second queue or a review of a review receipt without a concrete unmet requirement.
- Tool or instruction work must name the present obstacle, the smallest useful correction and the deliverable it enables. Test the correction and use it on that deliverable before treating it as useful progress. Defer speculative dashboards, generic frameworks and polishing that do not improve the current outcome; a short existing procedure can be cheaper than new automation.

## Model selection

Use the fastest, lightest available model that can meet the task's acceptance check. Check the runtime's actual choices and required image, tool and context capabilities; use observed quality and latency where available, not a permanently prescribed model name. Honor an explicit owner choice. Coordinator or reviewer status alone does not require the strongest model.

- Run existing scripts directly for deterministic inventory, hashes, conversions and checks. Do not spawn a worker just to launch a script; choose a model only for the judgment the tool cannot supply.
- Use a small model for bounded text, record and implementation work with clear inputs and a checkable return. For image interpretation, choose a model that can actually inspect the supplied images; a text-only worker cannot certify pixels from labels or receipts.
- Establish the visual reviewer's capability on the first representative region. Source-to-model finish review can require perspective, occlusion, shape and material interpretation even for one room. A reviewer that invents an absence, mounting or fixture type has failed that check; give the unresolved comparison to a stronger image-capable model before authoring its proposed corrections. Keep the lighter model on work it has demonstrated it can do well.
- Start with a lighter capable model for clear visual checks. Verify that its claimed discrepancy is visible in the supplied views: an out-of-frame object is not absent, and an ambiguous silhouette does not establish mounting or profile. Use another view or native inspection to resolve that ambiguity; escalate unresolved physical identity, conflicting controls or cross-region decisions to a stronger image-capable reasoning model. Supply the concrete conflict and prior result. Missing evidence remains missing regardless of model strength; do not repeat unchanged attempts or manufacture certainty.
- Reconstructing an entire house from an unstructured RGB-D capture combines topology, coordinate interpretation, geometry and visual judgment. Treat that as complex reasoning when choosing the lead model; reserve small workers for bounded pieces with independently checkable returns. If a prior end-to-end run guessed the layout, missed source regions or evaded a failed check, change the method and escalate the lead model before a fresh retry. Lower latency is not success when the result fails the requested quality.
- Keep tiny tasks in the current agent when dispatch costs more than it saves. If this runtime cannot switch models or delegate, do the authorized work with available capabilities and state a material limitation; never claim a model switch that did not happen.

When delegating, include the required capability, bounded return and quality check in the existing brief. Verify that return before relying on it, escalate only the unresolved part, and use a lighter model again for subsequent routine work. Model selection needs no separate ledger or supervisory loop.

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
Acceptance check: <the physical relationship or evidence contract the reviewer must verify>
Next gate: <the concrete evidence or review required before the next stage>
Attempt bound / stop: <finite source selection or candidate check; no-result and escalation conditions>
Reopen reason, if any: <changed evidence, corrected method or different question and its expected decision impact>
```

The `Role` names the agent executing the work item, not the person or agent who authored the brief. Bind immutable inputs before work and write only to fresh allowed outputs. Report what was actually opened or measured, preserve rejected alternatives and unresolved limits, and distinguish a finished investigation from a finished project milestone. A reviewer must be able to follow each claim to the project records and source components. Use [project-records.md](project-records.md) as the record authority and [evidence-workflow.md](evidence-workflow.md) for provenance and uncertainty rules. A discovery job binds its starting index or input set and may return newly identified frame or source bindings; it does not require undiscovered frame IDs as prerequisites. Mark the packet planning-only when a required accepted scope or input is still missing.

## Planner or PM

```text
Choose one bounded next increment from the project's coverage atlas and register, finishing an existing candidate before dispatching more geometry. Prioritize coordinate ties, levels and envelope; then major surfaces and connections; then fixed assemblies and contents; then fine details. Stable regions may advance independently within available acceptance capacity. Name the exact source and expected decision, retain the parent milestone separately, and state a finite success condition and stop condition. Return a small machine-readable or Markdown work brief with inputs, allowed output paths, dependencies, next gate and unresolved obligations. Report delivered geometry, completed investigations, delivered documentation and remaining blockers separately; do not count worker activity or receipts as physical completion. Apply the outcome-first execution rules to retries, handoffs and tool work.
```

Use [scan-to-model](../skills/scan-to-model/SKILL.md) for routing and [project-records.md](project-records.md) for coverage, handoff and bounded completion.

## Source examiner

```text
Inspect the named original photos or native frames and preserve their hashes and display/native mapping. For native capture frames, derive ordinals programmatically from the declared source inventory and record the index basis; for Polycam use `polycam.capture_inventory(root)["frame_ids"]`. Verify each immutable frame ID to native ordinal mapping. Keep contact-sheet/display positions separate, and never copy native ordinals from narrative or contact labels. Bind the exact reviewed selection record and serialized spec hashes; compare frame/source identity, orientation and polygon before running a measurement, then verify those same fields in the output. A revised preview does not authorize reusing an earlier mask whose serialized selection was not updated. Record visible physical facts, candidate identity, endpoint meaning, chronology and uncertainty separately. Return exact opened-source records, marked review artifacts and a finite result or no-result. Route native depth and surface support through the depth-inspect skill, and rigid correspondence questions through the scan-register skill. Escalate an ambiguous physical identity, conflicting fixed control or unsupported endpoint instead of inventing a match or placement.
```

Use [source-observe](../skills/source-observe/SKILL.md), [formats.md](formats.md), and [source-observations.md](source-observations.md) for the source record and review contract. Route native depth and surface support to [depth-inspect](../skills/depth-inspect/SKILL.md), and rigid correspondence questions to [scan-register](../skills/scan-register/SKILL.md).

## Geometry builder

```text
Build only the named candidate increment in a fresh candidate/output path. Preserve unrelated architecture, current finishes, contents, historical construction and observed services as separate categories. Bind source records and accepted transforms before claiming measured placement or physical contacts. Carry existing interpolation permission into the brief: authorized inferred surfaces and joins may complete an approximation, with affected objects marked tentative and their basis and unresolved dimensions recorded. They do not establish accepted transforms or measured contacts. Check the assembly's visible extent, placement and contacts against sources before detailed drawings. Return the candidate hash, changed object IDs, input bindings, unresolved dimensions, inventory comparison and reviewed renders. Stop only the portion that requires an unmet evidence gate; continue work covered by the owner's authorization. Escalate a proposed change to accepted geometry, transform scope or physical identity that lacks the required independent record.

For a room's native extraction or drawing, derive membership from accepted object/feature records and semantic room tags; inspect shared collections as well as room collections, then compare the live membership with the declared set so collection layout cannot silently drop artwork or other contents.

For native extraction, preserve the exact producer bytes beside each attempt, whether it succeeds or fails. If correction is needed, use a fresh runtime directory and bind that process to its own frozen producer, inputs and outputs; if failed-producer bytes are unavailable, record that gap explicitly rather than claiming complete preservation.
```

Use [blender-reconstruct](../skills/blender-reconstruct/SKILL.md), [blender-review.md](blender-review.md), and [manufactured-shapes.md](manufactured-shapes.md) for candidate, component and saved-file contracts.

For a rendered result, include the context/detail source views, expected visible shape and finish, and the source-matched comparison in the brief. Apply [rendered-reconstruction.md](rendered-reconstruction.md) before repeating construction or material helpers across regions.

## Independent reviewer

```text
Review the supplied candidate or evidence packet against its declared scope and immutable input hashes. Preserve the evidence packet itself, including failed attempts, their exact producer bytes when available, and retained inputs. Use a fresh review output directory; retain command, runtime, failure and receipt details. Archived producers may write beside their scripts, so inspect write behavior before rerunning and use frozen input copies or an explicit fresh output path. Check source identity, accepted versus diagnostic roles, preservation of unrelated content, model membership and visual evidence. Return pass, bounded pass, or fail with exact findings and the next gate. Do not repair the candidate, promote geometry, or treat a valid tool receipt as proof of depicted pixels or physical acceptance.

Check the declared physical relationships before reviewing presentation polish. A narrow documentation scope or approximate label cannot excuse a known source conflict in affected final sheets. Return the concrete findings together; on a corrected return, recheck those findings and affected preservation contracts rather than restarting unrelated accepted work. Reuse immutable-bound evidence unless a changed input or discovered failure invalidates it.
```

Use [blender-review.md](blender-review.md) for saved-scene and presentation review. For scripted presentations, validate the contract and hash-bound sample receipt with `scripts/presentation.py`, then inspect the actual sample images.

## Reusable-tool learning loop

Use the outcome-first tool rule before extracting a recurring operation. When it helps the current deliverable, capture mechanics as a tested script or fixture, stable interpretation rules as a skill or reference, and repeated worker/reviewer boundaries as this prompt pattern. Verify the improvement on the blocked task, not just on its fixture. Keep publishing authorization project-owned, and keep private scans, models, addresses and owner observations out of the plugin.
