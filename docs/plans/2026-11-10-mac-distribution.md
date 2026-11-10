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

`electron-builder.mac-dmg.yml` is an opt-in installation preview. It builds a
Finder window containing ChemClaw.app on the left and an Applications link on
the right. It retains the ZIP for compatibility, the existing app identifier,
data locations and ad-hoc signing. It explicitly disables notarization and
publishing. It does not claim to remove the system prompt.

The default packaging and formal release workflow remain ZIP-based until the
preview passes native checks. This matters because the earlier desktop design
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
No new commit, upload, PR, merge, release or tag is authorized by this document.

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
