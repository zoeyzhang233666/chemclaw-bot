import { createHash } from 'node:crypto'
import { encodeUrlComponent } from './secrets.js'
import { own } from './store.js'
import { join } from 'node:path'
import { rm, stat } from 'node:fs/promises'
import { packageRoot, ensureSkillLibrary } from './catalog-seed.js'
import { parseSkill, readSkillFile, skillDirectoryOf, skillFiles, managedSkillPath } from './skill-files.js'
import { skillLabel } from '../shared/skills.js'
import { validSkillEmoji } from '../shared/skill-presentation.js'

const MCP_CLIENT = '@deepseek-ai/dsh-mcp-client'
const NAME = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/
const SECRET_REFERENCE = /\$DSH_SECRET_([A-Z][A-Z0-9_]*)/g
const ENSURE_TIMEOUT_MS = 15_000

export function validateCapabilityName(value) {
  const name = String(value ?? '').trim()
  if (name.length > 32 || !NAME.test(name) || name === 'github') {
    throw new Error('Use a capability name with lowercase letters, digits, and single hyphens; "github" is reserved.')
  }
  return name
}

export function expandCapabilityNames(capabilities, library) {
  const expanded = new Set()
  for (const name of capabilities ?? []) {
    const item = own(library, name)
    if (!item) throw new Error(`No capability named ${name}.`)
    if (item.kind === 'pack') {
      for (const childName of item.items ?? []) {
        const child = own(library, childName)
        if (!child || !['mcp', 'skill'].includes(child.kind)) throw new Error(`Pack ${name} refers to an unavailable capability ${childName}.`)
        expanded.add(childName)
      }
    } else if (item.kind === 'mcp' || item.kind === 'skill') {
      expanded.add(name)
    } else {
      throw new Error(`Capability ${name} has an unknown kind.`)
    }
  }
  return expanded
}

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b)
const strings = value => {
  if (value === undefined) return []
  if (!Array.isArray(value) || value.some(item => typeof item !== 'string')) throw new Error('Arguments must be a list of text values.')
  return [...value]
}
const stringMap = (value, label) => {
  if (value === undefined) return {}
  if (value === null || typeof value !== 'object' || Array.isArray(value)
    || Object.values(value).some(item => typeof item !== 'string')) throw new Error(`${label} must contain text values.`)
  return Object.fromEntries(Object.entries(value))
}

