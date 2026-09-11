# Blender review helper

Before reviewing a manufactured component, distinguish immutable photo/depth controls from the geometry fitted to them. A projected four-corner trace can be skewed by perspective, a poor projection plane, uncertain calibration or imprecise selection. If evidence establishes a rectangular physical part, use an explicit rectangle constraint in its local frame; record the constraint source, fitted dimensions and residual from every original control. Do not silently move the source marks, enlarge their allowance to absorb a failed fit, or treat the constraint as an independent metric measurement. Large residuals require investigation. Shape constraints do not establish matching product sizes, hidden profiles or house placement.

Show the constrained component clearly by default and label any raw trace overlay as evidence. Verify right angles and opposite-edge relationships on the saved mesh, including recessed/inset profiles and dependent holes or adjoining faces. A rectangular diagram alone does not establish rectangular Blender geometry; a corrected panel can still leave a mismatched opening around it.

Run:

```text
/Applications/Blender.app/Contents/MacOS/Blender -b FILE.blend --python scripts/blender_review.py -- --output DIR [--camera NAME ...] [--view-layer NAME] [--compare INVENTORY.json]
```

## Candidate save and promotion paths

Choose the path-binding policy before saving a candidate. Blender stores `//` paths relative to the blend file and `bpy.ops.wm.save_as_mainfile` defaults to `relative_remap=True`. Saving into a scratch directory therefore rewrites relative external references so they keep resolving from the scratch candidate. That behavior is appropriate when the candidate stays there, or when the blend and referenced assets move together with the same layout.

When a candidate will be promoted by copying its bytes to the original canonical directory, the scratch candidate instead needs to retain the canonical file's relative strings. Save that candidate explicitly with `relative_remap=False`:

```python
bpy.ops.wm.save_as_mainfile(filepath=str(candidate_path), relative_remap=False)
```

This option is specific to a workflow where the intended final location has the same reference base as the source file. It can make relative references look broken while the candidate is open in scratch; candidate-local validity does not prove, or disprove, validity after promotion. For a different final directory or asset layout, choose remapping or stage the candidate beside that final layout instead.

Before promotion, inspect every stored external path, including packed paths from `bpy.utils.blend_paths(packed=True)`, as if the candidate were located at the intended final path. Require each relative path to resolve to its recorded target from the final directory. Then copy the candidate, reopen the promoted file, repeat the resolution audit, and verify unpacked sources can be read. Packed data can hide a bad source path, so separately compare packed payload hashes before saving and after reopening; retain the recorded filename even when the packed bytes match because it remains part of provenance and may be used when unpacking.

The synthetic check demonstrates both policies with invented packed and unpacked images. The first command must fail after byte-copy promotion because the default binds paths to scratch; the second must pass because the final-path references and packed bytes survive:

```text
blender -b --factory-startup --python-exit-code 1 --python tests/blender_candidate_promotion.py -- --save-mode default
blender -b --factory-startup --python-exit-code 1 --python tests/blender_candidate_promotion.py -- --save-mode preserve-final-paths
```

Repeat `--camera NAME` for each requested camera. The camera must belong to the active scene. `--view-layer NAME` selects the view layer to render; the default is Blender's active view layer. All requested cameras share that selected layer, so use separate invocations and output directories for cameras that need different collection exclusions or other view-layer settings. Unknown layer names fail. Use separate output directories for the baseline and candidate. The helper rejects using the input file's directory itself, writing through output paths that escape the chosen folder or have multiple hard links, and overwriting the comparison inventory. It does not save the blend file. Optional rendering temporarily changes the active scene's camera and render settings in memory, then restores those settings.

The inventory covers these source properties:

- Objects: type, transforms, parent and datablock references, writable scalar/array settings including visibility and instancing, collection membership, material slots, custom source tags, modifier order/settings, and constraint order/settings. Modifier and constraint settings include writable scalar/array properties and datablock references; modifier custom properties include Geometry Nodes input values.
- Meshes: counts plus exact SHA256 snapshots of 32-bit coordinate, edge, corner, face, material-index, and smooth-shading buffers. Supported numeric mesh attributes include UV coordinates and color attributes. Unsupported attribute types are named with `values not captured`. Shared mesh datablocks are inventoried once.
- Materials: writable scalar/array properties, source tags, node types/settings, input/output defaults, links, color ramps, and nested node groups. Material slots retain empty slots and object/data linkage. Image references and color-space settings are recorded.
- Collections: object/child membership, source tags, visibility and other writable scalar settings. Scenes include collection exclusions, per-view-layer hidden objects, active camera/world, current frame, units, general render settings, and color management. Camera, light, and world settings are recorded, including light/world node trees.

`--compare` produces added/removed/changed names separately for each inventoried datablock category. Compare inventories produced by this helper schema with the same Blender version; older or different-version inventories are rejected. A changed material or shared mesh is reported under its own category, so inspect all categories. Changes are review findings and do not themselves cause a nonzero exit: an intentional candidate edit should produce changes.

Different active or excluded view layers can change the cached `matrix_world`, `matrix_local`, and `dimensions` values read from original objects, even when their stored transforms and geometry are unchanged. A large raw object-difference count therefore needs investigation. Keep the reported differences, compare stored location/rotation/scale and delta channels, `matrix_basis`, parent references and `matrix_parent_inverse`, then compare objects under the same view layer and dependency-graph evaluation context. For evaluated world transforms and dimensions, inspect `obj.evaluated_get(depsgraph)`; original-object getters can retain stale values after switching layers. Record which objects were actually evaluated and any remaining differences. Do not infer preservation merely by discarding computed fields or by matching a few representative objects.

This is a scoped source-state comparison, **not a complete preservation proof or Blender serializer**. It does not evaluate modifiers, constraints, or Geometry Nodes into final geometry. It does not capture animation/drivers, shape-key coordinates, curve/text/volume geometry, arbitrary nested RNA settings (such as curve mappings, constraint target collections, or modifier caches), engine-specific render settings, compositor graphs, or external/packed texture pixel contents. Referenced datablocks use their names and library paths. Texture pixels can change while their recorded references remain equal. Recorded node settings do not prove the final rendered appearance is unchanged. Viewport-only presentation settings may also produce harmless differences. Changes limited to omitted properties can go undetected; inspect the candidate and source-matched renders before promotion.

Optional renders are PNG workbench geometry previews using the saved resolution. Workbench previews do not validate shader or texture appearance. The helper renders only the selected view layer, temporarily disabling every other layer and restoring the original enable flags afterward. It disables compositor and sequencer processing for these previews and derives a contained filename from each camera name plus a stable hash, so slashes, duplicate-looking labels, and filename punctuation cannot create paths outside the output directory. `inventory.json` maps camera and view-layer names to their render files. Existing files with those generated names in the chosen output folder can be replaced; retain separate review folders for checkpoints.

A missing camera, non-finite numeric values encountered in captured properties or mesh buffers, invalid comparison, render failure, or unsafe output path produces a nonzero process exit, even when Blender was launched without `--python-exit-code`. A successful inventory is written only after all requested renders succeed. A failed rerun can leave outputs from an earlier invocation; rely on the process result and use a fresh folder when collecting evidence.

For model-preservation evidence, hash the input blend before and after the command and record both hashes alongside the inventory. This verifies that the on-disk model stayed unchanged during this run; the helper's comparison and visual inspection address the separate question of whether a candidate preserves the relevant scene content.

Large scenes can produce large inventories. A scene with roughly 10,000 objects and hundreds of view layers took about two minutes per inventory and produced about 197 MB of indented JSON, including its expanded view-layer collection graph. Allow storage and runtime for both baseline and candidate reports.
