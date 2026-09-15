# Reusable work packets

Use this reference to give a bounded worker or reviewer enough context to produce a reusable project record. It is a prompt pattern, not a queue format or executor. Keep the job-specific room, source, model, paths and decisions in the private project. Pair it with [goals.md](goals.md) when the work item belongs to a larger completion goal.

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

For a new attempt, freeze the maintained plugin entrypoint, launcher and worker bytes before execution instead of replaying obsolete launcher defaults; preserve historical frozen runs unchanged.

Before a source-readiness worker reads a predecessor producer, resolve the work item's stable candidate ID through the active routing queue and accepted ledger to the latest explicit root disposition. Carry identity, metric, placement and physical-contact status separately: an accepted source identity or qualified diagnostic does not make the other scopes accepted. Preserve that disposition in the handoff and do not propose an existing accepted identity gate as new work; only a genuinely different source or question reopens it. For capture denominators, validate every capture/frame pair against its declared index before taking a filename or frame-ID set union; rotation checks and reviewed PDF pages do not establish full-resolution photograph inspection.

## Planner or PM

```text
Choose one bounded next increment from the project's coverage atlas and register. Prioritize coordinate ties, levels and envelope; then major surfaces and connections; then fixed assemblies and contents; then fine details. Stable regions may advance independently. Name the exact source and expected decision, retain the parent milestone separately, and state a finite success condition and stop condition. Return a small machine-readable or Markdown work brief with inputs, allowed output paths, dependencies, next gate and unresolved obligations. Do not count indexed, reviewed, or partially reconciled work as accepted geometry without the project's acceptance record. After an exhausted bounded attempt, repeat only for a genuinely different source or question.

First reconcile structured package actions to the latest accepted source dispositions, then run `scripts/plan_actions.py` to keep machine and human plan actions aligned; matching actions alone do not establish physical readiness.
```

Use [scan-to-model](../skills/scan-to-model/SKILL.md) for routing and [project-records.md](project-records.md) for coverage, handoff and bounded completion.

For a follow-up to a settled source investigation, preserve the settled status and attach successor evidence as a handoff note tied to the current project next gate. Do not use an expected-state guard to reopen the investigation or create a new milestone; consult the Chit command's `status` and `help` output for the note syntax.

## Source examiner

```text
Inspect the named original photos or native frames and preserve their hashes and display/native mapping. For native capture frames, derive ordinals programmatically from the declared source inventory and record the index basis; for Polycam use `polycam.capture_inventory(root)["frame_ids"]`. Verify each immutable frame ID to native ordinal mapping. Keep contact-sheet/display positions separate, and never copy native ordinals from narrative or contact labels. Bind the exact reviewed selection record and serialized spec hashes; compare frame/source identity, orientation and polygon before running a measurement, then verify those same fields in the output. A revised preview does not authorize reusing an earlier mask whose serialized selection was not updated. Record visible physical facts, candidate identity, endpoint meaning, chronology and uncertainty separately. Return exact opened-source records, marked review artifacts and a finite result or no-result. Route native depth and surface support through the depth-inspect skill, and rigid correspondence questions through the scan-register skill. Escalate an ambiguous physical identity, conflicting fixed control or unsupported endpoint instead of inventing a match or placement.

For exact Polycam frame retention, run `python3 scripts/retain_frames.py --capture <capture> --frame-id <id> --orientation upright90cw --output <fresh-output>`. Repeat `--frame-id` for each selected frame and add repeatable `--record <path>` to retain exact selection, spec or other record bytes. The command derives zero-based native ordinals from the inventory, validates the selected RGB/camera sources before writing artifacts, retains their original bytes and source manifest when present, and creates lossless display PNGs. Use the generated `frame-retention.json` paths, hashes, dimensions and pixel mapping; its `records[].original_record.sha256` hashes the actual record bytes separately from any `model_sha256`. Retain the output receipt and its sibling `.<output-name>.frame-retention-runtime` directory containing the producer and helper bytes frozen before processing.

Before using an external-tool empty output as evidence of absence, verify that the executable ran successfully and inspect its exit status and stderr. A missing tool, command-not-found error, redirected error, or failed invocation means the scope is unexamined, not absent.

Source identity includes the assembly side and face. Before concluding that a new view adds nothing, compare its actual image with the accepted source image; record newly visible face coverage separately from uncertain thickness or placement.

Keep page-left/right, pixel or upright orientation, geographic cardinal direction, project axes and legacy object names as separate conventions. Use bound compass or site evidence together with identifiable landmarks before assigning directional report groups to plan or model regions; page-right alone does not establish east, and numeric group counts do not locate individual components.

Before selecting same-kind objects or subtracting completed obligations, match each item to its explicit physical room, level and capture identity; report different identities as excluded and do not substitute same-named items from another level or capture. Resolve feature membership from saved `feature_id`/`room_id` and accepted-ledger annotations; a multi-room component approval does not make every feature shared. Separately verify authoring-record presence and native Blender-object presence: geometry JSON or detail rows are records until native presence is independently confirmed. Name resemblance is a discovery hint, not scope fulfillment. Follow the explicit bound path and JSON selector contract before reporting membership unavailable; a limited lookup is not evidence of archive absence. Label saved-snapshot membership separately from current native presence and retain later holds.

Distinguish the original source-control record from the actual rendered manufactured mesh. Analytical source provenance, or unknown reveal depth, does not by itself exclude shape correction of a complete visible manufactured pane when rectangularity is established; preserve raw controls and dimensional limits. A curtain or crop boundary is not a physical pane boundary and cannot be completed into a rectangle from the crop alone.

For source-readiness checks, perform the queue and ledger disposition lookup before opening predecessor reports or producers. An accepted identity check is a dependency to carry forward, not a new proposed gate; keep any separately pending metric, placement or contact scope explicit.

Inspect the current model or project alignment manifest before declaring a source unplaced. Distinguish a defined seed or source coordinate convention from independently validated metric registration; when an authoritative convention applies to the exact source scope, reuse it once for qualified candidates without inventing another fit gate, preserving its datum and accuracy limits. A matrix merely present or applied does not establish acceptance or extend scope.
```

