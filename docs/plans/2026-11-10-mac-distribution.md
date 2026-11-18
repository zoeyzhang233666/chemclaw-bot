# macOS installation with ad-hoc signing

The maintainer requests a conventional Finder drag-to-Applications window and
confirms that no paid Apple Developer account or Developer ID certificate is
available. Keep ad-hoc signing. Do not make a paid account or notarization a
requirement for this iteration, change the version to a release decision, disable
Gatekeeper, or remove quarantine attributes on a user's behalf.

Both the v0.3.0 release configuration at
`c5c81d72a17dc4073a43e6fbc93c06412527c21c` and the tested
`0.3.1-audit.20261110` ARM64 candidate use `identity: '-'` and
`hardenedRuntime: false`, without Developer ID signing or notarization. The
macOS 15.5 screenshot reports Apple's inability to verify the app, before
ChemClaw starts. It does not itself establish malware or a corrupt bundle.
The reason the earlier copy did not show the prompt is unverified. Quarantine,
download route and earlier local approvals are possible differences.

Ad-hoc code-signature integrity verification does not establish Gatekeeper
acceptance. The previous cloud runs verified integrity and native behavior but
did not verify a browser-downloaded, quarantined first launch on a clean Mac.
The current installer therefore cannot be described as warning-free. Apple's
supported direct-download trust route is Developer ID signing and notarization:
https://developer.apple.com/developer-id/ . This remains optional future work
under the maintainer's present constraint.

## Installation change

`electron-builder.mac-dmg.yml` began as an opt-in installation preview. It builds a
Finder window containing ChemClaw.app on the left and an Applications link on
the right. It retains the ZIP for compatibility, the existing app identifier,
data locations and ad-hoc signing. It explicitly disables notarization and
publishing. It does not claim to remove the system prompt.

The initial decision kept default packaging and formal releases ZIP-based until
native checks and maintainer acceptance. The promotion below supersedes that
release decision. The earlier desktop design
records Safari-downloaded unsigned DMGs being rejected as damaged on macOS 26
(#351). Creating or mounting a DMG in CI alone cannot close that issue.

Before DSH starts, an app launched outside Applications now only explains how
to quit and drag the app in Finder, then quits. It does not move, overwrite or
relaunch itself. This supersedes the automatic move flow in the earlier
2026-11-10 app-path note. The live-move guard remains active. Development and
isolated synthetic-profile runs retain their installation bypass.

The Mac release-page update checker recognizes a matching-architecture DMG or
ZIP, while preserving the custom asset check used by Linux. Update instructions
require quitting before replacement. Older installed versions still recognize
the retained ZIP.

## Acceptance and scope

Local tests may use mock Electron and synthetic files only within the approved
audit scratch root. No real application installation or user data access.
This document does not itself authorize commits, uploads, PRs, merges or releases;
the maintainer subsequently authorized them in the release conversation.

Native checks still required:

- Build on ARM64 macOS; mount in a temporary location; inspect ChemClaw.app,
  Applications link, Finder layout and signature integrity; eject in finally.
- Start an isolated copy with the mock model and check HTML, Office and reopening.
- Test a browser-downloaded DMG and ZIP on macOS 15.5 and macOS 26, with their
  quarantine metadata intact and without prior local approvals. Record separately
  whether mounting succeeds, what Gatekeeper displays, and whether Apple's
  per-app approval permits subsequent launches.
- Test the actual Finder drag into Applications, replacing only a fully exited
  synthetic test copy; verify Launchpad and saved synthetic conversations.
  Installation into Applications needs separate native-test authorization.

Do not count mocked schema/startup tests or CI mounting as a Gatekeeper pass.
The release target remains v0.3.1. This change does not bump or publish a version.

## Promotion to formal distribution (2026-11-10)

After native preview checks and the maintainer's macOS 15.5 acceptance of
`0.3.1-audit.20261110.2`, the maintainer reported that the formal ZIP still showed
only the application's text installation fallback (#118). Formal Mac releases
now provide the accepted Finder DMG layout alongside the ZIP. The completion
gate requires both architectures and both formats (eleven release assets).
The fallback remains useful when someone directly opens an uninstalled app.

For the already published v0.3.1, a separate workflow downloads each existing
release ZIP, verifies its GitHub SHA-256, signature, architecture, version and
critical source files against the immutable release tag, then wraps that exact
app in a DMG. A native read-only mount checks the Finder layout and compares
all app file contents and symlink targets with the extracted ZIP. Only these
two new assets and installation notes may be added; the nine original assets
and tag must stay unchanged. Branch pushes only build and record evidence;
publication requires an explicit dispatch from main.

These packaging checks do not establish a warning-free first download on
macOS 15.5 or macOS 26. Ad-hoc signing and the remaining native acceptance
limitations above still apply. No user application or data is used by the
supplemental workflow.
