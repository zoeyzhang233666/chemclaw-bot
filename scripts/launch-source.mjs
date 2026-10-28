import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, realpathSync } from 'node:fs'
import { join, resolve } from 'node:path'

export function launchSource(checkout, args = [], env = process.env) {
  const origin = realpathSync(resolve(env.CHEMCLAW_LAUNCH_HOME || checkout))
  const at = args.indexOf('--source')
  if (at >= 0 && (!args[at + 1] || args[at + 1].startsWith('--'))) throw new Error('--source needs a ChemClaw checkout path')
  const file = join(origin, '.chemclaw-dev', 'source.json')
  let selected = checkout
  let config = null
  if (at >= 0) selected = resolve(checkout, args[at + 1])
  else if (!env.CHEMCLAW_LAUNCH_HOME && existsSync(file)) {
    config = JSON.parse(readFileSync(file, 'utf8'))
    if (typeof config.source !== 'string' || !config.source.trim()) throw new Error('The local source selection needs a source path')
    selected = resolve(origin, config.source)
  } else if (existsSync(file)) {
    // Forwarded launches keep origin data root but may still want profile/manifest metadata.
    try { config = JSON.parse(readFileSync(file, 'utf8')) } catch { config = null }
  }
  const source = realpathSync(selected)
  for (const [folder, name] of [['app', 'chemclaw'], ['chemclaw-bot', 'chemclaw-bot']]) {
    const manifest = JSON.parse(readFileSync(join(source, folder, 'package.json'), 'utf8'))
    if (manifest.name !== name) throw new Error('The selected folder is not a ChemClaw source checkout')
  }
  if (!existsSync(join(source, 'scripts', 'launch-chemclaw.mjs'))) throw new Error('The selected source has no ChemClaw launcher')
  const forwarded = args.filter((_, index) => at < 0 || (index !== at && index !== at + 1))
  const selection = config?.selection || null
  const manifest = config?.manifest
    || (selection?.kind === 'integration' ? readPreviewManifest(origin) : null)
  return {
    source,
    origin,
    args: forwarded,
    profile: config?.profile || null,
    selection,
    remoteConfirmed: config?.remoteConfirmed,
    manifest,
  }
}

function readPreviewManifest(origin) {
  const file = join(origin, '.chemclaw-dev', 'preview-manifest.json')
  try {
    if (!existsSync(file)) return null
    return JSON.parse(readFileSync(file, 'utf8'))
  } catch {
    return null
  }
}

export function sourceRevision(source) {
  try {
    const git = (...args) => execFileSync('git', ['-C', source, ...args], { encoding: 'utf8', windowsHide: true, stdio: ['ignore', 'pipe', 'ignore'] }).trim()
    return {
      branch: git('branch', '--show-current') || 'detached',
      revision: git('rev-parse', '--short=8', 'HEAD'),
      fullRevision: git('rev-parse', 'HEAD'),
      modified: git('status', '--porcelain', '--untracked-files=no') !== '',
    }
  } catch {
    return { branch: 'source', revision: 'unversioned', fullRevision: 'unversioned', modified: false }
  }
}