Use [source-observe](../skills/source-observe/SKILL.md), [formats.md](formats.md), and [source-observations.md](source-observations.md) for the source record and review contract. Route native depth and surface support to [depth-inspect](../skills/depth-inspect/SKILL.md), and rigid correspondence questions to [scan-register](../skills/scan-register/SKILL.md).

For raw Polycam camera centers, use `polycam.camera_matrix(camera)[:3, 3]` or the origin returned by `polycam.pixel_ray`; these poses are camera-to-world, so inverting them produces the wrong center. Compare camera positions only within the same tracking segment and frame convention unless a reviewed intersegment relation exists.

When projecting reviewed world points, use `polycam.project_points` to obtain native RGB pixels and positive camera-axis depths, then convert those native pixels with the existing `display_pixel_center` helper for presentation. First round-trip saved depth-grid points against the actual RGB/depth resolution ratio and check native/display known corners; only then interpret cross-view errors. Do not apply upright rotation inside the projection helper.

Observation marks in `observations` (`marks.coordinates`) and native depth arrays from `surfaces.py` are native RGB/depth pixels as declared by the serialized spec. Pass native RGB pixels to `polycam.pixel_ray` with `orientation='raw'`; use `upright90cw` only with actual display coordinates, and never rotate a native coordinate twice. For source/model buffer checks, apply the declared `raw_to_display_matrix` before comparing against native local buffers; never invert quantized world points to manufacture an exact local fingerprint.

## Geometry builder

