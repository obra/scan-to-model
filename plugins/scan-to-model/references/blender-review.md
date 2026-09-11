# Blender review helper

Before reviewing a manufactured component, distinguish immutable photo/depth controls from the geometry fitted to them. A projected four-corner trace can be skewed by perspective, a poor projection plane, uncertain calibration or imprecise selection. If evidence establishes a rectangular physical part, use an explicit rectangle constraint in its local frame; record the constraint source, fitted dimensions and residual from every original control. Do not silently move the source marks, enlarge their allowance to absorb a failed fit, or treat the constraint as an independent metric measurement. Large residuals require investigation. Shape constraints do not establish matching product sizes, hidden profiles or house placement.

Show the constrained component clearly by default and label any raw trace overlay as evidence. Verify right angles and opposite-edge relationships on the saved mesh, including recessed/inset profiles and dependent holes or adjoining faces. A rectangular diagram alone does not establish rectangular Blender geometry; a corrected panel can still leave a mismatched opening around it.

## Keep diagnostic geometry out of physical placement

A ray intersection, projected point, fitted plane or sensitivity trial can be numerically exact while remaining diagnostic. Its coordinates do not establish the physical surface used to derive them, a contact at that surface or an attachment between modeled parts. Keep the observation, assumed construction, derived result and disposition linked when evidence passes between tools. The project's explicit handoff schema should preserve the source identity and uncertainty, the assumed plane or other construction, the result, its allowed uses, and whether independent evidence has accepted it for physical placement. Do not infer acceptance from coordinates being present or from words embedded in an arbitrary property string.

Consumers must require an explicit accepted measured or registered placement record before using derived coordinates for object transforms, contacts or connections. A diagnostic result may drive an evidence overlay, reprojection check or sensitivity comparison within its recorded scope. If no accepted record exists, keep the physical plane, contact or attachment unknown and preserve the diagnostic result separately; a visually plausible connection does not promote it.

For example, an intersection of a source ray with an assumed support plane remains a diagnostic point when the plane is only a comparison surface. Its handoff records that assumption and limits the point to reprojection or sensitivity work. If a separately measured or registered surface and independent controls later establish a physical contact, add an accepted placement record that cites that evidence and its scope while retaining the original diagnostic. Reusing the observations that produced the diagnostic is not independent validation.

Before promotion, reopen the final blend and trace each modeled physical placement back through the project's schema. Confirm that every consumed point or plane has an explicit accepted disposition and supporting independent validation, and that diagnostic-only results did not become transforms or contacts. Check that unresolved physical planes and contacts remain recorded as unknown.

## Define room sheets by physical subject

Create a manifest before rendering a room sheet. Give each view a stable ID and record its kind, named coordinate frame, projection, view direction, image-up direction, camera and view-layer identity, complete renderable object inclusion list, and intentional exclusions. Collection membership is organizational evidence only: do not derive the sheet from a room or collection name. Resolve the physical subjects first, then declare their actual objects. Keep the manifest with the rendered output.

For every wall elevation, list the exact room-facing wall-face identifiers and the exact attached-fixture identifiers separately. A face identifier must resolve through the project's explicit geometry schema to an object face or other stable wall-surface record; an object or collection name alone does not identify one side of a wall. Include returns, neighboring faces, loose objects and fixtures from other collections only when the manifest names them for that elevation. Record the view from the room toward the wall, building-up direction, projection and framing bounds.

Define the remaining views without relying on drawing-name conventions:

- A plan records its horizontal cut-plane origin or elevation, downward view direction, image-up axis, retained side and visible depth beyond the cut.
- A reflected ceiling plan records its cut plane, upward view direction, image-up axis, retained depth and whether its horizontal orientation matches or mirrors the plan.
- A section records the plane origin and normal, viewing side and direction, image-up axis, retained side or depth, and the exact cut and projected subjects.

Show only geometry present in the reviewed candidate. Do not create cap faces, concealed wall-core layers or hidden continuation to make a section look conventional. If graphical cut treatment is needed, distinguish it from modeled construction and do not use it as evidence of hidden material.

