# Commands and record formats

Use a Python 3.11+ environment with the packages in `requirements.txt`. In these examples `$PLUGIN` is the absolute installed plugin root, `$PROJECT` is the project directory, and `$CAPTURE` is an extracted directory containing `keyframes/`. Quote paths. Investigate CLI failures before continuing. Do not edit raw inputs to make a tool pass.

## Preserve and inspect a capture

```sh
python "$PLUGIN/scripts/ingest.py" /path/to/capture.zip --project "$PROJECT" --capture-id survey-one
python "$PLUGIN/scripts/reference.py" "$CAPTURE" "$PROJECT/derived/reference-one.npz" --frame-step 20 --pixel-step 4 --depth-variant raw --pose-variant raw
```

Intake preserves the original archive in `sources/`, extracts it under `derived/scan-to-model/captures/`, and writes a frame index and inventory under `docs/scan-to-model/captures/`. Read the returned `capture_root`: exports may contain an enclosing folder. References are sampled, not a full surface reconstruction. Clean depth and corrected poses require explicit selection and actual corresponding source files.

Native depth must be a 16-bit grayscale PNG (IHDR bit depth 16, color type 0), with unsigned millimetre samples. The reader verifies this source format and exposes the decoded values as `uint16`, preserving zero and the full sample range regardless of Pillow's integer storage mode. It does not rescale or clamp values, accept other image formats, or rewrite source files. The array API still requires nonempty 2-D `uint16` depth and matching 2-D `uint8` confidence.

## Surface measurement

```sh
python "$PLUGIN/scripts/surfaces.py" --spec "$PROJECT/docs/surfaces.json" --output "$PROJECT/derived/surface-review"
```

Paths in the spec are relative to the spec's directory, or absolute. `frame_id` is the exact camera/image filename stem, not a contact-sheet index. Coordinates are pixels in the stated orientation. Polycam's usual landscape RGB can be shown upright with a 90-degree clockwise rotation; inspect the particular export before selecting it. Use coordinates strictly inside the image. Missing or low-confidence depth stays missing; it is never interpolated into a measurement.

Polygon edges are rasterized in the chosen RGB orientation. Rotating equivalent polygons can change a few boundary pixel memberships; the saved native `(u,v)` list is the exact measurement support. Keep selections inside the intended opaque surface rather than treating a drawn polygon edge as a measured physical boundary.

For review of mapped sample locations before plane fitting, put `"fit": false` on **each patch** and leave `"comparisons": []`. The switch is per patch; a top-level `fit` value does not disable fitting. The example below selects this sample-only stage:

```json
{
  "capture": "../derived/scan-to-model/captures/survey-one",
  "orientation": "upright90cw",
  "depth_variant": "raw",
  "pose_variant": "raw",
  "max_depth_m": 5,
  "confidence_value": 255,
  "patches": [
    {"id": "floor-view-a", "frame_id": "EXACT_FRAME_STEM", "physical_surface": "entry-floor", "fit": false, "polygon_px": [[80,600],[300,600],[300,800],[80,800]], "notes": "Opaque floor; exclude the mat and threshold."},
    {"id": "floor-view-b", "frame_id": "SECOND_FRAME_STEM", "physical_surface": "entry-floor", "fit": false, "polygon_px": [[100,550],[320,550],[320,780],[100,780]], "notes": "Withheld view of the same physical floor patch."}
  ],
  "comparisons": []
}
```

With `fit: false`, confidence/range filtering, polygon selection, calibration and the selected transform still produce exact eligible `pixels`, `raw_points` and `points` in the NPZ. `measurements.json` reports `plane: null` and `fit_status: "not fitted"`. The all-false `inlier_mask` means no plane classification was performed; it does **not** mean those eligible samples were rejected or that native depth is absent. Read the status with the mask, and use `eligible_pixels` for support count.

Check mapped sample centers separately from any declared picking margin and depth-cell or kernel footprint assumption. A distance to exterior raster-pixel centers is not a continuous polygon-boundary margin, and a center inside a mask does not prove pure target support. Zero confidence-qualified samples means no matches to that filter; it does not by itself establish missing native depth.

