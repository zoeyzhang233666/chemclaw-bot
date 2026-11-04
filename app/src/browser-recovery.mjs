// An Electron desktop Host can be restarted without its browser automation
// after a known Playwright frame assertion. This is a one-run fallback, never
// a blanket uncaughtException handler: other Host failures still surface normally.
export const BROWSER_SAFE_ARG = '--chemclaw-browser-safe-mode'

export const browserSafeMode = (argv = process.argv) => argv.includes(BROWSER_SAFE_ARG)

export function browserFrameAssertion(error) {
  const detail = String(error?.stack ?? error?.message ?? error ?? '')
  return /Assertion error/u.test(detail) && /FrameManager\.frameAttached/u.test(detail)
}

export function browserRecoveryArgs(argv) {
  return argv.includes(BROWSER_SAFE_ARG) ? [...argv] : [...argv, BROWSER_SAFE_ARG]
}
