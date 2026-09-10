---
name: street-view-reference
description: Collect and verify Google Street View exterior references for a building reconstruction, preserving panorama identity, imagery dates, attribution and viewpoint separately from calibrated scan evidence.
---

Use Street View to supplement facade, roofline, opening and trim appearance. Inspect the project's existing exterior sources first, then obtain a bounded set of useful views through the available browser or an already configured official API. Use the property location authorized for the task; private scan uploads are unnecessary for this workflow.

### Identify the building and capture state

- Open the actual panorama. A search result, map thumbnail or address link alone is not an examined exterior photograph. Compare the building with existing verified exterior photographs when available, recording discriminating fixed-feature matches and mismatches: opening arrangement, bay/porch form, entries and corner geometry. Geographic proximity and similar paint are insufficient. The address shown by Street View may describe the camera location or a neighboring parcel; retain that label separately from the target property's identity.
- Preserve the exact panorama/share URL and panorama ID when available. Record the displayed imagery month/year, provider, attribution, retrieval time, useful visible features and view direction. Heading, pitch and field of view are known only when the interface or source supplies them; leave unavailable values unknown.
- Check the date again when moving between panoramas or selecting historical imagery, including after closing the history panel: the interface can restore the latest panorama. Do not combine different dates into a single current facade. If the house or date cannot be verified, retain that uncertainty instead of adopting the nearest panorama.
- An owner's wrong-building correction retires that target-identity claim. Record the correction, reidentify the intended facade and verify a new view; a plausible address or panorama ID does not override the correction. A panorama location and its current viewing direction can show different buildings.

### Verify the saved evidence

Capture the useful view with provider attribution and the date visible where possible. Preserve an unchanged acquisition image before making annotations. A browser/native-app screenshot is a rendered panorama view, not an original camera photograph or native scan frame: record its viewport dimensions and any crop, rotation or resizing used in derivatives. Annotation pixels refer to that specific captured raster.

Reopen and visually inspect the exact saved file before accepting it. Confirm the intended panorama, building, date and viewpoint; a successful tool response, filename or hash does not establish image content. Browser/window focus can change between inspection and capture. Reject a wrong-window capture, record the reason, and exclude unrelated private screen content from the delivered evidence packet. Reacquire only after verifying the target surface.

Detect the actual encoded image format before choosing its filename extension; a screenshot tool can return JPEG bytes even when the proposed filename ends in PNG. Correcting a suffix does not require re-encoding. Hash each accepted acquisition file and derived annotation separately. Bind the source URL, date, viewpoint, attribution, identity assessment, native screenshot pixels and reviewed features in a machine-readable source ledger. Keep clean and annotated views reviewable. If access or reliable capture remains unavailable, report the precise limitation and any verified links; do not count imagery as obtained.

### Use and handoff

Street View supports dated visible appearance. It does not supply the project's native RGB-D depth, confidence maps, calibrated camera poses, measured trim sections or proof of current survival. Panorama stitching, perspective and occlusion can alter apparent edges. Do not promote screenshot proportions or map-camera coordinates into architectural dimensions or a house transform.

Keep house-specific images, panorama locations and observations in the private project. Shared plugin guidance contains only the reusable workflow. Link useful observations to the exterior coverage register and any candidate component matches, with historical state, unknown sections and hidden surfaces retained. For source annotations, use the observation/identity/placement separation in [source-observations.md](../../references/source-observations.md), adapting the source type to a rendered panorama capture. Retrieval, visual examination, dimensional measurement and model integration remain separate accomplishments.