Record the original per-object, collection and view-layer visibility state before applying a view manifest. Verify the requested renderable set before rendering, then restore and verify the original state afterward as described below. A successful render process is not a visual pass: inspect every requested image, confirm its declared faces and fixtures, note unintended content or occlusion, and check all four frame edges plus near and far camera clipping for unintended loss. Identify intentional cropping in the manifest. Record each render path/hash and its inspection finding.

Retain rejected images, partial output, process status and logs with the manifest and frozen input identities. Do not overwrite a failed attempt or present stale output as a successful sheet. After correcting the manifest, camera, cut or visibility setup, render into a fresh directory and repeat every affected inspection. Never save visibility changes into the reviewed model merely to produce a sheet.

## Bind review inputs before launch

Choose the exact model artifact and review-helper bytes before starting Blender. Prefer an existing saved immutable source or candidate for the model. Make an ordinary byte-for-byte copy of the helper selected from its reviewed commit or package into review-controlled storage. When the model path can be replaced during the review, copy it there as well. Invoke Blender only with the frozen model and helper paths, retain them, and leave them untouched until their post-run hashes are recorded. Do not use a hard link as a snapshot if the source may be modified in place, because both names share the same underlying bytes. Do not resave a blend merely to freeze it; saving can rewrite relative external paths.

Keep the frozen model under the same intended relative-path semantics as the reviewed artifact. A copy beside the source retains its `//` reference base. A copy elsewhere must retain the required directory layout and referenced assets, or be reviewed under the final-path policy described below. Record these values before launch:

- Resolved frozen model path and SHA256.
- Resolved frozen helper path and SHA256, plus its commit or package version when known.
- Resolved Blender executable path and its complete `--version` output, including the version and build hash when reported.
- Exact argument vector, output directory and start time.

After Blender exits, recompute and record the frozen model and helper hashes alongside the prelaunch values, plus the inventory's `blender_version`, end time and exit status. Require both hash pairs to match and confirm that the inventory's `blend` path identifies the frozen model. Invalidate and rerun the review if a bound input is missing or changed, or if the loaded model and helper identities cannot be demonstrated. A path hash first read after Blender has loaded a file proves only the path's later contents; it does not prove which bytes Blender loaded. Replacing an upstream canonical model or upgrading an installed helper during a run does not alter that run when Blender was launched exclusively from unchanged frozen inputs. A later independent inventory may use new helper bytes, but a baseline and candidate compared with `--compare` must use the same helper SHA256; regenerate the baseline after a helper change.

## Isolate interactive GUI review state

Read-only artifact review and runtime-write isolation are separate checks. An unchanged blend hash and a no-save workflow do not prevent interactive Blender from writing recent-file state, support diagnostics, caches, temporary files or recovery files such as `quit.blend`. Before starting Blender, create a unique retained runtime root for that review. Do not redirect `HOME` or `CODEX_HOME`, reuse the user's normal configuration directories, or remove unknown files after the run.

On Linux, create each directory first, make `XDG_RUNTIME_DIR` accessible only to the reviewing user, and launch the GUI with process-local paths:

```sh
set -eu
runtime_root=/short/path/to/permanent-scratch/gui-review-unique-id
mkdir "$runtime_root"
mkdir "$runtime_root/blender-config" "$runtime_root/xdg-config" \
  "$runtime_root/xdg-cache" "$runtime_root/xdg-data" \
  "$runtime_root/xdg-runtime" "$runtime_root/tmp"
chmod 700 "$runtime_root/xdg-runtime"

env \
  BLENDER_USER_CONFIG="$runtime_root/blender-config" \
  XDG_CONFIG_HOME="$runtime_root/xdg-config" \
  XDG_CACHE_HOME="$runtime_root/xdg-cache" \
  XDG_DATA_HOME="$runtime_root/xdg-data" \
  XDG_RUNTIME_DIR="$runtime_root/xdg-runtime" \
  TMPDIR="$runtime_root/tmp" \
  XAUTHORITY="$runtime_root/xauthority" \
  DISPLAY="$task_display" \
  blender --factory-startup --disable-autoexec FROZEN.blend
```