```text
Build only the named candidate increment in a fresh candidate/output path. Preserve unrelated architecture, current finishes, contents, historical construction and observed services as separate categories. Bind source records and accepted transforms before using coordinates; keep diagnostic or provisional results out of physical contacts. Return the candidate hash, changed object IDs, input bindings, unresolved dimensions, inventory comparison and reviewed renders. Escalate any proposed change to accepted geometry, transform scope or physical identity that lacks the required independent record.

For a room's native extraction or drawing, derive membership from accepted object/feature records and semantic room tags; inspect shared collections as well as room collections, then compare the live membership with the declared set so collection layout cannot silently drop artwork or other contents.

When a geometry or drawing producer adds a collection, reconcile its accepted room and level ownership against every relevant saved view intent and compare before/after visible sets. Verify upstairs additions stay out of lower-only views while retained upstairs and full-house views remain; collection names are discovery hints, not authority. If a collection mixes levels, use scoped layer hides instead of excluding it wholesale. Reuse the maintained helper's equality-based RNA selection and assert the intended view layer is enabled before rendering.

Before handing a drawing contract to root, call the maintained `validate_view_frame` on every proposed view. Check the physical outside or inside viewpoint separately against accepted geometry; mathematical handedness does not establish the building side.

For native extraction, preserve the exact producer bytes beside each attempt, whether it succeeds or fails. If correction is needed, use a fresh runtime directory and bind that process to its own frozen producer, inputs and outputs; if failed-producer bytes are unavailable, record that gap explicitly rather than claiming complete preservation.

When reading native geometry from an editable mesh with modifiers, compare the reported original and evaluated topology counts and retain the modifier records; a count difference alone is not evidence of a stale model.

Source-authoring geometry may serve as qualified base geometry only after exact current coordinate and polygon buffer matching plus frame, parent, constraint and modifier checks. Keep evaluated shape and view visibility separate; names, bounds or hashes alone do not establish geometry, and an unevaluated `matrix_world` may be a stale pose even for an unparented object. Freeze the original authoring and producer bytes before execution, then retain the inputs and results.

For geometry producers, declare the source and destination coordinate frames and apply the source-to-model transform exactly once before deriving extents, voids, or attached parts. When a reviewed plan supplies explicit vertices and faces, consume those arrays verbatim and validate the resulting mesh against the plan. Appearance parameters are not geometry: resolve shader inputs, UV mapping, and created datablock names in the saved candidate and record those resolved values in the receipt.

Compute any reported reprojection from the actual geometry through the maintained projection helper; copying input pixels is not reprojection evidence. Parse or read back saved geometry exports and compare both their vertices and face winding against the reviewed plan before accepting them.

Reuse `geometry.panel_quad` for regular planar faces so its finite and increasing bounds and outward-orientation checks apply. A physical perforated panel retains its filled surface minus actual apertures; tracing aperture outlines with curves is not equivalent. When an accepted panel mesh already supplies the true holes, reuse its saved surface geometry within the authorized coordinate transform instead of recreating it from contours.
```

Use [blender-reconstruct](../skills/blender-reconstruct/SKILL.md), [blender-review.md](blender-review.md), and [manufactured-shapes.md](manufactured-shapes.md) for candidate, component and saved-file contracts.

## Independent reviewer

```text
Review the supplied candidate or evidence packet against its declared scope and immutable input hashes. Preserve the evidence packet itself, including failed attempts, their exact producer bytes when available, and retained inputs. Use a fresh review output directory; retain command, runtime, failure and receipt details. Archived producers may write beside their scripts, so inspect write behavior before rerunning and use frozen input copies or an explicit fresh output path. Check source identity, accepted versus diagnostic roles, preservation of unrelated content, model membership and visual evidence. Return pass, bounded pass, or fail with exact findings and the next gate. Do not repair the candidate, promote geometry, or treat a valid tool receipt as proof of depicted pixels or physical acceptance.

Shader reviews use the actual saved native objects and materials; recreating geometry with guessed material colors is not a shader review. For selected assembly views, prefer a disposable scene linking the selected native objects and their parent ancestors with one review view layer, or use the maintained helper's explicit single-layer control. Frame each camera from the subject bounds rather than a default orthographic scale.

Preservation is fail-closed: additions must match the exact declared allowlist, while undeclared changes or removals across every compared datablock fail the review. Match scene identities and list counts before pairing scene records; never zip unmatched lists and treat the comparison as complete.
```

Use [blender-review.md](blender-review.md) for saved-scene and presentation review. For scripted presentations, validate the contract and hash-bound sample receipt with `scripts/presentation.py`, then inspect the actual sample images.

## Reusable-tool learning loop

When a recurring mechanical operation is demonstrated, capture it as a tested script or fixture. Capture stable interpretation rules as a skill or reference. Capture repeated worker/reviewer boundaries as this prompt pattern. Keep publishing authorization project-owned, and keep private scans, models, addresses and owner observations out of the plugin.
For explicit world-space mesh replacement in Blender, use the maintained [`blender_mesh.py`](../scripts/blender_mesh.py) helper and its fixture rather than reimplementing transform or face-order handling.
An older readback may be reused for qualified polygon geometry only when its [`mesh_fingerprint.py`](../scripts/mesh_fingerprint.py) coordinate and polygon hashes and its frame, parent and modifier scope match the current inventory; age or bounds alone neither establishes nor refutes currentness. Exact source and input scope remain an acceptance decision.
