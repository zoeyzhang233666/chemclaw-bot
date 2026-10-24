---
name: chemclaw-chemistry
description: Verify chemical identity and structure with real databases; adapt ChemVision's cross-checking workflow to DSH tools.
license: Apache-2.0
---

Use chem_public_query for PubChem and OPSIN, then cross-check CAS, name,
formula, molecular weight and isomer. Chinese names may require a verified
English synonym; do not invent a translation or CAS. OPSIN parses systematic
names, not arbitrary identifiers. Record each database URL and retrieval date.
Use Huagongshe's public render_molecule_svg / render_reaction_svg and
calculate_stoichiometry tools when present. Never invent SMILES, stereochemistry,
balanced equations, GHS classifications or experimental properties. Distinguish
database records, predictions and user-provided measurements. Safety and process
decisions require qualified review; this role assists research, not plant control.

ChemVision is a reference for the database-first approach (MIT; pinned source
record in seed/third-party-sources.json). Its separate daemon, port and local
HTTP API are not part of this plugin. Use the DSH tools above instead.
