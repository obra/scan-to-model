---
name: depth-inspect
description: Inspect native RGB, depth, confidence, calibration, and poses to make finite, source traceable reference points and surface measurements.
---

Use when depth availability, orientation, or surface support is in question. Record RGB/depth/confidence/calibration orientation and selectable raw/clean depth and raw/corrected pose variants. Distinguish depth availability from local repeatability and absolute accuracy. Flag glass background returns, occluded furniture, opaque surfaces without support, and nonfinite samples.

Segment physical patches before fitting: ramp, floor, curb, soffit, jamb return, and other planes are separate surfaces. Retain rejected samples, all point residuals, and inlier statistics. Read [formats.md](../../references/formats.md) and [evidence-workflow.md](../../references/evidence-workflow.md).

Use `scripts/surfaces.py` with the exact filename stem, image orientation, physically reviewed polygon, surface identity and selected variants. Inspect both the photo polygon and native depth map in its output. Reject proposals that include a door, object or another plane even if their labels sound correct. Do not convert a contact-sheet index into a timestamp by estimation; look it up in the index.

Compare the same physical patch only within a shared coordinate frame and overlapping footprint. Reserve sufficiently separated views and independent features to expose pose/depth correlation. Report support counts, all-sample and retained residuals, overlap size and cross-view disagreement separately. Measure a slope freely before deciding whether it should be horizontal. Do not call a mixed ramp/floor fit a scan error.

If a boundary lacks native depth, report it as an image observation or an intersection inferred from identified planes. Do not give that boundary the same confidence as a directly supported patch. An optional physical length can check absolute scale; it is not a prerequisite for processing calibrated native depth.
