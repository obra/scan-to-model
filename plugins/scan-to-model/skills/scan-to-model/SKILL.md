---
name: scan-to-model
description: Coordinate evidence based reconstruction from scans, photos, plans, and measurements into a reviewable Blender architectural model.
---

Use this skill for an end to end scan to model task. Keep source intake, depth inspection, surface measurement, registration, modeling, and visual review as separate evidence records. Preserve immutable source hashes and identify every claim as observed, measured, inferred, owner supplied, historical, or unknown.

Read [evidence-workflow.md](../../references/evidence-workflow.md) for shared provenance, uncertainty, coverage, and modeling rules. Route archive work to `scan-ingest`, photograph-first construction inventories to `source-observe`, native depth questions to `depth-inspect`, rigid alignment to `scan-register`, and Blender edits/review to `blender-reconstruct`.

1. Inspect the existing project's source ledger, model, accepted transforms, owner corrections and unresolved coverage. Preserve work already done; do not restart the reconstruction or inherit an unverified transform.
2. State a bounded next increment: one room with its ceilings/connections, or one named missing connection. Name the sources and the reviewable output. Proceed with previously authorized work; ask only for missing information that changes the result.
3. Ingest new archives, examine all contact sheets and sharp source frames, then update the coverage atlas. Keep photo examination distinct from depth support.
4. Measure only physically identified patches. Validate room/level joins with opaque shared features and independent views before integrating geometry.
5. Build and inspect a saved Blender candidate. Preserve unrelated architecture and contents. Promote supported changes and report exactly what remains provisional.
6. Update the project handoff so the next scan adds evidence to the same coordinate system and coverage record.

A photograph-first inventory can proceed while the base geometry or registration is under review. Keep source observations and tentative feature identities separate from replaceable model placements; see [source-observations.md](../../references/source-observations.md).

Use [project-records.md](../../references/project-records.md) for source, room/connection, observation, registration and model records. Use the package scripts through [formats.md](../../references/formats.md). These are local tools; keep private project evidence outside the plugin package. If delegating, give mechanical intake/index tasks a precise contract and independently verify counts, timestamps and marked pixels before using their outputs as geometry evidence.

Current finishes lead current geometry; historical open wall material supplies services only where spatially reconciled. Leave unsupported connections visibly unresolved and ask only for a specific missing physical fact when it cannot be recovered from supplied evidence. Do not add approval gates or depend on Superpowers.
