import { createElement as h, Fragment, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { currentPart } from './text.js'
import { CheckIcon, CloseIcon, SlidersIcon } from './icons.js'
import { ApiHubMark } from './brand-icons.js'
import { BotMark } from './mark.js'
import { KeyIcon, MaskedInput } from './secret-card.js'
import { SPRING_POP, SPRING_SHAPE, spring, useLinger, useViewport, viewBottom } from './motion.js'
import { useEscape } from './overlay-hooks.js'
import { APIHUB } from '../shared/model-providers.js'
import { hostText, t } from './i18n.js'

const MENU_EXIT_MS = 120

// -------------------------------------------------------------------------
// A Bot's model: the picker in its details panel and settings, and the message its
// chat opens on while it has none. Models come from DeepSeek Harness, grouped by provider.

export function groupModels(models) {
  const groups = new Map()
  for (const model of models ?? []) {
    const provider = model.provider ?? model.providerName ?? model.ref.split('/')[0]
    if (!groups.has(provider)) groups.set(provider, [])
    groups.get(provider).push(model)
  }
  const names = new Map()
  for (const [provider, list] of groups) {
    const name = list[0].providerName ?? provider
    names.set(name, (names.get(name) ?? 0) + 1)
  }
  const isApiHub = ([provider, list]) => /api[\s_-]*hub/i.test(`${provider} ${list[0].providerName ?? ''}`)
  return [...groups].sort((a, b) => Number(isApiHub(b)) - Number(isApiHub(a))).map(([provider, list]) => {
    const name = list[0].providerName ?? provider
    return [names.get(name) > 1 ? `${name} (${provider})` : name, list]
  })
}

const servedOf = (roster, ref) => (roster.models ?? []).find(model => model.ref === ref)

// What a Bot runs on, for display: the chosen model, else the one it last ran on.
export function modelOf(bot, roster) {
  const ref = bot.model ?? bot.appliedModel
  if (!ref) return undefined
  const served = servedOf(roster, ref)
  const [provider, ...rest] = ref.split('/')
  return { ref, name: served?.name ?? rest.join('/'), provider: served?.providerName ?? provider, served: served !== undefined }
}

// The thinking levels of one model, `{efforts, defaultEffort?}` or undefined when it
// has none. The catalog carries them for models Bots use; any other ref asks the host.
const effortCache = new Map()
function useEfforts(served, ref, actions) {
  const [fetched, setFetched] = useState(undefined)
  useEffect(() => {
    setFetched(undefined)
    if (ref === undefined || served?.reasoning !== undefined || actions?.efforts === undefined) return undefined
    let live = true
    if (effortCache.has(ref)) setFetched(effortCache.get(ref))
    else void Promise.resolve(actions.efforts(ref)).then((value) => {
      const reasoning = value?.efforts ? value : null
      effortCache.set(ref, reasoning)
      if (live) setFetched(reasoning)
    }).catch(() => {})
    return () => { live = false }
  }, [ref, served?.reasoning !== undefined, actions])
  return served?.reasoning ?? fetched
}

// The rows of the Thinking section: a Default row that clears the Bot's pick, then every
// level the model serves.
export function effortRows(reasoning) {
  if (reasoning?.efforts === undefined || reasoning.efforts.length === 0) return []
  return [
    { effort: undefined, label: t('Default') },
    ...reasoning.efforts.map(effort => ({ effort: effort.id, label: effort.name })),
  ]
}

function EffortRows({ reasoning, current, onPick }) {
  return h(Fragment, null,
    h('div', { className: 'bt-menu-sep', role: 'separator' }),
    h('div', { className: 'bt-model-group', role: 'presentation' }, t('Thinking level')),
    effortRows(reasoning).map(row => h('button', {
      key: row.effort ?? 'default', type: 'button', role: 'menuitemradio', 'aria-checked': (row.effort ?? null) === (current ?? null),
      onClick: () => onPick(row.effort),
    },
    h('span', { className: 'bt-menu-label' }, row.label),
    h('span', { className: 'bt-model-tick', 'aria-hidden': true }, (row.effort ?? null) === (current ?? null) ? h(CheckIcon) : null))))
}

function ModelRows({ roster, current, onPick }) {
  return groupModels(roster.models).map(([provider, list]) => h(Fragment, { key: list[0].provider ?? provider },
    h('div', { className: 'bt-model-group', role: 'presentation' }, provider),
    list.map(model => h('button', {
      key: model.ref, type: 'button', role: 'menuitemradio', 'aria-checked': model.ref === current, title: model.ref,
      onClick: () => onPick(model.ref),
    },
    h('span', { className: 'bt-menu-label' }, model.name),
    model.ref === roster.defaultModel ? h('span', { className: 'bt-menu-hint' }, t('Default')) : null,
    h('span', { className: 'bt-model-tick', 'aria-hidden': true }, model.ref === current ? h(CheckIcon) : null)))))
}

export const Caret = () => h('svg', { className: 'bt-model-caret', width: 12, height: 12, viewBox: '0 0 20 20', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }, h('path', { d: 'M5.5 8l4.5 4.5L14.5 8' }))

// A menu that opens under its trigger, or above when the window has no room below. A
// click outside, Escape, or a scroll outside it closes it.
export function useAnchoredMenu({ width: requestedWidth, followScroll = false } = {}) {
  const [anchor, setAnchor] = useState(null)
  const [place, setPlace] = useState(null)
  const [shownPlace, leaving] = useLinger(place, MENU_EXIT_MS)
  const button = useRef(null)
  const menu = useRef(null)
  const tick = useViewport()
  const close = () => { setAnchor(null); setPlace(null) }
  useEffect(() => {
    if (place === null) return undefined
    const onDown = (event) => {
      if (menu.current?.contains(event.target) || button.current?.contains(event.target)) return
      close()
    }
    const onKey = (event) => { if (event.key === 'Escape') { event.stopPropagation(); close(); button.current?.focus() } }
    const onScroll = (event) => {
      if (menu.current?.contains(event.target)) return
      const rect = button.current?.getBoundingClientRect()
      if (followScroll && rect && rect.bottom > 0 && rect.top < viewBottom()) setAnchor({})
      else close()
    }
    window.addEventListener('mousedown', onDown)
    window.addEventListener('keydown', onKey, true)
    window.addEventListener('scroll', onScroll, true)
    return () => {
      window.removeEventListener('mousedown', onDown)
      window.removeEventListener('keydown', onKey, true)
      window.removeEventListener('scroll', onScroll, true)
    }
  }, [place, followScroll])
  const open = () => setAnchor({})
  // Re-reads the trigger's rect whenever the visible viewport moves: the menu
  // tracks its anchor through the on-screen keyboard, not past it.
  useLayoutEffect(() => {
    if (anchor === null || !button.current) return
    const rect = button.current.getBoundingClientRect()
    const width = requestedWidth === undefined ? Math.max(240, rect.width) : Math.min(requestedWidth, window.innerWidth - 16)
    const left = Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8))
    const below = viewBottom() - rect.bottom
    setPlace(below >= 260 || below >= rect.top
      ? { left, width, top: rect.bottom + 4, maxHeight: below - 16, '--bt-origin': 'top right' }
      : { left, width, bottom: viewBottom() - rect.top + 4, maxHeight: rect.top - 16, '--bt-origin': 'bottom right' })
  }, [anchor, tick, requestedWidth])
  return { isOpen: place !== null, shownPlace, leaving, button, menu, open, close }
}

