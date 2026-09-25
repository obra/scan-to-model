# Appearance and usable model delivery

Use this workflow when the requested result includes materials, renders, a portable native file or a browser model. Keep the requested outputs in one project-owned delivery job. A geometry-only task does not acquire a rendering, browser or publishing requirement. Existing authorization remains authoritative; record whether interpolation was authorized and its basis. Never equate visual completion with independent metric acceptance.

## Implementation decisions

The shared tools operate on an existing Blender candidate and an explicit object/source register. House-specific names, material choices, geometry authoring and private photographs stay in the project. The delivery path adds materials and presentation lights without changing model vertices or source properties. Mesh defects go back to the geometry authoring step for a bounded correction; the exporter does not silently weld, move or delete architecture.

`delivery_contract.py` validates the requested outputs and source closure. `appearance.py` implements calibrated depth-filtered projection, native-pixel exclusion masks, rectified repeated samples, matched colors and explicit inferred fallback. `mesh_quality.py` reports degenerate geometry, winding defects and overlapping coplanar surfaces. `delivery_runtime.py` locates helpers relative to its installed package, isolates Blender runtime state, hashes inputs and keeps one frozen helper copy per revision across runs.

Appearance methods remain distinct in the native metadata and delivery report:

- `matched-color`: a reviewed source-guided color, shared consistently across the assigned surfaces.
- `photo-projection`: actual source pixels surviving the depth, confidence, angle, highlight and exclusion-mask filters. Unsupported pixels use the declared inferred color; they are not counted as direct photographic coverage.
- `repeated-photo`: a reviewed source quadrilateral rectified and repeated in one world-coordinate material frame. The grain is photographic; placement and continuation are inferred.
- `inferred`: an explicitly chosen finish with its reason and no claim of direct photographic coverage.

Optional broad-illumination normalization preserves limited detail around a reviewed base color. It is an approximation, not recovered physical reflectance. Glass, mirrors, moving objects and strong shadows often need explicit masking or a different material method. Depth agreement alone does not establish surface identity or registration accuracy.

## Review order

Check the declared complete scene and geometry before baking. Inspect source comparisons for extent, placement and contacts. Fix avoidable trim overlaps and wrong normals in the authoring candidate. Open architectural surfaces are legitimate; the mesh checks do not require every room face to be a watertight solid.

Use low-resolution views of the complete candidate before final renders. A named room camera can be blocked by adjoining architecture or a door in another capture state. Actual object/material raster passes establish which surfaces rendered. Passing pixel counts does not establish useful composition: inspect the image and reject empty corners, misleading crops or inappropriate camera roll. Do not silently remove a door to make a walkthrough view work.

After review, retain the packed native model, selected deliverables, source dependencies actually used, final views, visual findings and compact input/output hashes. Keep unique rejected evidence when it explains a decision. Deduplicate helpers by their content hash, and retire disposable caches and superseded outputs according to the project's retention request. A user's request to retain working evidence overrides the compact default.

## Runtime and delivery

Probe the selected Blender build's real rendering and denoising capabilities before a batch; matching version strings do not guarantee the same build options. Plan atlas size and texel density before sampling textures. Position inferred fill lights beneath the actual ceiling above each light, including sloped ceilings.

Browser delivery uses a classic script with the GLB, embedded textures and libraries bundled locally. A delivery test must open a copied output directory through `file://` with networking disabled and normal browser security settings, load all named views and stills, and exercise keyboard/touch navigation. Server-only success does not establish that double-clicking the delivered HTML works. Keep viewer lighting limitations distinct from Cycles still-render quality.
