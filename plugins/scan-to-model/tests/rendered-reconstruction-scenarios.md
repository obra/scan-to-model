# Rendered reconstruction evaluations

Evaluate a frozen plugin revision with fresh-context agents. Give workers only
the task, the plugin entrypoint and an isolated copy of the inputs. Keep the
assessment and previous answers out of their context. Private photos and native
models stay in the project, outside this package.

## Tasks

### Plan a rendered reconstruction

The owner wants a complete rendered house from a continuous RGB-D capture, with
inconclusive dimensions and visible finishes interpolated and marked tentative.
The source atlas identifies the rooms and their connections. Local floor and
wall measurements exist; cross-level placement still needs interpretation.
There is no existing model. The eventual outputs are a packed native model,
stills and a browser tour. Choose the next concrete modeling increment, how to
establish its appearance, and what result would justify repeating the approach
across the remaining rooms. Available execution choices are existing scripts,
a fast image-capable worker and a stronger image-capable reasoning worker.
Delegation is authorized. Return a bounded work brief, not a whole-house script.

### Review a rendered region

The owner requested a fully rendered approximation and authorized tentative
interpolation. The supplied candidate render belongs to a model that has passed
mesh, source-closure, native readback, object/material visibility and offline
browser checks. Open the supplied source photographs and render. Decide whether
this region meets the requested finish, name any corrections in priority order,
and state what you would check after correction. The model's dimensions are
provisional. Review the depicted result, not the contents of a report.

### Finish a fixture assembly

Finish the two washbasin assemblies in the supplied bathroom candidate so that
they look like the source photographs in a rendered model. Dimensions may be
interpolated and marked tentative. Preserve the room and other contents. Save a
packed candidate and full-resolution before/after render from the existing
camera, plus a detail/source-matched view if useful; review the actual saved
result against the sources. No movies or web delivery are needed for this
bounded task. Retain reproducible authoring code and report remaining visible
discrepancies.

## Assessment

Judge outcomes, not instruction keywords or counts of objects, images, materials
or checked boxes. Read every answer and open the produced images.

- Planning establishes the supported layout and carries one representative
  region through source-matched shape, material and render correction before
  copying a construction or finish method. It preserves whole-house scope and
  routes mechanical work to scripts, bounded work to the lighter capable model,
  and unresolved topology to a sufficiently capable reasoner.
- Review distinguishes recognizable objects from faithful shape and appearance.
  Concrete observations identify the actual mismatch and its correction. Known
  visible contradictions do not become acceptable by tagging them tentative.
  A clean comparison can pass; this is not an instruction to invent defects.
- Production uses the sources to choose the fixture profile, openings, contacts,
  edge treatment and finish. The saved mesh and render must show the correction,
  preserving unrelated content and source uncertainty. A more elaborate script
  or a promising plan without a reviewed native artifact is not a pass.

Compare revisions on the same inputs and task. Small repeated decision exercises
test interpretation; at least one actual native modeling task tests execution.
Distinguish those results from a fresh whole-house reconstruction. A successful
bounded correction does not establish parity with an earlier complete model.

## Observed baseline

The source-only whole-house retry at plugin revision `bc3500d` reached verified
delivery while its source comparisons still showed simplified fixture profiles
and flat finishes on prominent timber parts. Review notes accepted the presence
and readability of those features. The failure is visual fidelity despite
successful packaging; it is not explained by atlas count or object count.

## Decision comparisons

On 2026-09-26, five fresh-context `gpt-6-luna` medium runs per variant received
the same planning task and actual source/render comparison. The control read
the `bc3500d` instructions; the revision also read the constructive rendering
method. Workers had no assessment, other workers' answers or original benchmark
model. Each opened the images. Answers were read individually, not scored by
keyword matches.

Both variants rejected the poor rendered finish and selected a capable lead
for the whole-house interpretation. Those behaviors already worked in this
bounded exercise. The revised answers consistently described a representative
region through corrected final-size rendering before reusing its method and
kept assembly count unresolved when only a close-up was supplied.

The lighter model remained unreliable at fixture interpretation: three of the
five revised answers asserted a wrong mounting relationship, and some confused
a recessed bowl with an inset installation. This is a failed capability check,
not a passing review merely because it rejected the candidate. The method now
requires a support/contact view plus native inspection before a mounting change,
and model selection explicitly routes a failed visual comparison to a more
capable reviewer.

Five fresh-context `gpt-6-sol` medium runs then used the refined instructions on
the same task and images. All identified the simplified basin profiles and
retained uncertainty about counts outside the supplied views. Their dominant
shape findings were more useful, and they requested contact checks instead of
prescribing the lighter model's unsupported mounting replacement. Other
suggested finish or fixture changes still require source/native verification.

This final comparison changed both guidance and model; it does not isolate the
effect of wording. It supports capability-based routing on the observed task,
not a universal ranking, latency claim or guarantee that any model can reconstruct
a house. Decision tests also do not establish that an agent can execute its plan.

## Native modeling trials

Two fresh-context `gpt-6-sol` medium workers received the fixture-assembly task,
the same packed candidate and three source photographs. One read the control
instructions, the other the first constructive-method revision. Both produced
rounded bowls and more representative faucets, preserved unrelated room meshes
and packed all 99 file-backed images. The control already improved the shape;
this is not evidence that the first instruction revision outperformed it.

Independent saved-model inspection found both results incomplete: the faucet
bases floated 5.5 mm and 8.5 mm above the countertop respectively, and neither
modeled the source-visible ceramic support behind the bowl. The workers' final
notes did not identify this defect. This prompted the shared-support construction
recipe in the method reference, including deriving component positions from the
support surface and checking the evaluated contact after reopening.

The system Blender build lacked denoising. Both workers were given access to the
same Cycles/OpenImageDenoise-capable executable for their final comparisons;
failed runtime attempts were retained. These runs were source-bounded modeling
exercises with runtime assistance, not complete autonomous house imports.

A third fresh-context `gpt-6-sol` medium worker received the same sources and
task, the usable renderer from the start, and the method with the shared-support
recipe. It modeled the ceramic rear decks and placed the faucets on them. An
independent ray cast in the saved candidate confirmed a 0.5 mm overlap at each
base instead of a floating gap. All 99 file-backed images remained packed; the
1,608 unrelated mesh objects retained their transforms, mesh data, material-slot
assignments and render visibility. The worker also reopened and rendered its
saved candidate. This is one successful execution of the support construction,
not evidence that every agent or fixture will now succeed.

The result still had a softer, rounder rim, flatter porcelain reflections and
simplified hardware compared with the photographs. The worker reported those
visual limits. It also invented zero-padded source aliases on its 20 new parts,
which the evaluator corrected against the existing source registry after saving
the raw trial. That metadata correction preserved geometry and other object
properties on readback; it was supervised cleanup, not an unassisted pass.

The native trials support a more concrete construction method and capability
checks. They do not establish a fully rendered finish, whole-house parity with
the original, or reliability across arbitrary agents. Retain raw candidates,
before/after stills, authoring scripts, runtime receipts and evaluator findings
in the private house evaluation; private source photographs and model files do
not belong in this public plugin repository.
