import { randomUUID } from 'node:crypto'
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { dirname, join, posix } from 'node:path'
import { unzipSync } from 'fflate'
import { managedSkillPath, parseSkill, safeSkillPath, SKILL_LIMITS } from './skill-files.js'
import { skillEmoji, skillExample, validSkillEmoji } from '../shared/skill-presentation.js'

function validateEntries(entries) {
  const names = new Set()
  let bytes = 0
  if (entries.length > SKILL_LIMITS.files) throw new Error('Too many files in this skill archive.')
  for (const entry of entries) {
    entry.path = safeSkillPath(entry.path)
    const key = entry.path.toLowerCase()
    if (names.has(key)) throw new Error(`Duplicate skill path: ${entry.path}`)
    names.add(key)
    bytes += entry.data.length
    if (bytes > SKILL_LIMITS.expanded) throw new Error('Expanded skills exceed 500 MB.')
  }
  return entries
}

export function unpackSkills(bytes) {
  if (bytes.length > SKILL_LIMITS.upload) throw new Error('Choose a skill archive smaller than 100 MB.')
  const buffer = Buffer.from(bytes)
  if (buffer.length < 22) throw new Error('Invalid ZIP archive.')
  // Unix link modes are in the central directory, not the local file headers.
  let end = buffer.length - 22
  for (; end >= Math.max(0, buffer.length - 65557); end--) if (buffer.readUInt32LE(end) === 0x06054b50) break
  if (end < Math.max(0, buffer.length - 65557) || buffer.readUInt32LE(end) !== 0x06054b50) throw new Error('Invalid ZIP archive.')
  const count = buffer.readUInt16LE(end + 10)
  let cursor = buffer.readUInt32LE(end + 16)
  if (count === 0xffff || count > SKILL_LIMITS.files) throw new Error('ZIP64 and archives with too many files are not supported.')
  let total = 0
  for (let index = 0; index < count; index++) {
    if (cursor + 46 > end || buffer.readUInt32LE(cursor) !== 0x02014b50) throw new Error('Invalid ZIP directory.')
    const size = buffer.readUInt32LE(cursor + 24)
    const mode = buffer.readUInt32LE(cursor + 38) >>> 16
    if ((mode & 0xf000) === 0xa000 || ((mode & 0xf000) && ![0x8000, 0x4000].includes(mode & 0xf000))) throw new Error('Skill archives cannot contain links or special files.')
    if (buffer.readUInt16LE(cursor + 8) & 1) throw new Error('Encrypted skill archives are not supported.')
    total += size
    if (total > SKILL_LIMITS.expanded) throw new Error('Expanded skills exceed 500 MB.')
    const length = buffer.readUInt16LE(cursor + 28)
    const name = buffer.subarray(cursor + 46, cursor + 46 + length).toString('utf8').replace(/\/$/, '')
    if (name) safeSkillPath(name)
    cursor += 46 + length + buffer.readUInt16LE(cursor + 30) + buffer.readUInt16LE(cursor + 32)
  }
  const files = unzipSync(buffer, { filter: file => {
    if (file.originalSize > SKILL_LIMITS.expanded) throw new Error('Expanded skill file exceeds 500 MB.')
    return !file.name.endsWith('/')
  } })
  return validateEntries(Object.entries(files).map(([path, data]) => ({ path, data: Buffer.from(data) })))
}

async function download(url, request, limit, signal) {
  const response = await request(url, { headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'ChemClaw' }, redirect: 'error', signal })
  if (!response.ok) throw new Error(`GitHub answered ${response.status}. Use a public repository and try again.`)
  if (Number(response.headers.get('content-length')) > limit) throw new Error('GitHub download exceeds the size limit.')
  const chunks = []
  let bytes = 0
  for await (const chunk of response.body) {
    bytes += chunk.length
    if (bytes > limit) throw new Error('GitHub download exceeds the size limit.')
    chunks.push(chunk)
  }
  return Buffer.concat(chunks)
}

