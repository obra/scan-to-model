# Scan to Model

Seven Codex skills and local Python tools for turning scan evidence into reviewable Blender architectural models. The tools preserve Polycam exports, unproject calibrated native depth, measure photographed surface patches, fit rigid registration, and inspect saved Blender candidates. They do not infer an entire house automatically from a ZIP.

The package contains no project address, private scans, accepted house transforms, or owner observations. Keep those in the working project. No server or API key is required. Blender and a Python 3.11+ environment with NumPy, Pillow, SciPy and Matplotlib are required for the respective tools; install the Python dependencies from `requirements.txt` into an existing suitable environment or a dedicated virtual environment.

## Use in Codex

Follow the [repository installation instructions](https://github.com/obra/scan-to-model#install-in-codex), then start a task that loads the installed skills. Ask: “Use scan-to-model to ingest these scans, build a coverage atlas, and model the next evidence-supported room.” Existing project instructions and prior authorization still apply; the plugin introduces no permission loop or test-suite requirement.

| Skill | Use |
| --- | --- |
| `scan-to-model` | Plan the evidence workflow, update room/connection coverage, and choose the next bounded model increment. |
| `scan-ingest` | Preserve archives, audit pairing and variants, create frame indices and contact sheets. |
| `source-observe` | Annotate visible construction in original photographs, retaining uncertain identity and endpoints independently of model placement. |
| `street-view-reference` | Collect dated exterior panorama views, verify saved image content and retain source attribution independently of model geometry. |
| `depth-inspect` | Select physical surfaces in actual photos; inspect native confidence, depth, calibration and local repeatability. |
| `scan-register` | Establish rigid transforms with withheld observations and explicit regional validity. |
| `blender-reconstruct` | Build source-tagged candidates, inspect saved scenes, render and promote supported changes. |

## Direct tools

Read [commands and scan-geometry JSON examples](references/formats.md) or the [source-observation contract](references/source-observations.md) before running the corresponding tool. Call `--help` on each entrypoint for its arguments.

- `scripts/ingest.py`: preserve and audit a ZIP; repeat ingestion verifies existing data.
- `scripts/observations.py`: validate native marks and render exact-byte source sheets plus native-scale assertion and endpoint review crops.
- `scripts/reference.py`: create finite metre point references with frame/pixel provenance.
- `scripts/surfaces.py`: measure source-photo polygons; save native samples, fits and evidence figures.
- `scripts/manufactured.py`: [fit manufactured rectangles](references/manufactured-shapes.md) in common component axes and report original controls and residuals.
- `scripts/register.py`: fit unit-scale rigid landmark alignment and report withheld checks.
- `scripts/blender_review.py`: run inside Blender to inventory and render without saving the input.
- `scripts/polycam.py`: shared native reader and calibrated unprojection.

The supplied reader is for Polycam's keyframe export layout and millimetre depth PNGs. Another scanner format needs an explicit adapter and a verified units/axis/calibration contract. Preserve raw and Clean depth, raw and corrected poses as separate choices. Smoothing, sample density and confidence labels do not establish physical accuracy.

Read the [evidence workflow](references/evidence-workflow.md) for coverage and uncertainty rules and [Blender review guidance](references/blender-review.md) for preservation limits. A source archive being ingested does not mean its rooms have been examined, aligned, modeled or visually verified.