Review those mapped sample locations against the exact unmarked and marked native source before accepting their physical surface interpretation. Sample-only output does not complete that review. Preserve the packet; for a later fitting stage, write a new spec with `fit: true` on accepted patches (omitting a patch's `fit` also enables fitting), set the intended `rejection_m`, and run into a fresh output directory. Add comparison pairs such as `[["floor-view-a", "floor-view-b"]]` only when their physical identity and shared frame are established. Do not reuse a premature fitted plane as a substitute for sample review.

These example pixels are illustrative, not selections to reuse. Each patch may override `capture`, `orientation`, `depth_variant`, `pose_variant` and `transform`. Optional `transform` is a row-major 4×4 rigid matrix mapping raw capture points into the analysis frame, in metres. When comparing captures, explicitly set a shared `analysis_frame` label and supply the appropriate transform for each capture. No transform is inferred or applied twice. Without a transform, output retains the capture's raw axes (ARKit: +Y up, camera looks along −Z).

`tracking_segment` may be declared at the top level or overridden per patch. When declared, it must be an integer matching the native raw camera JSON; missing or different camera metadata stops the patch before unprojection or its analysis transform. The output records both `declared_tracking_segment` and `camera_tracking_segment`, including when corrected poses are selected. If a source-local capture has no segment metadata, leave the declaration absent and retain both values as `null`; never substitute segment 0. A registered transform still needs the exact capture and tracking-segment scope established by its registration record.

Output `measurements.json` records exact component hashes, variant selection, native sample support, transforms, plane parameters, all-sample and retained-sample residuals, comparison overlap, and review figure names. Per-patch NPZs contain `raw_points`, transformed `points`, native depth `pixels` in `(u,v)` order, and `inlier_mask`. JPEGs show the selected photo polygon beside the native filtered depth. A low plane residual does not establish sensor accuracy. Interpret the physical surface before comparing it; a ramp and a flat floor cannot be treated as repeat observations of one plane.

Add `--pixel-inspections` to inspect small selection boundaries at native-pixel detail. Each patch also gets a PNG with the complete polygon and 32 displayed pixels of surrounding context, clipped at the image edges. Unmarked and marked panels are enlarged 3× with nearest-neighbor sampling. A second PNG shows every vertex using the same unmarked context, open locator and exact-pixel detail as `observations.py --coordinate-inspections`. Neither derivative adds source detail. Read the complete polygon as well as its vertices: vertices on one surface do not prove that all selected depth cells belong to it.

The patch's `pixel_inspection` record retains source RGB identity, artifact hashes, polygon coordinates in native and displayed pixel-center frames, crop bounds in displayed pixel-edge coordinates, panel bounds and enlargement. Native pixel centers rotate clockwise as `(u,v) -> (height-1-v,u)`; half-pixel offsets are used only to express crop edges and draw the enlarged overlay. Coordinate detail chooses the nearest native pixel with `floor(coordinate+0.5)` before rotating it. Inspection output remains `pending visual review` and does not change sample selection, transforms, fitting, or the meaning of `fit: false`. Use a fresh output directory and preserve earlier results.

Surface polygon coordinates near the image edge can round outside the source pixel grid. Those vertex records have null `nearest_native_pixel` and `nearest_display_pixel`, `source_pixel_status: "outside image"`, and retain the rounded locations in `outside_image_nearest_native_center` and `outside_image_nearest_display_center`. Their detail panels say `no source pixel`; padding is context, not source evidence. The original polygon coordinates and measurement samples remain unchanged.

`rejection_m` classifies inliers by distance to the final fitted plane. If fewer than 30 samples survive rejection, or the retained support cannot span a plane, the patch reports `plane: null` with an explicit `fit_status`. Its eligible native samples remain in the NPZ, with no accepted inliers, and comparisons involving that patch report `not measured`. Do not loosen the threshold just to obtain a plane; inspect the source patch and measurement purpose first.

Comparison overlap counts first-patch inliers inside the second patch's projected convex hull. It is directional and can span holes in native depth support; it is not a count of paired sensor returns. `plane_separation_m` measures distances between fitted planes at those projected sites, so it excludes first-patch point noise. A zero overlap count produces null separation statistics. Inspect the actual support before interpreting this local plane statistic as a repeatability bound.

## Rigid landmark registration

```sh
python "$PLUGIN/scripts/register.py" --spec "$PROJECT/docs/landmarks.json" --output "$PROJECT/derived/registration.json"
```

```json
{
  "source_frame": "survey-two raw metres",
  "target_frame": "project house metres",
  "landmarks": [
    {"id":"jamb-foot-a", "source":[0,0,0], "target":[2,1,0], "role":"fit", "evidence":{"source":"source-patch-record","target":"target-patch-record"}},
    {"id":"jamb-foot-b", "source":[1,0,0], "target":[3,1,0], "role":"fit", "evidence":"paired native samples and reviewed photos"},
    {"id":"jamb-head", "source":[0,2,0], "target":[2,3,0], "role":"fit", "evidence":"paired native samples and reviewed photos"},
    {"id":"withheld-corner", "source":[1,2,1], "target":[3,3,1], "role":"check", "evidence":"separate withheld frames and feature"}
  ]
}
```

The example is synthetic. Supply real points from named frames and pixels. At least three noncollinear fit landmarks are required. The script fits rotation/translation at unit scale and reports every fit and check residual. It does not remove outliers or declare acceptance. Repeated observations or coordinates copied from fitting evidence are not independent checks. Surface-constrained alignment can use a project-specific analysis; save its method, source selections, transform and withheld residuals with equivalent provenance.

## Blender

See [blender-review.md](blender-review.md) for the Blender command, inventory scope, candidate comparison and rendering. The Python measurement tools run outside Blender; Blender's own Python supplies `bpy` for scene review.
