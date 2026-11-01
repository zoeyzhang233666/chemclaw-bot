// This runs in the Electron parent BEFORE starting the DSH Host. On some
// Windows D: workspaces inherited Authenticated Users:Modify is not sufficient
// for the DSH workspace-write grantWrite security descriptor operation.
// Scope the optional one-time WRITE_OWNER ACL grant strictly to ChemClaw-owned
// source-preview profiles. Never change arbitrary user paths or production EXEs.
import { spawnSync } from 'node:child_process'
import { existsSync, lstatSync, realpathSync } from 'node:fs'
import { join, resolve, sep } from 'node:path'

const low = p => resolve(p).replace(/[\\/]+$/, '').toLowerCase()

export function isManagedPreviewWorkspace({ workspace, env = process.env, platform = process.platform } = {}) {
  if (platform !== 'win32' || !workspace) return null
  const { CHEMCLAW_LAUNCH_HOME: origin, CHEMCLAW_PROFILE_KEY: profile } = env
  if (!origin || !/^(?:pr-\d+|integration|worktree-[\w.-]+)$/.test(profile || '')) return null
  const parent = resolve(origin, '.chemclaw-workspace-profiles')
  const expected = join(parent, profile)
  if (low(workspace) !== low(expected)) return null
  try {
    for (const path of [parent, expected]) {
      const stat = lstatSync(path)
      if (!stat.isDirectory() || stat.isSymbolicLink()) return null
      if (low(realpathSync(path)) !== low(path)) return null
    }
  } catch { return null }
  return expected
}

export function preparePreviewSandboxAcl({ workspace, env = process.env, platform = process.platform, run = spawnSync } = {}) {
  const target = isManagedPreviewWorkspace({ workspace, env, platform })
  if (!target) return { status: 'skipped' }
  const { USERDOMAIN: domain, USERNAME: user } = env
  if (!domain || !user || /[:\r\n]/.test(domain) || /[:\r\n]/.test(user)) return { status: 'error', message: 'Cannot determine current Windows user' }
  const account = [domain, user].join(String.fromCharCode(92))
  const exe = join(env.SystemRoot || 'C:\\Windows', 'System32', 'icacls.exe')
  if (run === spawnSync && !existsSync(exe)) return { status: 'error', message: 'Windows icacls.exe is missing' }
  const opts = { encoding: 'utf8', windowsHide: true, timeout: 8000 }
  try {
    const read = run(exe, [target], opts)
    if (read.status !== 0) return { status: 'error', message: 'Cannot read preview workspace ACL' }
    const principal = account.toLowerCase() + ':'
    const hasWO = String(read.stdout || '').split(/\r?\n/).some(line => {
      const norm = line.toLowerCase()
      return norm.includes(principal) && !norm.includes('(deny)') && /\((?:WO|F)\)/i.test(line)
    })
    if (hasWO) return { status: 'ready' }
    // No /T (recursive), no Full Control, no admin privilege, no sandbox change.
    const grant = run(exe, [target, '/grant', account + ':(WO)'], opts)
    if (grant.status !== 0) return { status: 'error', message: 'Failed granting current user WRITE_OWNER on preview workspace' }
    // Read back and verify rather than claiming success based on icacls exit code.
    const check = run(exe, [target], opts)
    if (check.status !== 0) return { status: 'error', message: 'Could not verify the updated preview ACL' }
    const verified = String(check.stdout || '').split(/\r?\n/).some(line =>
      line.toLowerCase().includes(principal) && /\((?:WO|F)\)/i.test(line) && !/\(DENY\)/i.test(line))
    return verified ? { status: 'granted' } : { status: 'error', message: 'WRITE_OWNER was not visible on ACL re-read' }
  } catch (error) { return { status: 'error', message: String(error.message || error) } }
}
