# Appearance and usable model delivery

Use this workflow when the requested result includes materials, renders, a portable native file or a browser model. Keep the requested outputs in one project-owned delivery job. A geometry-only task does not acquire a rendering, browser or publishing requirement. Existing authorization remains authoritative; record whether interpolation was authorized and its basis. Never equate visual completion with independent metric acceptance.

Contents: [decisions](#implementation-decisions), [review order](#review-order), [runtime](#runtime-and-delivery), [commands](#run-the-shared-producer), [job format](#delivery-job), [photographic inputs](#photographic-inputs), [retention and limits](#retention-and-limits).

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

Browser delivery uses a classic script with the GLB, embedded textures and libraries bundled locally. A delivery test must open a copied output directory through `file://` with networking disabled and normal file-origin rules, load all named views and stills, and exercise keyboard/touch navigation. Server-only success does not establish that double-clicking the delivered HTML works. Keep viewer lighting limitations distinct from Cycles still-render quality.

## Run the shared producer

Use the installed plugin's path for `plugin_dir`, a Python environment with its `requirements.txt`, and an explicit Blender executable. The integration fixture exercises Blender 4.0.2 with Cycles and OpenImageDenoise. Preparation runs an actual tiny render using the requested denoising setting. Node.js/npm are needed only to build a viewer; Chrome/Chromium and `websocket-client` are needed for its delivery check.

```sh
python3 "$plugin_dir/scripts/delivery.py" prepare \
  --job /project/delivery-job.json --output /project/work/delivery-prepared \
  --blender /path/to/blender
```

Preparation checks immutable inputs, complete drawable membership, metre units, mesh quality and renderer capability before baking. It saves one packed candidate, reopens it and renders whole-scene previews at at most 320 pixels on the longer edge. `prepared.json` reports whether required object/material pixels are present. `review-template.json` starts pending: inspect source comparisons and every preview, then record findings and concrete notes in a project-owned review file. Never fabricate pass notes from hashes or pixel counts. A failed camera remains a failed view even if its review text says `pass`.

The acting agent can perform this review under existing user authorization; this is not another permission gate. For a blocked view, correct the camera in a fresh authoring candidate and prepare again, retaining the rejected image when it explains the choice. Do not hide a wall or alter a door merely to force a pass. Physical conflicts still require authoring corrections.

```sh
python3 "$plugin_dir/scripts/delivery.py" finish \
  --prepared /project/work/delivery-prepared --review /project/preview-review.json \
  --output /project/delivery --blender /path/to/blender
```

Finishing rechecks the input, candidate, atlas and reviewed image hashes. It renders requested final stills, reads actual index rasters, exports the complete GLB and checks world vertices, oriented triangles, source properties and each photo material's embedded image binding. It creates the requested portable files and a pending `final-review-template.json`. Inspect the final images and record their findings too; previews are not a review of final render bytes.

```sh
python3 "$plugin_dir/scripts/delivery.py" verify \
  --output /project/delivery --review /project/final-review.json
```

Verification rechecks delivered hashes and final image findings. For a viewer, it copies the output into a new directory and opens its real `file://` URL with networking disabled. It exercises room jumps, model membership, keyboard/touch movement, floor/roof/amber/reset controls, still-tour navigation and mobile layout. Screenshots and the browser result are retained beside `delivery-checks.json`. Only then does `delivery.json` say `verified`. A rendering, browser or data failure leaves the task incomplete with its actual error. These checks establish delivery behavior, not metric acceptance.

Prepare and finish require fresh output directories. Successful native phases and viewer builds are reused when finishing unchanged preparations into a new destination. Changed helpers or inputs require a new preparation. Failed browser attempts retain their captures/logs; retries get a new capture directory. Re-verifying unchanged approved files reuses the bound result; an explicit `--browser` requests a fresh browser run.

## Delivery job

Paths resolve relative to the job file. Every model/source file has a SHA-256 beside its path. Declare complete object membership, not name-prefix guesses. Each object needs stable `id`, exact Blender `name`, `room`, `level` and `role`. Roles `roof` and `ceiling` control roof visibility; other roles follow the declared level. `intent.model_scope` defaults to `full-model`, which rejects any `excluded_objects`. Use `selected-objects` only for a user-requested subset, recording that request in `intent.basis` and exact excluded names and reasons in `excluded_objects`. A failed mesh or camera check does not authorize a smaller scope. Geometry, finish choices, sources and cameras remain project-owned.

This example shows the required shape. Replace names/hashes and expand `objects` to the actual complete scene.

```json
{
  "schema_version": 1,
  "units": "m",
  "title": "House study",
  "model": "candidate.blend",
  "model_sha256": "SHA256_OF_CANDIDATE",
  "deliverables": ["native", "glb", "stills", "viewer", "sources"],
  "intent": {
    "basis": "The owner requested a rendered house with tentative interpolation",
    "interpolation_authorized": true,
    "model_scope": "full-model",
    "geometry_status": "tentative",
    "metric_status": "Dimensions remain approximate pending independent checks"
  },
  "objects": [{
    "id": "room-floor", "name": "Room floor", "room": "room",
    "level": "ground", "role": "floor", "material": "finish",
    "sources": ["room-photo"]
  }],
  "sources": [{
    "id": "room-photo", "image": "references/room.jpg",
    "image_sha256": "SHA256_OF_ORIGINAL_PHOTO"
  }],
  "materials": [{
    "id": "finish", "method": "matched-color", "sources": ["room-photo"],
    "color": [180, 150, 120], "roughness": 0.65,
    "basis": "Reviewed native-photo sample; illumination remains uncertain"
  }],
  "views": [{
    "id": "room", "title": "Room", "camera": "Room camera",
    "required_objects": ["room-floor"], "minimum_pixels": 64
  }],
  "renderer": {"engine": "CYCLES", "width": 1024, "height": 768, "samples": 32, "denoise": true},
  "texture": {"density": 128, "minimum_density": 16, "max_size": 2048}
}
```

Supported outputs are `native`, `glb`, `stills`, `viewer`, `sources`. A viewer includes its GLB and metadata even without a separate `glb` request. Stills also generate `tour.html`. Native-only jobs can omit materials, sources and views, requiring no npm, browser or rendered images. Optional `scene` and `view_layer` select the native context. The view ID `exterior` is reserved for the generated whole-model overview. Views require perspective cameras and explicit subjects. Pixel thresholds apply to previews and final renders; choose meaningful thresholds within the preview resolution.

World coordinates use metres with native `scale_length=1`; resolve other units in the authoring candidate. Linked libraries, unresolved external dependencies and instances are rejected rather than silently converted. Original image data is preserved and packed alongside selected material sources. Native readback requires the bytes already packed and checks active shaders, assignments and UVs without repairing them.

### Photographic inputs

`matched-color` uses reviewed sRGB 0–255 values and source IDs. Every method requires a nonempty `basis`. `inferred` may omit sources but requires interpolation authorization. Optional `roughness`, `metallic` and `transmission` range from zero to one. Do not project reflected scenery onto a mirror or the background behind glass as if it were surface paint.

Each `photo-projection` source needs `image`, `depth`, `confidence`, their `_sha256` fields, `camera`, and `camera_to_world`. Optional native-RGB `mask` plus `mask_sha256` excludes zero-valued pixels. The camera has `width`, `height`, `fx`, `fy`, `cx`, `cy`. Its rigid pose maps camera-local coordinates into the model's metre world frame, viewing along local −Z with local +Y upward. Depth is axial distance with `depth_scale` metres per stored unit (default 0.001). Confidence must equal `confidence_value` (default 255). Depth/confidence may have a lower, matching resolution. Camera poses must already be registered; appearance does not estimate registration.

Material `depth_tolerance_m` defaults to 0.1 and must reflect a justified project tolerance. Incidence and saturation filtering supplement depth/confidence/masks. Depth agreement cannot identify every foreground object or reflection; inspect source identity and mask those cases. Unsupported texels use inferred base color. Face records retain direct-photo coverage and source contributions; repeated samples report no direct coverage of the modeled surface.

A `repeated-photo` material declares `sample: {"source": "SOURCE_ID", "quad": [[x0,y0],[x1,y1],[x2,y2],[x3,y3]]}`: an ordered convex quadrilateral in original image pixels. Its `mapping` gives world-space `origin`, orthonormal `u`/`v` directions and two positive `size_m` dimensions. Sharing this frame across objects preserves grain scale/alignment. Mirrored repetition reduces edge seams; continuation remains inferred. Optional `detail_contrast` (0–1) reduces broad captured illumination around the reviewed color for either photographic method; it does not recover calibrated albedo.

Choose a patch belonging entirely to one physical finish, excluding trim, furniture, openings and reflections. Save and inspect the rectified sample before baking, then review the mapped surface against its source for color, grain scale and direction. Repeating an entire room photograph across a floor is not a usable floor texture. Use a reviewed matched color when no clean material patch is available; keep the appearance limitation explicit.

Photo baking supports planar mesh faces without modifiers. Atlas density is planned before sampling, reducing from `density` texels/metre only as far as `minimum_density` to fit `max_size`. Insufficient capacity stops the task. Handle nonplanar geometry deliberately or use another material method; delivery does not re-mesh it.

Optional `lighting.world` has linear RGB `color` in 0–1 and nonnegative `strength`. Each `lighting.fills` item needs `id`, `xy`, `floor_z`, `ceiling_objects`, `size`, `energy`, `color` and optional `clearance` (default 0.2 metres). Fills are positioned beneath the nearest named ceiling above each point, including slopes. Presentation lighting requires authorized inference and is labeled accordingly.

## Retention and limits

Keep requested deliverables and their dependencies: packed native, embedded GLB, selected source files, final PNGs and compressed index rasters, tour/viewer assets and compact checks. Viewer source, locked package versions, build script and license notices support rebuilding. `sources.json` uses relative paths; the intake directory is not copied. The complete native file preserves preexisting images, including any unrelated to newly assigned finishes.

Preparation holds the detailed preservation snapshot, renderer probe, previews, atlas, frozen helpers, runtime logs and npm cache. Retain it during active work and diagnosis. After the decision, preserve requested source/review/rejected evidence and deliverables; retire disposable caches and superseded preparations according to project instructions. The producer does not automatically delete evidence. Delivery manifests remain usable without historical preparation paths.

Mesh diagnostics cover degeneracy, inconsistent winding, inverted closed meshes and coplanar overlapping triangles. Opposite-facing contacts are separately flagged for physical review because adjacent surfaces can legitimately touch. The checks do not detect every solid intersection or establish hidden construction. Raster counts establish visible subjects/materials, not composition. GLB readback establishes export fidelity, not survey accuracy. Local-file browser checks exercise Chromium; test other required browsers/devices separately. Free flight has no collision simulation and browser lighting/reflections differ from Cycles stills.

See [synthetic delivery validation](../tests/delivery-validation.md) for executable positive/negative tests and retained public screenshots.
