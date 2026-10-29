// Model providers and their API keys, for a window that has no DSH Models page of its
// own. DSH keeps all of it: a provider route in the settings of the adapter that serves
// it, the route's key in DSH's credential store under the reference the route names.
// The providers to add are the ones DSH's directory of configurable providers offers.

import { APIHUB, OPENCODE_GO } from '../shared/model-providers.js'

const PI_AI = 'llm-pi-ai'
const ROUTE_ID = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/
// The wire protocols DSH's pi-ai adapter serves on a route it ships nothing about.
export const PROTOCOLS = ['openai-completions', 'openai-responses', 'anthropic-messages']
const MAX_MODELS = 500

// The reference DSH's own Models page derives for a route's key, so a provider added
// here and one added there read the same key.
export const keyRefFor = provider => `${provider.toUpperCase().replace(/[^A-Z0-9]+/g, '_')}_API_KEY`

const invalid = message => Object.assign(new Error(message), { code: 'bot/invalid' })

// What an HTTP header can carry, like DSH's own key check: a pasted `NAME=value` line
// or a quoted value would be stored as the key and refused by the provider.
export function checkKey(value) {
  const key = typeof value === 'string' ? value.trim() : ''
  if (key === '') throw invalid('Enter the API key')
  if (/^[A-Za-z_][A-Za-z0-9_]*=[^=]/.test(key)) throw invalid('Paste only the key, not a NAME=value line')
  if (/^(["']).*\1$/.test(key)) throw invalid('Paste the key without quotes')
  if (!/^[\x21-\x7E]+$/.test(key)) throw invalid('An API key has no spaces or special characters')
  return key
}

function checkEndpoint(value) {
  const text = typeof value === 'string' ? value.trim() : ''
  let url
  try { url = new URL(text) } catch { throw invalid('Enter the endpoint as an http or https address') }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') throw invalid('Enter the endpoint as an http or https address')
  return text
}

// A model as the route stores it: what discovery told about it, under pi-ai's names.
function modelEntry(model) {
  const id = typeof model === 'string' ? model.trim() : typeof model?.id === 'string' ? model.id.trim() : ''
  if (id === '') throw invalid('Every model needs an id')
  const whole = value => (Number.isInteger(value) && value > 0 ? value : undefined)
  return {
    id,
    ...(typeof model?.name === 'string' && model.name.trim() !== '' ? { name: model.name.trim() } : {}),
    ...(whole(model?.contextWindow) ? { contextWindow: model.contextWindow } : {}),
    ...(whole(model?.maxTokens) ? { maxTokens: model.maxTokens } : {}),
    ...(inputOf(model) ? { input: [...inputOf(model)] } : {}),
  }
}

function inputOf(model) {
  const input = model?.inputModalities ?? model?.input
  return Array.isArray(input) && input.length > 0 && input.every(kind => kind === 'text' || kind === 'image') ? input : undefined
}

export function install(rt) {
  const { ctx } = rt

  const seams = () => {
    const settings = ctx.get?.('settings')
    const credentials = ctx.get?.('credentials')
    return settings && credentials && ctx.llm.listConfigurableProviders ? { settings, credentials } : undefined
  }
  const usable = () => {
    const found = seams()
    if (found === undefined) throw invalid('This DSH cannot set up model providers')
    return found
  }
  const sections = settings => new Map(settings.describe({ redactSecrets: true }).map(section => [section.ns, section]))
  const profileOf = (entry, map, layer = 'value') => entry.settingsPath.reduce((value, key) => value?.[key], map.get(entry.settingsNs)?.[layer])
  const refOf = profile => (typeof profile?.apiKeyEnv === 'string' && profile.apiKeyEnv !== '' ? profile.apiKeyEnv : undefined)
  const entryOf = provider => ctx.llm.listConfigurableProviders().find(entry => entry.provider === provider)

  let preparing
  function prepareProviderRoutes() {
    if (preparing) return preparing
    preparing = (async () => {
      await restoreOpenCodeGo()
      await restoreApiHubInputs()
    })().finally(() => { preparing = undefined })
    return preparing
  }

  let nativeInputs
  ctx.on?.('llm/adapters-updated', () => { nativeInputs = undefined })
  // Catalog discovery is documented to be local and to retain modalities. Endpoint
  // discovery in older DSH drops them; only an exact, unambiguous catalog ID fills a gap.
  function catalogInputs() {
    return nativeInputs ??= (async () => {
      const entries = ctx.llm.listConfigurableProviders().filter(entry => entry.settingsNs === PI_AI && entry.declared === false)
      const replies = await Promise.allSettled(entries.map(entry => ctx.llm.discoverModels(PI_AI, { provider: entry.provider })))
      const inputs = new Map()
      for (const reply of replies) {
        if (reply.status !== 'fulfilled') continue
        for (const model of reply.value) {
          const input = inputOf(model)
          if (!input) continue
          const previous = inputs.get(model.id)
          if (previous === null) continue
          inputs.set(model.id, previous && [...previous].sort().join() !== [...input].sort().join() ? null : input)
        }
      }
      return inputs
    })().catch(error => { nativeInputs = undefined; throw error })
  }

  async function apiHubInputs(models) {
    if (!models.some(model => inputOf(model) === undefined)) return models
    const inputs = await catalogInputs()
    return models.map(model => {
      if (inputOf(model)) return model
      const input = inputs.get(typeof model === 'string' ? model : model?.id)
      return input ? { ...(typeof model === 'string' ? { id: model } : model), input: [...input] } : model
    })
  }

  async function restoreApiHubInputs() {
    const found = seams()
    if (!found) return
    const entry = entryOf(APIHUB.id)
    if (entry?.settingsNs !== PI_AI) return
    const map = sections(found.settings)
    const profile = profileOf(entry, map)
    if (profile?.api !== APIHUB.api || profile.baseURL?.replace(/\/+$/, '') !== APIHUB.baseURL || !Array.isArray(profile.models)) return
    const models = await apiHubInputs(profile.models)
    if (models.every((model, index) => model === profile.models[index])) return
    // Discovery can yield while a settings editor saves; never write a stale route.
    const latest = sections(found.settings)
    if (latest.get(PI_AI)?.revision !== map.get(PI_AI)?.revision) return
    await found.settings.mutate(PI_AI, [{ op: 'set', path: entry.settingsPath, value: { ...profile, models } }], map.get(PI_AI)?.revision)
    rt.dropCatalog()
  }

  async function restoreOpenCodeGo() {
    const found = seams()
    if (!found) return
    const entry = entryOf(OPENCODE_GO.id)
    if (entry?.settingsNs !== PI_AI || entry.declared !== false) return
    const map = sections(found.settings)
    const profile = profileOf(entry, map)
    const base = profileOf(entry, map, 'base')
    if (base?.api !== undefined || base?.baseURL !== undefined || base?.models !== undefined) return
    if (profile?.displayName !== OPENCODE_GO.name || profile.api !== OPENCODE_GO.api
      || profile.baseURL !== OPENCODE_GO.baseURL) return
    const selected = Object.values(rt.state.bots ?? {}).map(bot => bot.model).filter(ref => ref?.startsWith(`${OPENCODE_GO.id}/`))
    const defaultModel = ctx.get('agentDefaultModel')?.currentSelection?.()
    if (defaultModel?.provider === OPENCODE_GO.id) selected.push(`${OPENCODE_GO.id}/${defaultModel.model}`)
    if (selected.length) {
      const models = new Set((await ctx.llm.discoverModels(PI_AI, { provider: OPENCODE_GO.id })).map(model => model.id))
      const missing = selected.find(ref => !models.has(ref.slice(OPENCODE_GO.id.length + 1)))
      if (missing) throw invalid(`Update DSH: its OpenCode Go catalog does not include ${missing}. The provider has not been changed.`)
    }
    // An explicit protocol bypasses the catalog provider's session-header wrapper.
    // Its models also need their native protocol and endpoint from that catalog.
    const { api: _api, baseURL: _base, models: _models, ...native } = profile
    await found.settings.mutate(PI_AI, [{ op: 'set', path: entry.settingsPath, value: native }], map.get(PI_AI)?.revision)
    rt.dropCatalog()
  }

  // Per provider route, the credential its DSH settings name as its API key. A
  // provider with none authenticates some other way.
  function keyRefs() {
    const found = seams()
    if (found === undefined) return new Map()
    const map = sections(found.settings)
    const refs = new Map()
    for (const entry of ctx.llm.listConfigurableProviders()) {
      const ref = refOf(profileOf(entry, map))
      if (ref !== undefined) refs.set(entry.provider, ref)
    }
    return refs
  }

  async function missingKeys(providers) {
    let refs
    try { refs = keyRefs() } catch { return new Set() }
    const missing = new Set()
    await Promise.all(providers.filter(id => refs.has(id)).map(async (id) => {
      const info = await seams().credentials.describe(refs.get(id)).catch(() => undefined)
      if (info?.configured === false) missing.add(id)
    }))
    return missing
  }

  // The providers set up in DSH, with their models and key state, and the ones DSH
  // can add. A provider with no key and no models (DeepSeek's account route before a
  // sign-in) is left out.
  async function providersView() {
    const found = seams()
    if (found === undefined) return { available: false }
    await prepareProviderRoutes()
    const map = sections(found.settings)
    const catalog = await rt.catalog({ fresh: true })
    const providers = []
    const addable = []
    for (const entry of ctx.llm.listConfigurableProviders()) {
      const profile = profileOf(entry, map)
      if (entry.settingsNs === PI_AI && profile === undefined) {
        if (entry.declared !== true) addable.push({ id: entry.provider, name: entry.displayName })
        continue
      }
      const ref = refOf(profile)
      const models = catalog.filter(model => model.provider === entry.provider).map(model => ({ ref: model.ref, name: model.name }))
      if (ref === undefined && models.length === 0 && entry.error === undefined) continue
      const info = ref === undefined ? undefined : await found.credentials.describe(ref).catch(() => undefined)
      providers.push({
        id: entry.provider,
        name: entry.displayName,
        models,
        key: ref === undefined ? null : { configured: info?.configured === true, writable: info?.writable !== false },
        removable: entry.settingsNs === PI_AI && profileOf(entry, map, 'user') !== undefined && profileOf(entry, map, 'base') === undefined,
        custom: entry.declared === true,
        ...(entry.error ? { error: entry.error } : {}),
      })
    }
    // ChemClaw's OpenCode Go route is not in DSH's directory; offer it until set up.
    if (!providers.some(item => item.id === OPENCODE_GO.id) && !addable.some(item => item.id === OPENCODE_GO.id)) {
      addable.push({ id: OPENCODE_GO.id, name: OPENCODE_GO.name })
    }
    // The ones that come with the setup first, then the added ones as DSH lists them.
    providers.sort((a, b) => Number(b.id === APIHUB.id) - Number(a.id === APIHUB.id) || Number(a.removable) - Number(b.removable))
    return { available: true, providers, addable, protocols: PROTOCOLS, featured: APIHUB }
  }

  async function writableRef(provider) {
    const ref = keyRefs().get(provider)
    if (ref === undefined) throw invalid(`${provider} takes no API key here`)
    if ((await usable().credentials.describe(ref)).writable === false) throw invalid(`The API key for ${provider} is set outside ChemClaw and cannot be changed here`)
    return ref
  }

  // A key is only ever written; nothing here reads one back.
  async function setProviderKey(provider, value) {
    const key = checkKey(value)
    await usable().credentials.set(await writableRef(provider), key)
    rt.dropCatalog()
  }

  async function clearProviderKey(provider) {
    await usable().credentials.unset(await writableRef(provider))
    rt.dropCatalog()
  }

  // `provider` from DSH's directory, ChemClaw's OpenCode Go preset, or a route the user
  // declares (`custom`) for an endpoint DSH ships nothing about. The route goes in first,
  // then its key, as DSH's own Models page does it: a failed key write leaves a provider
  // that asks for one.
  async function addProvider(body) {
    if (body.preset === 'apihub') return setupApiHub(body)
    const provider = String(body.provider ?? '').trim()
    if (body.custom !== true && (provider === OPENCODE_GO.id || body.preset === OPENCODE_GO.id)) return setupOpenCodeGo(body)
    const { settings, credentials } = usable()
    const map = sections(settings)
    const entry = entryOf(provider)
    if (entry !== undefined && (entry.settingsNs !== PI_AI || profileOf(entry, map) !== undefined)) throw invalid(`${provider} is already set up`)
    const custom = body.custom === true
    if (!custom && (entry === undefined || entry.declared === true)) throw invalid(`DSH offers no provider ${provider}`)
    if (custom && !ROUTE_ID.test(provider)) throw invalid('A provider id is lowercase letters, digits and dashes, starting with a letter')
    if (custom && entry !== undefined) throw invalid(`DSH already offers ${provider}; add it from its list`)
    const key = typeof body.key === 'string' && body.key.trim() !== '' ? checkKey(body.key) : undefined
    const ref = keyRefFor(provider)
    const info = await credentials.describe(ref)
    if (key !== undefined && info.writable === false) throw invalid(`The API key for ${provider} is set outside ChemClaw and cannot be changed here`)
    // A blank key keeps a key that is already there, else the provider's own sign-in.
    const keyed = key !== undefined || info.configured === true
    const profile = custom ? customProfile(body) : {}
    if (keyed) profile.apiKeyEnv = ref
    await settings.mutate(PI_AI, [{ op: 'set', path: entry?.settingsPath ?? ['providers', provider], value: profile }], map.get(PI_AI)?.revision)
    if (key !== undefined) await credentials.set(ref, key)
    rt.dropCatalog()
    return providersView()
  }

  function apiHubProfile(settings) {
    const entry = entryOf(APIHUB.id)
    if (entry && entry.settingsNs !== PI_AI) throw invalid('An existing adapter owns the apihub provider name')
    const map = sections(settings)
    const profile = entry && profileOf(entry, map)
    if (profile?.baseURL && profile.baseURL.replace(/\/+$/, '') !== APIHUB.baseURL) throw invalid('The existing apihub route has a different endpoint. Keep it under another provider name before using the built-in APIHub.')
    return { entry, map, profile }
  }

  async function setupApiHub(body) {
    const { settings, credentials } = usable()
    const models = Array.isArray(body.models) ? (await apiHubInputs(body.models.slice(0, MAX_MODELS))).map(modelEntry) : []
    const { entry, map, profile } = apiHubProfile(settings)
    if (!models.length || new Set(models.map(model => model.id)).size !== models.length) throw invalid('Choose one or more different APIHub models')
    const ref = refOf(profile) ?? keyRefFor(APIHUB.id)
    const key = typeof body.key === 'string' && body.key.trim() ? checkKey(body.key) : undefined
    const info = await credentials.describe(ref)
    if (!key && !info.configured) throw invalid('Enter the APIHub key')
    if (key && info.writable === false) throw invalid('This APIHub key is configured outside ChemClaw')
    await settings.mutate(PI_AI, [{ op: 'set', path: entry?.settingsPath ?? ['providers', APIHUB.id], value: { ...profile, displayName: APIHUB.name, api: APIHUB.api, baseURL: APIHUB.baseURL, apiKeyEnv: ref, models } }], map.get(PI_AI)?.revision)
    if (key) await credentials.set(ref, key)
    rt.dropCatalog()
    return providersView()
  }

  // Keep DSH's catalog provider: it owns OpenCode's per-conversation headers.
  async function setupOpenCodeGo(body) {
    const { settings, credentials } = usable()
    const entry = entryOf(OPENCODE_GO.id)
    if (entry && entry.settingsNs !== PI_AI) throw invalid('An existing adapter owns the opencode-go provider name')
    if (entry?.declared !== false) throw invalid('Update DSH to a version with the built-in OpenCode Go provider')
    const map = sections(settings)
    if (entry && profileOf(entry, map) !== undefined) throw invalid(`${OPENCODE_GO.id} is already set up`)
    const ref = OPENCODE_GO.apiKeyEnv
    const key = typeof body.key === 'string' && body.key.trim() !== '' ? checkKey(body.key) : undefined
    const info = await credentials.describe(ref)
    if (!key && !info.configured) throw invalid('Enter the API key')
    if (key && info.writable === false) throw invalid(`The API key for ${OPENCODE_GO.id} is set outside ChemClaw and cannot be changed here`)
    await settings.mutate(PI_AI, [{ op: 'set', path: entry?.settingsPath ?? ['providers', OPENCODE_GO.id], value: {
      displayName: OPENCODE_GO.name, apiKeyEnv: ref,
    } }], map.get(PI_AI)?.revision)
    if (key) await credentials.set(ref, key)
    rt.dropCatalog()
    return providersView()
  }

  function customProfile(body) {
    if (!PROTOCOLS.includes(body.api)) throw invalid(`The protocol must be one of ${PROTOCOLS.join(', ')}`)
    const models = Array.isArray(body.models) ? body.models.slice(0, MAX_MODELS).map(modelEntry) : []
    if (models.length === 0) throw invalid('Add at least one model')
    if (new Set(models.map(model => model.id)).size !== models.length) throw invalid('Two models have the same id')
    const name = typeof body.name === 'string' ? body.name.trim().slice(0, 80) : ''
    return { ...(name ? { displayName: name } : {}), api: body.api, baseURL: checkEndpoint(body.baseURL), models }
  }

  // The models an endpoint (or a provider DSH ships) says it serves. The key typed for
  // the question goes with it and is not stored.
  async function discoverModels(body) {
    usable()
    const apiHub = body.preset === 'apihub'
    if (body.preset === 'apihub') {
      const { settings, credentials } = usable()
      const { profile } = apiHubProfile(settings)
      const ref = refOf(profile) ?? keyRefFor(APIHUB.id)
      const key = body.key?.trim() ? checkKey(body.key) : (await credentials.resolve(ref))?.value
      if (!key) throw invalid('Enter the APIHub key')
      body = { baseURL: APIHUB.baseURL, api: APIHUB.api, key }
    }
    const provider = typeof body.provider === 'string' && body.provider !== '' ? body.provider : undefined
    const request = provider !== undefined && entryOf(provider)?.declared === false
      ? { provider }
      : {
          baseURL: checkEndpoint(body.baseURL),
          ...(PROTOCOLS.includes(body.api) ? { api: body.api } : {}),
          ...(typeof body.key === 'string' && body.key.trim() !== '' ? { apiKey: checkKey(body.key) } : {}),
        }
    let models
    try { models = await ctx.llm.discoverModels(PI_AI, request) }
    catch (error) {
      if (body.baseURL === APIHUB.baseURL) throw invalid('APIHub model discovery failed. Check the Key, network and service status, then retry.')
      throw error
    }
    models = models.slice(0, MAX_MODELS)
    if (apiHub) models = await apiHubInputs(models)
    return models.map(model => ({
      id: model.id,
      ...(model.name ? { name: model.name } : {}),
      ...(model.contextWindow ? { contextWindow: model.contextWindow } : {}),
      ...(model.maxTokens ? { maxTokens: model.maxTokens } : {}),
      ...(inputOf(model) ? { inputModalities: [...inputOf(model)] } : {}),
    }))
  }

  // Only a route the user added goes; its key goes with it when it is the one this page
  // derives and no other provider names it.
  async function removeProvider(provider) {
    const { settings, credentials } = usable()
    const map = sections(settings)
    const entry = entryOf(provider)
    if (entry === undefined || entry.settingsNs !== PI_AI || profileOf(entry, map) === undefined) throw invalid(`${provider} is not set up`)
    if (profileOf(entry, map, 'user') === undefined || profileOf(entry, map, 'base') !== undefined) throw invalid(`${provider} comes with this setup and cannot be removed`)
    const ref = refOf(profileOf(entry, map))
    const shared = [...keyRefs()].some(([other, otherRef]) => other !== provider && otherRef === ref)
    await settings.mutate(PI_AI, [{ op: 'unset', path: entry.settingsPath }], map.get(PI_AI)?.revision)
    if (ref === keyRefFor(provider) && !shared) {
      const info = await credentials.describe(ref)
      if (info.configured && info.writable) await credentials.unset(ref)
    }
    rt.dropCatalog()
    return providersView()
  }

  Object.assign(rt, { keyRefs, missingKeys, prepareProviderRoutes, providersView, setProviderKey, clearProviderKey, addProvider, discoverModels, removeProvider })
}
