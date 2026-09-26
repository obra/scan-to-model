# Build a source-faithful rendered approximation

Use this method when the requested finish includes photographic appearance or
fully rendered architecture. [Delivery](delivery.md) packages an authored model;
this method establishes what to author and whether it looks like the sources.
Keep decisions in the existing room record and review notes.

## Establish one working example

After mapping rooms, levels and connections, block out supported extents and
resolve the next consequential join. Choose one well-covered region containing
representative construction and finishes. Take that region through shape,
materials, lighting and a corrected final-size render before repeating its
helpers or material assignments through the house. A plausible blockout or a
successful export is too early to standardize the construction method.

Keep the surrounding shell in review views so adjoining walls, ceilings and
stairs still constrain the region. Continue through all authorized regions after
this example works; one finished room is a method check, not house completion.

## Read the sources into a modeling brief

Open a context view and sharp detail views. In the existing room record, connect
each dominant feature to its source view, intended geometry and material:

| Observation | Modeling decision | Comparison |
| --- | --- | --- |
| Extent, opening, ceiling or connection | Local frame, proportions, shared contacts | Source-matched overview and plan/section |
| Fixture silhouette, rim, recess or profile | Actual contour, depth, mounting and edge treatment | Detail view showing the supporting surface |
| Timber, stone, tile, paint, glass or metal | Surface family, pattern scale/direction and roughness | Final-size lit surface beside its source |

Use only the portion of a photograph that shows the feature being compared.
An object outside a close-up is **unreviewed**, not absent. Establish counts and
layout from context views; establish profiles and finishes from details. Check
another angle or the saved geometry before asserting mounting, contact or shape
from an ambiguous silhouette, reflection or occlusion. Describe the visible cue
supporting a proposed correction. If it remains ambiguous, retain supported work
and route that question to a stronger image-capable reviewer or a better view.
For a mounting or contact correction, inspect a view exposing the fixture base
and its support, and locate that contact in the saved candidate. If the supplied
images do not expose it and native inspection is unavailable, return that check
as unresolved instead of specifying a replacement mounting.

## Model the visible shape

Match the large envelope and proportions first, then the features that change
the silhouette, shadow or highlight at the requested viewing distance. Model
openings as openings, bowls as recessed surfaces, rims with thickness, and
profiles with their observed curve or taper. Boxes are useful for blocking out
extent; an assembly of sharp boxes is finished only when the source shows that
shape. Regular manufactured rectangles still use the component-frame method in
[manufactured-shapes.md](manufactured-shapes.md).

For example, a ceramic basin with a rectangular outer rim and rounded bowl can
be built from aligned contour rings: underside, outside wall, rim, inner rim,
sloping bowl and drain. Connect corresponding vertices, close the underside,
and add the source-supported rear deck and hardware. Match the side profile
and the rim above the worktop, not just the top-down outline. Curve segments,
bevel width and smooth normals should preserve that profile in the final view.
Dimensions and unseen profile portions can remain tentative.

Build related parts in one component frame, with their placements derived from
shared support surfaces. First identify what carries each part in the source:
for example, a tap may stand on a ceramic rear deck rather than the countertop
behind it. Model that support and derive the tap base from its top surface. For
a horizontal support at local height `h` and a base of thickness `t`, the base
center is `h + t/2`; transform the assembly into the room together. Separate
guesses for every world-space coordinate create floating or intersecting parts.
After reopening, check the actual evaluated contact with bounds, a section or a
ray cast. A numerically closed contact verifies assembly consistency, not the
accuracy of an interpolated dimension.

Curved objects are compatible with delivery. Construct planar polygons or
triangulate curved strips; apply topology-changing modifiers on the candidate
before photographic baking. Inspect the resulting silhouette and normals.
Do not simplify a supported curve into a box to accommodate the planar-face
baker. Matched-color porcelain or metal still needs its correct shape and shader.

## Match surfaces before tuning the lights

Choose the appearance method per physical surface:

- Use direct projection for recognizable surface detail when camera-to-model
  alignment and depth support are adequate. Inspect the surviving coverage and
  fallback in the render; pose metadata alone does not establish alignment.
- Use a rectified single-material sample for repeated grain or texture. Review
  the crop, its physical scale, and its orientation on the actual part. A useful
  crop from a floor is not automatically the finish of every timber component.
- Use source-guided color and roughness for visually uniform finishes. If grain
  or veining is prominent in the source and rendered view, preserve that detail
  with a suitable sample or projection. A brown swatch does not reproduce wood.
- Infer unseen continuation under existing authorization and keep its basis and
  uncertainty visible. Reflections and transmitted scenery are not paint.

The repeated-photo mapper uses one world-space plane per material definition.
Its two mapping axes must span the target surface. Reusing a horizontal floor
frame on a vertical or sloping part can collapse the sample into streaks. Use
separate oriented material definitions for differently aligned surface groups,
reusing the reviewed source crop where physically appropriate. Check grain along
the part, seams across adjoining parts and thin edge faces in a detail render.

Judge texture density at the requested output size. Inspect important crops at
that size before increasing atlas size or render samples. Atlas count, source
count and object count are not visual quality measures. Preserve geometric tile
courses or board divisions when repetition alone cannot match their structure.

Use neutral diagnostic illumination to distinguish a wrong base color from a
lighting error, then place source-plausible daylight and interior lights. Tune
exposure, roughness and soft contact shadows together. Broad warm fill that
erases contrast cannot recover missing shape or grain.

## Compare, correct, then deliver

Keep a source-matched review camera as well as any tour camera. Match viewpoint,
verticals and field of view closely enough to compare proportions. An extreme
wide-angle tour view can distort a correct fixture or conceal a poor one; use a
detail view to resolve the question. A manually matched camera is diagnostic,
not independently calibrated registration.

Compare the source and saved-model render in this order: extent and contacts;
silhouette and profile; major features and hardware; material pattern, scale,
direction and color; then lighting and composition. Correct the largest visible
differences and rerender the affected views. Low-resolution previews establish
visibility cheaply; inspect final-size details for shape and finish decisions.

In the existing review note, name the source/view compared, the observed match
or discrepancy, and the remaining limitation. Distinguish an unknown dimension
from a known visible mismatch. A fixture being present and recognizable is not
enough to call a photographic finish complete. A passing raster, hash or browser
test establishes only its mechanical contract.

If an earlier model is the quality target, compare corresponding views before
claiming parity, with source evidence deciding conflicts. For an independent
source-only retry, give the original model to the evaluator after construction,
not to the builder. Keep bounded passes narrower than whole-house claims.
