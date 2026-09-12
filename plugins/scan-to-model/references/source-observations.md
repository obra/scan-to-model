# Photograph observations that survive model changes

Use this record contract for visible construction inventories from scan RGB or standalone photographs, including photographs embedded in documents. It extends the [project records](project-records.md); reuse existing project IDs and records where they already carry the information. No new database or particular filename is required. The example below illustrates the fields. `scripts/observations.py` validates and renders photo annotations; it does not perform automatic object recognition.

## Keep three things separate

| Record | What it identifies | What can change independently |
| --- | --- | --- |
| Observation | A specific visible feature or span in one identified source image, with native pixel marks | A corrected annotation is a new revision with a reason; preserve the reviewed predecessor. |
| Feature relation | A supported or tentative assertion that observations depict the same physical thing | Identity can be confirmed, rejected or left unresolved without deleting either observation. |
| Placement | A measurement or authored position in a named capture/model coordinate system | A later candidate can supersede the placement while keeping source observations unchanged. |

Keep IDs stable when room names, coordinates, Blender object names or an interpretation such as “hot water” change. Treat legacy IDs as opaque identifiers; a room name embedded in one is not a reason to rename it. An observation can remain unlocated. Reference an older trace ID where the physical match is established; record a possible match as possible rather than silently merging it. A crossing in an image is not proof of a physical junction.

## Source identity and image coordinates

For each source, record:

- Original path or archive/document reference and SHA256 of the preserved bytes; frame ID where present.
- Native decoded width/height and the decoder/EXIF orientation treatment used to define the pixel array. An optional decoded-pixel digest must name mode, channel order, dimensions and orientation.
- Pixel convention: origin, axis directions and whether coordinates refer to pixel centers or image edges. Use finite native coordinates; record the annotation type (point, polyline or polygon) and its intended meaning (centerline, visible boundary, face or locator).
- Any displayed image's source relationship: crop, rotation, scaling and an explicit invertible mapping into native pixels. Hash the derivative as a derivative. Keep annotations in the native convention even when selecting or presenting them upright.
- Source-date claims and their provenance. Folder names, scan clock values, PDF metadata and EXIF dates retain their stated uncertainty; a timestamp without known epoch/units is not a calendar date.

For a raw image with width W and height H, pixel-center coordinates `(u,v)` have origin at the center of the top-left pixel. A 90-degree clockwise display maps them to `(H-1-v,u)`. An SVG image rectangle instead starts at a pixel edge: place native pixel-center marks at `(u+0.5,v+0.5)` before applying the corresponding display transform. State a different convention explicitly. Check corners and a known feature so a plausible rotated overlay does not hide an incorrect mapping.

For a PDF photograph, preserve the document hash, page numbering, image object/resource identifier and page placement/orientation. Record PDF color-space, decode and mask settings that affect display; a raw JPEG stream alone may not reproduce the page appearance. Inspect the extraction method. An image-export API can recompress JPEG data, alter decoded pixels or discard metadata; the word “extract” is not proof of original bytes. For a directly embedded JPEG, preserve its raw DCT image stream where accessible. Keep page renderings and recompressed exports as derivatives. For tiled, masked or composite photographs, record the reconstruction components and transforms; a rendered page is not an original camera photograph.

When preserving PDF drawing commands, distinguish the encoded stream bytes stored in the document (compressed when applicable), their original decoded bytes, parsed semantic operations and any parser-normalized serialization. Read and preserve original bytes before accessing mutable parser operations: deserialization or later serialization can normalize whitespace without changing the drawing. Hash and label each representation independently, and compare the purported original against a fresh read of the document stream. A correct placement matrix does not prove exact command-text preservation.

## Observation record

Each observation needs the following information, whether stored in JSON or another existing project format:

- Stable observation ID and source reference.
- Native pixel marks and their geometric meaning. A line drawn for legibility is not a measured pipe diameter or member section.
- Plain visible facts: for example, “orange-brown cylindrical span passes behind a wood face.” Keep material, system, installation and function interpretations separately qualified with their basis.
- A meaning for each polyline endpoint or relevant polygon boundary: **visible physical termination**, **occlusion**, **image boundary**, **annotation boundary**, or **unknown**. A deliberate review crop is an annotation boundary even when more of the object is visible beyond it. Split an interrupted span at the occlusion rather than drawing unseen continuity.
- Any physical-feature association and its confidence/basis, separately from confidence that the pixels were traced correctly.
- Construction state and current-survival assessment, with supporting sources or explicit unknown. A photographed installation is not proof that it is still present behind today's finish.
- Review status and the scope actually examined. Missing from an annotated selection does not mean physically absent or absent from the entire scan.

Do not force all categories into every image. A bounded packet may show cables and framing but no identifiable retrofit component. Record an unidentified metal item as such; a nearby drawing detail or inspection count does not establish its installed type, embedment or load path. Preserve observed versus prescribed properties separately.

