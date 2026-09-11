---
name: source-observe
description: Use when cataloging or annotating visible construction in photographs or scan RGB, especially before registration or while the base model may be replaced.
---

Build a bounded, source-linked inventory that remains useful without a house coordinate system. Read [source-observations.md](../../references/source-observations.md) for the observation, identity, endpoint and placement records.

1. Select a coherent photographic scope and inspect the original images. Preserve source bytes, extraction provenance and the mapping between displayed and native pixels.
2. Record visible member faces, pipe/cable spans, boxes, fittings and candidate hardware as individually identified observations. Separate visible facts, tentative classification, endpoint meaning and present-day survival.
3. Produce annotated source sheets from the stored pixel marks. Use [`scripts/observations.py`](../../scripts/observations.py) when the source is a standalone JPEG or PNG and the record matches the documented contract. Treat the whole-source sheet as orientation and context, then open each generated native-scale assertion crop and confirm the mark lies on the claimed construction. For every polyline endpoint, inspect its dedicated crop and check that the authored endpoint kind and basis match the visible transition. A plausible overview or valid coordinate transform is not this review.
4. Record the checked assertion-crop path and hash, mark status and finding, plus every endpoint-crop path/hash, checked status, kind and finding. Keep the observation pending when the feature or transition is ambiguous. Correct misplaced marks, downgrade unsupported endpoint meanings to `unknown` or `annotation boundary`, regenerate into a fresh directory and repeat review before using the observation to support identity or geometry.
5. Link observations to a bounded physical feature or group only with stated correspondence evidence. Record construction-state differences and occlusions alongside matches; assess capture chronology and current survival separately. Keep later depth measurements, registrations and candidate placements in separately referenced records.

A useful inventory can have no depth, no physical dimensions and no accepted placement. Continue supported observation work while those questions remain open. Use `depth-inspect`, `scan-register` and `blender-reconstruct` when advancing to their respective evidence stages.
