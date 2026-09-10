# Project records and handoff

Maintain small human-readable Markdown/JSON files in the project. Reuse existing records rather than introducing a second source of truth. A project can choose its exact filenames. Save references to actual source components and tool outputs, not just prose claims.

## Source ledger

For each capture record its archive path/hash, capture date and condition, extracted root, image/depth/confidence/camera counts, available variants, calibration/units, audit results, and source-frame index. Separate intake, full-photo examination, depth measurement, registration, modeling and saved-file review status. Capture dates may come from owner context rather than the export's internal timestamp.

## Coverage atlas

Use one row per room surface or connection: floor, each wall/opening, ceiling/soffit, adjacent room/landing, and visible service segment. Record supported/partial/conflicting/inaccessible/unobserved, dated sources, what was actually examined, remaining constraint, and next action. Maintain the room adjacency graph alongside the plan. A doorway seen from one room does not certify the adjoining room's depth or the inter-room transform.

## Owner observations

Record the owner's statement, date and affected element. Preserve the distinction between an observation, an approximate estimate and a measured value. Do not promote a guessed wood species into a confirmed material or a unit conversion into scanner precision. Use owner corrections immediately for topology/identity; find metric support separately.

## Registration ledger

For each transform name source and target frames, metre scale, axes, camera convention, rigid matrix direction, source frame/pixel selections, fitting method, fit and withheld checks, and accepted regional scope. Keep rejected alternatives with the reason if they prevent repeating a known error. Never apply an accepted transform to another capture by filename resemblance. Never scale or warp a capture to conceal misalignment.

## Model change record

Link the input file hash, candidate, objects added/changed, source selections, accepted transforms, unresolved dimensions, inventory comparison, and reviewed render paths. Separate hidden display thickness from measured visible surfaces. Preserve removed or superseded evidence in a dated project checkpoint when needed; do not quietly rewrite unrelated geometry.

## Capture requests

Generate requests only after checking supplied evidence. For each missing fact, show a real source image with the target marked, identify a reachable camera position, the physical surface or shared doorway/ceiling needed, and the reason. Prefer short overlapping walks and stationary sharp views across a connection. Record inaccessible obstructions so the owner is not repeatedly asked to move them. An independent ruler/tape control is optional when sensor absolute accuracy or a repeatability conflict remains unresolved; missing depth and missing physical control are different problems.

## Bounded completion

Finish one room/connection increment with its ceilings and connections, source-backed geometry, uncertainty, saved-file review and a concrete remaining list. Do not call the building complete because the intake pipeline ran or a plausible render exists. A review candidate may be complete as a deliverable while its geometry is still provisional; name both facts plainly.
