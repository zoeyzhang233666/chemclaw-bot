import assert from 'node:assert/strict'
import { test } from 'node:test'
import { MAC_INSTALL_TEXT, prepareMacInstall } from '../src/mac-install.mjs'

function fixture({ installed = false, answer = async () => ({ response: 0 }) } = {}) {
  const calls = { dialogs: [], moves: 0, quits: 0 }
  const app = {
    isPackaged: true,
    isInApplicationsFolder: () => installed,
    moveToApplicationsFolder: () => { calls.moves += 1; throw new Error('A running app must not move itself') },
    quit: () => { calls.quits += 1 },
  }
  const dialog = { showMessageBox: options => { calls.dialogs.push(options); return answer() } }
  const prepare = options => prepareMacInstall({ app, dialog, platform: 'darwin', isolated: false, messages: MAC_INSTALL_TEXT.en, ...options })
  return { app, calls, prepare }
}

test('installed Mac apps proceed without a prompt', async () => {
  const f = fixture({ installed: true })
  assert.equal(await f.prepare(), true)
  assert.deepEqual(f.calls, { dialogs: [], moves: 0, quits: 0 })
})

test('opening an app outside Applications quits before team startup and never moves or replaces it', async () => {
  const f = fixture()
  assert.equal(await f.prepare(), false)
  assert.equal(f.calls.moves, 0)
  assert.equal(f.calls.quits, 1)
  assert.equal(f.calls.dialogs.length, 1)
  assert.deepEqual(f.calls.dialogs[0].buttons, ['Quit'])
})

test('startup waits for the installation instruction to close', async () => {
  let close
  const f = fixture({ answer: () => new Promise(done => { close = done }) })
  let completed = false
  const pending = f.prepare().then(result => { completed = true; return result })
  await Promise.resolve()
  assert.equal(completed, false)
  assert.equal(f.calls.quits, 0)
  close({ response: 0 })
  assert.equal(await pending, false)
  assert.equal(f.calls.quits, 1)
})

test('a failed native dialog still quits without a move or relaunch', async () => {
  const f = fixture({ answer: async () => { throw new Error('mock dialog failure') } })
  await assert.rejects(f.prepare(), /mock dialog failure/u)
  assert.equal(f.calls.quits, 1)
  assert.equal(f.calls.moves, 0)
})

test('Windows, Linux, development and isolated runs bypass installation', async () => {
  for (const options of [{ platform: 'win32' }, { platform: 'linux' }, { isolated: true }, { development: true }]) {
    const f = fixture()
    if (options.development) f.app.isPackaged = false
    assert.equal(await f.prepare(options), true)
    assert.deepEqual(f.calls, { dialogs: [], moves: 0, quits: 0 })
  }
})
