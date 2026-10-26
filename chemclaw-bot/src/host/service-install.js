import { createHash, randomUUID } from 'node:crypto'
import { validateCapabilityName } from './capabilities.js'
import { CHEM_CONNECTORS } from '../shared/connectors.js'

const map = value => {
  let result
  try { result = typeof value === 'string' ? JSON.parse(value || '{}') : value ?? {} } catch { throw new Error('Check the configuration JSON syntax.') }
  if (!result || typeof result !== 'object' || Array.isArray(result) || Object.values(result).some(value => typeof value !== 'string')) throw new Error('Configuration fields must contain text values.')
  return result
}
const reference = /^\$DSH_SECRET_[A-Z][A-Z0-9_]*$/
const sensitive = /key|token|password|secret|credential|authorization/i

export function parseServiceDraft(body) {
  let entries
  if (body.mode === 'json') {
    let doc
    try { doc = JSON.parse(body.json) } catch { throw new Error('Check the configuration JSON syntax.') }
    if (!doc?.mcpServers || typeof doc.mcpServers !== 'object' || Array.isArray(doc.mcpServers)) throw new Error('Expected mcpServers JSON')
    entries = Object.entries(doc.mcpServers).map(([name, config]) => ({ ...config, name }))
  } else entries = [{ name: body.name, description: body.description, url: body.url, command: body.mode === 'stdio' ? body.command : undefined,
    args: String(body.args ?? '').split('\n').filter(Boolean), env: map(body.env), headers: { ...map(body.headers), ...(body.key ? { Authorization: `Bearer ${body.key}` } : {}) } }]
  if (!entries.length || entries.length > 20) throw new Error('Import between 1 and 20 servers')
  const seen = new Set()
  return entries.map(value => {
    if (!value || typeof value !== 'object') throw new Error('Invalid tool service configuration.')
    const name = validateCapabilityName(value.name)
    if (seen.has(name)) throw new Error('Import each MCP service only once')
    seen.add(name)
    const secrets = []
    const keep = (label, raw) => {
      if (reference.test(raw)) return raw
      if (String(raw).includes('$DSH_SECRET_')) {
        if (raw.replace(/\$DSH_SECRET_[A-Z][A-Z0-9_]*/g, '').includes('$DSH_SECRET_')) throw new Error('Invalid credential reference.')
        return raw
      }
      if (raw.length < 4) throw new Error('Credential values must contain at least four characters.')
      const secret = `MCP_${createHash('sha256').update(`${name}:${label}`).digest('hex').slice(0, 24).toUpperCase()}`
      secrets.push({ name: secret, value: raw, purpose: `${name} ${label}` })
      return `$DSH_SECRET_${secret}`
    }
    const fields = (values, headers = false) => Object.fromEntries(Object.entries(map(values)).map(([key, raw]) => {
      if (!/^[\w-]+$/.test(key)) throw new Error('Use valid environment variable or header names.')
      const staticEnv = /^(MODE|NODE_ENV|LANG|LC_ALL|TZ|PATH|PYTHONPATH|PORT|HOST|LOG_LEVEL)$/i.test(key)
      return [key, raw && (headers || sensitive.test(key) || (!staticEnv && raw.length >= 4)) ? keep(key, raw) : raw]
    }))
    const item = { id: name, name, description: String(value.description ?? 'Custom tool service').slice(0, 2000), generic: true, anonymous: true }
    if (value.command) {
      if (typeof value.command !== 'string' || /[\r\n\x00]/.test(value.command)) throw new Error('Enter one executable command.')
      if (value.args !== undefined && (!Array.isArray(value.args) || value.args.some(arg => typeof arg !== 'string'))) throw new Error('Arguments must be a list of text values.')
      const args = [...(value.args ?? [])]
      for (let index = 0; index < args.length; index++) {
        const flag = args[index].match(/^--?([^=]+)(?:=(.*))?$/)
        if (!flag || !sensitive.test(flag[1])) continue
        if (flag[2] !== undefined) args[index] = `${args[index].slice(0, args[index].indexOf('='))}=${keep(`arg-${index}`, flag[2])}`
        else if (args[index + 1] !== undefined) { args[index + 1] = keep(`arg-${index + 1}`, args[index + 1]); index++ }
      }
      Object.assign(item, { transport: 'stdio', command: value.command.trim(), args, env: fields(value.env) })
    } else {
      let url
      try { url = new URL(value.url) } catch { throw new Error('Enter a valid HTTPS service address.') }
      if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash) throw new Error('MCP addresses must use HTTPS without credentials, query or fragment in the URL')
      Object.assign(item, { transport: 'streamable-http', url: url.href, headers: fields(value.headers, true) })
    }
    return { item, secrets }
  })
}

export function install(rt) {
  const previews = new Map()
  rt.serviceEndpoint = async (endpoint, body) => {
    for (const [key, value] of previews) if (value.expires < Date.now()) previews.delete(key)
    if (endpoint === 'service-cancel') { previews.delete(body.token); return true }
    if (endpoint === 'service-preview') {
      if (rt.config.companyConnectors === false) throw new Error('Tool services are disabled in this profile.')
      const entries = parseServiceDraft(body)
      for (const { item } of entries) {
        const existing = rt.connectorsView().find(entry => entry.id === item.id || (item.url && entry.url === item.url))
        if (existing || CHEM_CONNECTORS.some(entry => entry.id === item.id) || item.id === 'github') throw new Error('This service already exists. Configure it in Connectors.')
      }
      if (previews.size >= 4) throw new Error('Finish or cancel the other service setups first.')
      const token = randomUUID()
      previews.set(token, { entries, expires: Date.now() + 10 * 60 * 1000 })
      return { token, items: entries.map(({ item, secrets }) => ({ name: item.name, description: item.description, transport: item.transport, ...(item.url ? { url: item.url } : { command: item.command }), credentials: secrets.length })) }
    }
    if (endpoint !== 'service-save') throw new Error('Unknown service operation.')
    const preview = previews.get(body.token)
    if (!preview) throw new Error('This service preview expired. Review the configuration again.')
    await rt.loadSecrets()
    for (const { item } of preview.entries) {
      if (rt.connectorsView().some(entry => entry.id === item.id || (item.url && entry.url === item.url))) throw new Error('This service already exists. Configure it in Connectors.')
    }
    rt.state.customConnectors ??= {}
    rt.state.connectors ??= {}
    for (const { item, secrets } of preview.entries) {
      for (const secret of secrets) await rt.secretEndpoint('secret-set', { ...secret, scope: [] })
      rt.state.customConnectors[item.id] = item
      rt.state.connectors[item.id] = { disabled: false }
    }
    await rt.save()
    previews.delete(body.token)
    await Promise.all(preview.entries.map(({ item }) => rt.connectorEndpoint('connector-retry', { id: item.id })))
    return rt.connectorsView()
  }
  rt.ctx.effect(() => () => previews.clear(), 'chemclaw-bot: service preview cleanup')
}