// The trigger shows the model name over its provider. A Thinking section lists the
// levels of the shown model when it has them.
// `onPick`/`onPickEffort` replace saving to the Bot, for a Bot that does not exist yet.
export function ModelMenu({ bot, roster, actions, run, wide = false, onPick, onPickEffort }) {
  const { isOpen, shownPlace, leaving, button, menu, open, close } = useAnchoredMenu()
  const shown = modelOf(bot, roster)
  const current = bot.model ?? bot.appliedModel
  const served = servedOf(roster, current)
  const reasoning = useEfforts(served, current, actions)
  // The level the Bot runs on: its pick when the model serves it, else the model's own.
  const picked = reasoning?.efforts?.some(effort => effort.id === bot.effort) ? bot.effort : undefined
  const currentEffort = picked ?? reasoning?.defaultEffort
  const effortLabel = currentEffort === undefined
    ? (reasoning?.efforts?.length > 0 ? t('Default') : undefined)
    : reasoning.efforts.find(effort => effort.id === currentEffort)?.name ?? currentEffort
  const toggle = () => {
    if (isOpen) { close(); return }
    // DSH settings can change the list at any time, so opening asks again.
    void actions?.refreshModels?.()
    open()
  }
  const pick = (ref) => {
    close()
    if (onPick) onPick(ref)
    else if (ref !== current || !bot.model) void run(actions.updateBot(bot.id, { model: ref }))
  }
  const pickEffort = (effort) => {
    close()
    if (onPickEffort) onPickEffort(effort)
    else if (effort !== bot.effort) void run(actions.updateBot(bot.id, { effort: effort ?? null }))
  }
  const models = roster.models ?? []
  const manage = manageModels(actions)
  return h(Fragment, null,
    h('button', {
      ref: button, type: 'button', className: 'bt-model-trigger', 'data-wide': wide || undefined,
      'aria-haspopup': 'menu', 'aria-expanded': isOpen, 'aria-label': t('Model: {model}', { model: shown?.name ?? t('none') }),
      'data-missing': shown !== undefined && !shown.served && models.length > 0 ? '' : undefined, onClick: toggle,
    },
    h('span', { className: 'bt-model-copy' },
      h('span', { className: 'bt-model-name' }, shown?.name ?? t('Choose a model')),
      shown ? h('span', { className: 'bt-model-provider' }, shown.served || models.length === 0
        ? (effortLabel === undefined ? shown.provider : `${shown.provider} · ${effortLabel}`)
        : t('{provider} · not available', { provider: shown.provider })) : null),
    h(Caret)),
    shownPlace ? createPortal(h('div', { ref: menu, className: `bt-menu bt-model-menu${shownPlace.bottom !== undefined ? ' bt-menu-up' : ''}`, role: 'menu', 'aria-label': t('Model for {name}', { name: bot.name }), style: shownPlace, 'data-leaving': leaving || undefined },
      models.length > 0 ? h(ModelRows, { roster, current, onPick: pick })
        : h('div', { className: 'bt-model-none' }, t('No models are set up in DeepSeek Harness yet.')),
      effortRows(reasoning).length > 0 ? h(EffortRows, { reasoning, current: picked, onPick: pickEffort }) : null,
      manage ? h('div', { className: 'bt-menu-sep', role: 'separator' }) : null,
      manage ? h('button', { type: 'button', role: 'menuitem', onClick: () => { close(); manage() } }, h(SlidersIcon), h('span', { className: 'bt-menu-label' }, t('Models and providers…'))) : null), document.body) : null)
}

