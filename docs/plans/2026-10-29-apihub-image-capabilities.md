# APIHub image input metadata

DSH's session attachment admission uses a model's declared input modalities.
The rc.3 generic endpoint discovery parser drops those fields, and APIHub models
saved without them resolve as text only. The rejection happens before the
ChemClaw image stream hook, so an OCR retry there cannot fix attachment admission.

Use only DSH's public configurable-provider directory and model discovery service.
Native Pi catalog discovery is local, needs no key and preserves modalities. Fill
missing APIHub inputs from exact full model IDs with consistent explicit catalog
declarations. Preserve explicit inputs, unknown IDs and conflicting declarations;
never infer capabilities from a family name or mark every relay model as vision.
The gateway can still expose a narrower capability than its upstream model.

Apply this to APIHub discovery candidates, new setup, and existing routes at the
verified APIHub endpoint using the documented settings mutation service. Existing
model fields and route controls survive. Repair runs at plugin startup after team
load and before publishing the ChemClaw model list. Repeated/concurrent reads are
idempotent. Revision checks protect concurrent settings edits; a later read retries.
Other endpoints, adapters and OpenCode Go catalog routing are left to their owners.

No DSH patches, credential-file access or live-key tests. Regression tests cover
exact-ID enrichment and exclusions, persisted migration and the official adapter's
image metadata and transport with mocked HTTP. Existing OCR behavior is unchanged.

The remaining upstream fix is preserving endpoint-provided modalities in DSH
model discovery; an official DSH release should carry that general parser fix.
