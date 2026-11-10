# Mac application installation and live moves

The v0.3.1 release target keeps the existing ZIP distribution and separate data
folder. Two isolated runs of the original v0.3.0 ARM64 ZIP reproduced the user's
main-process SIGTRAP after moving the running bundle and creating a browser view.
The matching Electron UUID and first four frame offsets identify the Helper path
CHECK in ElectronBrowserClient::AppendExtraCommandLineSwitches. Position-stable
and quit-before-move controls passed on macOS 15.8.2; exact macOS 15.5 remains
unverified. See the isolated audit evidence; these are not DSH process crashes.

Before starting DSH, a packaged Mac app outside Applications offers the official
moveToApplicationsFolder flow. Successful moves quit/relaunch; failure, cancellation
and conflicts do not start a team. The conflict handler always refuses replacement.
Development and explicitly isolated DS_BOT_HOME runs skip installation, so tests
never install into the runner's or the user's Applications directory.

A separate guard remains active for packaged Mac apps, including isolated runs.
It remembers the executable and bundle's real paths and file identities, checks
before native browser creation/navigation and CDP commands, cancels renderer-driven
frame navigation/webview attachment when unavailable, and polls while idle. Failure
latches once: stop new operations, stop DSH through its existing shutdown path,
show a native reopen instruction and quit. Do not relaunch a stale executable path
or replay interrupted tasks. No data migration, cleanup, DSH patch or Electron
patch is involved. Windows and development runs retain their existing behavior.

These are application-level protections. A concurrent filesystem change after a
check can still race native code; navigation events do not cover every programmatic
load. Unit tests cannot close the original native crash. A new Mac candidate must
repeat all three native cases, including an immediate create after moving, HTML
iframe navigation, CDP navigation, idle detection and synthetic history reopening.
The guard must keep working when DS_BOT_HOME is set. No formal release or product
source upload is authorized by the earlier test-only cloud workflow approval.