// A missing model remains a setup control, not an unsolicited chat turn.
// Preset Bots show an ordinary setup hint beside their welcome panel.
export function ModelChoiceDock({ sessionId, useRoster, actions }) {
  const roster = useRoster(value => value)
  const bot = roster.byId[sessionId]
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const shown = Boolean(bot) && currentPart(bot) === sessionId && roster.ready
  useEffect(() => { if (shown) void actions.refreshModels?.() }, [shown, sessionId])
  if (!bot || currentPart(bot) !== sessionId || !roster.ready) return null
  const models = roster.models ?? []
  // A model whose provider has no API key fails every turn, so it is no choice.
  const usable = models.filter(model => !model.needsKey)
  // Preset experts inherit the harness default with no card. A held greeting
  // (waiting) still needs an explicit pick so kickoff can run.
  if (!bot.model && bot.templateId && !bot.waiting && usable.some(model => model.ref === roster.defaultModel)) return null
  const lost = bot.model ? !models.some(model => model.ref === bot.model) : false
  // An unknown catalog (none listed) cannot tell a lost model from a slow provider.
  if (bot.model && (!lost || models.length === 0)) return null
  // A window without DSH's own settings takes the missing key here.
  const keyFor = usable.length === 0 && actions.setProviderKey ? models.find(model => model.needsKey) : undefined
  const manage = manageModels(actions)
  const pick = (ref) => {
    setBusy(ref)
    setError('')
    void Promise.resolve(actions.updateBot(bot.id, { model: ref }))
      .catch((failure) => { setError(failure?.message ?? String(failure)); void actions.refreshModels?.() })
      .finally(() => setBusy(''))
  }
  // User-created Bots retain their introductory card; presets never impersonate
  // an assistant message before the user has spoken.
  const text = lost
    ? t('{model} is not available anymore. Pick another model for me.', { model: bot.model.split('/').slice(1).join('/') })
    : keyFor
      ? t("Hi, I'm {name}. I need a {provider} API key before I can start.", { name: bot.name, provider: keyFor.providerName ?? keyFor.provider })
      : usable.length === 0
        ? t("Hi, I'm {name}. I don't have a model yet. How do you want to set one up?", { name: bot.name })
        : t("Hi, I'm {name}. Pick a model for me first. You can change it later in my details.", { name: bot.name })
  const choices = usable.length === 0
    ? setupChoices(actions).map(([label, run]) => h('button', { key: label, type: 'button', className: 'bt-model-chip', onClick: run }, label))
    : [
        ...groupModels(usable).map(([provider, list]) => h('div', { key: list[0].provider ?? provider, className: 'bt-model-choice-group', role: 'group', 'aria-label': provider },
          h('div', { className: 'bt-model-choice-provider', 'aria-hidden': true }, provider),
          h('div', { className: 'bt-model-choice-chips' }, list.map(model => h('button', {
            key: model.ref, type: 'button', className: 'bt-model-chip', disabled: busy !== '', 'aria-busy': busy === model.ref || undefined,
            'aria-label': `${model.name} · ${provider}`,
            title: model.ref === roster.defaultModel ? `${model.ref} · ${t('Harness default')}` : model.ref,
            onClick: () => pick(model.ref),
          }, model.name, busy === model.ref ? h('span', { className: 'bt-model-spin', 'aria-label': t('Saving…') }) : null))))),
        manage ? h('button', { key: 'manage', type: 'button', className: 'bt-model-chip bt-model-chip-quiet', onClick: manage }, h(SlidersIcon), t('Manage models')) : null,
      ]
  return h('div', { className: 'bt-model-dock' },
    bot.templateId ? h('p', { className: 'bt-set-hint' }, t('Choose a model')) : h('div', { className: 'bt-astack', 'data-lead': '' },
      h('div', { className: 'bt-msg' },
        h('div', { className: 'bt-msg-line' },
          h(BotMark, { bot, size: 22 }),
          h('div', { className: 'bt-bubble' }, text)))),
    keyFor
      ? h(ModelKeyCard, { key: keyFor.provider, model: keyFor, actions })
      : h('div', { className: 'bt-model-chips', role: 'group', 'aria-label': t('Choose a model') }, choices),
    error ? h('div', { className: 'bt-secret-error bt-model-error', role: 'alert' }, error) : null)
}

