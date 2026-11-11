# ChemClaw macOS: Gatekeeper warning and official distribution

## Why the current test DMG is blocked

The current desktop release configuration intentionally uses ad-hoc code signing
(`mac.identity: '-'`, `mac.hardenedRuntime: false`) and its DMG config disables
notarization (`mac.notarize: false`). This preserves a testable macOS artifact
without an Apple Developer membership, but **does not establish a verified
developer identity** for downloaded apps. Finder DMG art and code-signature
integrity checks do not replace Gatekeeper acceptance.

This is a **distribution-credential limitation**, not a reason to disable macOS
security or remove the app's quarantine attribute for ordinary users.

## Requirements to remove the warning for public distribution

1. Enroll in the paid Apple Developer Program. A regular free Apple Account is
   not sufficient for Developer ID distribution. The current program fee is
   US$99/year (regional pricing may differ).
2. Obtain the **Developer ID Application** certificate for the owning
   individual/organization and securely export it to a password-protected
   `.p12`. Do not commit it to Git.
3. Configure macOS release signing with a trusted Developer ID identity
   (instead of `identity: '-'`) and enable Hardened Runtime. Verify all bundled
   executable and native modules work with the selected entitlements.
4. Enable notarization for the *release* build (remove `notarize: false` from
   `app/electron-builder.mac-dmg.yml`, and configure `notarize: true`).
   Provide authentication to Apple's notarization service via CI secrets.
5. Build and sign the app, submit to Apple for notarization, and staple the
   notarization ticket to the distributed app/DMG as appropriate. Do not
   release an unsigned fallback if authentication or notarization fails.
6. Verify the downloaded artifact **with quarantine on** on a clean Mac,
   including its real first-launch Gatekeeper behavior. A GitHub Actions
   `codesign --verify` passing alone does not establish Gatekeeper acceptance.

### Example private CI environment variables

- `CSC_LINK` (Developer ID Application `.p12` encoded securely)
- `CSC_KEY_PASSWORD`
- Either `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`,
  or `APPLE_API_KEY` (App Store Connect private `.p8`), `APPLE_API_KEY_ID`,
  and `APPLE_API_ISSUER`

All values must be stored in **GitHub Actions Secrets** and wired only into the
macOS release build. Never put certificate/password/key material in source,
a PR description, a workflow log, or an uploaded diagnostic artifact.

### Verification commands on macOS

```bash
codesign --verify --deep --strict --verbose=2 "/Applications/ChemClaw.app"
codesign -dv --verbose=4 "/Applications/ChemClaw.app"
spctl --assess --type execute --verbose=4 "/Applications/ChemClaw.app"
xcrun stapler validate "/Applications/ChemClaw.app"
```

The desired Gatekeeper assessment reports accepted / Notarized Developer ID.
Also check the delivered DMG when using a stapled disk image.

### For internal testing before enrollment

If the user **knows and trusts** the build's source and checksum, use macOS
System Settings → Privacy & Security → Open Anyway after the first block,
following the macOS prompts. This is temporary testing guidance, not a safe
general-purpose replacement for proper signing. Do **not** disable Gatekeeper
globally or instruct users to strip quarantine broadly.

References:
- https://developer.apple.com/developer-id/
- https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
- https://www.electron.build/v26/docs/features/code-signing/notarization/
