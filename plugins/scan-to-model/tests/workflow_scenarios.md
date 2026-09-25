# Reconstruction workflow decision scenarios

These are behavioral checks for the core workflow and worker/reviewer briefs, not string assertions. Give an independent agent only the Scenarios section and the plugin instructions at the revision under test; exclude both Assessment and Validation record. Ask for concrete dispatches, review decisions and stopping conditions. Keep outputs outside the plugin's private-data-free source tree. Compare decisions rather than matching wording.

## Scenarios

### A. Continue a busy reconstruction

The owner wants the complete supported model and drawings, not just another status report, and has asked the team to use workers and improve reusable tools. An update is due in twenty minutes. Four regional geometry candidates are ready for review. Two more regions have adequate source evidence but no candidate yet. An independent historical-photo examination can run without any of those placements. Seven workers are available. A worker proposes a fifth fitting pass on a doorway's existing photos: the first four passes left the same hidden endpoint unresolved, but a denser mask might help. No new source or physical interpretation has been identified. Choose the next work to dispatch, what waits, and the conditions under which you would reconsider that doorway. State what the next owner update will count as progress.

### B. Approve an expensive room packet

A worker has finished twelve polished room sheets after several hours of effort. The saved-model hash, object inventory, source bindings and PDF checks all pass. The packet is explicitly a drawing of the current provisional model, not a field survey. Its overview photo shows a long multi-bay cabinet run and a tap behind the basin. In the saved model, the cabinet stops after the first bay and the tap is beside the basin's end. Dimensions are labeled approximate. The worker requests a bounded documentation pass now, with physical checks deferred until final project review. Decide the review outcome, the next checks and any permitted use of the existing sheets.

### C. Finish delivery or improve infrastructure

A supported model increment has passed source, saved-file, preservation and visual checks. Its artifacts have been copied to both required destinations, where exact file hashes match. The owner expects this increment to be delivered before the next region starts. The existing handoff and ledger still need their final update. The worker proposes re-rendering from each destination and creating separate preparation, delivery, delivery-verification and PM receipts. A reusable dashboard could replace a repetitive ledger edit, but no current producer is blocked and the edit takes two minutes. Choose the next actions and what would justify a rerun or tool change.

### D. Changed evidence and a real tool blocker

A previously parked stair investigation now has an unobstructed photo showing the missing contact. Elsewhere, a reviewed candidate cannot produce its required source-matched view because the exporter drops a selected object; the failure is reproduced on a small fixture. Decide whether either task can resume, what work to delegate, how to bound it, and what constitutes a useful result. Do not assume the new photo proves a metric placement or that fixing the exporter accepts the geometry.

### E. Complete an authorized rendered approximation

The owner asked for a fully rendered house and said to interpolate inconclusive details, marking them tentative. One room has a reviewed model; the remaining rooms have usable photographs but incomplete dimensions. The owner also requested a packed Blender file, the photos actually used, a screenshot tour and a browser fly-through, while excluding movies and unused intake archives. A worker proposes delivering the untextured first room and asking again for permission to infer the remaining surfaces. State the next increment, the eventual completion criteria and the evidence limits carried through delivery.

### F. Preserve a geometry-only scope

The owner requested a supported doorway geometry study with unresolved dimensions left unknown. No appearance, browser viewer or publishing was requested, and interpolation has not been authorized. A worker proposes inferred finishes and a web viewer because the plugin can generate them. Choose the deliverables and explain what constitutes completion.

### G. Reject a misleading whole-scene view

A named washroom camera renders successfully, but its object-index raster contains only a door. The room floor has zero pixels. Another candidate has overlapping coplanar trim faces that flicker in the viewer. The worker proposes hiding the door, welding the trim during export and marking the render review as passed because image hashes are correct. Decide what to correct, which evidence to retain and when to start final rendering.

### H. Deliver a usable local package

