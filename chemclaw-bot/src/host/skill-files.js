import { createHash } from 'node:crypto'
import { lstat, readdir, readFile, realpath } from 'node:fs/promises'
import { basename, dirname, isAbsolute, relative, resolve, sep } from 'node:path'
import { parseDocument } from 'yaml'

export const SKILL_LIMITS = { upload: 100 * 1024 * 1024, expanded: 500 * 1024 * 1024, files: 50000, instruction: 1024 * 1024 }
const NAME = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/

export function safeSkillPath(value) {
  const path = String(value).normalize('NFC').replaceAll('\\', '/')
  if (!path || path.startsWith('/') || path.split('/').some(part => !part || part === '.' || part === '..'
    || /[<>:"|?*\x00-\x1f]/.test(part) || /[. ]$/.test(part) || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(part))) throw new Error(`Unsafe skill path: ${path}`)
  return path
}

export function managedSkillPath(home, directory) {
  if (!/^skills\/installed\/[a-f0-9-]+$/.test(String(directory))) throw new Error('Invalid installed skill directory.')
  const root = resolve(home)
  const path = resolve(root, directory)
  if (!path.startsWith(root + sep)) throw new Error('Invalid installed skill directory.')
  return path
}

export function parseSkill(content, fallback = 'skill') {
  if (Buffer.byteLength(content) > SKILL_LIMITS.instruction) throw new Error('SKILL.md must be smaller than 1 MB.')
  const match = content.replace(/^\uFEFF/, '').match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/)
  let data = {}
  if (match) {
    const doc = parseDocument(match[1], { uniqueKeys: true })
    if (doc.errors.length) throw new Error(`Invalid skill metadata: ${doc.errors[0].message.split('\n')[0]}`)
    data = doc.toJS({ maxAliasCount: 0 })
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Skill metadata must be an object.')
  }
  const boolean = key => {
    if (data[key] === undefined) return undefined
    if (typeof data[key] === 'boolean') return data[key]
    if (/^(true|yes|on|1)$/i.test(String(data[key]))) return true
    if (/^(false|no|off|0)$/i.test(String(data[key]))) return false
    throw new Error(`Invalid ${key} in SKILL.md.`)
  }
  const originalName = String(data.name ?? fallback).trim()
  const name = NAME.test(originalName) && originalName.length <= 32 && originalName !== 'github' ? originalName
    : `skill-${createHash('sha256').update(originalName).digest('hex').slice(0, 16)}`
  return { name, originalName, description: String(data.description ?? '').slice(0, 2000),
    version: String(data.version ?? data.metadata?.version ?? ''),
    invocation: { userInvocable: boolean('user-invocable') !== false, modelInvocable: boolean('disable-model-invocation') !== true } }
}

export async function skillFiles(root, { limit = SKILL_LIMITS.files } = {}) {
  const base = await realpath(root)
  const files = []
  const walk = async directory => {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const path = resolve(directory, entry.name)
      const info = await lstat(path)
      if (info.isSymbolicLink()) throw new Error(`Skill links are not supported: ${entry.name}`)
      if (entry.isDirectory()) await walk(path)
      else if (entry.isFile()) {
        const actual = await realpath(path)
        if (!actual.startsWith(base + sep) || isAbsolute(relative(base, actual))) throw new Error('Skill resource escaped its directory.')
        files.push({ path: relative(base, path).replaceAll('\\', '/'), bytes: info.size })
        if (files.length > limit) throw new Error('Too many files in this skill.')
      }
    }
  }
  await walk(base)
  return files.sort((a, b) => a.path.localeCompare(b.path))
}

export async function readSkillFile(root, file = 'SKILL.md') {
  const path = resolve(root, safeSkillPath(file))
  const base = await realpath(root)
  const actual = await realpath(path)
  if (!actual.startsWith(base + sep) || (await lstat(path)).isSymbolicLink()) throw new Error('Skill resource escaped its directory.')
  const bytes = await readFile(actual)
  if (bytes.length > SKILL_LIMITS.instruction) throw new Error('SKILL.md must be smaller than 1 MB.')
  return bytes.toString('utf8')
}

export const skillDirectoryOf = (item, home, packageRoot) => item.directory ? managedSkillPath(home, item.directory)
  : item.sourcePath ? dirname(resolve(packageRoot, item.sourcePath)) : undefined
export const skillFallbackName = path => basename(dirname(path)) || 'skill'
