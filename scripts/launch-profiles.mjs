import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const SENSITIVE = ['.credentials.yaml', 'secrets.json']

export function profileKey(selection) {
  if (typeof selection?.profile === 'string' && selection.profile.trim()) return selection.profile.trim()
  if (!selection || selection.kind === 'main') return 'baseline'
  if (selection.kind === 'integration') return 'integration'
  if (selection.kind === 'pr') return `pr-${selection.number}`
  if (selection.kind === 'worktree') {
    const branch = String(selection.branch || 'worktree').replace(/[^\w.-]+/g, '-')
    return `worktree-${branch}`
  }
  return 'baseline'
}

/** Resolve isolated data/shell/workspace. Never copies credentials unless copyCredentials is true. */
export function resolveProfile(origin, selection = { kind: 'main' }, { copyCredentials = false } = {}) {
  const key = profileKey(selection)
  const root = join(origin, '.chemclaw-dev')
  if (key === 'baseline') {
    return {
      key,
      home: root,
      data: join(root, 'data'),
      shell: join(root, 'shell'),
      workspace: join(origin, '.chemclaw-workspace'),
      isolated: false,
      copiedCredentials: false,
    }
  }

  const home = join(root, 'profiles', key)
  const data = join(home, 'data')
  const shell = join(home, 'shell')
  const workspace = join(origin, '.chemclaw-workspace-profiles', key)
  mkdirSync(data, { recursive: true })
  mkdirSync(shell, { recursive: true })
  mkdirSync(workspace, { recursive: true })

  let copiedCredentials = false
  if (copyCredentials) copiedCredentials = seedCredentials(join(root, 'data'), data)
  else writeMarker(home, 'Credentials were not copied. Configure keys in this isolated preview if needed.')

  return { key, home, data, shell, workspace, isolated: true, copiedCredentials }
}

function seedCredentials(fromData, toData) {
  mkdirSync(join(toData, 'chemclaw'), { recursive: true })
  let copied = false
  const pairs = [
    [join(fromData, '.credentials.yaml'), join(toData, '.credentials.yaml')],
    [join(fromData, 'chemclaw', 'secrets.json'), join(toData, 'chemclaw', 'secrets.json')],
  ]
  for (const [src, dest] of pairs) {
    if (!existsSync(src) || existsSync(dest)) continue
    writeFileSync(dest, readFileSync(src))
    copied = true
  }
  if (copied) writeMarker(join(toData, '..'), `Copied sensitive files on request: ${SENSITIVE.join(', ')}`)
  return copied
}

function writeMarker(home, message) {
  writeFileSync(join(home, 'PROFILE.txt'), `${message}\n`, 'utf8')
}
