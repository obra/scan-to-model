# Scan to Model

A Codex plugin for turning scan evidence into reviewable Blender architectural models.

Start with photographs, calibrated depth, camera poses, plans, and observations. Preserve the evidence, measure real surfaces, align captures, and build a model whose geometry can be traced back to its sources. The plugin provides seven skills and seven local Python tools. It does not automatically reconstruct an entire building from a ZIP.

## Install in Codex

Add this repository as a marketplace and install its plugin:

```sh
codex plugin marketplace add obra/scan-to-model
codex plugin add scan-to-model@scan-to-model
```

Start a new Codex task so it can load the installed skills, then ask:

> Use scan-to-model to inventory these scans, build a coverage atlas, and model the next evidence-supported room, including its ceiling and connections.

The workflow runs locally. It needs no server or API key. Supply your own project directory and scans; keep private evidence in that project.

## What it does

| Skill | Result |
| --- | --- |
| `scan-to-model` | An evidence hierarchy, a coverage atlas, and a bounded modeling plan. |
| `scan-ingest` | Preserved source archives, pairing and variant audits, frame indices, and contact sheets. |
| `source-observe` | Annotate visible construction in original photographs, retaining uncertain identity and endpoints independently of model placement. |
| `street-view-reference` | Verified exterior panorama references with imagery dates, viewpoint, attribution and explicit limits on dimensional use. |
| `depth-inspect` | Calibrated native point references and measurements tied to photographed physical surfaces. |
| `scan-register` | Unit-scale rigid alignment with withheld checks and explicit limits on where a transform is valid. |
| `blender-reconstruct` | Source-tagged model candidates, saved-scene inventories, comparison renders, and a review before promotion. |

The guidance keeps current architecture, historical concealed construction, movable contents, and unresolved geometry distinguishable. It supports repeated components when observations establish matching dimensions and trim. Newer scans take precedence when the project owner identifies them as the better record of current conditions.

## Local tools and dependencies

Use Python 3.11 or newer for the scan tools. Install their dependencies in a suitable environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r plugins/scan-to-model/requirements.txt
```

Blender is required for model inspection and reconstruction. The Blender review script runs inside Blender; the scan tools run in the Python environment. The native reader currently supports Polycam keyframe exports with millimetre depth PNGs. Other formats require an explicit adapter and verified units, axes, poses, and calibration.

See the [tool commands and input formats](plugins/scan-to-model/references/formats.md), [source-observation contract](plugins/scan-to-model/references/source-observations.md), [package overview](plugins/scan-to-model/README.md), and [Blender review guide](plugins/scan-to-model/references/blender-review.md).

## Evidence and limits

Confidence labels and dense points do not establish physical accuracy. Glass, occlusion, moving objects, drift, and poor viewing angles can contaminate otherwise valid depth samples. Measure identified surfaces, examine repeat observations, and retain uncertainty. Registration is regional until independent observations support extending it.

An ingested source is not automatically examined, aligned, modeled, or verified. A plausible render is not evidence. Read the [evidence workflow](plugins/scan-to-model/references/evidence-workflow.md) and [project record conventions](plugins/scan-to-model/references/project-records.md) before promoting geometry.

This repository contains only reusable skills, scripts, and guidance. Private scans, project models, capture records, and property-specific observations belong in a separate working project.
