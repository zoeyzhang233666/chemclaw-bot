// Models. Every Bot runs on one model of its own, fixed when it is created and changed
// only in its settings or by a Main Bot. The team's first Main Bot has none until the
// user picks one in its chat. The Session keeps the selection durably.
import { assembleAuxiliaryLlm } from './auxiliary-llm.js'
import { normalize, splitRef } from './text.js'

const CATALOG_TTL_MS = 10_000
const ROUTE_WAIT_MS = 30_000

export function install(rt) {
  const { ctx, state } = rt

  let modelsSynced = null
  let catalogCache = { at: 0, value: [] }
  let catalogPending
  let catalogGeneration = 0
  const dropCatalog = () => { catalogCache = { at: 0, value: [] }; catalogGeneration += 1; catalogPending = undefined }
  // A model's thinking levels, resolved once and kept for a short while: they change
  // only with the provider, which also drops the catalog cache.
  const reasoningCache = new Map()
  ctx.on?.('llm/adapters-updated', () => { dropCatalog(); reasoningCache.clear() })
  for (const name of ['credentials/reference-updated', 'settings/document-updated']) ctx.on?.(name, dropCatalog)

  // The thinking levels a model serves: `{efforts: [{id, name, description?}],
  // defaultEffort?}`, or undefined when it has none or the provider cannot say.
  async function reasoningOf(ref) {
    const cached = reasoningCache.get(ref)
    if (cached !== undefined && Date.now() - cached.at < CATALOG_TTL_MS) return cached.value
    const route = splitRef(ref)
    const info = route === undefined ? undefined : await ctx.llm.resolveModelInfo?.(route.provider, route.model).catch(() => undefined)
    const value = info?.reasoning === undefined ? undefined : {
      efforts: (info.reasoning.efforts ?? []).map(effort => ({ id: effort.id, name: effort.name ?? effort.id, ...(effort.description ? { description: effort.description } : {}) })),
      ...(info.reasoning.defaultEffort === undefined ? {} : { defaultEffort: info.reasoning.defaultEffort }),
    }
    reasoningCache.set(ref, { at: Date.now(), value })
    return value
  }

  // A provider's model list can change in DSH settings without any event, so a picker
  // that is about to be used asks for a `fresh` one. Entries for models a Bot uses
  // also carry their `reasoning`, so the picker can offer thinking levels.
  async function catalog({ fresh = false } = {}) {
    if (!fresh && Date.now() - catalogCache.at < CATALOG_TTL_MS) return catalogCache.value
    if (catalogPending) return catalogPending
    const generation = catalogGeneration
    const pending = readCatalog().then(entries => {
      if (generation === catalogGeneration) catalogCache = { at: Date.now(), value: entries }
      return entries
    }).finally(() => { if (catalogPending === pending) catalogPending = undefined })
    catalogPending = pending
    return pending
  }
  // An optional provider can hang while discovering models. The roster still
  // uses its cached catalog; the shared discovery promise prevents piling up
  // new requests while that provider remains stuck.
  rt.catalogForView = async () => {
    let timer
    try {
      return await Promise.race([
        catalog(),
        new Promise(resolve => { timer = setTimeout(() => resolve(catalogCache.value), 1000) }),
      ])
    } finally { clearTimeout(timer) }
  }
  async function readCatalog() {
    await rt.prepareProviderRoutes?.()
    const entries = []
    for (const provider of [...ctx.llm.listProviders()].sort((a, b) => Number(b.id === 'apihub') - Number(a.id === 'apihub'))) {
      let models = []
      try { models = await ctx.llm.listModels(provider.id) } catch { continue }
      for (const model of models) {
        entries.push({
          ref: `${provider.id}/${model.id}`,
          provider: provider.id,
          providerName: provider.name ?? provider.id,
          id: model.id,
          name: model.name ?? model.id,
          ...(model.inputModalities ? { input: [...model.inputModalities] } : {}),
        })
      }
    }
    // DSH serves a provider's models whether or not its key is set; without one, every
    // turn on them fails.
    const missing = await rt.missingKeys?.([...new Set(entries.map(entry => entry.provider))]) ?? new Set()
    for (const entry of entries) if (missing.has(entry.provider)) entry.needsKey = true
    const used = new Set(Object.values(state.bots ?? {}).flatMap(bot => [bot.model, bot.appliedModel].filter(Boolean)))
    await Promise.all(entries.filter(entry => used.has(entry.ref)).map(async (entry) => {
      const reasoning = await reasoningOf(entry.ref)
      if (reasoning !== undefined) entry.reasoning = reasoning
    }))
    return entries
  }

  // The profile default model of DSH as set, served or not.
  const defaultRef = () => {
    const selection = ctx.get?.('agentDefaultModel')?.currentSelection?.()
    return selection?.provider && selection?.model ? `${selection.provider}/${selection.model}` : undefined
  }
  // A served model without credentials cannot be a default for a new conversation.
  function pickDefault(entries) {
    const ref = defaultRef()
    const usable = entries.filter(entry => !entry.needsKey)
    const preferred = usable.find(entry => entry.ref === ref)
    return preferred?.provider === 'apihub' ? preferred.ref
      : usable.find(entry => entry.provider === 'apihub')?.ref ?? preferred?.ref ?? usable[0]?.ref
  }
  const defaultModel = async () => pickDefault(await catalog())

  // A full `provider/model` ref, or a model id or name that only one provider serves.
  async function resolveModel(text) {
    const entries = await catalog({ fresh: true })
    const wanted = String(text ?? '').trim()
    const exact = entries.find(entry => entry.ref === wanted)
    if (exact) return exact.ref
    const key = normalize(wanted)
    const named = entries.filter(entry => normalize(entry.id) === key || normalize(entry.name) === key)
    if (named.length === 1) return named[0].ref
    const known = entries.map(entry => entry.ref).join(', ') || 'none'
    throw new Error(named.length > 1
      ? `Model ${wanted} is served by more than one provider; use one of ${named.map(entry => entry.ref).join(', ')}`
      : `Model ${wanted} is not available. Available models: ${known}`)
  }

  // A Bot with no model yet waits for the user to pick one and changes nothing. A
  // model that is no longer usable falls back to the last one it ran on, then the default.
  async function desiredModel(bot) {
    if (!bot.model && bot.templateId) return defaultModel()
    if (!bot.model) return undefined
    const entries = await catalog()
    const served = new Set(entries.filter(entry => !entry.needsKey).map(entry => entry.ref))
    return [bot.model, bot.appliedModel].find(ref => ref && served.has(ref)) ?? pickDefault(entries)
  }

  async function selectAgentModel(agent, signal) {
    if (signal?.aborted || !agent.model?.select || rt.readOnly?.()) return
    const bot = rt.botOf?.(rt.selfOf?.(agent.id))
    if (bot ? rt.isBotSession?.(agent.id) === false : rt.roomOf?.(agent.id) === undefined) return
    const ref = bot ? await desiredModel(bot) : await defaultModel()
    if (ref === undefined || signal?.aborted) return
    const effort = bot ? await desiredEffort(bot, ref) : undefined
    if (signal?.aborted) return
    const route = { ...splitRef(ref), ...(effort === undefined ? {} : { reasoningEffort: effort }) }
    if (!sameSelection(agent.model.current(), route)) agent.model.select(route)
    if (!bot || (bot.appliedModel === ref && bot.appliedEffort === effort)) return
    bot.appliedModel = ref
    if (effort === undefined) delete bot.appliedEffort
    else bot.appliedEffort = effort
    await rt.save()
  }

  // DSH awaits creation listeners before releasing queued input, and takes the
  // model snapshot before pre-step. Select on the live Agent without changing the
  // Harness-wide default or opening the sessions of idle presets.
  async function prepareAgentModel(agent, signal) {
    try {
      await rt.load?.()
      await selectAgentModel(agent, signal)
    } catch (error) {
      rt.warn('chemclaw-bot: model for %s not selected: %s', agent.id, error)
    }
  }
  ctx.on?.('agent/created', ({ agent, signal }) => prepareAgentModel(agent, signal))
  ctx.on?.('agent/pre-step', async ({ agent, signal }, next) => {
    const bot = rt.botOf?.(rt.selfOf?.(agent.id))
    if (!signal.aborted && rt.isBotSession?.(agent.id) !== false && (bot?.model || bot?.templateId) && await desiredModel(bot) === undefined) {
      throw new Error('No configured model is available. Connect APIHub or another provider in Settings > Models.')
    }
    return next()
  })
  async function syncLiveModels() {
    const agents = ctx.get?.('agents')?.list?.() ?? []
    await Promise.all(agents.map(agent => prepareAgentModel(agent)))
  }

  // The thinking level a Bot asked for, when the model it runs on serves it; else the
  // model's own default applies. A level the model does not have is ignored, never
  // sent: an explicit effort a provider does not know is a hard refusal there.
  async function desiredEffort(bot, ref) {
    if (bot.effort === undefined || ref === undefined) return undefined
    const reasoning = await reasoningOf(ref)
    return reasoning?.efforts?.some(effort => effort.id === bot.effort) ? bot.effort : undefined
  }

  // A thinking level id, or a name only one level of the model has, like resolveModel.
  async function resolveEffort(ref, text) {
    const wanted = String(text ?? '').trim()
    if (wanted === '') return undefined
    const reasoning = await reasoningOf(ref)
    const efforts = reasoning?.efforts ?? []
    if (efforts.length === 0) throw new Error(`Model ${ref} has no thinking levels`)
    const key = normalize(wanted)
    const named = efforts.filter(effort => normalize(effort.id) === key || normalize(effort.name) === key)
    if (named.length === 1) return named[0].id
    throw new Error(`Thinking level ${wanted} is not available for ${ref}. Available: ${efforts.map(effort => effort.name).join(', ')}`)
  }

  // The profile default model's thinking level, when the model a Bot starts on
  // serves it. A level the model does not know is ignored, like an inherited
  // `bot.effort` — the model's own default applies instead.
  async function defaultEffort(ref) {
    const wanted = ctx.get?.('agentDefaultModel')?.currentSelection?.()?.reasoningEffort
    if (ref === undefined || wanted === undefined) return undefined
    return resolveEffort(ref, wanted).catch(() => undefined)
  }

  // DSH's selectModel also saves the selection as the profile default model, in the
  // background. A Bot's model is its own, so the user's default is written back after
  // it. Selections run one at a time and wait for the write-back: profile writes land in
  // submission order, so the next one reads the user's default, not a Bot's.
  let selecting = Promise.resolve()
  function selectSessionModel(sessionId, { provider, model, reasoningEffort }) {
    const run = selecting.then(async () => {
      const defaults = ctx.get?.('agentDefaultModel')
      const before = defaults?.currentSelection?.()
      const result = await ctx.sessionController.selectModel({
        sessionId, provider, model,
        ...(reasoningEffort === undefined ? {} : { reasoningEffort }),
      })
      const saved = result?.selected ?? { provider, model, ...(reasoningEffort === undefined ? {} : { reasoningEffort }) }
      if (before?.provider && before?.model && !sameSelection(before, saved)) {
        await defaults.saveSelection(before).catch(error => rt.warn('chemclaw-bot: the default model was not restored: %s', error))
      }
      return result
    })
    selecting = run.catch(() => {})
    return run
  }

  const sameSelection = (a, b) => a?.provider === b.provider && a.model === b.model && a.reasoningEffort === b.reasoningEffort

  // `force` re-selects even when the record says it is applied: the composer's own
  // model picker can move the Session without telling this plugin.
  async function applyModel(bot, { force = false } = {}) {
    const ref = await desiredModel(bot)
    if (ref === undefined) return ref
    const effort = await desiredEffort(bot, ref)
    if (!force && bot.appliedModel === ref && (bot.appliedEffort ?? undefined) === effort) return ref
    const route = { ...splitRef(ref), ...(effort === undefined ? {} : { reasoningEffort: effort }) }
    await selectSessionModel(rt.chatOf(bot.id), route)
    for (const sessionId of rt.groupSessionsOf(bot.id)) {
      await selectSessionModel(sessionId, route)
        .catch(error => rt.warn('chemclaw-bot: model for %s in a group not applied: %s', bot.name, error))
    }
    bot.appliedModel = ref
    if (effort === undefined) delete bot.appliedEffort
    else bot.appliedEffort = effort
    await rt.save()
    return ref
  }

  // A provider may register after the plugin starts; a greeting waits for its Bot's
  // model instead of failing with "no adapter registered".
  async function waitForModel(bot, ms = ROUTE_WAIT_MS) {
    const deadline = Date.now() + ms
    for (;;) {
      if (!bot.model) return undefined
      catalogCache = { at: 0, value: [] }
      const served = new Set((await catalog()).map(entry => entry.ref))
      if (served.has(bot.model) || Date.now() >= deadline) return desiredModel(bot)
      await new Promise((resolve) => {
        const timer = setTimeout(done, Math.min(2000, deadline - Date.now()))
        const off = ctx.on?.('llm/adapters-updated', done)
        function done() { clearTimeout(timer); off?.(); resolve() }
      })
    }
  }

  // Sequential, and again whenever the served models change: a provider that
  // registers late still gets its Bots' models selected.
  let syncedKey
  const syncModels = () => {
    const key = catalogCache.value.map(entry => `${entry.ref}${entry.needsKey ? '!' : ''}`).join(',')
    if (key !== syncedKey) { syncedKey = key; modelsSynced = modelsSynced?.then(syncAll, syncAll) ?? syncAll() }
    return modelsSynced
  }
  async function syncAll() {
    for (const bot of Object.values(state.bots)) {
      // A new preset with no explicit selection already inherits DSH's default.
      // Materializing every idle preset here competes with the user's first turn.
      if (bot.templateId && !bot.model) continue
      await applyModel(bot).catch(error => rt.warn('chemclaw-bot: model for %s not applied: %s', bot.name, error))
    }
    await syncLiveModels()
  }

  // Stop pending auxiliary retries when the plugin is disposed or hot-reloaded.
  const lifetime = new AbortController()
  ctx.effect?.(() => () => lifetime.abort(), 'chemclaw-bot: auxiliary llm retry')
  const assembleLlm = options => assembleAuxiliaryLlm(ctx, options, { signal: lifetime.signal, backoff: rt.config?.llmRetryBackoff })

  Object.assign(rt, {
    assembleLlm,
    catalog, cachedCatalog: () => catalogCache.value, cachedDefault: () => pickDefault(catalogCache.value),
    defaultRef, defaultModel, defaultEffort, resolveModel, desiredModel, reasoningOf, resolveEffort, desiredEffort,
    selectSessionModel, applyModel, waitForModel, syncModels, selectAgentModel, syncLiveModels,
    dropCatalog,
  })
}
