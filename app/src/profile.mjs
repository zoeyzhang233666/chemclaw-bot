// The app's own DSH profile: its name, its bundles and its installation.
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { initProfile, loadProfileDirectory, readProfileManifest, resolveProfileDir, writeProfileBundles } from '@deepseek-ai/dsh-app-boot'

export const PROFILE = 'chemclaw'
// DSH's shared core, DSH's web front end (the window), then the Bot team. Bundles the user installs follow.
export const BUNDLES = ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', 'chemclaw-bot']
// The first-run check reads a copy of the team's chats without the Bot team running on them.
// DSH reads a log the same way whatever the profile mounts.
export const CHECK_PROFILE = 'import-check'
export const CHECK_BUNDLES = ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app']
// Bundles that earlier builds of the app put in its profile: the engine layer of its own window (../engine).
const RETIRED_BUNDLES = ['deepseek-bot-engine', 'ds-bot']
// The app's own manifest is the installation: DSH imports plugins only from the installation's dependency
// graph, resolves bundles there first, and keeps the bundles it names as direct dependencies from removal.
export const INSTALL_ANCHOR = fileURLToPath(new URL('../package.json', import.meta.url))

// GenUI is an optional visual enhancement: a partial local install must never
// prevent the original ChemClaw chat and show_view charts from booting.
const GENUI_RECOVERY = '# ChemClaw managed optional GenUI recovery'
const GENUI_RECOVERY_END = '# End ChemClaw managed optional GenUI recovery'
const GENUI_RECOVERY_BLOCK = `${GENUI_RECOVERY}\n- id: genui\n  disabled: true\n${GENUI_RECOVERY_END}\n`

export function ensureOptionalGenuiRecovery(dir, installed = existsSync(join(dirname(INSTALL_ANCHOR), 'node_modules', '@changfenhuang', 'dsh-genui', 'package.json'))) {
  const file = join(dir, 'cordis.patch.yml')
  const original = readFileSync(file, 'utf8')
  const start = original.indexOf(GENUI_RECOVERY)
  let content = original
  if (start >= 0) {
    const end = original.indexOf(GENUI_RECOVERY_END, start)
    if (end < 0) throw new Error('Incomplete ChemClaw managed GenUI recovery marker; preserving profile settings.')
    const after = end + GENUI_RECOVERY_END.length
    content = original.slice(0, start) + original.slice(after).replace(/^\r?\n/u, '')
  }
  if (!installed) {
    console.warn('ChemClaw: optional GenUI dependency is unavailable; the original chat and charts remain enabled. Reinstall app dependencies to restore GenUI.')
    content = `${content.replace(/\s*$/u, '')}\n\n${GENUI_RECOVERY_BLOCK}`
  }
  if (content !== original) writeFileSync(file, content)
}

// Skip DeepSeek Harness first-run onboarding / credit screens inside ChemClaw.
const ACCOUNT_DONE_PATCH = `- id: ui-settings-account
  name: "@deepseek-ai/dsh-client-ui-settings-account"
  config:
    version: 1
    step: done
    purpose: office
    process: compact
    completion: completed
    usage: compact
    developerTools: true
`

/**
 * Put the app's bundles at the head of a profile's bundle list and keep the user's after them.
 * initProfile writes the list only into a new profile, so a profile from an earlier build keeps its old list.
 * @param {string} dir - the profile directory
 */
export function claimBundles(dir) {
  const manifest = readProfileManifest('dsh', dir)
  const listed = manifest.dsh?.profile?.bundles ?? []
  const bundles = [...BUNDLES, ...listed.filter((name) => !BUNDLES.includes(name) && !RETIRED_BUNDLES.includes(name))]
  if (bundles.join('\n') !== listed.join('\n')) writeProfileBundles(dir, manifest, bundles)
}

