import assert from 'node:assert/strict'
import { test } from 'node:test'
import { desktopBrowserSafeMode, install } from '../src/host/browser-plugins.js'

test('desktop browser safe mode is explicitly scoped to app Host and one launch', () => {
  assert.equal(desktopBrowserSafeMode({ DS_BOT_APP: '1', CHEMCLAW_BROWSER_SAFE_MODE: '1' }), true)
  assert.equal(desktopBrowserSafeMode({ DS_BOT_APP: '1' }), false)
  assert.equal(desktopBrowserSafeMode({ CHEMCLAW_BROWSER_SAFE_MODE: '1' }), false)
  assert.equal(desktopBrowserSafeMode({ DS_BOT_APP: '0', CHEMCLAW_BROWSER_SAFE_MODE: '1' }), false)
})

test('the crashed browser plugin is not mounted in safe mode; other Host startup is unaffected', () => {
  const beforeApp = process.env.DS_BOT_APP
  const beforeSafe = process.env.CHEMCLAW_BROWSER_SAFE_MODE
  try {
    process.env.DS_BOT_APP = '1'
    process.env.CHEMCLAW_BROWSER_SAFE_MODE = '1'
    const warnings = []
    const rt = {
      warn(message) { warnings.push(message) },
      get config() { throw new Error('safe mode must not load the browser configuration') },
      get ctx() { throw new Error('safe mode must not register Playwright tools') },
    }
    assert.equal(install(rt), undefined)
    assert.match(warnings[0], /browser automation is isolated/)
  } finally {
    if (beforeApp === undefined) delete process.env.DS_BOT_APP
    else process.env.DS_BOT_APP = beforeApp
    if (beforeSafe === undefined) delete process.env.CHEMCLAW_BROWSER_SAFE_MODE
    else process.env.CHEMCLAW_BROWSER_SAFE_MODE = beforeSafe
  }
})
