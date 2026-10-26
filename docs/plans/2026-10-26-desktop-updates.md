# ChemClaw desktop updates and complete releases

The packaged ChemClaw app checks its own GitHub releases by default. Development
and isolated runs (`DS_BOT_HOME`) check only an explicitly supplied
`CHEMCLAW_UPDATE_URL`. Windows uses electron-updater with the GitHub provider in
electron-builder; macOS keeps the matching-architecture ZIP download prompt.
The pinned DSH and bundled plugin update with the application.

About uses an origin-checked Electron bridge for application update status,
manual checks and restart/download actions. It does not reinstall the plugin
inside a packaged application. Official DSH plugin installs keep their existing
update path. Checks share in-flight work and failures remain retryable.

The native delivery routes require DSH's documented workspaceChanges service.
Keep it mounted with a one-second Git command timeout; repair the disabled row
written by earlier ChemClaw profiles. This restores native file actions without
changing DSH or waiting on the default 30-second repository snapshot timeout.

A version tag on main (or a non-dry Release workflow dispatch on main) builds
into a draft release. Publish only after the plugin TGZ, Windows EXE, blockmap
and latest.yml, and both macOS ZIPs have passed checks and been uploaded. A
failed run leaves a draft for retry rather than an empty public release.
Normal CI remains required before merging. npm publishing stays optional through
the existing Trusted Publisher setting.

Both manifests and lockfiles advance to 0.2.1. Older installed builds that do not
initialize an updater need one manual installation before automatic checks work.
