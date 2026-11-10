import assert from 'node:assert/strict'
import { test } from 'node:test'
import { MAC_INSTALL_TEXT, prepareMacInstall } from '../src/mac-install.mjs'

function fixture({ response = 0, installed = false, moved = true, conflict, error } = {}) {
  const calls = { dialogs: [], moves: 0, quits: 0 }
  const app = {
    isPackaged: true,
    isInApplicationsFolder: () => installed,
    moveToApplicationsFolder: options => {
      calls.moves += 1
      if (conflict) { calls.conflictAllowed = options.conflictHandler(conflict); return calls.conflictAllowed }
      if (error) throw error
      return moved
    },
    quit: () => { calls.quits += 1 },
  }
  const dialog = { showMessageBox: async options => { calls.dialogs.push(options); return { response } } }
  const prepare = options => prepareMacInstall({ app, dialog, platform: 'darwin', isolated: false, messages: MAC_INSTALL_TEXT.en, ...options })
  return { app, calls, prepare }
}

test('installed Mac apps start without a move or prompt', async () => {
  const f = fixture({ installed: true })
  assert.equal(await f.prepare(), true)
  assert.equal(f.calls.moves, 0)
  assert.deepEqual(f.calls.dialogs, [])
})

test('successful installation leaves startup to the native relaunch', async () => {
  const f = fixture()
  assert.equal(await f.prepare(), false)
  assert.equal(f.calls.moves, 1)
  assert.equal(f.calls.dialogs.length, 1)
})

test('cancelling installation quits without moving or starting the team', async () => {
  const f = fixture({ response: 1 })
  assert.equal(await f.prepare(), false)
  assert.equal(f.calls.moves, 0)
  assert.equal(f.calls.quits, 1)
})

for (const conflict of ['exists', 'existsAndRunning']) {
  test(`installation refuses to replace an app when ${conflict}`, async () => {
    const f = fixture({ conflict })
    assert.equal(await f.prepare(), false)
    assert.equal(f.calls.conflictAllowed, false)
    assert.equal(f.calls.quits, 1)
    assert.equal(f.calls.dialogs.at(-1).message, MAC_INSTALL_TEXT.en.conflict)
  })
}

for (const failure of [{ moved: false }, { error: new Error('mock move failure') }]) {
  test(`failed installation quits without starting DSH (${failure.error ? 'throw' : 'cancel'})`, async () => {
    const f = fixture(failure)
    assert.equal(await f.prepare(), false)
    assert.equal(f.calls.quits, 1)
    assert.equal(f.calls.dialogs.at(-1).message, MAC_INSTALL_TEXT.en.failed)
  })
}

test('Windows, development and isolated runs never invoke the Mac move API', async () => {
  for (const options of [{ platform: 'win32' }, { isolated: true }, { development: true }]) {
    const f = fixture()
    if (options.development) f.app.isPackaged = false
    assert.equal(await f.prepare(options), true)
    assert.equal(f.calls.moves, 0)
    assert.deepEqual(f.calls.dialogs, [])
  }
})