Keep the runtime path short because Unix-domain sockets have path-length limits. For Xvfb, create and populate the shown authorization file when starting the task-owned server, keep its logs under the same root, wait for the selected display to become ready, and record the server PID. Stop only that PID after Blender exits. When the display server's own socket and lock files must also be contained, run it in an operating-system private temporary namespace backed by a directory under the runtime root; the Blender environment variables do not redirect those server files.

Before inspecting the model, confirm that `bpy.app.tempdir` and `bpy.context.preferences.filepaths.temporary_directory` are both under `runtime_root/tmp`; set the latter there for this session if necessary. For a read-only audit, also set `bpy.context.preferences.filepaths.save_version = 0` and `use_auto_save_temporary_files = False`. Do not save these settings to shared user preferences, and abort if either temporary path resolves outside the root. Quit Blender normally so its exit-recovery state stays under the task temp directory. Retain the runtime root and record its generated config, cache, data, runtime, temporary and recovery files. On Linux, retain a file-syscall trace such as `strace -f -e trace=%file` when the review requires proof that every successful file mutation stayed inside the root; a listing of the root alone cannot prove that nothing was written elsewhere. Any observed Blender write outside the root invalidates the GUI-isolation check even when the reviewed blend and source hashes are unchanged. `--factory-startup` and `--disable-autoexec` avoid user startup state and automatic blend-file scripts; they do not replace the environment isolation.

This GUI command is for manual inspection and does not run the inventory helper. Bind any inspection script it does run in the same way as the helper. Run the inventory separately from the frozen model and helper paths described above.

## Snapshot collections before visibility changes

`Collection.all_objects` is a live Blender collection. A render helper that changes `hide_render` or other visibility state while iterating that live collection can invalidate the traversal, skip descendants or return invalid entries. Materialize the selected descendants before the first visibility change. Use that same tuple to capture original state, compute the complete requested state, apply it, verify it after updating the view layer, and restore and verify it in `finally`:

```python
render_objects = tuple(root.all_objects)
original = {obj.name: obj.hide_render for obj in render_objects}
requested = {
    obj.name: original[obj.name] or obj.name not in included_names
    for obj in render_objects
}
try:
    for obj in render_objects:
        obj.hide_render = requested[obj.name]
    view_layer.update()
    if {obj.name: obj.hide_render for obj in render_objects} != requested:
        raise RuntimeError("render visibility assignment did not stick")
    selected_visible = {
        obj.name for obj in render_objects
        if obj.type in {"CURVE", "FONT", "MESH", "SURFACE"}
        and not obj.hide_render
        and obj.visible_get(view_layer=view_layer)
    }
    if selected_visible != included_names:
        raise RuntimeError("pre-render selection does not match the requested set")
    # Render only after both checks pass.
finally:
    for obj in render_objects:
        obj.hide_render = original[obj.name]
    view_layer.update()
    if {obj.name: obj.hide_render for obj in render_objects} != original:
        raise RuntimeError("render visibility was not restored")
```

Here `included_names` is the exact set of renderable descendants expected to be enabled and visible in the selected view layer after preserving any original `hide_render=True` state. `visible_get` is a viewport and view-layer check; it does not account for collection-level `hide_render` or prove final renderer output. Audit collection render flags separately and inspect the resulting render.

The synthetic fixture links one nested collection into source and disposable render scenes, applies fourteen visibility configurations to 384 descendants, checks the assigned flags and selected view-layer-visible set, and restores every original flag:

```text
blender -b --factory-startup --disable-autoexec --python-exit-code 1 --python tests/blender_collection_visibility.py -- --output /path/to/review/collection-visibility
```

Run:

```text
/Applications/Blender.app/Contents/MacOS/Blender -b FROZEN.blend --python /path/to/frozen/blender_review.py -- --output DIR [--camera NAME ...] [--view-layer NAME] [--compare INVENTORY.json]
```

Repeat `--camera NAME` for each requested camera. The camera must belong to the active scene. `--view-layer NAME` selects the view layer to render; the default is Blender's active view layer. All requested cameras share that selected layer, so use separate invocations and output directories for cameras that need different collection exclusions or other view-layer settings. Unknown layer names fail. Use separate output directories for the baseline and candidate. The helper rejects using the input file's directory itself, writing through output paths that escape the chosen folder or have multiple hard links, and overwriting the comparison inventory. It does not save the blend file. Optional rendering temporarily changes the active scene's camera and render settings in memory, then restores those settings.