export async function githubSkills(value, { request = fetch, signal = AbortSignal.timeout(60000) } = {}) {
  let url
  try { url = new URL(value) } catch { throw new Error('Enter a GitHub repository or skill directory URL.') }
  if (url.protocol !== 'https:' || url.hostname !== 'github.com' || url.port || url.username || url.password || url.search || url.hash) throw new Error('Use a public https://github.com repository URL without credentials.')
  const parts = url.pathname.split('/').filter(Boolean).map(decodeURIComponent)
  const [owner, rawRepo, kind, ...tail] = parts
  const repo = rawRepo?.replace(/\.git$/, '')
  if (!/^[\w.-]+$/.test(owner ?? '') || !/^[\w.-]+$/.test(repo ?? '') || (kind && !['tree', 'blob'].includes(kind))) throw new Error('Enter a GitHub repository or skill directory URL.')
  const api = `https://api.github.com/repos/${owner}/${repo}`
  const info = JSON.parse((await download(api, request, 1024 * 1024, signal)).toString())
  if (info.private) throw new Error('Only public GitHub repositories are supported.')
  let ref = info.default_branch
  let subdir = ''
  if (kind) {
    // A branch may contain slashes; resolve the longest actual ref before the path.
    let found = false
    for (let split = tail.length; split >= 1; split--) {
      const candidate = tail.slice(0, split).join('/')
      try {
        const commit = JSON.parse((await download(`${api}/commits/${encodeURIComponent(candidate)}`, request, 1024 * 1024, signal)).toString())
        ref = commit.sha
        subdir = tail.slice(split).join('/')
        found = true
        break
      } catch (error) { if (!/answered 404|answered 422/.test(error.message)) throw error }
    }
    if (!found) throw new Error('GitHub branch or revision was not found.')
    if (kind === 'blob') {
      if (!/(^|\/)SKILL\.md$/i.test(subdir)) throw new Error('Choose a SKILL.md file or a skill directory.')
      subdir = posix.dirname(subdir)
      if (subdir === '.') subdir = ''
    }
  }
  if (subdir) safeSkillPath(subdir)
  const archive = await download(`https://codeload.github.com/${owner}/${repo}/zip/${encodeURIComponent(ref)}`, request, SKILL_LIMITS.upload, signal)
  const entries = unpackSkills(archive)
  const root = entries[0]?.path.split('/')[0]
  const prefix = `${root}/${subdir ? `${subdir}/` : ''}`
  return { entries: entries.filter(entry => entry.path.startsWith(prefix)).map(entry => ({ ...entry, path: entry.path.slice(prefix.length) })), source: { type: 'github', url: url.href, revision: ref } }
}

export function identifySkills(entries) {
  const instructions = entries.filter(entry => /(^|\/)SKILL\.md$/i.test(entry.path))
  if (!instructions.length) throw new Error('No SKILL.md was found. Choose a skill file, folder, or ZIP archive.')
  return instructions.map((entry, index) => {
    const root = posix.dirname(entry.path)
    try {
      const content = new TextDecoder('utf-8', { fatal: true }).decode(entry.data)
      const metadata = parseSkill(content, root === '.' ? 'skill' : posix.basename(root))
      const files = entries.filter(file => root === '.' || file.path.startsWith(`${root}/`))
      return { key: String(index), root, instruction: entry.path, ...metadata, valid: true, files: files.length, bytes: files.reduce((sum, file) => sum + file.data.length, 0) }
    } catch (error) { return { key: String(index), root, instruction: entry.path, valid: false, error: error.message } }
  })
}