/** Ensure the ChemClaw profile skips DeepSeek account onboarding. */
export function ensureChemClawShellPatch(dir) {
  const file = join(dir, 'cordis.patch.yml')
  const previous = existsSync(file) ? readFileSync(file, 'utf8') : ''
  if (previous.includes('step: done') && previous.includes('ui-settings-account')) return
  if (previous.includes('id: ui-settings-account')) {
    // Replace an incomplete account row rather than duplicating it.
    const next = previous.replace(
      /- id: ui-settings-account\n(?:  .*\n)*/u,
      `${ACCOUNT_DONE_PATCH}\n`,
    )
    if (next !== previous) writeFileSync(file, next.endsWith('\n') ? next : `${next}\n`)
    return
  }
  // initProfile seeds comments + `[]`. Replace the empty array; do not append after it.
  let body
  if (/(^|\n)\[\s*\]\s*$/u.test(previous) || previous.trim() === '' || previous.trim() === '[]') {
    body = previous.replace(/(^|\n)\[\s*\]\s*$/u, `$1${ACCOUNT_DONE_PATCH.trimEnd()}\n`)
    if (body === previous) body = ACCOUNT_DONE_PATCH
  } else {
    body = `${previous.replace(/\s*$/u, '')}\n\n${ACCOUNT_DONE_PATCH}`
  }
  writeFileSync(file, body.endsWith('\n') ? body : `${body}\n`)
}

/**
 * Create or update the profile under the current DSH_HOME and load it.
 * @returns {import('@deepseek-ai/dsh-app-boot').Profile} the loaded profile
 * @throws when one of the app's own bundles does not load
 */
export function loadAppProfile() {
  const dir = resolveProfileDir(PROFILE)
  initProfile(dir, BUNDLES)
  claimBundles(dir)
  ensureChemClawShellPatch(dir)
  ensurePresentationDefaults(dir)
  ensureOptionalGenuiRecovery(dir)
  return loadOwnBundles(dir, BUNDLES)
}

function ensurePresentationDefaults(dir) {
  const file = join(dir, 'cordis.patch.yml')
  let content = readFileSync(file, 'utf8')
  // Deliverables require this service even without a change summary. Bound Git
  // snapshots so research in a large repository cannot wait on the 30s default.
  const changes = '- id: workspace-changes\n  config:\n    timeoutMs: 1000\n'
  content = content.replace(/- id: workspace-changes\r?\n  disabled: true\s*(?=\n- |$)/u, changes.trimEnd())
  if (!/(?:^|\n)- id: workspace-changes\s*(?:\n|$)/u.test(content)) content += `\n${changes}`
  if (!/(?:^|\n)- id: ui-settings\s*(?:\n|$)/u.test(content)) content += '\n- id: ui-settings\n  config:\n    enabled: true\n'
  if (!/(?:^|\n)- id: session-controller\s*(?:\n|$)/u.test(content)) content += '\n- id: session-controller\n  config:\n    nativeOpen: true\n'
  if (!/(?:^|\n)- id: locale\s*(?:\n|$)/u.test(content)) content += '\n- id: locale\n  config:\n    preference: zh\n'
  // Public general-preference field for the pinned DSH preview notice.
  if (!/(?:^|\n)- id: ui-settings-general\s*(?:\n|$)/u.test(content)) content += '\n- id: ui-settings-general\n  config:\n    welcomeNoticeVersion: "2026-09-28.1"\n'
  else content = content.replace(/(^|\n)- id: ui-settings-general[^\n]*(?:\n[ \t]+[^\n]*)*/u, block => {
    if (/welcomeNoticeVersion:/.test(block)) return block.replace(/welcomeNoticeVersion:[^\n]*/u, 'welcomeNoticeVersion: "2026-09-28.1"')
    if (/\n  config:\s*\n/u.test(block)) return block.replace(/\n  config:\s*\n/u, '\n  config:\n    welcomeNoticeVersion: "2026-09-28.1"\n')
    return `${block}\n  config:\n    welcomeNoticeVersion: "2026-09-28.1"`
  })
  writeFileSync(file, content)
}

/** The profile of the first-run check, under the current DSH_HOME. */
export function loadCheckProfile() {
  const dir = resolveProfileDir(CHECK_PROFILE)
  initProfile(dir, CHECK_BUNDLES)
  return loadOwnBundles(dir, CHECK_BUNDLES)
}

function loadOwnBundles(dir, bundles) {
  const profile = loadProfileDirectory('dsh', dir, INSTALL_ANCHOR)
  const lost = profile.skippedBundles.filter(({ packageName }) => bundles.includes(packageName))
  if (lost.length > 0) throw new Error(`The app could not load its own bundles:\n${lost.map(({ packageName, reason }) => `${packageName}: ${reason}`).join('\n')}`)
  return profile
}
