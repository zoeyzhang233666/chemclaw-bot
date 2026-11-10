import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { test } from 'node:test'
import { app, state } from './helpers/fake-electron.mjs'
import { state as host } from './helpers/fake-host-process.mjs'
import { startApp, waitFor } from './helpers/app-harness.mjs'
import { installHooks } from './helpers/register.mjs'

await installHooks()
registerHooks({
  resolve(specifier, context, next) {
    if (specifier === './mac-install.mjs' && context.parentURL?.endsWith('/src/main.mjs')) {
      return { url: new URL('./helpers/mac-install-outside.mjs', import.meta.url).href, shortCircuit: true }
    }
    return next(specifier, context)
  },
})

test('a Mac app opened before installation never starts DSH or creates its main window', async t => {
  t.after(() => { app.quit() })
  let close
  state.dialogAnswer = () => new Promise(done => { close = done })
  await startApp()
  await waitFor(() => typeof close === 'function', 'show the installation instruction')
  assert.equal(host.starts, 0)
  assert.equal(state.windows.length, 0)
  close({ response: 0 })
  await waitFor(() => state.quits > 0, 'quit before installation')
  assert.equal(host.starts, 0)
  assert.equal(state.windows.length, 0)
  assert.equal(state.relaunches.length, 0)
})