## Candidate save and promotion paths

Choose the path-binding policy before saving a candidate. Blender stores `//` paths relative to the blend file and `bpy.ops.wm.save_as_mainfile` defaults to `relative_remap=True`. Saving into a scratch directory therefore rewrites relative external references so they keep resolving from the scratch candidate. That behavior is appropriate when the candidate stays there, or when the blend and referenced assets move together with the same layout.

When a candidate will be promoted by copying its bytes to the original canonical directory, the scratch candidate instead needs to retain the canonical file's relative strings. Save that candidate explicitly with `relative_remap=False`:

```python
bpy.ops.wm.save_as_mainfile(filepath=str(candidate_path), relative_remap=False)
```

This option is specific to a workflow where the intended final location has the same reference base as the source file. It can make relative references look broken while the candidate is open in scratch; candidate-local validity does not prove, or disprove, validity after promotion. For a different final directory or asset layout, choose remapping or stage the candidate beside that final layout instead.

Before promotion, inspect every stored external path, including packed paths from `bpy.utils.blend_paths(packed=True)`, as if the candidate were located at the intended final path. Require each relative path to resolve to its recorded target from the final directory. Then copy the candidate, reopen the promoted file, repeat the resolution audit, and load each unpacked source to verify its bytes can be decoded. Packed data can hide a bad source path, so separately compare both source-file and packed-payload hashes before saving and after reopening; retain the recorded filename even when the packed bytes match because it remains part of provenance and may be used when unpacking.

The synthetic check demonstrates both policies with invented packed and unpacked images. Each invocation requires a new output directory and retains its source images, source blend, reopened candidate, byte-copied promoted blend, and `result.json`. The first command must fail after byte-copy promotion because the default binds paths to scratch; the second must pass because the final-path references, readable source pixels, source hashes, and packed bytes survive:

```text
blender -b --factory-startup --python-exit-code 1 --python tests/blender_candidate_promotion.py -- --save-mode default --output /path/to/review/candidate-promotion-default
blender -b --factory-startup --python-exit-code 1 --python tests/blender_candidate_promotion.py -- --save-mode preserve-final-paths --output /path/to/review/candidate-promotion-preserved
```

## Evidence-reference closure

A source ID stored on an object does not bring its photograph or registry record into the blend. Likewise, image counts and “all present images are packed” checks say nothing about originals that were never appended. Before promotion, declare the project's evidence schema explicitly: which objects are substantive, where their source ID lists live, which registry resolves them, and which fields preserve complete source identity and uncertainty. Do not infer this contract by tokenizing arbitrary custom-property strings.

Audit every substantive object and every source ID it declares. An original or qualified-upright record must resolve to the named image datablock with matching identity metadata and source hash; the image must be packed and its pixels readable after reopening the final file. A qualified-upright record must also resolve to its original record. Append and pack that original even when no object cites it directly. A packed derivative alone does not preserve the native source.

Classify documentary evidence with no established image or location as documentary and unlocated. Preserve its full document identity and uncertainty without inventing a photograph binding or using it to claim image-grounded placement. In an interactive review, select representative substantive objects and follow their declared references. The promotion gate must then traverse all substantive objects and declared source chains under the same explicit schema; representative inspection alone is not closure. The inventory records custom properties and images, but it does not establish this semantic relationship.

The synthetic Blender fixture uses an explicit invented schema. Its first mode must fail even though every image present is packed, because a cited qualified-upright source has no appended original. Its complete mode appends and packs that original, reopens the final blend, and audits all declared visual and documentary references:

```text
blender -b --factory-startup --python-exit-code 1 --python tests/blender_evidence_reference_closure.py -- --mode missing-original --output /path/to/review/evidence-closure-missing-original
blender -b --factory-startup --python-exit-code 1 --python tests/blender_evidence_reference_closure.py -- --mode complete --output /path/to/review/evidence-closure-complete
```

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

Large scenes can produce large inventories. A scene with roughly 10,000 objects and hundreds of view layers took about two minutes per inventory and produced about 197 MB of indented JSON, including its expanded view-layer collection graph. Allow storage and runtime for both baseline and candidate reports.
