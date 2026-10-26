# Changelog

All notable changes to ChemClaw are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the versions follow [Semantic Versioning](https://semver.org/). Before 1.0, a minor version can contain breaking changes.

## [Unreleased]

## [0.2.0] - 2026-10-26

### Added

- **Public ChemClaw snapshot** for GitHub install and source archive: the `chemclaw-bot` DSH plugin, the ChemClaw Windows/macOS desktop app source, seed catalog and skills for chemical-industry work, and launch helpers.
- **Docker** compose stack and image entrypoint for a self-hosted run (`docker/`, `docker-compose.yml`).
- Repository helpers: leak scan (`scripts/scan.mjs`), catalog/docs scripts, Issue/PR templates, and the ChemClaw design note in `docs/plans/2026-10-22-chemclaw.md`.
- **Main Bot group coordination**: a Main Bot can join a group as an on-demand coordinator without taking over the admin role; catalog, connectors, providers, diagnostics and related tests updated for the public snapshot.

### Notes

- Plugin package name: `chemclaw-bot`. Desktop product name: **ChemClaw**.
- npm publish from this repository is gated until Trusted Publishing is configured (`ENABLE_NPM_PUBLISH`); GitHub Releases still attach the `.tgz` and installers.