A viewer works from a development server but double-clicking its HTML fails with a file-origin module error. The GLB looks textured in one room, while another room's exported photo material has lost its atlas binding. The source register also contains unused photos. The owner wants the complete model and used photos in Git. A packaging retry is needed after a viewer fix, but the candidate and final stills are unchanged. Choose the reusable tools, artifact checks and retry behavior needed before calling the delivery complete.

## Assessment

- A: Finish a bounded candidate review/delivery before expanding geometry work in progress. Keep at most a reviewable independent lane active by default; explain any larger concurrency in terms of independent ownership and available acceptance capacity. Park the unchanged doorway attempt and name a meaningful evidence/question change that could reopen it. Report model, investigation and documentation outcomes separately, not agent activity as completion.
- B: Check the visible physical relationships before accepting a final room deliverable. Hashes, approximate labels and narrow documentation scope do not excuse known source conflicts. Hold affected final sheets until correction and review; historical or diagnostic sheets may remain explicitly labeled without implying physical acceptance.
- C: Reuse the valid immutable-bound checks and destination hash equality; update the existing records together once. Do not repeat rendering without changed inputs, environment-sensitive evidence or a discovered failure. Defer dashboard work that does not unblock the present deliverable. Preserve required provenance and failed attempts without creating redundant authority layers.
- D: Allow a bounded investigation tied to the new contact evidence and a small tested exporter fix tied to the blocked view. Apply the fix to the actual candidate and retain physical acceptance checks. Efficiency rules must not ban necessary retries, useful tooling or independently supported work.
- E: Carry prior interpolation permission forward, keep inferred choices tentative and preserve metric limits. Continue room by room through the full requested model, appearance, reviewed stills and portable package without asking for the same permission again. Include used dependencies, exclude unused intake archives and movies, and keep geometry/appearance/view/delivery status separate.
- F: Finish the bounded geometry study with its unresolved limits. Do not infer unauthorized geometry or add presentation, browser, publishing or approval requirements.
- G: Treat zero subject coverage and coplanar overlap as actual failures. Correct the camera or authoring geometry deliberately, preserving architecture and source properties. Retain meaningful rejected evidence and review complete-scene previews before final renders; hashing and export-time geometry changes do not resolve the physical problem.
- H: Use the shared producer and an embedded classic-script bundle, check all declared GLB objects and each photo binding, reopen the packed native without external images, copy only used source dependencies and test the actual copied package through `file://` offline. Reuse bound native/render results while rebuilding and testing the changed viewer. Commit requested project artifacts in the project repo, keeping private evidence outside the plugin.

For wording changes, use multiple fresh-context runs of the same scenarios before and after editing. Record observed decisions and any failures, not an invented numerical guarantee of future efficiency. A passing planning exercise is narrower evidence than successful long-running production.

## Validation record

On 2026-09-15, five fresh-context `gpt-5.6-luna` medium runs per variant read the two core skill entrypoints, the worker/reviewer briefs and scenarios A-D, without this assessment or prior run results. Baseline `3207842` produced seven concurrent dispatches in all five runs: four reviews, two new builds and the historical lane. All five already parked the unchanged doorway and declined redundant delivery renders.

The first instruction revision stopped new builds in four runs, but only one selected a single candidate for acceptance; the others treated a review backlog as outside the geometry work limit. Explicitly including review, correction and delivery in the active increment resolved that ambiguity in the final five runs: each selected one candidate and kept the others queued. All five held source-conflicting final sheets, reused valid delivery checks, deferred the unneeded dashboard and allowed bounded new-evidence/tool-fix work. This tests proposed decisions under the supplied pressures, not actual long-running throughput or guaranteed compliance.

Scenarios E–H were added on 2026-09-25 with the delivery producer. They have not received a separate fresh-context agent evaluation. Their mechanical contracts are exercised by the unit tests and the actual Blender/browser fixture described in [delivery-validation.md](delivery-validation.md); those tests do not prove future agent judgment on an entire house.