### Example: one visible span, uncertain identity

The following is an illustrative record, not source evidence or reusable image coordinates. `photo-a` resolves to an immutable source record with its real hash, dimensions and display mapping.

```json
{
  "id": "obs-017",
  "source_id": "photo-a",
  "marks": {
    "type": "polyline",
    "meaning": "visible centerline",
    "coordinates": [[124, 318], [168, 300], [203, 297]],
    "space": "native pixel centers; top-left origin; u right, v down"
  },
  "observed": "Brown cylindrical span, partly hidden by a wood face.",
  "interpretation": {
    "category": "pipe candidate",
    "material": "copper-looking; unconfirmed",
    "system_function": "unknown"
  },
  "endpoints": [
    {"index": 0, "kind": "occlusion", "basis": "Disappears behind wood."},
    {"index": -1, "kind": "annotation boundary", "basis": "Review ends here; no physical end observed."}
  ],
  "current_survival": {"status": "unknown", "evidence": []},
  "review": "Source image and both endpoint meanings visually checked."
}
```

A separate relation can say that `obs-017` possibly matches another photo's span, citing fixed neighboring features and the unresolved discrepancy. Do not assign a shared physical feature merely because both spans have the same color.

## Cross-photo identity and construction state

Match a bounded fixed feature or feature group, not an entire room's construction state. Several distinctive joints can establish that two photographs show the same wall while an intervening member or installation differs. Record the retained correspondences and the differences together; neither erases the other. A group-level match does not establish that every individual member is the same physical piece.

For each proposed relation, record the observation IDs in both photographs, the precise physical-identity scope, supporting fixed features, contradictions or state differences, and relevant occlusions. Use a status such as supported, candidate/held or rejected, with the reason. Similar color, a generic stud pattern, loose offcuts, tools, packaging or temporarily leaning parts do not independently establish fixed identity.

An absence claim requires an examined corresponding region where the feature would have been visible. Distinguish an exposed region showing a different state from a region hidden by foreground framing, darkness, furnishings, the image edge or the review selection. Preserve native locators for the comparison region even when no corresponding feature is present. Do not turn a missing annotation into a missing physical object.

Assess chronology separately. Record camera timestamps verbatim with their device, time-zone/clock uncertainty and any conflicting metadata. Page order is not capture order. A state difference can be supported even when its sequence or cause is unknown. Matching a historical installation does not prove that it survives behind present finishes, and matching a photographed enclosure does not by itself assign a current room, storey or model transform.

Keep comparison locators distinct from detailed feature traces. When both reference the same source region, link them and report their counts separately; they are not additional installed objects. Present proposed matches side by side in original-image context, retaining the unmatched and occluded features that limit the conclusion.

## Measurement and placement after observation

Link optional measurement records to observation IDs and exact source selections. Retain native depth/confidence, calibration, pose variant and capture-local coordinates where available. A missing depth return does not invalidate a photographic observation and does not justify inventing a metric position. The existing `surfaces.py` requires a complete native scan frame; it is not a standalone-photo or PDF measurement command.

A placement record identifies the observation/feature IDs, candidate/model hash, target coordinate frame and units, object IDs, proposed or accepted transform, measurement references, uncertainty, review status and supersession relationship. Model A and model B may carry different placements of the same observation. Review the new placement against independent evidence; keep A's placement as historical rather than rewriting the source marks to fit B. Rebuilding base geometry can invalidate a placement without invalidating source identity or a reviewed observation.

## Reviewable output

Deliver the source manifest, observation/feature-relation records, annotated source sheets and a concise scope/unknowns report. A vector overlay referencing or embedding unchanged source bytes can reproduce marks without repainting the photograph. Keep annotation labels readable and distinguish locator lines from measured outlines. Record output hashes and the script/command used to reproduce them when a generator is used.

The bundled renderer accepts local JPEG and PNG paths and writes only to a new output directory:

```sh
python "$PLUGIN/scripts/observations.py" \
  --spec /path/to/review/observations.json \
  --output /path/to/review/annotated-source-evidence \
  --coordinate-inspections
```

```json
{
  "sources": [
    {
      "id": "photo-a",
      "path": "sources/photo-a.jpg",
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "orientation": "upright90cw",
      "metadata": {"capture_date": "unknown"}
    }
  ],
  "observations": [
    {
      "id": "obs-017",
      "label": "visible span",
      "source_id": "photo-a",
      "marks": {
        "type": "polyline",
        "meaning": "visible centerline",
        "coordinates": [[124, 318], [168, 300], [203, 297]]
      },
      "endpoints": [
        {"index": 0, "kind": "occlusion", "basis": "Disappears behind wood."},
        {"index": -1, "kind": "annotation boundary", "basis": "Review ends here."}
      ],
      "qualification": {"identity": "unresolved"},
      "metadata": {"observed": "Brown cylindrical span."}
    }
  ],
  "features": [
    {
      "id": "feature-candidate-1",
      "observation_ids": ["obs-017"],
      "qualification": {"status": "candidate", "basis": "Single-view observation."}
    }
  ],
  "metadata": {"review_scope": "One invented example span."}
}
```