export function install(rt) {
  const staged = new Map()
  let commits = Promise.resolve()
  const clear = async token => {
    const entry = staged.get(token)
    if (!entry) return
    staged.delete(token)
    await rm(entry.root, { recursive: true, force: true })
  }
  const preview = async (body, signal) => {
    for (const [token, entry] of staged) if (entry.expires < Date.now()) await clear(token)
    if (staged.size >= 4) throw new Error('Finish or cancel the other skill imports first.')
    let entries
    let source = { type: 'upload' }
    if (body.url) ({ entries, source } = await githubSkills(body.url, { signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(60000)]) : undefined }))
    else if (body.archive) {
      if (typeof body.archive !== 'string' || body.archive.length > Math.ceil(SKILL_LIMITS.upload * 4 / 3) + 4) throw new Error('Choose a skill archive smaller than 100 MB.')
      entries = unpackSkills(Buffer.from(body.archive, 'base64'))
    } else {
      if (!Array.isArray(body.files) || body.files.length > SKILL_LIMITS.files) throw new Error('Choose skill files first.')
      let total = 0
      entries = body.files.map(file => {
        if (typeof file.data !== 'string') throw new Error('Invalid skill upload.')
        total += file.data.length
        if (total > Math.ceil(SKILL_LIMITS.upload * 4 / 3)) throw new Error('Choose skill files smaller than 100 MB in total.')
        return { path: file.path, data: Buffer.from(file.data, 'base64') }
      })
      validateEntries(entries)
    }
    const candidates = identifySkills(entries).map(candidate => {
      const existing = rt.state.capabilities.items[candidate.name]
      const known = existing?.kind === 'skill' && existing.originalName === candidate.originalName ? existing
        : Object.values(rt.state.capabilities.items).find(item => item.kind === 'skill' && item.originalName === candidate.originalName)
      return known ? { ...candidate, category: known.category, labels: known.labels, purpose: known.purpose, inputs: known.inputs, deliverables: known.deliverables,
        emoji: known.emoji ?? (known.builtinSource ? skillEmoji(known) : ''), examples: known.builtinSource ? [skillExample(known)] : known.examples } : candidate
    })
    const token = randomUUID()
    const root = join(rt.home, 'skills', 'staging', token)
    try {
      for (const entry of entries) {
        const path = join(root, entry.path)
        await mkdir(dirname(path), { recursive: true })
        await writeFile(path, entry.data, { flag: 'wx' })
      }
      staged.set(token, { root, candidates, source, entries: entries.map(({ path }) => path), expires: Date.now() + 30 * 60 * 1000 })
    } catch (error) { await rm(root, { recursive: true, force: true }); throw error }
    return { token, candidates: candidates.map(item => ({ ...item, exists: Boolean(rt.state.capabilities.items[item.name]) })), source }
  }
  const commit = async body => {
    const stage = staged.get(body.token)
    if (!stage || stage.expires < Date.now()) throw new Error('This skill import expired. Choose the files again.')
    if (!Array.isArray(body.selections) || !body.selections.length) throw new Error('Select at least one skill.')
    const pending = []
    const names = new Set()
    const skipped = []
    const previous = {}
    try {
      for (const choice of body.selections) {
        const candidate = stage.candidates.find(item => item.key === choice.key && item.valid)
        if (!candidate) throw new Error('The selected skill is invalid.')
        const name = rt.validateSkillName(choice.name || candidate.name)
        const existing = rt.state.capabilities.items[name]
        if (existing && choice.conflict !== 'replace') { skipped.push(name); continue }
        if (existing && existing.kind !== 'skill') throw new Error(`A tool or pack already uses ${name}. Choose another name.`)
        if (names.has(name)) throw new Error(`Select each skill name only once: ${name}`)
        const emoji = choice.emoji ?? existing?.emoji ?? candidate.emoji ?? ''
        if (emoji !== '' && !validSkillEmoji(emoji)) throw new Error('Choose an emoji from the skill icon list.')
        names.add(name)
        previous[name] = existing
        const directory = `skills/installed/${randomUUID()}`
        const destination = managedSkillPath(rt.home, directory)
        await mkdir(destination, { recursive: true })
        pending.push({ name, directory })
        const prefix = candidate.root === '.' ? '' : `${candidate.root}/`
        for (const path of stage.entries.filter(path => path.startsWith(prefix))) {
          const target = join(destination, path.slice(prefix.length))
          await mkdir(dirname(target), { recursive: true })
          await writeFile(target, await readFile(join(stage.root, path)), { flag: 'wx' })
        }
        const entry = pending.at(-1)
        Object.assign(entry, { kind: 'skill', ...candidate, name, directory, content: undefined,
          instructionFile: candidate.instruction.slice(prefix.length),
          displayName: String(choice.displayName ?? '').trim().slice(0, 100),
          purpose: String(choice.purpose ?? candidate.purpose ?? candidate.description).trim().slice(0, 2000),
          category: String(choice.category || candidate.category || '未分类').trim().slice(0, 80),
          emoji,
          source: stage.source, createdAt: existing?.createdAt ?? Date.now(), updatedAt: Date.now(), createdBy: null })
        for (const key of ['key', 'root', 'instruction', 'valid', 'files', 'bytes']) delete entry[key]
      }
      for (const entry of pending) rt.state.capabilities.items[entry.name] = entry
      await rt.save()
    } catch (error) {
      for (const entry of pending) {
        if (previous[entry.name]) rt.state.capabilities.items[entry.name] = previous[entry.name]
        else delete rt.state.capabilities.items[entry.name]
        await rm(managedSkillPath(rt.home, entry.directory), { recursive: true, force: true })
      }
      throw error
    }
    await clear(body.token)
    return { installed: pending.map(item => item.name), skipped }
  }
  rt.skillImportEndpoint = async (endpoint, body, signal) => {
    await rt.load()
    const readOnly = rt.readOnly()
    if (readOnly !== undefined) throw new Error(readOnly)
    if (endpoint === 'skill-import-preview') return preview(body, signal)
    if (endpoint === 'skill-import-cancel') { await clear(body.token); return true }
    if (endpoint === 'skill-import-commit') {
      const result = commits.then(() => commit(body))
      commits = result.catch(() => {})
      return result
    }
    throw new Error('Unknown skill import operation.')
  }
  ctxCleanup(rt, staged, clear, () => commits)
}

function ctxCleanup(rt, staged, clear, commits) {
  rt.ctx.effect(() => () => commits().then(() => Promise.all([...staged.keys()].map(clear))), 'chemclaw-bot: skill import cleanup')
}
