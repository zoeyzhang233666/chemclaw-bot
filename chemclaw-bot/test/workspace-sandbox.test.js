import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { managedPreviewWorkspace, ensurePreviewWorkspaceAcl } from '../src/host/workspace-sandbox.js'

function fixture(t) {
  const origin = mkdtempSync(join(tmpdir(), 'chemclaw-acl-'))
  t.after(() => rmSync(origin, { recursive: true, force: true }))
  const workspace = join(origin, '.chemclaw-workspace-profiles', 'pr-93')
  mkdirSync(workspace, { recursive: true })
  return { origin, workspace, env: {
    CHEMCLAW_LAUNCH_HOME: origin, DS_BOT_WORKSPACE: workspace, CHEMCLAW_PROFILE_KEY: 'pr-93',
    USERDOMAIN: 'TESTPC', USERNAME: 'EDY',
  } }
}
test('ACL bootstrap scopes only to exactly managed preview directories', t => {
  const { origin, workspace, env } = fixture(t)
  assert.equal(managedPreviewWorkspace(env, 'win32'), workspace)
  assert.equal(managedPreviewWorkspace(env, 'linux'), null)
  assert.equal(managedPreviewWorkspace({ ...env, DS_BOT_WORKSPACE: origin }, 'win32'), null)
  assert.equal(managedPreviewWorkspace({ ...env, CHEMCLAW_PROFILE_KEY: 'baseline' }, 'win32'), null)
})
test('ACL bootstrap grants only WRITE_OWNER on preview root', t => {
  const { workspace, env } = fixture(t)
  const calls = []
  const run = (exe, args) => { calls.push(args); return { status: 0, stdout: 'Authenticated Users:(I)(M)' } }
  assert.equal(ensurePreviewWorkspaceAcl({ env, platform: 'win32', run }).status, 'granted')
  assert.deepEqual(calls, [[workspace], [workspace, '/grant', ['TESTPC', 'EDY'].join(String.fromCharCode(92)) + ':(OI)(CI)(WO)']])
})
test('ACL bootstrap does not rewrite already provisioned directories', t => {
  const { env } = fixture(t)
  let calls = 0
  const run = () => {
    calls++
    return { status: 0, stdout: ['TESTPC', 'EDY'].join(String.fromCharCode(92)) + ':(OI)(CI)(WO)' }
  }
  assert.equal(ensurePreviewWorkspaceAcl({ env, platform: 'win32', run }).status, 'ready')
  assert.equal(calls, 1)
})
test('ACL bootstrap fails closed instead of disabling sandbox', t => {
  const { env } = fixture(t)
  assert.equal(ensurePreviewWorkspaceAcl({ env, platform: 'win32', run: () => ({ status: 5 }) }).status, 'error')
})