// The provider's API key, saved through the host; once it is set, the provider's
// models become the choices.
function ModelKeyCard({ model, actions }) {
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const label = t('{provider} API key', { provider: model.providerName ?? model.provider })
  const ready = value.trim() !== '' && !busy
  const save = () => {
    if (!ready) return
    setBusy(true)
    setError('')
    void Promise.resolve(actions.setProviderKey(model.provider, value))
      .then(() => setValue(''), failure => setError(hostText(failure?.message ?? String(failure))))
      .finally(() => setBusy(false))
  }
  return h('div', { className: 'bt-q bt-model-key', role: 'group', 'aria-label': label },
    h('div', { className: 'bt-model-key-title' }, h(KeyIcon), label),
    h('label', { className: 'bt-q-field bt-secret-field' }, h(MaskedInput, { value, onChange: setValue, onEnter: save, label, autoFocus: true })),
    error ? h('div', { className: 'bt-secret-error', role: 'alert' }, error) : null,
    h('div', { className: 'bt-q-foot' },
      actions.openModels ? h('button', { type: 'button', className: 'bt-q-btn bt-model-key-other', onClick: actions.openModels }, t('Another provider')) : null,
      h('button', { type: 'button', className: 'bt-q-submit', disabled: !ready, onClick: save }, busy ? t('Saving…') : t('Save'))))
}

// Where the providers are set up: the window's own Models page, else DSH's settings.
const manageModels = actions => actions.openModels ?? actions.openHarnessSettings

// Ways to get a first model. ChemClaw steers users to Apihub, not DeepSeek account login.
function setupChoices(actions) {
  const openKeys = () => { window.open(APIHUB.tokenUrl, '_blank', 'noopener,noreferrer'); actions.openModels?.() }
  const openPortal = () => { window.open(APIHUB.portalUrl, '_blank', 'noopener,noreferrer') }
  return [
    actions.openModels ? [t('Set up APIHub or another model'), actions.openModels] : null,
    actions.signIn ? [t('Get started'), () => actions.signIn()] : null,
    [t('Add API Key'), openKeys],
    [t('Sign in'), openPortal],
    actions.openHarnessSettings ? [t('Open settings to set up a custom model'), actions.openHarnessSettings] : null,
  ].filter(Boolean)
}

/** ChemClaw get-started: Apihub portal + keys, not DeepSeek Platform OAuth. */
export function ApihubGetStarted({ useUi, actions }) {
  const open = useUi(state => state.signIn)
  if (!open) return null
  return h(ApihubGetStartedDialog, { key: open, actions })
}

