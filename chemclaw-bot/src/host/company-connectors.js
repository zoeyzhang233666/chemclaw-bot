import { CHEM_CONNECTORS, parseMcpImport } from '../shared/connectors.js'
import { createHash } from 'node:crypto'

export function install(rt) {
  if (rt.config.companyConnectors === false) return
  const { ctx, state } = rt
  const githubView = rt.connectorsView
  const githubEndpoint = rt.connectorEndpoint
  const githubChanged = rt.secretsChanged
  const mounts = new Map()
  const statuses = new Map()
  const queues = new Map()
  let stopped = false
  const publicTools = new Set(['search_chemistry_data', 'get_chemical', 'get_reaction', 'render_molecule_svg', 'render_reaction_svg', 'list_skills', 'get_skill', 'calculate_stoichiometry'])
  ctx.tools.guard(exec => {
    if (!exec.name.startsWith('mcp__huagongshe__')) return
    const raw = exec.name.slice('mcp__huagongshe__'.length)
    if (!publicTools.has(raw)) return 'ChemClaw uses Huagongshe public read-only tools. Private data and write operations are disabled.'
    if (raw === 'search_chemistry_data' && /similarity|substructure/i.test(JSON.stringify(exec.args ?? exec.arguments ?? {}))) return 'Structure similarity requires separately authorized access.'
  })
  const definitions = () => [...CHEM_CONNECTORS, ...Object.values(state.customConnectors ?? {})]
  const reason = error => rt.redactSecrets([error?.message, error?.cause?.message].filter(Boolean).join(': ') || 'Connection failed').slice(0, 300)
  ctx.on('tools/execute', async (exec, next) => {
    const def = definitions().find(item => exec.name.startsWith(`mcp__${item.id}__`))
    if (!def) return next()
    try {
      const result = await next()
      if (mounts.get(def.id)?.fiber) statuses.set(def.id, result?.isError ? { state: 'error', error: reason(result.error) } : { state: 'ready' })
      return result
    } catch (error) { statuses.set(def.id, { state: 'error', error: reason(error) }); throw error }
  })
  const dispose = async id => {
    const mount = mounts.get(id)
    mounts.delete(id)
    await mount?.fiber?.dispose()
  }
  async function reconcile(def, force) {
    const token = rt.secretValue(def.secret)
    const enabled = !stopped && state.connectors?.[def.id]?.disabled !== true && (def.anonymous || token !== undefined)
    const previous = mounts.get(def.id)
    const signature = def.generic ? createHash('sha256').update(JSON.stringify(def) + Object.values({ ...def.env, ...def.headers }).map(value => String(value).replace(/\$DSH_SECRET_([A-Z][A-Z0-9_]*)/g, (_match, name) => rt.secretValue(name) ?? '')).join('\n')).digest('hex') : undefined
    if (!force && previous?.token === token && previous?.enabled === enabled && previous?.signature === signature) return
    await dispose(def.id)
    if (!enabled) { statuses.set(def.id, { state: 'off' }); return }
    statuses.set(def.id, { state: 'connecting' })
    try {
      if (def.transport !== 'stdio' && !def.url.startsWith('https://')) throw new Error('MCP addresses must use HTTPS')
      const resolve = value => String(value).replace(/\$DSH_SECRET_([A-Z][A-Z0-9_]*)/g, (_match, name) => {
        const secret = rt.secretValue(name)
        if (secret === undefined) throw new Error(`Secret ${name} is missing. Configure this service in Connectors.`)
        return secret
      })
      const fields = values => Object.fromEntries(Object.entries(values ?? {}).map(([key, value]) => [key, resolve(value)]))
      const loader = ctx.get?.('loader')
      if (!loader?.import || !ctx.plugin) throw new Error('This DSH cannot load connectors')
      const exports = await loader.import('@deepseek-ai/dsh-mcp-client')
      if (stopped) return
      const plugin = loader.unwrapExports?.(exports) ?? exports.default ?? exports
      const config = def.transport === 'stdio' ? { transport: 'stdio', command: def.command, args: (def.args ?? []).map(resolve), env: fields(def.env) }
        : { transport: 'streamable-http', url: def.url, headers: def.generic ? fields(def.headers) : token ? { Authorization: `Bearer ${token}` } : {} }
      const fiber = ctx.plugin(plugin, { ...config, serverName: def.id, failOnStartupError: true, toolCallTimeoutMs: 30_000 })
      mounts.set(def.id, { token, enabled, signature, fiber })
      let timer
      try {
        await Promise.race([fiber.await(), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Connection timed out')), rt.config.connectorTimeoutMs ?? 20_000) })])
      } finally { clearTimeout(timer) }
      if (!stopped && mounts.get(def.id)?.fiber === fiber) statuses.set(def.id, { state: 'ready' })
    } catch (error) {
      await dispose(def.id).catch(() => {})
      mounts.set(def.id, { token, enabled, signature })
      statuses.set(def.id, { state: 'error', error: reason(error) })
    }
  }
  function sync(def, force = false) {
    const pending = (queues.get(def.id) ?? Promise.resolve()).then(() => reconcile(def, force)).catch(error => {
      statuses.set(def.id, { state: 'error', error: reason(error) })
    })
    queues.set(def.id, pending)
    return pending
  }
  rt.connectorsView = () => [...githubView(), ...definitions().map(def => ({
    id: def.id, name: def.name, description: def.description, url: def.url, tokenUrl: def.tokenUrl,
    anonymous: Boolean(def.anonymous), authenticated: rt.secretValue(def.secret) !== undefined,
    ...(def.generic ? { generic: true, transport: def.transport } : {}),
    ...(statuses.get(def.id) ?? { state: 'off' }),
  }))]
  rt.connectorOwns = (id, url) => definitions().some(def => def.id === id || (url && def.url === url))
  rt.connectorStatus = id => statuses.get(id) ?? { state: 'off' }
  // Restore saved connections in the background; opening Settings is not required.
  let mountedOnce = false
  let ensureJob = null
  rt.ensureCompanyConnectors = () => {
    if (rt.config.companyConnectors === false || stopped) return Promise.resolve()
    if (ensureJob) return ensureJob
    ensureJob = (async () => {
      await rt.load()
      await rt.loadSecrets()
      if (stopped || rt.readOnly()) return
      mountedOnce = true
      for (const def of definitions()) {
        if (rt.secretValue(def.secret) !== undefined) {
          await rt.secretEndpoint('secret-update', { name: def.secret, scope: [] }).catch(() => {})
        }
        if (!stopped) void sync(def)
      }
      await Promise.allSettled(queues.values())
    })().catch(error => { if (!stopped) rt.warn('ChemClaw connector ensure: %s', reason(error)) })
      .finally(() => { ensureJob = null })
    return ensureJob
  }
  rt.secretsChanged = () => { githubChanged?.(); if (mountedOnce) for (const def of definitions()) void sync(def) }
  rt.connectorEndpoint = async (endpoint, body) => {
    if (endpoint === 'connector-import' || endpoint === 'connector-connect'
      || endpoint === 'connector-retry' || endpoint === 'connector-disconnect') {
      await rt.ensureCompanyConnectors()
    }
    if (endpoint === 'connector-import') {
      const imported = parseMcpImport(body.json)
      const skipped = imported.skipped ?? []
      for (const entry of imported) {
        const named = definitions().find(def => def.id === entry.id)
        if (entry.id === 'github' || (named && named.url !== entry.url)) throw new Error('A saved connector address cannot be replaced; use a new service name')
        const existing = definitions().find(def => def.url === entry.url)
        if (existing) entry.id = existing.id
      }
      if (new Set(imported.map(entry => entry.id)).size !== imported.length) throw new Error('Import each MCP service only once')
      // Validate the complete document before storing any configuration or key.
      for (const entry of imported) {
        const preset = CHEM_CONNECTORS.find(def => def.id === entry.id)
        if (entry.id === 'github' || (preset && preset.url !== entry.url)) throw new Error('A built-in connector address cannot be replaced')
      }
      state.customConnectors ??= {}
      for (const entry of imported) {
        const preset = CHEM_CONNECTORS.find(def => def.id === entry.id)
        const secret = preset?.secret ?? state.customConnectors[entry.id]?.secret ?? `MCP_${createHash('sha256').update(entry.id).digest('hex').slice(0, 24).toUpperCase()}`
        if (!preset) state.customConnectors[entry.id] = { id: entry.id, name: entry.id, url: entry.url, secret, anonymous: !entry.token, description: 'Custom MCP connector' }
        if (entry.token) await rt.secretEndpoint('secret-set', { name: secret, value: entry.token, purpose: entry.id, scope: [] })
        state.connectors ??= {}
        state.connectors[entry.id] = { disabled: entry.disabled }
      }
      await rt.save()
      await Promise.all(imported.map(entry => sync(definitions().find(def => def.id === entry.id), true)))
      const view = rt.connectorsView()
      if (skipped.length) view.skipped = skipped
      return view
    }
    const def = definitions().find(item => item.id === body.id)
    if (!def) return githubEndpoint(endpoint, body)
    await rt.loadSecrets()
    state.connectors ??= {}
    if (endpoint === 'connector-disconnect') {
      state.connectors[def.id] = { disabled: true }
      if (rt.secretValue(def.secret) !== undefined) await rt.secretEndpoint('secret-delete', { name: def.secret })
    } else if (endpoint === 'connector-connect') {
      const token = typeof body.token === 'string' ? body.token.trim() : ''
      if (!token && !def.anonymous) throw new Error('Paste a token first')
      state.connectors[def.id] = { disabled: false }
      if (token) await rt.secretEndpoint('secret-set', { name: def.secret, value: token, purpose: def.name, scope: [] })
    } else if (endpoint !== 'connector-retry') throw new Error('No such connector action')
    await rt.save()
    await sync(def, true)
    return rt.connectorsView()
  }
  ctx.effect(() => {
    const startup = rt.ensureCompanyConnectors()
    return async () => {
      stopped = true
      await startup
      await ensureJob
      await Promise.allSettled([...mounts.keys()].map(dispose))
      await Promise.allSettled(queues.values())
    }
  }, 'chemclaw-bot: company connectors')
}
