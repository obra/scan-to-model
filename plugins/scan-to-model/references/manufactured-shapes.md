# Manufactured assembly shape fitting

Use a component-local shape pass when evidence establishes manufactured rectangles. Inventory the whole assembly: outer leaf/boundary, panels/insets, their dependent openings, rectangular hardware and regular surrounds. Declare which members have evidence for common axes; fit those together while retaining each member's independent size and position. If an axis came only from one uncertain traced edge, fit the common orientation to the unchanged controls instead. Keep deliberately rotated or dissimilar parts in separate groups and preserve circular/rotational parts.

Regular shape does not establish nominal stock dimensions, installation plumb, house registration, hidden depth profiles or exact product reuse. Preserve the original controls, constraint justification and dimensional qualification. The helper carries arbitrary JSON metadata unchanged; it does not validate that metadata or decide which parts belong together. Investigate large residuals against existing evidence allowances. Update dependent openings/profiles from the constrained geometry and verify the saved native meshes as described in [Blender review](blender-review.md).

## Numeric contract

`scripts/manufactured.py` exports `fit_rectangles(spec)` and accepts `--spec INPUT.json --output OUTPUT.json`. It fits only 2D rectangles and writes a candidate report; it does not edit Blender scenes.

- `frame_id` identifies the input 2D coordinate system; `units` names its existing units, including `uncalibrated`. No unit conversion or scale inference occurs. Project image/depth controls into an explicitly justified component plane before fitting; this is not perspective rectification.
- `frame.origin` is a finite input-plane point. `frame.u_axis` is a unit vector in that plane; `v_axis` is its positive 90-degree rotation. An optional supplied `v_axis` must agree. Local-to-input coordinates are `origin + u*u_axis + v*v_axis`.
- `rectangles` is a nonempty list with unique string `id` and four finite `controls` per member. Order is `(-u,-v), (+u,-v), (+u,+v), (-u,+v)`: counterclockwise around the intended rectangle in a plane whose coordinates increase right/up. Image coordinates increasing downward must be transformed and reordered explicitly. Controls must form a convex, nondegenerate quadrilateral. The tool never guesses correspondence or reorders points.
- `fit_orientation` defaults to `false`: hold the declared axes. When `true`, minimize the sum of squared corner displacements across all supplied members, with a shared orientation and independent centers, widths and heights. All corners have equal weight; larger members consequently influence orientation more. The fitted `u_axis` sign is selected toward the declared axis. Ordering must yield positive widths/heights; otherwise the fit is rejected. Use an approximately correct declared axis, with intended `+u` within 90 degrees of it.
- Output `input` is a deep copy of the entire specification, including evidence metadata. `frame` contains `origin`, `u_axis`, `v_axis`; `orientation_fitted` records the mode. Each result in `rectangles` contains its `id`, original `controls`, constrained `corners` in original order/input coordinates, `local_bounds` as `[[min_u,min_v],[max_u,max_v]]`, `width`, `height`, four `residuals` (`fitted - control`, in input axes), and four Euclidean `errors`, all in the declared units.
- To reuse an orientation fitted from selected members, pass the returned `frame` unchanged into another specification with `fit_orientation: false`. Include the frame's derivation and selection rationale in that specification's metadata. Rectangles in the second call do not influence the orientation.

Malformed, nonfinite, degenerate, nonconvex, incorrectly ordered or numerically unresolved inputs raise `ValueError`; the CLI exits nonzero. Numerical rejection uses relative tolerances, not physical evidence allowances. Output may not alias the input specification. Other existing output reports can be overwritten, so retain separate paths for checkpoints. A failed command does not certify an older output left at that path.

## Invented example

These values are synthetic and uncalibrated:

```json
{
  "frame_id": "example-front-plane",
  "units": "uncalibrated",
  "frame": {"origin": [0, 0], "u_axis": [1, 0]},
  "fit_orientation": true,
  "qualification": "Invented example; no physical dimensions established",
  "rectangles": [
    {"id": "front", "controls": [[0, 0], [3.2, 2.4], [2, 4], [-1.2, 1.6]]},
    {"id": "plate", "controls": [[8, 6], [9.6, 7.2], [7.8, 9.6], [6.2, 8.4]]}
  ]
}
```

Save as `example.json`, then run from the plugin directory:

```sh
python3 -B scripts/manufactured.py --spec example.json --output fitted.json
```

The common axes are `u=[0.8,0.6]`, `v=[-0.6,0.8]`; sizes are `4 × 2` and `2 × 3` input units. Errors are zero up to floating-point precision. These dimensions remain uncalibrated.

Run the synthetic numeric contract tests from the repository root:

```sh
python3 -B -m unittest discover -s plugins/scan-to-model/tests -v
```
