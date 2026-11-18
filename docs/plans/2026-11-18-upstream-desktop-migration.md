# ChemClaw desktop migration to DS Bot v0.3.8

The migration branch starts at DS Bot v0.3.8. The desktop application keeps the ChemClaw package name, release repository, desktop app ID, DSH profile name and default data path. The Bot host continues to use the `chemclaw` team directory within the profile home. A new import from a separate DSH home copies that home's Bot team into the ChemClaw team directory.

The upstream Ledger reads old room state, append-only room logs and long-message sidecars on first access. Preserve old DSH Sessions and sidecars through the upgrade. A new team receives the versioned expert roster, collaborative groups and skill library without sending a first message. A later installation refreshes preset metadata without creating duplicate experts or groups.

ChemClaw's dedicated skill library and company connector controls use the shared upstream settings shell. APIHub uses DSH settings and credentials with its fixed HTTPS endpoint. The public research and market tools remain registered separately from model setup. The desktop icon and DMG layout come from the existing ChemClaw assets and release workflow.

Check a new profile and a ChemClaw 0.3.2 fixture. Gate distribution on the plugin suite, generated bundles, and Windows and macOS packaged upgrade tests. Use the existing release workflow with dry-run packaging before public distribution.