function ApihubGetStartedDialog({ actions }) {
  const close = () => actions.closeSignIn()
  useEscape(close)
  const addKey = () => {
    window.open(APIHUB.tokenUrl, '_blank', 'noopener,noreferrer')
    close()
    actions.openModels?.()
  }
  const login = () => {
    window.open(APIHUB.portalUrl, '_blank', 'noopener,noreferrer')
    close()
  }
  return createPortal(
    h('div', { className: 'bt-apihub-start-layer' },
      h('div', { className: 'bt-scrim', onMouseDown: close }),
      h('div', { className: 'bt-apihub-start', role: 'dialog', 'aria-modal': true, 'aria-labelledby': 'bt-apihub-start-title' },
        h('div', { className: 'bt-apihub-start-head' },
          h('span', { className: 'bt-connector-mark bt-apihub-start-mark' }, h(ApiHubMark)),
          h('h2', { id: 'bt-apihub-start-title' }, t('Get started')),
          h('button', { type: 'button', className: 'bt-apihub-start-x', 'aria-label': t('Close'), onClick: close }, h(CloseIcon))),
        h('p', { className: 'bt-apihub-start-body' }, t('Sign in to your Apihub account and add an API Key to get started. Your projects and files are stored locally.')),
        h('div', { className: 'bt-apihub-start-actions' },
          h('button', { type: 'button', className: 'bt-apihub-start-secondary', onClick: addKey }, t('Add API Key')),
          h('button', { type: 'button', className: 'bt-apihub-start-primary', onClick: login }, t('Sign in'))))),
    document.body,
  )
}

