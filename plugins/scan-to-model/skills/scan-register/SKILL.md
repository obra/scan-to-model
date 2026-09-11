---
name: scan-register
description: Fit and independently validate rigid scan alignment from named, source traceable correspondences.
---

Use for aligning captures or references to existing fixed geometry. Fit one rigid transform from distributed shared opaque surfaces and landmarks, with explicit `fit` and withheld `check` roles. Report all and inlier residuals, holdout residuals, scale policy, source frame/pixel provenance, and unresolved regions. Independent checks must not tune the fit.

Use planar and right angle constraints only where supported. Do not bend rooms, move levels independently, or absorb drift into plausible walls. Read [formats.md](../../references/formats.md) and [evidence-workflow.md](../../references/evidence-workflow.md).

Use `scripts/register.py` for paired landmarks with known source and target coordinates. Its transform is source-to-target, rigid, metre scale; it does not automatically certify acceptance. Identify each match visually from fixed details. Color alone, a repeated tile pattern or furniture position does not establish correspondence.

When native camera records declare tracking segments, record the accepted transform scope as exact `(capture_id, tracking_segment)` pairs. Before placement or reprojection, require the source frame's capture and tracking segment to match one accepted pair; reject missing or mismatched scope before applying the matrix. A frame outside that scope may still support source-local appearance or census observations when the record makes no placement claim. Register and accept the other scope separately before using it for metric placement.

Distribute fitting constraints across position and orientation, then check separate frames/features at both ends of the proposed connection. Compare planes over actual overlap rather than extrapolating tilted planes across a room. Report a regional transform if only part of a long scan passes. Keep a room adjacency/level check so a visually tidy plan cannot hide an incorrect junction.
