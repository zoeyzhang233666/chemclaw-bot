import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, rmSync, symlinkSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { isManagedPreviewWorkspace, preparePreviewSandboxAcl } from '../src/preview-sandbox-acl.mjs'

function fixture(t) {
  const origin = mkdtempSync(join(tmpdir(), 'chemclaw-windows-sandbox-'))
  t.after(() => rmSync(origin, { recursive: true, force: true }))
  const workspace = join(origin, '.chemclaw-workspace-profiles', 'pr-93')
  mkdirSync(workspace, { recursive: true })
  const env = {
    CHEMCLAW_LAUNCH_HOME: origin, CHEMCLAW_PROFILE_KEY: 'pr-93',
    USERDOMAIN: 'TESTPC', USERNAME: 'EDY',
  }
  return { origin, workspace, env }
}
test('Windows preview ACL bootstrap only recognizes exact managed workspace roots', t => {
  const { origin, workspace, env } = fixture(t)
  assert.equal(isManagedPreviewWorkspace({ workspace, env, platform: 'win32' }), workspace)
  assert.equal(isManagedPreviewWorkspace({ workspace, env, platform: 'linux' }), null)
  assert.equal(isManagedPreviewWorkspace({ workspace: origin, env, platform: 'win32' }), null)
  assert.equal(isManagedPreviewWorkspace({ workspace, env: { ...env, CHEMCLAW_PROFILE_KEY: 'baseline' }, platform: 'win32' }), null)
  assert.equal(isManagedPreviewWorkspace({ workspace, env: { ...env, CHEMCLAW_PROFILE_KEY: '../outside' }, platform: 'win32' }), null)
})
test('Windows preview ACL bootstrap grants only WRITE_OWNER and verifies it', t => {
  const { workspace, env } = fixture(t)
  const args = []
  const principal = ['TESTPC', 'EDY'].join(String.fromCharCode(92))
  const run = (exe, argv) => {
    args.push(argv)
    return argv.length === 1
      ? { status: 0, stdout: args.length > 2 ? workspace + ' ' + principal + ':(WO)' : workspace + ' BUILTIN\\Users:(RX)' }
      : { status: 0 }
  }
  assert.equal(preparePreviewSandboxAcl({ workspace, env, platform: 'win32', run }).status, 'granted')
  assert.deepEqual(args, [[workspace], [workspace, '/grant', principal + ':(WO)'], [workspace]])
})
test('Windows preview ACL bootstrap is idempotent on an already prepared workspace', t => {
  const { workspace, env } = fixture(t)
  const principal = ['TESTPC', 'EDY'].join(String.fromCharCode(92))
  let checks = 0
  const run = () => { checks++; return { status: 0, stdout: workspace + ' ' + principal + ':(F)' } }
  assert.equal(preparePreviewSandboxAcl({ workspace, env, platform: 'win32', run }).status, 'ready')
  assert.equal(checks, 1)
})
test('ACL read failure never falls back to danger-full-access or elevated permissions', t => {
  const { workspace, env } = fixture(t)
  assert.equal(preparePreviewSandboxAcl({ workspace, env, platform: 'win32', run: () => ({ status: 5 }) }).status, 'error')
})
test('symlinked workspace cannot redirect changes outside managed folder', t => {
  const { origin, env } = fixture(t)
  const outside = join(origin, 'outside')
  mkdirSync(outside)
  const trap = join(origin, '.chemclaw-workspace-profiles', 'pr-94')
  try { symlinkSync(outside, trap, 'dir') } catch { t.skip('Symlink creation restricted'); return }
  assert.equal(isManagedPreviewWorkspace({ workspace: trap, env: { ...env, CHEMCLAW_PROFILE_KEY: 'pr-94' }, platform: 'win32' }), null)
})
