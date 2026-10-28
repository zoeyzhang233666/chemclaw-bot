import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  defaultTrustedPrs, describeWorktreeVsMain, ensurePrWorktree, fetchRemote,
  listOpenPullRequests, listWorktrees, mainTip,
} from './launch-discover.mjs'
import { resolveIntegration, writeManifest } from './launch-integrate.mjs'
import { resolveProfile } from './launch-profiles.mjs'

const checkout = resolve(dirname(fileURLToPath(import.meta.url)), '..')

export function shouldShowPicker(args = process.argv.slice(2), env = process.env) {
  if (args.includes('--no-picker')) return false
  if (args.includes('--source')) return false
  if (args.includes('--info')) return false
  if (args.includes('--sync-only')) return false
  if (env.CHEMCLAW_LAUNCH_HOME) return false
  if (env.CHEMCLAW_NO_PICKER === '1') return false
  return true
}

export function loadChoice(origin) {
  const file = join(origin, '.chemclaw-dev', 'launcher-choice.json')
  try {
    if (!existsSync(file)) return {}
    return JSON.parse(readFileSync(file, 'utf8'))
  } catch {
    return {}
  }
}

export function saveChoice(origin, choice) {
  const dir = join(origin, '.chemclaw-dev')
  mkdirSync(dir, { recursive: true })
  writeFileSync(join(dir, 'launcher-choice.json'), JSON.stringify(choice, null, 2))
}

export function writeSourceSelection(origin, { source, profile, selection, manifest, remoteConfirmed }) {
  const dir = join(origin, '.chemclaw-dev')
  mkdirSync(dir, { recursive: true })
  const payload = {
    source,
    profile,
    selection,
    remoteConfirmed: Boolean(remoteConfirmed),
    updatedAt: new Date().toISOString(),
  }
  if (manifest) payload.manifest = manifest
  writeFileSync(join(dir, 'source.json'), JSON.stringify(payload, null, 2))
  return payload
}

function buildCatalog(origin, previous = {}) {
  const fetch = fetchRemote(origin)
  const listed = listOpenPullRequests(origin)
  const tip = mainTip(origin)
  const trees = listWorktrees(origin)
  const trusted = defaultTrustedPrs(listed.prs || [])
  const excluded = new Set((previous.excludedPrs || []).map(Number))
  const previousIncluded = Array.isArray(previous.includedPrs) ? previous.includedPrs.map(Number) : null

  const statusParts = []
  if (!fetch.ok) statusParts.push('Remote fetch failed - local/offline mode')
  else statusParts.push('Remote fetch ok')
  if (!listed.ok) statusParts.push(`PR list failed: ${listed.error || 'unknown'}`)
  else statusParts.push(`${listed.prs.length} open PR(s)`)

  const items = [
    {
      id: 'integration',
      kind: 'integration',
      label: '最新功能集成预览 (default) - checked open PRs; reuses single-PR worktree when possible',
    },
    {
      id: 'main',
      kind: 'main',
      label: `main - ${origin} @ ${(tip.sha || '').slice(0, 8)}`,
      source: origin,
      branch: 'main',
    },
  ]

  for (const pr of listed.prs || []) {
    const tree = trees.find(t => t.branch === pr.headRefName)
    const mark = pr.mergeable === 'CONFLICTING' ? ' [CONFLICTING]' : ''
    items.push({
      id: `pr-${pr.number}`,
      kind: 'pr',
      number: pr.number,
      branch: pr.headRefName,
      headRefOid: pr.headRefOid,
      title: pr.title,
      source: tree?.path || null,
      label: `PR #${pr.number} - ${pr.title} [${pr.headRefName} @ ${String(pr.headRefOid).slice(0, 8)}${tree ? '; worktree ready' : '; will add worktree'}]${mark}`,
    })
  }

  for (const tree of trees) {
    if (realpathSync(tree.path) === realpathSync(origin)) continue
    if ((listed.prs || []).some(pr => pr.headRefName === tree.branch)) continue
    const vs = tip.sha ? describeWorktreeVsMain(origin, tree, tip.sha) : { behind: 0, ahead: 0, containedInMain: false }
    const stale = vs.containedInMain ? ' [already in main]' : (vs.behind > 0 ? ` [behind main by ${vs.behind}]` : '')
    items.push({
      id: `worktree:${tree.path}`,
      kind: 'worktree',
      branch: tree.branch || 'detached',
      source: tree.path,
      label: `Worktree - ${tree.branch || 'detached'} @ ${tree.short} - ${tree.path}${stale}`,
    })
  }

  let selectedIndex = items.findIndex(item => item.id === previous.id)
  if (selectedIndex < 0) selectedIndex = 0

  const prs = (listed.prs || []).map(pr => {
    const included = previousIncluded
      ? previousIncluded.includes(pr.number)
      : trusted.some(t => t.number === pr.number) && !excluded.has(pr.number)
    return {
      number: pr.number,
      label: `#${pr.number} ${pr.title} [${pr.headRefName}] mergeable=${pr.mergeable || 'unknown'}`,
      included,
    }
  })

  return {
    items,
    prs,
    selectedIndex,
    copyCredentials: Boolean(previous.copyCredentials),
    status: statusParts.join(' | '),
    remoteConfirmed: fetch.ok && listed.ok,
    listed,
    tip,
  }
}

