import { existsSync, mkdirSync, readFileSync, realpathSync, renameSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import {
  defaultTrustedPrs, fetchRemote, findWorktreeForBranch, git, isAncestor, listOpenPullRequests,
  mainTip, orderPrsForMerge, PR_REMOTE, validateChemclawCheckout, worktreeDirty,
} from './launch-discover.mjs'

const INTEGRATION_DIR = 'cursor-chembot-preview-integration'
const INTEGRATION_NEXT = 'cursor-chembot-preview-integration-next'
const INTEGRATION_PREV = 'cursor-chembot-preview-integration-prev'
const INTEGRATION_BRANCH = 'preview/integration'

/**
 * Resolve source for "最新功能集成预览".
 * Single included PR that already contains main → reuse its worktree (no extra copy).
 * Multiple PRs → build in *-next, validate, then swap into integration entry.
 */
export function resolveIntegration(checkout, {
  excluded = [],
  included = null,
  remoteConfirmed = true,
} = {}) {
  const origin = realpathSync(checkout)
  const parent = dirname(origin)
  const warnings = []
  const fetch = remoteConfirmed ? fetchRemote(origin) : { ok: false, error: 'skipped' }
  if (!fetch.ok) warnings.push(`Remote fetch unavailable: ${fetch.error || 'offline'}. Using local refs; not confirmed remote-latest.`)

  const listed = listOpenPullRequests(origin)
  if (!listed.ok) warnings.push(`GitHub PR list failed: ${listed.error}. Falling back to local open-branch hints.`)

  let candidates = listed.ok ? listed.prs : []
  if (!listed.ok) {
    const local = findWorktreeForBranch(origin, 'feat/bot-multi-session')
    if (local) {
      candidates = [{
        number: 64,
        title: 'Add Bot multi-chat sessions (Batch 2) [local fallback]',
        headRefName: 'feat/bot-multi-session',
        headRefOid: local.head,
        mergeable: 'UNKNOWN',
      }]
    }
  }

  const trusted = defaultTrustedPrs(candidates)
  const excludeSet = new Set((excluded || []).map(Number))
  let chosen = trusted.filter(pr => !excludeSet.has(pr.number))
  if (Array.isArray(included) && included.length) {
    const want = new Set(included.map(Number))
    chosen = candidates.filter(pr => want.has(pr.number))
  }

  const tip = mainTip(origin)
  const base = { sha: tip.sha, ref: tip.ref }
  const skipped = [
    ...trusted.filter(pr => excludeSet.has(pr.number)).map(pr => ({ number: pr.number, reason: 'excluded-by-user' })),
    ...candidates.filter(pr => pr.mergeable === 'CONFLICTING' && !excludeSet.has(pr.number)).map(pr => ({ number: pr.number, reason: 'conflicting' })),
  ]

  if (chosen.length === 0) {
    return result({
      source: origin,
      mode: 'main-only',
      reused: true,
      included: [],
      skipped,
      warnings,
      remoteConfirmed: fetch.ok && listed.ok,
      base,
      conflicts: [],
    })
  }

  // Drop PRs whose tips are already ancestors of another chosen tip (duplicate content).
  const ordered = orderPrsForMerge(origin, tip.ref, chosen)
  const unique = []
  for (const pr of ordered) {
    if (unique.some(other => isAncestor(origin, pr.headRefOid, other.headRefOid))) {
      skipped.push({ number: pr.number, reason: 'contained-in-another-selected-pr' })
      continue
    }
    unique.push(pr)
  }

  if (unique.length === 1) {
    const pr = unique[0]
    const existing = findWorktreeForBranch(origin, pr.headRefName)
    if (existing) {
      if (worktreeDirty(existing.path)) warnings.push(`PR #${pr.number} worktree has local changes; launching as-is without overwrite.`)
      else if (fetch.ok && pr.headRefOid && existing.head !== pr.headRefOid && !worktreeDirty(existing.path)) {
        try {
          // Fast-forward only when clean and behind the PR head.
          if (isAncestor(origin, existing.head, pr.headRefOid)) {
            git(existing.path, ['merge', '--ff-only', pr.headRefOid])
          } else {
            warnings.push(`PR #${pr.number} worktree tip diverges from remote head; launching local tip without overwrite.`)
          }
        } catch (error) {
          warnings.push(`Could not fast-forward PR #${pr.number}: ${error.message}`)
        }
      }
      if (!isAncestor(origin, tip.sha, git(existing.path, ['rev-parse', 'HEAD']))) {
        warnings.push(`PR #${pr.number} does not contain current main; single-PR reuse still used for disk savings.`)
      }
      return result({
        source: existing.path,
        mode: 'reuse-single-pr',
        reused: true,
        included: [summarize(pr, git(existing.path, ['rev-parse', 'HEAD']))],
        skipped,
        warnings,
        remoteConfirmed: fetch.ok && listed.ok,
        base,
        conflicts: [],
      })
    }
  }

  // Multi-PR (or single PR with no worktree): build atomically in *-next then swap.
  return buildIntegrationWorktree(origin, parent, tip, unique, {
    skipped, warnings, remoteConfirmed: fetch.ok && listed.ok, base, fetchOk: fetch.ok,
  })
}

function buildIntegrationWorktree(origin, parent, tip, prs, meta) {
  const nextPath = join(parent, INTEGRATION_NEXT)
  const livePath = join(parent, INTEGRATION_DIR)
  const prevPath = join(parent, INTEGRATION_PREV)
  const conflicts = []

  if (existsSync(nextPath)) {
    try {
      if (worktreeDirty(nextPath)) throw new Error('temporary integration worktree has local changes')
      git(origin, ['worktree', 'remove', '--force', nextPath], { allowFail: true })
    } catch {
      rmSync(nextPath, { recursive: true, force: true })
      git(origin, ['worktree', 'prune'], { allowFail: true })
    }
  }

  // Ensure local branch exists for the durable integration entry; next uses detached then branch move.
  git(origin, ['branch', '-f', INTEGRATION_BRANCH, tip.sha], { allowFail: true })
  git(origin, ['worktree', 'add', '--detach', nextPath, tip.sha])
  git(nextPath, ['checkout', '-B', `${INTEGRATION_BRANCH}-next`, tip.sha])

  const included = []
  let tipSha = tip.sha
  for (const pr of prs) {
    if (isAncestor(nextPath, pr.headRefOid, tipSha)) {
      meta.skipped.push({ number: pr.number, reason: 'already-in-integration-tip' })
      continue
    }
    git(origin, ['fetch', PR_REMOTE, pr.headRefOid], { allowFail: true })
    const probe = git(nextPath, ['merge-tree', tipSha, tipSha, pr.headRefOid], { allowFail: true })
    if (probe.includes('changed in both') || probe.includes('CONFLICT')) {
      conflicts.push({ number: pr.number, title: pr.title, detail: 'merge-tree reported conflicts' })
      // Keep previous live integration if any; do not swap.
      cleanupNext(origin, nextPath)
      const fallback = existsSync(livePath) ? realpathSync(livePath) : (findWorktreeForBranch(origin, prs[0].headRefName)?.path || origin)
      meta.warnings.push(`Conflict while integrating PR #${pr.number}. Keeping previous preview source: ${fallback}`)
      return result({
        source: fallback,
        mode: 'conflict-kept-previous',
        reused: true,
        included: readPreviousIncluded(join(origin, '.chemclaw-dev', 'preview-manifest.json')),
        skipped: meta.skipped,
        warnings: meta.warnings,
        remoteConfirmed: meta.remoteConfirmed,
        base: meta.base,
        conflicts,
      })
    }
    try {
      git(nextPath, ['merge', '--no-ff', '--no-edit', pr.headRefOid, '-m', `preview: integrate PR #${pr.number} ${pr.headRefName}`])
    } catch (error) {
      conflicts.push({ number: pr.number, title: pr.title, detail: error.message })
      git(nextPath, ['merge', '--abort'], { allowFail: true })
      cleanupNext(origin, nextPath)
      const fallback = existsSync(livePath) ? realpathSync(livePath) : origin
      meta.warnings.push(`Merge failed for PR #${pr.number}. Keeping previous preview source: ${fallback}`)
      return result({
        source: fallback,
        mode: 'conflict-kept-previous',
        reused: true,
        included: readPreviousIncluded(join(origin, '.chemclaw-dev', 'preview-manifest.json')),
        skipped: meta.skipped,
        warnings: meta.warnings,
        remoteConfirmed: meta.remoteConfirmed,
        base: meta.base,
        conflicts,
      })
    }
    tipSha = git(nextPath, ['rev-parse', 'HEAD'])
    included.push(summarize(pr, tipSha))
  }

  try {
    validateChemclawCheckout(nextPath)
  } catch (error) {
    cleanupNext(origin, nextPath)
    throw new Error(`Integration validation failed: ${error.message}`)
  }

  // Atomic-ish swap: live -> prev, next -> live. Never delete original PR worktrees.
  if (existsSync(prevPath)) {
    git(origin, ['worktree', 'remove', '--force', prevPath], { allowFail: true })
    rmSync(prevPath, { recursive: true, force: true })
    git(origin, ['worktree', 'prune'], { allowFail: true })
  }
  if (existsSync(livePath)) {
    renameSync(livePath, prevPath)
  }
  renameSync(nextPath, livePath)
  git(livePath, ['checkout', '-B', INTEGRATION_BRANCH], { allowFail: true })
  git(origin, ['worktree', 'prune'], { allowFail: true })

  return result({
    source: realpathSync(livePath),
    mode: 'multi-pr-swapped',
    reused: false,
    included,
    skipped: meta.skipped,
    warnings: meta.warnings,
    remoteConfirmed: meta.remoteConfirmed,
    base: meta.base,
    conflicts,
  })
}

function cleanupNext(origin, nextPath) {
  git(origin, ['worktree', 'remove', '--force', nextPath], { allowFail: true })
  rmSync(nextPath, { recursive: true, force: true })
  git(origin, ['worktree', 'prune'], { allowFail: true })
}

function summarize(pr, sha) {
  return {
    number: pr.number,
    title: pr.title,
    branch: pr.headRefName,
    sha: String(sha).slice(0, 8),
    headRefOid: pr.headRefOid,
  }
}

function readPreviousIncluded(manifestPath) {
  try {
    if (!existsSync(manifestPath)) return []
    return JSON.parse(readFileSync(manifestPath, 'utf8')).included || []
  } catch {
    return []
  }
}

function result(payload) {
  return {
    ...payload,
    builtAt: new Date().toISOString(),
  }
}

export function writeManifest(origin, integration) {
  const dir = join(origin, '.chemclaw-dev')
  mkdirSync(dir, { recursive: true })
  const manifest = {
    source: integration.source,
    mode: integration.mode,
    reused: integration.reused,
    base: integration.base,
    included: integration.included,
    skipped: integration.skipped,
    conflicts: integration.conflicts,
    warnings: integration.warnings,
    remoteConfirmed: integration.remoteConfirmed,
    builtAt: integration.builtAt,
  }
  writeFileSync(join(dir, 'preview-manifest.json'), JSON.stringify(manifest, null, 2))
  return manifest
}

export function integrationPaths(checkout) {
  const parent = dirname(realpathSync(checkout))
  return {
    live: join(parent, INTEGRATION_DIR),
    next: join(parent, INTEGRATION_NEXT),
    prev: join(parent, INTEGRATION_PREV),
    branch: INTEGRATION_BRANCH,
  }
}
