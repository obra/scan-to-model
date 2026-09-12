---
name: depth-inspect
description: Inspect native RGB, depth, confidence, calibration, and poses to make finite, source traceable reference points and surface measurements.
---

Use when depth availability, orientation, or surface support is in question. Record RGB/depth/confidence/calibration orientation and selectable raw/clean depth and raw/corrected pose variants. Distinguish depth availability from local repeatability and absolute accuracy. Flag glass background returns, occluded furniture, opaque surfaces without support, and nonfinite samples.

Segment physical patches before fitting: ramp, floor, curb, soffit, jamb return, and other planes are separate surfaces. Retain rejected samples, all point residuals, and inlier statistics. Read [formats.md](../../references/formats.md) and [evidence-workflow.md](../../references/evidence-workflow.md).

Use `scripts/surfaces.py` with the exact filename stem, image orientation, physically reviewed polygon, surface identity and selected variants. Declare the capture's tracking segment when its camera metadata supplies one, especially before applying a registered transform; the declaration must match the native raw camera rather than a filename or corrected-pose inference. Preserve missing segment metadata as unknown instead of substituting segment 0. Inspect both the photo polygon and native depth map in its output. Reject proposals that include a door, object or another plane even if their labels sound correct. Do not convert a contact-sheet index into a timestamp by estimation; look it up in the index.

Each measured patch reports native depth zero/nonzero, in-range/out-of-range and confidence-value counts over the selected mask. These counts describe encoded availability and filtering only; they do not establish physical support or sensor accuracy. With `--pixel-inspections`, the source crop also marks the eligible native depth sample centers after the existing depth-to-RGB mapping and records that mapping for pending visual review.

Before running a measurement, bind the exact reviewed selection record and serialized spec hashes. Programmatically compare the frame/source identity, orientation and polygon between the reviewed selection and the spec, then verify those same fields in the output. A revised preview does not authorize reusing an earlier mask whose serialized selection was not updated.

To review mapped sample locations before fitting, set `"fit": false` on every patch and `"comparisons": []` in the spec. Inspect the retained eligible native pixels and points against the source; this mode does not validate the selection's physical meaning. Its all-false `inlier_mask` means not fitted, not rejected samples. Enable fitting only in a fresh run after physical sample review; see [formats.md](../../references/formats.md).

For small patches or ambiguous edges, add `--pixel-inspections`. Inspect the complete unmarked/marked polygon crop and every vertex's native-pixel context before interpreting support. Nearest-neighbor enlargement adds no detail, and a clean vertex does not prove the polygon interior avoids another surface. These optional outputs leave sampling and fitting unchanged and remain pending human review.

Compare the same physical patch only within a shared coordinate frame and overlapping footprint. Reserve sufficiently separated views and independent features to expose pose/depth correlation. Report support counts, all-sample and retained residuals, overlap size and cross-view disagreement separately. Measure a slope freely before deciding whether it should be horizontal. Do not call a mixed ramp/floor fit a scan error.

If a boundary lacks native depth, report it as an image observation or an intersection inferred from identified planes. Do not give that boundary the same confidence as a directly supported patch. An optional physical length can check absolute scale; it is not a prerequisite for processing calibrated native depth.
