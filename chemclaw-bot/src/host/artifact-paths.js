import { lstat, realpath, readdir } from 'node:fs/promises'
import { basename, isAbsolute, join, relative, resolve } from 'node:path'
import { artifactPath } from '../shared/artifact-links.js'

const inside = (path, root) => {
  const rest = relative(root, path)
  return rest === '' || (!rest.startsWith('..') && !isAbsolute(rest))
}

export async function resolveArtifacts(rt, { sessionId, botId, values }, signal) {
  if (!Array.isArray(values) || values.length > 40 || values.some(value => typeof value !== 'string')) throw new Error('Name up to 40 workspace files')
  const room = rt.roomOf(sessionId)
  const bot = rt.botOf(botId ?? rt.selfOf(sessionId))
  if (!room && !rt.selfOf(sessionId)) throw new Error('Use a Bot or group chat')
  if (botId && (!bot || (room && !room.members.includes(bot.id)))) throw new Error('Unknown member of this conversation')
  const owner = room ? room.sessions?.[bot?.id] : sessionId
  // Inspect is public and does not instantiate an idle Agent merely to open a file.
  const stored = owner ? await rt.ctx.sessionController.inspect?.(owner, signal).catch(() => undefined) : undefined
  const roots = [...new Set((await Promise.all([
    stored?.meta?.cwd, room?.workDir, bot?.workDir, rt.teamFolder() ?? rt.defaultTeamFolder(),
  ].filter(Boolean).map(path => realpath(path).catch(() => undefined)))).filter(Boolean))]
  const allowed = []
  for (const root of roots) if (!await rt.inData(root)) allowed.push(root)
  const files = Object.create(null)
  const pending = new Map()
  const existing = async path => {
    signal?.throwIfAborted()
    const real = await realpath(path).catch(() => undefined)
    if (!real || !allowed.some(root => inside(real, root)) || await rt.inData(real)) return undefined
    return (await lstat(real).catch(() => undefined))?.isFile() ? real : undefined
  }
  for (const value of values) {
    const path = artifactPath(value)
    if (!path) continue
    const exact = [...new Set((await Promise.all((isAbsolute(path) ? [path] : allowed.map(root => resolve(root, path))).map(existing))).filter(Boolean))]
    if (exact.length === 1) files[value] = exact[0]
    else if (exact.length === 0 && !path.split('/').includes('..')) pending.set(value, basename(path))
  }
  if (!pending.size) return { files, truncated: false }
  // Legacy replies often name just the basename. Search only these workspaces,
  // without symlinks, and refuse a match if an incomplete scan hides ambiguity.
  const wanted = new Set(pending.values())
  const matches = new Map([...wanted].map(name => [name, new Set()]))
  const queue = allowed.map(path => ({ path, depth: 0 }))
  const visited = new Set()
  let count = 0
  let truncated = false
  while (queue.length && !truncated) {
    signal?.throwIfAborted()
    const { path, depth } = queue.shift()
    if (visited.has(path)) continue
    visited.add(path)
    const entries = await readdir(path, { withFileTypes: true }).catch(() => { truncated = true; return [] })
    for (const entry of entries) {
      if (++count > 4000) { truncated = true; break }
      const child = join(path, entry.name)
      if (entry.isSymbolicLink()) continue
      if (entry.isDirectory()) {
        if (entry.name.startsWith('.') || ['node_modules', 'vendor'].includes(entry.name) || await rt.inData(child)) continue
        if (depth >= 6) { truncated = true; break }
        queue.push({ path: child, depth: depth + 1 })
      } else if (entry.isFile() && wanted.has(entry.name)) {
        const real = await existing(child)
        if (real) matches.get(entry.name).add(real)
      }
    }
  }
  if (!truncated) for (const [value, name] of pending) {
    const found = matches.get(name)
    if (found.size === 1) files[value] = [...found][0]
  }
  return { files, truncated }
}