function readJsonText(text) {
  const cleaned = String(text || '').replace(/^\uFEFF/, '').trim()
  if (!cleaned) throw new Error('Picker returned empty JSON')
  return JSON.parse(cleaned)
}

function showUi(catalog) {
  const script = join(dirname(fileURLToPath(import.meta.url)), 'launch-picker.ps1')
  const temp = mkdtempSync(join(tmpdir(), 'chemclaw-picker-'))
  const catalogFile = join(temp, 'catalog.json')
  const resultFile = join(temp, 'result.json')
  writeFileSync(catalogFile, JSON.stringify({
    items: catalog.items,
    prs: catalog.prs,
    selectedIndex: catalog.selectedIndex,
    copyCredentials: catalog.copyCredentials,
    status: catalog.status,
  }), 'utf8')
  try {
    const result = spawnSync('powershell.exe', [
      '-NoProfile', '-STA', '-ExecutionPolicy', 'Bypass', '-File', script,
      '-CatalogPath', catalogFile,
      '-ResultPath', resultFile,
    ], { encoding: 'utf8', windowsHide: false })
    if (existsSync(resultFile)) return readJsonText(readFileSync(resultFile, 'utf8'))
    const lines = (result.stdout || '').replace(/^\uFEFF/, '').trim().split(/\r?\n/).filter(Boolean)
    const jsonLine = [...lines].reverse().find(line => line.trim().startsWith('{'))
    if (!jsonLine) throw new Error(`Picker UI failed: ${result.stderr || result.status}`)
    return readJsonText(jsonLine)
  } finally {
    rmSync(temp, { recursive: true, force: true })
  }
}

export function runPicker(origin = checkout, { interactive = true } = {}) {
  const root = realpathSync(origin)
  const previous = loadChoice(root)
  const catalog = buildCatalog(root, previous)
  let picked
  if (interactive && process.platform === 'win32') picked = showUi(catalog)
  else {
    picked = {
      cancelled: false,
      id: previous.id || 'integration',
      copyCredentials: false,
      includedPrs: catalog.prs.filter(pr => pr.included).map(pr => pr.number),
    }
  }
  if (picked.cancelled) {
    console.error('Launch cancelled.')
    process.exit(1)
  }

  const item = catalog.items.find(entry => entry.id === picked.id) || catalog.items[0]
  const includedPrs = Array.isArray(picked.includedPrs) ? picked.includedPrs.map(Number) : []
  const allPrNumbers = catalog.prs.map(pr => pr.number)
  const excludedPrs = allPrNumbers.filter(number => !includedPrs.includes(number))

  let source = root
  let selection = { kind: 'main' }
  let manifest = null
  let remoteConfirmed = catalog.remoteConfirmed
  const notes = []

  if (item.kind === 'integration') {
    const integration = resolveIntegration(root, {
      excluded: excludedPrs,
      included: includedPrs,
      remoteConfirmed: catalog.remoteConfirmed,
    })
    source = integration.source
    selection = { kind: 'integration', included: includedPrs, excluded: excludedPrs }
    manifest = writeManifest(root, integration)
    remoteConfirmed = integration.remoteConfirmed
    for (const warning of integration.warnings || []) notes.push(warning)
    if (integration.conflicts?.length) notes.push(`Conflicts: ${integration.conflicts.map(c => `#${c.number}`).join(', ')}`)
  } else if (item.kind === 'pr') {
    const pr = (catalog.listed.prs || []).find(entry => entry.number === item.number) || {
      number: item.number, title: item.title, headRefName: item.branch, headRefOid: item.headRefOid,
    }
    const ensured = ensurePrWorktree(root, pr)
    source = ensured.path
    selection = { kind: 'pr', number: item.number, branch: item.branch }
    if (ensured.dirty) notes.push(`PR #${item.number} worktree has local changes; not overwritten.`)
  } else if (item.kind === 'worktree') {
    source = item.source
    selection = { kind: 'worktree', branch: item.branch }
  } else {
    source = root
    selection = { kind: 'main' }
  }

  const profile = resolveProfile(root, selection, { copyCredentials: Boolean(picked.copyCredentials) })
  saveChoice(root, {
    id: item.id,
    includedPrs,
    excludedPrs,
    copyCredentials: Boolean(picked.copyCredentials),
    profile: profile.key,
    updatedAt: new Date().toISOString(),
  })
  writeSourceSelection(root, {
    source,
    profile: profile.key,
    selection,
    manifest,
    remoteConfirmed,
  })

  return { source, profile, selection, manifest, remoteConfirmed, notes, item }
}

const invoked = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invoked) {
  const result = runPicker(checkout)
  for (const note of result.notes) console.log(`Note: ${note}`)
  console.log(`Selected: ${result.item.label}`)
  console.log(`Source: ${result.source}`)
  console.log(`Profile: ${result.profile.key} (${result.profile.isolated ? 'isolated' : 'baseline'})`)
}