Source paths may be absolute or relative. Relative paths, including `../` sibling references and symlinks, resolve from the specification directory. The evidence record preserves the declared path and the exact resolved target path with its hash; the helper does not copy, move or rewrite source files.

IDs may contain letters, numbers, dots, underscores and hyphens. All three top-level arrays are required; `observations` and `features` may be empty. Point, polyline and polygon coordinates are always native pixel centers. A point has one coordinate, a polyline at least two and a polygon at least three. Polylines require qualified endpoint records at indices `0` and `-1`; points and polygons use an empty `endpoints` list. Qualification and arbitrary metadata remain authored input and are preserved unchanged. Labels must contain only characters valid in XML 1.0; unsupported control characters cause generation to fail rather than being removed or replaced.

`raw` keeps native display orientation. `upright90cw` maps native centers `(u,v)` to `(H-1-v,u)` and rotates the embedded image bytes in SVG without recompressing them. JPEGs with a nontrivial EXIF orientation are rejected so the browser cannot silently add another transform. The output `evidence.json` contains the complete input record, exact before/after source and spec hashes, decoded dimensions, native/display coordinates, round-trip checks and generated artifact hashes. Each SVG embeds the original source bytes.

Schema version 3 adds the generator's `coordinate_inspections` setting and a nullable `coordinate_inspection` record to every annotation review. The existing `review/<observation-id>/assertion.svg` is a native-scale detail of the entire authored mark. A polyline's directory also contains `endpoint-0.svg` and `endpoint-last.svg`. The per-observation directory keeps derived artifact names separate from every other valid observation ID. Crop bounds include 32 displayed source pixels of context where the source boundary permits, and are recorded as pixel-edge `[left, top, right, bottom]` values. SVG width and height equal those bounds, so one SVG unit is one displayed source pixel; opening a crop does not create additional image detail. Every crop embeds the unchanged full source bytes and has its own SHA256. Review crops omit visible text so labels cannot cover the pixels being checked; their escaped SVG titles, paths and evidence records retain identity. The whole-source sheet keeps visible labels for context.

With `--coordinate-inspections`, each observation also gets one `coordinates.png`. Every authored coordinate has unmarked and open-locator context panels covering 128 displayed source pixels in each direction at 1×, plus a 9×9 nearest-neighbor pixel detail at 12× with an open locator. Visible labels give the exact native coordinate, mapped display coordinate and nearest native pixel. The PNG retains decoded source alpha; dark padding identifies context beyond a source edge. The evidence record gives each panel's output bounds and selects the nearest native pixel as `floor(coordinate + 0.5)` on each axis. A sheet balances coordinates across columns with at most eight rows. This view makes selected pixels and nearby boundaries inspectable; it does not decide which physical face they depict or whether the segment between coordinates stays on the intended face.

Generated review status is always `pending visual review`. Coordinate validation cannot set it to checked. Open the full sheet for context, then inspect every assertion crop at native scale: a point must land on the intended visible item, a polyline must follow the visible span and a polygon must bound the intended face. When coordinate inspections were generated, open them to check exact vertices without losing the full-span assertion review. Inspect each endpoint crop independently and compare the visible transition to the authored kind and basis. Wall edges, framing boundaries and crossings do not establish a physical termination or occlusion by themselves.

Save a separate review record rather than editing generated `evidence.json`. Identify the observation and evidence-packet hash; for the assertion and every endpoint, record the generated path/hash, `checked` or `rejected`, and a concrete finding. A missing check, ambiguous feature or ambiguous transition keeps the observation pending. Correct marks or downgrade unsupported endpoint meanings to `unknown` or `annotation boundary`, generate a fresh packet and review again before using the observation for physical identity, visible geometry, cross-photo correspondence or model decisions.

Review finalizers may bind separately supplied, explicit image-review decisions for each mark and endpoint. Never synthesize `checked`/`accepted` statuses or findings from authored labels or prose, successful rendering, coordinate replay, or uniform auto-pass loops. Those inputs establish what was proposed or generated, not what the image review found; missing or ambiguous decisions remain pending.

The renderer accepts no PDF input and does not recognize features, decide cross-photo identity, verify its own visual review, estimate depth, register a coordinate frame or establish that the review found every feature.

Check source hashes, image dimensions, finite/in-bounds marks, coordinate round trips, unique IDs and source/relation references. Then visually inspect the annotated originals: structural checks cannot prove feature identity or endpoint meaning. Inspect every authored mark in the packet; separately sample proposed cross-view matches in both full images. Report excluded/ambiguous features and what remains unexamined. A saved overlay proves reproducibility, not depth, room assignment, hidden continuity or present-day survival.