export function install(rt) {
  const { ctx, state } = rt
  const agents = new Map()
  // Mounted fibers live in each Agent's own context, so they outlive this plugin unless
  // its cleanup disposes them; a strong map keeps them reachable for that.
  const mounts = new Map()
  // One reconcile chain per Agent: a slow MCP server holds up only its own Agent.
  const chains = new WeakMap()
  const queued = new WeakSet()
  const sessionStatuses = new Map()
  // sessionId → JSON of bot.capabilities after a successful ensure/prepare.
  const ensured = new Map()
  let pluginPromise
  let scheduled = null
  let loadingSecrets = 0
  let stopped = false

  const library = () => state.capabilities.items
  const ensureLibrary = () => {
    state.capabilities ??= { items: {} }
    state.capabilities.items ??= {}
    return library()
  }
  const writeCheck = () => {
    const readOnly = rt.readOnly()
    if (readOnly !== undefined) throw new Error(readOnly)
  }
  const allowedToEdit = (item, botId) => rt.isMain(botId) || item.createdBy === botId
  const usedByOthers = (name, botId) => Object.values(state.bots).some(bot => bot.id !== botId
    && (bot.capabilities ?? []).some((attached) => {
      const item = own(library(), attached)
      return attached === name || (item?.kind === 'pack' && (item.items ?? []).includes(name))
    }))
  // A creator that is not a Main Bot could otherwise rewrite what a Main Bot runs.
  const editCheck = (item, botId, verb) => {
    if (!allowedToEdit(item, botId)) throw new Error(`Only ${item.createdBy ? 'its creator or a Main Bot' : 'a Main Bot'} can ${verb} ${item.name}.`)
    if (!rt.isMain(botId) && usedByOthers(item.name, botId)) throw new Error(`Another Bot uses ${item.name}, so only a Main Bot can ${verb} it.`)
  }
  const itemInput = (body, { botId, ui, builtinSeed = false }) => {
    const name = validateCapabilityName(body.name)
    const kind = body.kind
    if (!['mcp', 'skill', 'pack'].includes(kind)) throw new Error('Choose an MCP server, skill, or pack.')
    const items = ensureLibrary()
    const previous = own(items, name)
    if (previous && !ui) editCheck(previous, botId, 'change')
    if (previous && previous.kind !== kind) throw new Error('A capability cannot change its kind. Delete it and save a new one.')
    const now = Date.now()
    const item = {
      name,
      kind,
      description: String(body.description ?? '').trim().slice(0, 2000),
      createdBy: previous?.createdBy ?? (ui ? null : botId),
      createdAt: previous?.createdAt ?? now,
      updatedAt: now,
    }
    if (kind === 'skill') {
      const fields = ['displayName', 'labels', 'category', 'purpose', 'emoji', 'inputs', 'deliverables', 'examples', 'keywords', 'recommendedBots', 'originalName', 'sourcePath', 'directory', 'instructionFile', 'invocation', 'source', 'version', 'builtinHash', 'builtinSource', 'builtinVersion']
      for (const field of fields) {
        if (previous?.[field] !== undefined) item[field] = previous[field]
        if (ui && body[field] !== undefined && !['directory', 'sourcePath', 'instructionFile', 'builtinHash', 'builtinSource', 'builtinVersion'].includes(field)) item[field] = body[field]
      }
      // Only the built-in seeder can supply a packaged resource path.
      if (builtinSeed && body.sourcePath) item.sourcePath = body.sourcePath
      for (const field of ['displayName', 'purpose', 'category', 'inputs', 'deliverables']) if (item[field] !== undefined) item[field] = String(item[field]).trim().slice(0, field === 'displayName' ? 100 : 2000)
      if (item.emoji !== undefined && item.emoji !== '' && !validSkillEmoji(item.emoji)) throw new Error('Choose an emoji from the skill icon list.')
    }
    if (kind === 'mcp') {
      const transport = body.transport === 'streamable-http' ? 'streamable-http' : 'stdio'
      if (transport === 'stdio') {
        const command = String(body.command ?? '').trim()
        if (command === '') throw new Error('Enter a command for the MCP server.')
        const args = strings(body.args)
        const env = stringMap(body.env, 'Environment variables')
        const changed = !previous || previous.kind !== 'mcp' || previous.transport !== 'stdio'
          || previous.command !== command || !same(previous.args ?? [], args) || !same(previous.env ?? {}, env)
        Object.assign(item, { transport, command, args, env, approved: ui ? true : changed ? false : previous.approved === true })
      } else {
        const url = String(body.url ?? '').trim()
        try {
          const parsed = new URL(url)
          if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') throw new Error()
        } catch { throw new Error('Enter a valid HTTP or HTTPS URL.') }
        Object.assign(item, { transport, url, headers: stringMap(body.headers, 'Headers'), approved: true })
      }
    } else if (kind === 'skill') {
      if (item.directory && body.content !== undefined) throw new Error('Installed skill files are preserved. Reinstall the folder to replace its instructions.')
      item.content = String(body.content ?? previous?.content ?? '').trim()
      if (body.content !== undefined && !builtinSeed) item.invocation = parseSkill(item.content, name).invocation
    } else {
      const names = [...new Set(strings(body.items))]
      for (const childName of names) {
        const child = own(items, childName)
        if (!child || !['mcp', 'skill'].includes(child.kind)) throw new Error(`Packs can include only saved MCP servers and skills. ${childName} is not one.`)
      }
      item.items = names
    }
    items[name] = item
    return item
  }
  const capabilitySave = async (body, options = {}) => {
    await rt.load()
    writeCheck()
    const item = itemInput(body ?? {}, options)
    await rt.save()
    return item
  }
  rt.saveBuiltinCapabilities = async definitions => {
    await rt.load()
    writeCheck()
    for (const definition of definitions) itemInput(definition, { ui: true, builtinSeed: true })
    await rt.save()
  }
  const capabilityDelete = async (name, { botId, ui } = {}) => {
    await rt.load()
    writeCheck()
    const items = ensureLibrary()
    const item = own(items, String(name ?? ''))
    if (!item) throw new Error(`No capability named ${name}.`)
    if (!ui) editCheck(item, botId, 'delete')
    delete items[item.name]
    if (item.kind === 'skill') { state.removedSkills ??= []; if (!state.removedSkills.includes(item.name)) state.removedSkills.push(item.name) }
    for (const pack of Object.values(items)) if (pack.kind === 'pack') pack.items = (pack.items ?? []).filter(child => child !== item.name)
    for (const bot of Object.values(state.bots)) bot.capabilities = (bot.capabilities ?? []).filter(attached => attached !== item.name)
    await rt.save()
    if (item.directory) await rm(managedSkillPath(rt.home, item.directory), { recursive: true, force: true })
    return true
  }
  const changeAttachment = async (endpoint, { name, bot: targetRef }, callerId) => {
    await rt.load()
    writeCheck()
    const caller = rt.botOf(callerId)
    if (!caller) throw new Error('Only Bots on the team can change capabilities.')
    const target = targetRef ? rt.findBot(targetRef) : caller
    if (!target) throw new Error(`No Bot named ${targetRef}.`)
    if (target.id !== caller.id && !rt.isMain(callerId)) throw new Error('Only a Main Bot can change another Bot’s capabilities.')
    const item = own(ensureLibrary(), String(name ?? ''))
    if (!item) throw new Error(`No capability named ${name}.`)
    await setAttached(target, item.name, endpoint === 'attach')
    return { bot: target.name, attached: endpoint === 'attach' }
  }
  // Changes one name against the saved list, so two quick changes both land.
  const setAttached = async (bot, name, attached) => {
    bot.capabilities ??= []
    const wasEmpty = bot.capabilities.length === 0
    if (attached && !bot.capabilities.includes(name)) bot.capabilities.push(name)
    if (!attached) bot.capabilities = bot.capabilities.filter(entry => entry !== name)
    await rt.save()
    if (wasEmpty && bot.capabilities.length > 0) {
      await trackBotAgents(bot)
      void scheduleReconcile()
    }
    return bot.capabilities
  }

  const statusSet = (botId, itemName, sessionId, status) => {
    let byItem = sessionStatuses.get(botId)
    if (!byItem) sessionStatuses.set(botId, byItem = new Map())
    let bySession = byItem.get(itemName)
    if (!bySession) byItem.set(itemName, bySession = new Map())
    bySession.set(sessionId, status)
  }
  const clearStatus = (botId, itemName, sessionId) => {
    const byItem = sessionStatuses.get(botId)
    const bySession = byItem?.get(itemName)
    bySession?.delete(sessionId)
    if (bySession?.size === 0) byItem.delete(itemName)
    if (byItem?.size === 0) sessionStatuses.delete(botId)
  }
  const clearSession = sessionId => {
    ensured.delete(sessionId)
    for (const [botId, byItem] of sessionStatuses) {
      for (const [name, bySession] of byItem) {
        bySession.delete(sessionId)
        if (bySession.size === 0) byItem.delete(name)
      }
      if (byItem.size === 0) sessionStatuses.delete(botId)
    }
  }
  const statusFor = (botId, name) => {
    const values = [...(sessionStatuses.get(botId)?.get(name)?.values() ?? [])]
    if (values.some(status => status.state === 'error')) return values.find(status => status.state === 'error')
    if (values.some(status => status.state === 'needs-approval')) return { state: 'needs-approval' }
    if (values.some(status => status.state === 'connecting')) return { state: 'connecting' }
    return values.length > 0 ? { state: 'ready' } : undefined
  }
  const capabilityStatusesView = () => {
    const result = {}
    for (const bot of Object.values(state.bots)) {
      const statuses = {}
      for (const name of bot.capabilities ?? []) {
        const item = own(library(), name)
        if (!item) continue
        if (item.kind !== 'pack') {
          const status = statusFor(bot.id, name)
          if (status) statuses[name] = status
          continue
        }
        const children = (item.items ?? []).map(child => statusFor(bot.id, child)).filter(Boolean)
        const status = children.find(status => status.state === 'error')
          ?? children.find(status => status.state === 'needs-approval')
          ?? children.find(status => status.state === 'connecting')
          ?? children[0]
        if (status) statuses[name] = status
      }
      result[bot.id] = statuses
    }
    return result
  }
  const libraryView = () => Object.values(library()).map(({ content: _content, directory: _directory, sourcePath: _sourcePath, instructionFile: _instructionFile, ...item }) => ({
    ...item,
    ...(item.env ? { env: { ...item.env } } : {}),
    ...(item.headers ? { headers: { ...item.headers } } : {}),
    ...(item.items ? { items: [...item.items] } : {}),
  }))

  async function loadMcpPlugin() {
    if (!pluginPromise) {
      pluginPromise = (async () => {
        const loader = ctx.get?.('loader')
        if (typeof loader?.import !== 'function') throw new Error('This DSH cannot load MCP servers.')
        const exports = await loader.import(MCP_CLIENT)
        return loader.unwrapExports?.(exports) ?? exports?.default ?? exports
      })()
    }
    return pluginPromise
  }
  function secretFor(name, botId) {
    const value = rt.canUseSecret(name, botId) ? rt.secretValue(name) : undefined
    if (value === undefined) throw new Error(`Secret ${name} is missing or unavailable for this Bot.`)
    return value
  }
  function resolveValues(values, botId) {
    const resolved = {}
    for (const [key, raw] of Object.entries(values ?? {})) {
      resolved[key] = String(raw).replace(SECRET_REFERENCE, (_match, name) => secretFor(name, botId))
    }
    return resolved
  }
  const resolveUrl = (url, botId) => String(url).replace(SECRET_REFERENCE, (_match, name) => encodeUrlComponent(secretFor(name, botId)))
  const resolveList = (list, botId) => (list ?? []).map(raw => String(raw).replace(SECRET_REFERENCE, (_match, name) => secretFor(name, botId)))
  const definitionFor = async item => {
    const root = skillDirectoryOf(item, rt.home, packageRoot)
    const content = item.directory ? await readSkillFile(root, item.instructionFile) : item.content
    return { name: item.name, description: item.description || item.purpose || skillLabel(item), source: item.directory ? 'custom' : 'runtime',
      content: content || '', invocation: item.invocation ?? { modelInvocable: true, userInvocable: true },
      ...(root ? { path: join(root, item.instructionFile ?? 'SKILL.md'), resourceBase: { kind: 'directory', path: root } } : {}) }
  }
  const summaryFor = (item, provider, modelInvocable = false) => {
    const root = skillDirectoryOf(item, rt.home, packageRoot)
    return { name: item.name, description: item.description || item.purpose || item.name, source: 'custom', provider, rank: modelInvocable ? -1001 : -1000, locator: item.name,
      invocation: { modelInvocable: modelInvocable && item.invocation?.modelInvocable !== false, userInvocable: item.invocation?.userInvocable !== false },
      ...(root ? { path: join(root, item.instructionFile ?? 'SKILL.md'), resourceBase: { kind: 'directory', path: root } } : {}) }
  }
  const configFor = (item, botId) => {
    if (item.kind === 'skill') return { name: item.name, description: item.description, content: item.content, directory: item.directory, updatedAt: item.updatedAt, invocation: item.invocation }
    if (item.transport === 'stdio') return { transport: 'stdio', serverName: item.name, command: item.command, args: resolveList(item.args, botId), env: resolveValues(item.env, botId), failOnStartupError: true }
    return { transport: 'streamable-http', serverName: item.name, url: resolveUrl(item.url, botId), headers: resolveValues(item.headers, botId), failOnStartupError: true }
  }
  const disposeMount = async mount => {
    if (mount?.fiber) await Promise.resolve().then(() => mount.fiber.dispose()).catch(() => {})
  }
  const mountOne = async (agent, bot, agentMounts, name) => {
    const sessionId = agent.session.id
    const item = own(library(), name)
    const drop = async () => {
      await disposeMount(agentMounts.get(name))
      agentMounts.delete(name)
    }
    if (item.kind === 'mcp' && rt.connectorOwns?.(item.name, item.url)) {
      await drop()
      statusSet(bot.id, name, sessionId, rt.connectorStatus?.(item.name) ?? { state: 'off' })
      return
    }
    if (item.kind === 'mcp' && item.transport === 'streamable-http' && /^http:/i.test(item.url) && Object.keys(item.headers ?? {}).length) {
      await drop()
      statusSet(bot.id, name, sessionId, { state: 'error', error: 'Credentialed MCP requires a verified HTTPS endpoint. Configure this optional service in Connectors.' })
      return
    }
    if (item.kind === 'mcp' && item.transport === 'stdio' && item.approved !== true) {
      await drop()
      statusSet(bot.id, name, sessionId, { state: 'needs-approval' })
      return
    }
    let config
    try {
      config = configFor(item, bot.id)
    } catch (error) {
      await drop()
      statusSet(bot.id, name, sessionId, { state: 'error', error: rt.redactSecrets(error.message).slice(0, 300) })
      return
    }
    const key = `${name}:${createHash('sha256').update(JSON.stringify(config)).digest('hex')}`
    if (agentMounts.get(name)?.key === key) return
    await drop()
    statusSet(bot.id, name, sessionId, { state: 'connecting' })
    try {
      const plugin = item.kind === 'skill'
        ? {
          name: `chemclaw-bot-capability-skill-${name}`,
          inject: ['skills'],
          apply(c) {
            if (typeof c.skills.registerProvider === 'function') {
              c.effect(() => c.skills.registerProvider(control => {
                providerInvalidators.add(control.invalidate)
                control.signal.addEventListener('abort', () => providerInvalidators.delete(control.invalidate), { once: true })
                const provider = `chemclaw-assigned-${name}`
                return { name: provider, list: async () => [summaryFor(item, provider, true)],
                  get: async () => ({ ...await definitionFor(item), invocation: summaryFor(item, provider, true).invocation, provider }) }
              }))
            } else c.effect(() => c.skills.register({ name: config.name, description: config.description, source: 'runtime', content: config.content, invocation: { modelInvocable: item.invocation?.modelInvocable !== false, userInvocable: false } }))
          },
        }
        : await loadMcpPlugin()
      if (stopped) return
      const fiber = item.kind === 'skill' ? agent.ctx.plugin(plugin) : agent.ctx.plugin(plugin, config)
      agentMounts.set(name, { key, fiber })
      await fiber.await()
      if (stopped || agents.get(sessionId)?.deref() !== agent) return
      statusSet(bot.id, name, sessionId, { state: 'ready' })
    } catch (error) {
      await drop()
      const message = rt.redactSecrets([error, error?.cause].filter(Boolean).map(part => String(part?.message ?? part)).join(': ') || 'Connection failed').slice(0, 300)
      statusSet(bot.id, name, sessionId, { state: 'error', error: message })
    }
  }
  const reconcileAgent = async (agent, bot) => {
    const sessionId = agent.session.id
    const desired = bot ? expandCapabilityNames(bot.capabilities, library()) : new Set()
    const agentMounts = mounts.get(agent) ?? new Map()
    if (desired.size > 0) mounts.set(agent, agentMounts)
    if (bot) {
      for (const name of sessionStatuses.get(bot.id)?.keys() ?? []) {
        if (!desired.has(name)) clearStatus(bot.id, name, sessionId)
      }
    } else {
      clearSession(sessionId)
    }
    for (const [name, mount] of agentMounts) {
      if (desired.has(name)) continue
      await disposeMount(mount)
      agentMounts.delete(name)
    }
    await Promise.all([...desired].map(name => mountOne(agent, bot, agentMounts, name)))
    if (agentMounts.size === 0 && mounts.get(agent) === agentMounts) mounts.delete(agent)
  }
  const botOfSession = sessionId => (rt.isBotSession(sessionId) ? rt.botOf(rt.selfOf(sessionId)) : undefined)
  // At most one run waits behind the running one; it reads the latest state when it starts.
  const reconcileOne = agent => {
    if (queued.has(agent)) return chains.get(agent)
    queued.add(agent)
    const run = (chains.get(agent) ?? Promise.resolve()).then(async () => {
      queued.delete(agent)
      const sessionId = agent.session.id
      if (stopped || agents.get(sessionId)?.deref() !== agent) return
      await reconcileAgent(agent, botOfSession(sessionId))
    }).catch(error => rt.warn('chemclaw-bot: capability reconcile for %s failed: %s', agent.session?.id, error))
    chains.set(agent, run)
    return run
  }
  const loadInputs = async () => {
    await rt.load()
    loadingSecrets += 1
    try {
      await rt.loadSecrets()
    } finally {
      loadingSecrets -= 1
    }
  }
  async function reconcile() {
    if (stopped) return
    await loadInputs()
    const runs = []
    for (const [sessionId, reference] of agents) {
      const agent = reference.deref()
      if (agent) {
        runs.push(reconcileOne(agent))
        continue
      }
      agents.delete(sessionId)
      clearSession(sessionId)
    }
    await Promise.all(runs)
  }
  const scheduleReconcile = () => {
    if (!scheduled) {
      scheduled = new Promise(resolve => queueMicrotask(() => {
        scheduled = null
        resolve(reconcile().catch(error => rt.warn('chemclaw-bot: capability reconcile failed: %s', error)))
      }))
    }
    return scheduled
  }
  // A run that outlasts the limit goes on in the background, and later requests for the
  // same Agent do not wait for it again.
  const stalled = new WeakSet()
  const prepare = async (agent, sessionId) => {
    const run = loadInputs().then(() => reconcileOne(agent)).then(() => true, error => {
      rt.warn('chemclaw-bot: capability mount for %s failed: %s', sessionId, error)
      return true
    })
    if (stalled.has(agent)) return
    const timeoutMs = rt.capabilityEnsureTimeoutMs ?? ENSURE_TIMEOUT_MS
    let timer
    const completed = await Promise.race([run, new Promise(resolve => { timer = setTimeout(resolve, timeoutMs, false) })])
    clearTimeout(timer)
    if (completed) return
    stalled.add(agent)
    void run.then(() => stalled.delete(agent))
    rt.warn('chemclaw-bot: capability mount for %s did not finish within %dms; continuing', sessionId, timeoutMs)
  }
  // Skip re-prepare when this Session already mounted the same capability set (warm /
  // prior send). Cleared via clearSession; signature miss when the list changes.
  async function ensureCapabilities(sessionId) {
    await rt.load()
    const bot = botOfSession(sessionId)
    if (!bot) return
    if ((bot.capabilities ?? []).length === 0 && !mounts.get(agents.get(sessionId)?.deref())?.size) {
      ensured.set(sessionId, '[]')
      return
    }
    const signature = JSON.stringify(bot.capabilities ?? [])
    if (ensured.get(sessionId) === signature) return
    let agent
    try {
      agent = await rt.resolveAgent(sessionId)
    } catch (error) {
      rt.warn('chemclaw-bot: capability Agent for %s could not be resolved: %s', sessionId, rt.redactSecrets(String(error)))
      return
    }
    trackAgent(agent)
    await prepare(agent, sessionId)
    ensured.set(sessionId, signature)
  }
  const trackAgent = agent => {
    const sessionId = agent?.session?.id
    if (typeof sessionId !== 'string' || !agent.ctx) return
    if (agents.get(sessionId)?.deref() === agent) return
    agents.set(sessionId, new WeakRef(agent))
    agent.ctx.effect(() => () => {
      if (agents.get(sessionId)?.deref() === agent) agents.delete(sessionId)
      clearSession(sessionId)
      for (const mount of mounts.get(agent)?.values() ?? []) void disposeMount(mount)
      mounts.delete(agent)
    }, `chemclaw-bot: capabilities ${sessionId}`)
  }
  const trackBotAgents = async bot => {
    const sessionIds = new Set()
    try {
      const sessionId = rt.chatOf(bot.id)
      if (typeof sessionId === 'string') sessionIds.add(sessionId)
    } catch (error) {
      rt.warn('chemclaw-bot: capability chat session for %s could not be read: %s', bot.id, error)
    }
    try {
      for (const sessionId of rt.groupSessionsOf(bot.id) ?? []) {
        if (typeof sessionId === 'string') sessionIds.add(sessionId)
      }
    } catch (error) {
      rt.warn('chemclaw-bot: capability group sessions for %s could not be read: %s', bot.id, error)
    }
    for (const sessionId of sessionIds) {
      try {
        trackAgent(await rt.resolveAgent(sessionId))
      } catch (error) {
        rt.warn('chemclaw-bot: capability Agent for %s could not be resolved: %s', sessionId, error)
      }
    }
  }

  async function capabilityEndpoint(endpoint, body = {}) {
    if (endpoint === 'skill-catalog') { await rt.load(); return { items: libraryView().filter(item => item.kind === 'skill'), revision: state.revision } }
    if (endpoint === 'skill-reset') {
      await rt.load(); writeCheck()
      const item = own(library(), String(body.name))
      if (item?.builtinSource !== 'chemclaw') throw new Error('Only a built-in skill can be restored.')
      await ensureSkillLibrary(rt, { reset: item.name })
      return true
    }
    if (endpoint === 'capability-detail') {
      await rt.load()
      const item = own(ensureLibrary(), String(body.name ?? ''))
      if (!item) throw new Error('Unknown capability')
      if (item.kind !== 'skill') return { ...item }
      const root = skillDirectoryOf(item, rt.home, packageRoot)
      const definition = await definitionFor(item)
      const files = root ? await skillFiles(root) : [{ path: 'SKILL.md', bytes: Buffer.byteLength(item.content ?? '') }]
      const python = files.some(file => file.path.endsWith('.py'))
      const managedPython = python && await stat(join(rt.home, 'runtime/python', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')).then(info => info.isFile(), () => false)
      return { ...item, content: definition.content, files,
        usedBy: Object.values(state.bots).filter(bot => expandCapabilityNames(bot.capabilities, library()).has(item.name)).map(bot => ({ id: bot.id, name: bot.name })),
        dependencies: { state: python && !managedPython ? 'needs-setup' : root ? 'unchecked' : 'ready',
          manifests: files.filter(file => /(^|\/)(requirements[^/]*\.txt|pyproject\.toml|package\.json)$/.test(file.path)).map(file => file.path),
          message: python && !managedPython ? 'Python scripts are included. Managed Python is not installed; a compatible system Python may also be used.' : root ? 'Resources are installed. Script dependencies are checked when the task needs them.' : 'Inline instructions need no additional installation.' } }
    }
    if (endpoint === 'capability-save') return capabilitySave(body, { ui: true })
    if (endpoint === 'capability-delete') return capabilityDelete(body.name, { ui: true })
    if (endpoint === 'capability-approve') {
      await rt.load()
      writeCheck()
      const item = own(library(), String(body.name ?? ''))
      if (!item || item.kind !== 'mcp' || item.transport !== 'stdio') throw new Error(`No unapproved stdio MCP named ${body.name}.`)
      item.approved = true
      item.updatedAt = Date.now()
      await rt.save()
      return item
    }
    if (endpoint === 'bot-capability') {
      await rt.load()
      writeCheck()
      const bot = rt.botOf(String(body.botId ?? ''))
      if (!bot) throw new Error('Unknown Bot')
      const name = String(body.name ?? '')
      if (!own(library(), name)) throw new Error(`No capability named ${name}.`)
      return setAttached(bot, name, body.attached === true)
    }
    throw new Error('Unknown capability operation.')
  }
  const secretsChanged = rt.secretsChanged
  rt.secretsChanged = () => {
    secretsChanged?.()
    if (loadingSecrets === 0) void scheduleReconcile()
  }
  const providerInvalidators = new Set()
  rt.capabilitiesStateSaved = () => { for (const invalidate of providerInvalidators) invalidate(); void scheduleReconcile() }
  const userCatalogs = new Map()
  async function ensureUserSkillCatalog(agent) {
    const registry = agent.ctx?.get?.('skills') ?? ctx.get?.('skills')
    if (typeof registry?.registerProvider !== 'function' || !agent.ctx?.plugin) return false
    if (userCatalogs.has(agent)) { await userCatalogs.get(agent).await(); return true }
    const fiber = agent.ctx.plugin({ name: 'chemclaw-user-skills', inject: ['skills'], apply(c) {
      c.effect(() => c.skills.registerProvider(control => {
        providerInvalidators.add(control.invalidate)
        control.signal.addEventListener('abort', () => providerInvalidators.delete(control.invalidate), { once: true })
        return { name: 'chemclaw-user-skills', list: async () => Object.values(library()).filter(item => item.kind === 'skill').map(item => summaryFor(item, 'chemclaw-user-skills')),
          get: async candidate => {
            const item = own(library(), candidate.name)
            return item?.kind === 'skill' ? { ...await definitionFor(item), provider: 'chemclaw-user-skills', invocation: summaryFor(item, 'chemclaw-user-skills').invocation } : undefined
          } }
      }))
    } })
    userCatalogs.set(agent, fiber)
    agent.ctx.effect(() => () => { userCatalogs.delete(agent) }, 'chemclaw-bot: user skill catalog')
    await fiber.await()
    return true
  }
  // Creation waits for these listeners, so a new Agent's first request already has its
  // tools and skill catalog. agent/pre-step is too late: a step assembles its tools first.
  ctx.on('agent/created', async function prepareCapabilities({ agent }) {
    trackAgent(agent)
    try {
      await rt.load()
      const bot = botOfSession(agent.session.id)
      if (bot || rt.roomOf(agent.session.id)) await ensureUserSkillCatalog(agent)
      if ((bot?.capabilities ?? []).length > 0) await prepare(agent, agent.session.id)
    } catch (error) {
      rt.warn('chemclaw-bot: capability load failed: %s', error)
    }
  })
  ctx.effect(() => {
    void rt.load().then(async () => {
      const registry = ctx.get?.('agents')
      for (const bot of Object.values(state.bots)) {
        if (bot.templateId && typeof registry?.get === 'function') {
          for (const id of [rt.chatOf(bot.id), ...rt.groupSessionsOf(bot.id)]) {
            const agent = registry.get(id)
            if (agent) trackAgent(agent)
          }
          continue
        }
        if ((bot.capabilities ?? []).length > 0) await trackBotAgents(bot)
      }
      await scheduleReconcile()
    }).catch(error => rt.warn('chemclaw-bot: capability startup failed: %s', error))
    return async () => {
      stopped = true
      const live = [...mounts.values()]
      await Promise.all([...userCatalogs.values()].map(fiber => fiber.dispose()))
      userCatalogs.clear()
      mounts.clear()
      agents.clear()
      sessionStatuses.clear()
      await Promise.all(live.flatMap(agentMounts => [...agentMounts.values()].map(disposeMount)))
    }
  }, 'chemclaw-bot: capabilities')
  Object.assign(rt, {
    capabilitySave,
    capabilityDelete,
    capabilityEndpoint,
    capabilityLibraryView: libraryView,
    capabilityStatusesView,
    skillDefinition: name => {
      const item = own(library(), name)
      if (item?.kind !== 'skill') throw new Error(`Skill ${name} is no longer installed.`)
      return definitionFor(item)
    },
    validateSkillName: validateCapabilityName,
    ensureUserSkillCatalog,
    reconcileCapabilities: reconcile,
    scheduleCapabilitiesReconcile: scheduleReconcile,
    ensureCapabilities,
    expandCapabilities: names => expandCapabilityNames(names, library()),
    changeCapabilityAttachment: changeAttachment,
  })
}
