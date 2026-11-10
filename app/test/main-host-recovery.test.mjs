import assert from 'node:assert/strict'
import { test } from 'node:test'
import { app, state } from './helpers/fake-electron.mjs'
import { state as hostState } from './helpers/fake-host-process.mjs'
import { startApp, waitFor, window } from './helpers/app-harness.mjs'
import { installHooks } from './helpers/register.mjs'

await installHooks()

test('ordinary Host failure restarts only after the user chooses it and the old Host stops', async t => {
  await startApp()
  t.after(() => { app.quit() })
  await waitFor(() => hostState.starts > 0, 'start the fake Host')
  hostState.release()
  await waitFor(() => window()?.loaded.some(url => url.startsWith('http:')), 'load Host UI')
  let answer
  state.dialogAnswer = () => new Promise(resolve => { answer = resolve })
  hostState.failHost(new Error('mock Host crash'))
  await waitFor(() => typeof answer === 'function', 'offer recovery')
  assert.equal(state.relaunches.length, 0)
  answer({ response: 0 })
  await waitFor(() => state.relaunches.length === 1, 'schedule the requested restart')
  assert.equal(hostState.stops, 1)
  assert.equal(state.relaunches[0].args.includes('--chemclaw-browser-safe-mode'), false)
  assert.equal(hostState.starts, 1)
})
