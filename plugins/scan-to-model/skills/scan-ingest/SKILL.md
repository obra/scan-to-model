---
name: scan-ingest
description: Preserve and inventory scan archives while retaining capture variants, hashes, calibration, and frame provenance.
---

Use for ZIP or extracted scan intake. Copy archives without altering them, hash source files, and produce an inventory and frame index. Preserve raw and cleaned depth plus raw and corrected poses as explicit variants; retain units, calibration, native pixels, frame IDs, and capture coordinates. Never overwrite source material with a derived product.

Read [evidence-workflow.md](../../references/evidence-workflow.md) for provenance and [formats.md](../../references/formats.md) when emitting records. Use package scripts with caller supplied paths; never bake in an address, home directory, or capture index.

Run `scripts/ingest.py` with the archive and project paths. Inspect its actual inventory and variant counts, including any failed audit. Use the returned capture root when a ZIP contains an enclosing directory. Inspect the overview and every full contact sheet, and reopen native frames for important boundaries or uncertain identities. A clean inventory establishes that paired files can be read, not that every room was examined.

Run `scripts/reference.py` with explicit raw/Clean and raw/corrected choices. Check finite coordinates, confidence/range filtering and source-frame/pixel identity. Keep the raw source untouched and the derived reference separately named. Repeated ingestion should verify the same bytes and refuse conflicting files; investigate a refusal instead of deleting the evidence.
