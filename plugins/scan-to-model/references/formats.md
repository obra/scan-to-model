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

```json
{
  "capture": "../derived/scan-to-model/captures/survey-one",
  "orientation": "upright90cw",
  "depth_variant": "raw",
  "pose_variant": "raw",
  "max_depth_m": 5,
  "confidence_value": 255,
  "rejection_m": 0.02,
  "patches": [
    {"id": "floor-view-a", "frame_id": "EXACT_FRAME_STEM", "physical_surface": "entry-floor", "polygon_px": [[80,600],[300,600],[300,800],[80,800]], "notes": "Opaque floor; exclude the mat and threshold."},
    {"id": "floor-view-b", "frame_id": "SECOND_FRAME_STEM", "physical_surface": "entry-floor", "polygon_px": [[100,550],[320,550],[320,780],[100,780]], "notes": "Withheld view of the same physical floor patch."}
  ],
  "comparisons": [["floor-view-a", "floor-view-b"]]
}
```

These example pixels are illustrative, not selections to reuse. Each patch may override `capture`, `orientation`, `depth_variant`, `pose_variant` and `transform`. Optional `transform` is a row-major 4×4 rigid matrix mapping raw capture points into the analysis frame, in metres. When comparing captures, explicitly set a shared `analysis_frame` label and supply the appropriate transform for each capture. No transform is inferred or applied twice. Without a transform, output retains the capture's raw axes (ARKit: +Y up, camera looks along −Z).

Output `measurements.json` records exact component hashes, variant selection, native sample support, transforms, plane parameters, all-sample and retained-sample residuals, comparison overlap, and review figure names. Per-patch NPZs contain `raw_points`, transformed `points`, native depth `pixels` in `(u,v)` order, and `inlier_mask`. JPEGs show the selected photo polygon beside the native filtered depth. A low plane residual does not establish sensor accuracy. Interpret the physical surface before comparing it; a ramp and a flat floor cannot be treated as repeat observations of one plane.

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