export const MODEL_CSS = `
.bt-model-trigger{display:inline-flex;align-items:center;gap:8px;max-width:100%;min-width:0;height:auto;min-height:32px;padding:4px 8px 4px 10px;border:0;border-radius:8px;background:var(--bt-hover);color:var(--bt-ink);font:inherit;text-align:left;cursor:pointer;transition:background-color .12s ease}
.bt-model-trigger:hover,.bt-model-trigger[aria-expanded=true]{background:var(--bt-active)}
.bt-model-trigger:focus-visible{outline:2px solid var(--bt-accent);outline-offset:1px}
.bt-model-trigger[data-missing] .bt-model-provider{color:var(--bt-danger)}
.bt-model-trigger[data-wide]{display:flex;width:100%;min-height:48px;padding:7px 12px;justify-content:space-between;border-radius:12px;background:var(--bt-card);box-shadow:inset 0 0 0 1px var(--bt-line)}
.bt-model-trigger[data-wide]:hover,.bt-model-trigger[data-wide][aria-expanded=true]{background:var(--bt-hover)}
.bt-model-copy{display:flex;flex-direction:column;min-width:0}
.bt-model-name{font-size:13px;line-height:18px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bt-model-provider{font-size:11px;line-height:14px;color:var(--bt-ink-3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bt-model-caret{flex:none;color:var(--bt-ink-3);transition:${spring(SPRING_SHAPE, 'transform')}}
.bt-model-trigger[aria-expanded=true] .bt-model-caret{transform:rotate(180deg)}
.bt-model-menu{overflow-y:auto;scrollbar-width:thin}
.bt-model-group{flex:none;padding:8px 8px 2px;font-size:11px;line-height:14px;font-weight:500;color:var(--bt-ink-3);text-transform:none}
.bt-model-group:first-child{padding-top:2px}
.bt-model-tick{flex:none;width:16px;height:16px;display:inline-flex;color:var(--bt-ink-2)}
.bt-model-tick svg{animation:bt-check-pop ${SPRING_POP.duration}ms ${SPRING_POP.easing} 60ms backwards}
.bt-model-none{padding:8px;font-size:13px;line-height:18px;color:var(--bt-ink-2)}
.bt-model-dock{width:100%;max-width:var(--dsh-chat-content-width,748px);margin:0 auto;display:flex;flex-direction:column;align-items:flex-start;gap:8px;padding:0 0 10px;box-sizing:border-box;animation:bt-model-in ${SPRING_POP.duration}ms ${SPRING_POP.easing} backwards}
.bt-model-chips{display:flex;flex-wrap:wrap;gap:6px;margin-left:30px;max-width:min(560px,calc(100% - 30px));max-height:min(240px,36vh);max-height:min(240px,36dvh);overflow-y:auto;scrollbar-width:thin}
.bt-model-choice-group{display:flex;flex-direction:column;gap:6px;width:100%;min-width:0}
.bt-model-choice-provider{padding-top:4px;font-size:12px;line-height:16px;font-weight:500;color:var(--bt-ink-2);overflow-wrap:anywhere}
.bt-model-choice-chips{display:flex;flex-wrap:wrap;gap:6px}
.bt-model-chip{display:inline-flex;align-items:center;gap:6px;min-height:30px;padding:5px 12px;border:.5px solid var(--bt-line-2);border-radius:999px;background:var(--bt-surface,transparent);color:var(--bt-ink);font:inherit;font-size:13px;line-height:18px;cursor:pointer;transition:background-color .12s ease,border-color .12s ease}
.bt-model-chip:hover:not(:disabled){background:var(--bt-hover)}
.bt-model-chip:focus-visible{outline:2px solid var(--bt-accent);outline-offset:1px}
.bt-model-chip-quiet{color:var(--bt-ink-2)}
.bt-model-chip svg{width:14px;height:14px}
.bt-model-chip:disabled{cursor:default}
.bt-model-chip:disabled:not([aria-busy]){opacity:.5}
.bt-model-error{margin-left:30px}
.bt-q.bt-model-key{margin:0 0 0 30px;width:min(480px,calc(100% - 30px));gap:10px}
.bt-model-key-title{display:flex;align-items:center;gap:6px;font-size:13px;line-height:18px;font-weight:500;color:var(--bt-ink-2)}
.bt-model-key-title svg{flex:none;width:16px;height:16px}
.bt-model-key .bt-q-foot{margin-top:2px}
.bt-model-key-other{margin-right:auto}
@keyframes bt-model-in{from{opacity:0;transform:translateY(6px)}}
.bt-model-spin{flex:none;width:14px;height:14px;border-radius:50%;border:1.5px solid var(--bt-line-2);border-top-color:var(--bt-ink-2);animation:bt-model-spin .7s linear infinite}
@keyframes bt-model-spin{to{transform:rotate(360deg)}}
.bt-apihub-start-layer{position:fixed;inset:0;z-index:80;display:flex;align-items:center;justify-content:center;padding:24px;box-sizing:border-box;pointer-events:auto}
.bt-apihub-start-layer>.bt-scrim{position:absolute;inset:0}
.bt-apihub-start{position:relative;z-index:1;width:min(420px,100%);background:var(--bt-main);border-radius:16px;border:.5px solid var(--bt-line-2);box-shadow:0 24px 80px rgba(0,0,0,.24);color:var(--bt-ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;animation:bt-dialog-rise ${SPRING_SHAPE.duration}ms ${SPRING_SHAPE.easing},bt-veil-in .2s ease-out;user-select:none}
.bt-apihub-start-head{display:flex;align-items:center;gap:10px;padding:22px 24px 12px}
.bt-apihub-start-mark{width:36px;height:36px;color:var(--bt-accent)}
.bt-apihub-start-head h2{flex:1;margin:0;font-size:16px;line-height:24px;font-weight:500}
.bt-apihub-start-x{flex:none;width:28px;height:28px;border:0;padding:0;border-radius:6px;background:none;color:var(--bt-ink-2);display:inline-flex;align-items:center;justify-content:center;cursor:pointer}
.bt-apihub-start-x:hover{background:var(--bt-hover);color:var(--bt-ink)}
.bt-apihub-start-x svg{width:14px;height:14px}
.bt-apihub-start-body{margin:0;padding:0 24px;font-size:14px;line-height:22px;color:var(--bt-ink)}
.bt-apihub-start-actions{display:flex;justify-content:flex-end;align-items:center;gap:8px;padding:16px 24px 22px}
.bt-apihub-start-secondary,.bt-apihub-start-primary{box-sizing:border-box;min-width:72px;height:36px;padding:0 16px;border-radius:10px;font:inherit;font-size:14px;line-height:22px;cursor:pointer}
.bt-apihub-start-secondary{border:.5px solid var(--bt-line-2);background:var(--bt-card);color:var(--bt-ink)}
.bt-apihub-start-secondary:hover{background:var(--bt-hover)}
.bt-apihub-start-primary{border:0;background:var(--bt-ink);color:var(--bt-main);font-weight:500}
.bt-apihub-start-primary:hover{opacity:.9}
@media (prefers-reduced-motion:reduce){.bt-model-dock{animation:none}.bt-model-spin{animation-duration:2s}.bt-model-caret{transition:none}.bt-model-tick svg{animation:none}.bt-apihub-start{animation:none}}
`
