# Desktop browser-runtime failures in ordinary Agent Sessions

## Evidence and scope

Five macOS SIGSEGV reports on 2026-11-16 correlate with shell commands that
started the ChemClaw executable and called private `electron_browser_*`
bindings. Each failed process lived for roughly 50–70 ms. The original app and
Host remained alive. The task was an ordinary DSH Agent Session, had no Bot
owner, and had no browser tools in its actual request header.

The installed 0.3.2 archive predates the merge of ChemClaw #136. Source main
already contains DS-Bot #1005's isolated `browser_exec` implementation, but
that implementation cannot constrain a separate `bash` call. Repeating that
upstream port would leave the observed entry point unchanged.

## Upstream reuse and review

Checked on 2026-11-16: upstream main/dev, the 45 listed repository branches,
the 99 open PRs and focused searches of closed PRs, commits and issues.
Related changes were inspected rather than treating every desktop crash as
the same fault:

- [DS-Bot #1005](https://github.com/Fei2411/DS-Bot/pull/1005): retained through
  ChemClaw #136, including its independent child, timeout and packaged checks.
- [DS-Bot #1037](https://github.com/Fei2411/DS-Bot/pull/1037): ChemClaw already
  ships `playwright-core`; a missing dependency is not this task's failure.
- [fix/984-browser-tools](https://github.com/Fei2411/DS-Bot/tree/fix/984-browser-tools):
  defaults the interactive plugin on in the standalone app. ChemClaw already
  does this for Bots; it does not supply browser tools to ordinary Agents.
- [DS-Bot #1543](https://github.com/Fei2411/DS-Bot/pull/1543), merged into dev:
  accurately describes read-only versus interactive browsing. Reuse that
  capability distinction in runtime guidance, without replacing ChemClaw's
  correct standalone-app defaults with generic upstream settings copy.
- [DS-Bot #1545](https://github.com/Fei2411/DS-Bot/pull/1545) and open
  [#1309](https://github.com/Fei2411/DS-Bot/pull/1309): browser action/download
  lifetimes and cancellation, not shell-launched native bindings.
- Open [DS-Bot #1654](https://github.com/Fei2411/DS-Bot/pull/1654): maintenance
  guides and skill packaging; no matching native-browser crash implementation.
  Do not import its unrelated maintenance framework as a crash fix.

No reviewed upstream implementation specifically blocks the observed
ordinary-Agent shell route. Keep the proven browser stack and add only the
missing desktop boundary through public DSH plugin APIs.

## Behavior

- Register a desktop-only system-prompt section for every Session, including
  ordinary Agents. Explain the actual browser capability boundary, use
  `load_workspace_dependencies` for interpreter paths, and require truthful
  reporting when visual validation is unavailable.
- Before a `bash`/`pwsh` command runs, reject commands that mention the current
  Host executable and explicitly probe private Electron browser bindings or
  `electron/js2c/browser_init`. A JavaScript `catch` cannot catch native SIGSEGV.
- If an indirect invocation of that executable returns a native failure, keep
  the original result and stop further launches of that executable in the same
  Session turn. Other Sessions and commands using ordinary interpreters remain
  available. A fresh turn resets the failure state; late old results cannot
  contaminate it.
- Never log the command, environment or user data in the refusal.
- Retain existing CDP frame guards and browser-safe-mode recovery. No DSH
  patch, tool-scope expansion, user-data migration or automatic update.

This is a guard for the observed failure path, not a shell parser or a sandbox.
A previously written indirect script can still fail once before retry
suppression applies. The guidance and supported browser route remain necessary.

## Verification

- Replay the five captured commands against the middleware without spawning
  the executable; all must be refused before shell execution.
- Test ordinary Agent/Bot prompt coverage, Windows paths, ordinary Node/Python
  and Office calls, per-Session retry handling and turn races.
- Retain the upstream isolation regressions and run repository checks.
- Extend the existing packaged-Electron check: load the guard from the actual
  package, assert ordinary-Agent guidance and refuse a probe without starting
  it. Source tests alone must not be reported as an installed-app fix.
