// DSH's Win32 workspace-write sandbox requires WRITE_OWNER even when inherited
// Authenticated Users:Modify already grants ordinary file writes.
// Never change permissions outside ChemClaw-owned preview workspaces.
import { spawnSync } from 'node:child_process'
import { existsSync, lstatSync, realpathSync } from 'node:fs'
import { join, resolve } from 'node:path'

export function managedPreviewWorkspace(env = process.env, platform = process.platform) {
  if (platform !== 'win32') return null
  const { CHEMCLAW_LAUNCH_HOME: origin, CHEMCLAW_PROFILE_KEY: profile, DS_BOT_WORKSPACE: workspace } = env
  if (!origin || !workspace || !/^(?:pr-\d+|integration|worktree-[\w.-]+)$/.test(profile || '')) return null
  const parent = resolve(origin, '.chemclaw-workspace-profiles')
  const expected = join(parent, profile)
  if (resolve(workspace).toLowerCase() !== expected.toLowerCase()) return null
  try {
    // Reject symlink/junction escapes. Never recurse through workspace files.
    if (!lstatSync(parent).isDirectory() || lstatSync(parent).isSymbolicLink()) return null
    if (!lstatSync(workspace).isDirectory() || lstatSync(workspace).isSymbolicLink()) return null
    if (realpathSync(parent).toLowerCase() !== parent.toLowerCase()) return null
    if (realpathSync(workspace).toLowerCase() !== expected.toLowerCase()) return null
  } catch { return null }
  return expected
}

export function ensurePreviewWorkspaceAcl({ env = process.env, platform = process.platform, run = spawnSync } = {}) {
  const workspace = managedPreviewWorkspace(env, platform)
  if (!workspace) return { status: 'skipped' }
  const { USERDOMAIN: domain, USERNAME: user } = env
  if (!domain || !user || /[:\r\n]/.test(domain) || /[:\r\n]/.test(user)) return { status: 'skipped' }
  const account = [domain, user].join(String.fromCharCode(92))
  const exe = join(env.SystemRoot || 'C:\\Windows', 'System32', 'icacls.exe')
  if (run === spawnSync && !existsSync(exe)) return { status: 'error', message: 'Windows icacls.exe not found' }
  const options = { encoding: 'utf8', windowsHide: true, timeout: 8000 }
  try {
    const read = run(exe, [workspace], options)
    if (read.status !== 0) return { status: 'error', message: 'Cannot inspect workspace ACL' }
    const prefix = account.toLowerCase() + ':'
    const granted = String(read.stdout || '').split(/\r?\n/).some(line =>
      line.toLowerCase().includes(prefix) && /\((?:WO|F)\)/.test(line) && !/\(DENY\)/i.test(line))
    if (granted) return { status: 'ready' }
    // Only grant WRITE_OWNER to the invoking user on the exact preview root.
    // No FullControl, recursive rewrite, administrative privileges or sandbox bypass.
    const write = run(exe, [workspace, '/grant', account + ':(OI)(CI)(WO)'], options)
    if (write.status !== 0) return { status: 'error', message: 'Could not grant WRITE_OWNER to current user' }
    return { status: 'granted' }
  } catch (error) { return { status: 'error', message: String(error.message || error) } }
}
