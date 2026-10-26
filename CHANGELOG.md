# Changelog

All notable changes to ChemClaw are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the versions follow [Semantic Versioning](https://semver.org/). Before 1.0, a minor version can contain breaking changes.

## [Unreleased]

## [0.2.2] - 2026-10-27

### Added

- Interactive chat views: SVG charts, local formula inputs, and sandboxed HTML, with full blueprint replay in history.
- Group deliverable links resolve to existing workspace files so HTML and Excel open correctly from chat.

### Changed

- Group relay can pause and continue; Bot `message_bot` requests use durable receipts; handoff results and memory pending transactions recover more reliably, with clear failure feedback.
- Existing installs refresh Chinese skill metadata from the plugin seed on bootstrap.
- Slash skill menu shortens long host titles, adds Chinese labels for more native skills, and keeps row text from stacking.

### Notes

- Desktop and plugin packages are both `0.2.2`. Install from the GitHub Release assets or `github:zoeyzhang233666/chemclaw-bot#v0.2.2&path:/chemclaw-bot`.

## [0.2.1] - 2026-10-26

### Added

- Chinese skill library: search, browse, and install full skill packs by business category; invoke from cards or the `/` menu in the current chat while keeping drafts and attachments.
- Desktop app update checks for ChemClaw; Settings → About supports a manual check. Windows can restart to install; macOS opens the matching ZIP download.

### Fixed

- Deliverable files expose a local open action; large workspace Git snapshot waits are bounded.
- Release workflow packs and verifies the plugin `.tgz`, Windows installer plus update files, and both macOS ZIPs before publishing.

### Notes

- See [docs/releases/v0.2.1.md](docs/releases/v0.2.1.md) for download names.

## [0.2.0] - 2026-10-26

### Added

- **Public ChemClaw snapshot** for GitHub install and source archive: the `chemclaw-bot` DSH plugin, the ChemClaw Windows/macOS desktop app source, seed catalog and skills for chemical-industry work, and launch helpers.
- **Docker** compose stack and image entrypoint for a self-hosted run (`docker/`, `docker-compose.yml`).
- Repository helpers: leak scan (`scripts/scan.mjs`), catalog/docs scripts, Issue/PR templates, and the ChemClaw design note in `docs/plans/2026-10-22-chemclaw.md`.
- **Main Bot group coordination**: a Main Bot can join a group as an on-demand coordinator without taking over the admin role; catalog, connectors, providers, diagnostics and related tests updated for the public snapshot.

### Notes

- Plugin package name: `chemclaw-bot`. Desktop product name: **ChemClaw**.
- npm publish from this repository is gated until Trusted Publishing is configured (`ENABLE_NPM_PUBLISH`); GitHub Releases still attach the `.tgz` and installers.
