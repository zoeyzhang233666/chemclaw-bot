import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, realpathSync } from 'node:fs'
import { join, resolve } from 'node:path'

export const PR_REPO = 'zoeyzhang233666/chemclaw-bot'
export const PR_REMOTE = 'chemclaw'

export function git(cwd, args, { allowFail = false } = {}) {
  try {
    return execFileSync('git', ['-C', cwd, ...args], {
      encoding: 'utf8', windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
    }).trim()
  } catch (error) {
    if (allowFail) return ''
    const detail = error.stderr?.toString?.().trim() || error.message
    throw new Error(detail)
  }
}

export function fetchRemote(checkout) {
  try {
    git(checkout, ['fetch', PR_REMOTE, '--prune'])
    return { ok: true }
  } catch (error) {
    return { ok: false, error: error.message }
  }
}

export function listWorktrees(checkout) {
  const raw = git(checkout, ['worktree', 'list', '--porcelain'], { allowFail: true })
  if (!raw) return []
  const trees = []
  let current = null
  for (const line of raw.split(/\r?\n/)) {
    if (line.startsWith('worktree ')) {
      if (current) trees.push(current)
      current = { path: line.slice(9), head: '', branch: '', detached: false }
    } else if (!current) continue
    else if (line.startsWith('HEAD ')) current.head = line.slice(5)
    else if (line.startsWith('branch ')) current.branch = line.slice(7).replace(/^refs\/heads\//, '')
    else if (line === 'detached') current.detached = true
  }
  if (current) trees.push(current)
  return trees.map(tree => ({
    ...tree,
    path: existsSync(tree.path) ? realpathSync(tree.path) : tree.path,
    short: tree.head.slice(0, 8),
  }))
}

export function validateChemclawCheckout(path) {
  for (const [folder, name] of [['app', 'chemclaw'], ['chemclaw-bot', 'chemclaw-bot']]) {
    const manifest = JSON.parse(readFileSync(join(path, folder, 'package.json'), 'utf8'))
    if (manifest.name !== name) throw new Error('The selected folder is not a ChemClaw source checkout')
  }
  if (!existsSync(join(path, 'scripts', 'launch-chemclaw.mjs'))) throw new Error('The selected source has no ChemClaw launcher')
}

export function isAncestor(checkout, maybeAncestor, tip) {
  try {
    execFileSync('git', ['-C', checkout, 'merge-base', '--is-ancestor', maybeAncestor, tip], {
      windowsHide: true, stdio: 'ignore',
    })
    return true
  } catch {
    return false
  }
}

export function worktreeDirty(path) {
  return git(path, ['status', '--porcelain', '--untracked-files=no'], { allowFail: true }) !== ''
}

export function findWorktreeForBranch(checkout, branch) {
  const want = branch.replace(/^refs\/heads\//, '')
  return listWorktrees(checkout).find(tree => tree.branch === want && !tree.detached) || null
}

export function listOpenPullRequests(checkout) {
  try {
    const raw = execFileSync('gh', [
      'pr', 'list', '--repo', PR_REPO, '--state', 'open', '--limit', '50',
      '--json', 'number,title,headRefName,baseRefName,headRefOid,mergeable,updatedAt',
    ], { encoding: 'utf8', windowsHide: true, cwd: checkout, stdio: ['ignore', 'pipe', 'pipe'] }).trim()
    return { ok: true, prs: JSON.parse(raw || '[]'), repo: PR_REPO }
  } catch (error) {
    const detail = error.stderr?.toString?.().trim() || error.message
    return { ok: false, prs: [], error: detail, repo: PR_REPO }
  }
}

/** Trusted by default: open and not known-conflicting. */
export function defaultTrustedPrs(prs) {
  return prs.filter(pr => pr.mergeable !== 'CONFLICTING')
}

/**
 * Order PRs so an ancestor tip merges before a descendant.
 * Remaining ties: fewer commits from main first, then PR number.
 */
export function orderPrsForMerge(checkout, mainRef, prs) {
  const scored = prs.map(pr => {
    const ahead = Number(git(checkout, ['rev-list', '--count', `${mainRef}..${pr.headRefOid}`], { allowFail: true }) || '0')
    return { pr, ahead }
  })
  scored.sort((a, b) => {
    if (isAncestor(checkout, a.pr.headRefOid, b.pr.headRefOid)) return -1
    if (isAncestor(checkout, b.pr.headRefOid, a.pr.headRefOid)) return 1
    if (a.ahead !== b.ahead) return a.ahead - b.ahead
    return a.pr.number - b.pr.number
  })
  return scored.map(item => item.pr)
}

export function describeWorktreeVsMain(checkout, tree, mainSha) {
  const behind = Number(git(checkout, ['rev-list', '--count', `${tree.head}..${mainSha}`], { allowFail: true }) || '0')
  const ahead = Number(git(checkout, ['rev-list', '--count', `${mainSha}..${tree.head}`], { allowFail: true }) || '0')
  return { behind, ahead, containedInMain: ahead === 0 && isAncestor(checkout, tree.head, mainSha) }
}

export function mainTip(checkout) {
  const remote = git(checkout, ['rev-parse', `${PR_REMOTE}/main`], { allowFail: true })
  if (remote) return { ref: `${PR_REMOTE}/main`, sha: remote }
  const local = git(checkout, ['rev-parse', 'main'], { allowFail: true })
  return { ref: 'main', sha: local }
}

export function ensurePrWorktree(checkout, pr) {
  const existing = findWorktreeForBranch(checkout, pr.headRefName)
  if (existing) {
    return { path: existing.path, created: false, dirty: worktreeDirty(existing.path), head: existing.head }
  }
  const path = resolve(checkout, '..', `cursor-chembot-pr-${pr.number}`)
  if (existsSync(path)) {
    validateChemclawCheckout(path)
    return { path: realpathSync(path), created: false, dirty: worktreeDirty(path), head: git(path, ['rev-parse', 'HEAD']) }
  }
  git(checkout, ['fetch', PR_REMOTE, `pull/${pr.number}/head:refs/remotes/${PR_REMOTE}/pr-${pr.number}`], { allowFail: true })
  const start = git(checkout, ['rev-parse', pr.headRefOid], { allowFail: true }) || pr.headRefOid
  git(checkout, ['worktree', 'add', '--detach', path, start])
  return { path: realpathSync(path), created: true, dirty: false, head: git(path, ['rev-parse', 'HEAD']) }
}
