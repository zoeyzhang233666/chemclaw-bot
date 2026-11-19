import { createElement as h, useEffect, useId, useRef, useState } from 'react'
import { lookOf } from './characters.js'
import { t } from './i18n.js'

// -------------------------------------------------------------------------
// Computer use: the switch page, a Bot's Control card, its Computer drawer page,
// the app-access card, the handoff card's computer variant, and the bar that
// lists who holds a lease.

export const LEVELS = [
  ['off', 'Off'],
  ['view', 'View only'],
  ['background', 'Background'],
  ['foreground', 'Foreground'],
]
const levelId = bot => LEVELS.some(([id]) => id === bot?.computer?.level) ? bot.computer.level : 'background'

export function LevelPicker({ bot, actions, run, disabled }) {
  const level = levelId(bot)
  return h('select', {
    className: 'bt-select bt-level-pick', 'aria-label': t('Computer use level'), value: level, disabled,
    onChange: event => run(actions.computerSetLevel(bot.id, event.target.value)),
  }, LEVELS.map(([id, label]) => h('option', { key: id, value: id }, t(label))))
}

const PROVIDER_TEXT = {
  loading: ['Loading the provider…', 'loading'],
  ready: ['Ready', 'ready'],
  error: ['Could not load the provider', 'error'],
  missing: ['The provider package is not installed', 'error'],
  occupied: ['Another computer-use provider is running', 'error'],
  unsupported: ['Computer use is not available on this platform', 'error'],
}

// A missing provider package: what to install, and the command to copy.
function InstallRow({ install, Row }) {
  const [copied, setCopied] = useState(false)
  const copy = () => { void navigator.clipboard?.writeText(install.command).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1600) }, () => {}) }
  return h(Row, { label: t('Install it in this DSH'), hint: t('Run {command}, then restart DSH.', { command: install.command }) },
    h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: copy }, copied ? t('Copied') : t('Copy command')))
}

const providerWorks = provider => provider.state === 'ready' || provider.state === 'loading'

// Settings → Computer use. The switch, where the provider stands, the macOS
// permission rows, and every Bot's level.
export function ComputerPage({ roster, actions, run, Section, Row, Switch }) {
  const computer = roster.computer ?? { enabled: false }
  const [system, setSystem] = useState(null)
  const provider = computer.provider ?? { state: computer.enabled ? 'loading' : 'off' }
  const refresh = () => { if (actions.computerSystemStatus) void Promise.resolve(actions.computerSystemStatus()).then(setSystem, () => {}) }
  useEffect(() => {
    if (computer.enabled && computer.macos === true && provider.state === 'ready') refresh()
    else setSystem(null)
    return undefined
  }, [computer.enabled, computer.macos, provider.state])
  const perms = system ?? {}
  const permRow = (key, label) => {
    const state = perms[key]?.state ?? perms[key]
    const granted = state === 'granted' || state === true
    return h(Row, { key, label: t(label) },
      h('span', { className: 'bt-perm-state', 'data-on': granted || undefined }, granted ? t('Allowed') : t('Not allowed')),
      granted ? null : h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: () => run(Promise.resolve(actions.computerPermission(key)).then(refresh)) }, t('Grant')))
  }
  return [
    h(Section, { key: 'switch' },
      h(Row, { label: t('Let Bots use the computer') },
        Switch === undefined ? null : h(Switch, { label: t('Let Bots use the computer'), on: computer.enabled === true, onChange: on => run(actions.computerSetEnabled(on)) }))),
    computer.enabled ? h(Section, { key: 'provider', title: t('Computer provider') },
      h(Row, { label: t(PROVIDER_TEXT[provider.state]?.[0] ?? PROVIDER_TEXT.error[0]), hint: provider.message },
        ['error', 'missing', 'occupied'].includes(provider.state) && actions.computerProviderRetry
          ? h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: () => run(actions.computerProviderRetry()) }, t('Retry')) : null),
      provider.state === 'missing' && provider.install?.command ? h(InstallRow, { install: provider.install, Row }) : null,
      computer.macos === true && provider.state === 'ready' ? [permRow('accessibility', 'Accessibility'), permRow('screenRecording', 'Screen Recording')] : null) : null,
    h(Section, { key: 'bots', title: t('Bots') },
      computer.enabled && !providerWorks(provider) ? h('p', { className: 'bt-set-hint' }, t('Bots get no computer tools until the provider is ready.')) : null,
      roster.bots.map(bot => h(Row, { key: bot.id, label: bot.name },
        h(LevelPicker, { bot, actions, run, disabled: !computer.enabled })))),
  ]
}

// The Bot's own card in its settings: its level and the apps the user Always allows.
export function BotComputerCard({ bot, roster, actions, run, Card, Row }) {
  const computer = roster.computer ?? { enabled: false }
  const apps = Object.entries(bot.computer?.apps ?? {})
  return h(Card, { title: t('Control') },
    !computer.enabled
      ? h(Row, { label: t('Computer use') }, h('span', { className: 'bt-muted' }, t('Off in Settings → Computer use')))
      : [
          h(Row, { key: 'level', label: t('Computer use'), hint: providerWorks(computer.provider ?? { state: 'loading' }) ? undefined : t('Bots get no computer tools until the provider is ready.') }, h(LevelPicker, { bot, actions, run })),
          apps.map(([key, app]) => h(Row, { key, label: app.name },
            h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: () => run(actions.computerRevokeApp(bot.id, key)) }, t('Revoke')))),
        ])
}

// The drawer's Computer page: what the Bot does on the computer right now.
export function ComputerView({ bot, actions, hooks }) {
  const live = hooks.useComputer?.(map => map) ?? {}
  const entry = live.bots?.[bot.id] ?? { state: 'idle', steps: [] }
  const [shot, setShot] = useState(null)
  useEffect(() => {
    const id = entry.lastShot?.attachmentId
    if (id === undefined || !actions.computerShot) { setShot(null); return undefined }
    let current = true
    void Promise.resolve(actions.computerShot(id)).then(value => { if (current) setShot(value) }, () => {})
    return () => { current = false }
  }, [entry.lastShot?.attachmentId])
  const controlLabel = { idle: 'Idle', bot: 'Operating', user: 'You have the computer', waiting: 'Waiting for you' }[entry.state] ?? 'Idle'
  return h('div', { className: 'bt-cview' },
    h('div', { className: 'bt-cview-head' },
      h('span', { className: 'bt-cview-state', 'data-state': entry.state }, t(controlLabel)),
      entry.app ? h('span', { className: 'bt-cview-app' }, entry.app) : null),
    shot?.dataUrl ? h('img', { className: 'bt-cview-shot', src: shot.dataUrl, alt: t('Latest screenshot') }) : null,
    entry.waitingFor === 'user-idle'
      ? h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: () => void actions.computerAllowForeground(bot.id) }, t('Let it continue'))
      : null,
    h('div', { className: 'bt-cview-actions' },
      h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: () => void actions.computerStop(bot.id) }, t('Stop')),
      entry.state !== 'user'
        ? h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: () => void actions.computerTakeover(bot.id) }, t('Take over the computer'))
        : h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: () => void actions.computerHandback(bot.id) }, t('Hand back'))),
    entry.steps.length > 0 ? h('div', { className: 'bt-cview-steps' },
      h('div', { className: 'bt-section-title' }, t('Recent steps')),
      [...entry.steps].reverse().map((step, index) => h('div', { key: index, className: 'bt-cview-step', 'data-ok': step.ok === false ? 'no' : undefined },
        h('span', { className: 'bt-cview-step-what' }, [step.app, step.action].filter(Boolean).join(' · ')),
        step.ok === false ? h('span', { className: 'bt-cview-step-err', title: step.error }, t('failed')) : null))) : null)
}

// ---- The app-access card: "Allow {bot} to use {app}?" ----
function PendingAppAccess({ ask, bot, actions }) {
  const [sending, setSending] = useState(false)
  const busyRef = useRef(false)
  const titleId = useId()
  const answer = (choice) => {
    if (busyRef.current) return
    busyRef.current = true
    setSending(true)
    void Promise.resolve().then(() => actions.computerAppAnswer(ask.id, choice)).catch((error) => {
      busyRef.current = false
      setSending(false)
      actions.reportError?.(error, 'computer')
    })
  }
  return h('section', { className: 'bt-q bt-computer-card', role: 'group', 'aria-labelledby': titleId },
    h('div', { className: 'bt-q-head' },
      h('div', { className: 'bt-q-text' },
        h('p', { className: 'bt-q-title', id: titleId }, t('Allow {name} to use {app}?', { name: bot.name, app: ask.appName })))),
    h('div', { className: 'bt-q-foot' },
      h('button', { type: 'button', disabled: sending, className: 'bt-q-btn', onClick: () => answer('deny') }, t('Deny')),
      h('button', { type: 'button', disabled: sending, className: 'bt-q-btn', onClick: () => answer('always') }, t('Always')),
      h('button', { type: 'button', disabled: sending, className: 'bt-q-submit', onClick: () => answer('once') }, t('This time'))))
}

// ---- The handoff card's computer variant ----
const HANDOFF_TITLES = {
  login: 'Sign-in needed',
  payment: 'Payment needed',
  captcha: 'Verification needed',
  confirm: 'Needs your confirmation',
  other: 'Help needed on the computer',
}
const handoffTitle = hold => t(HANDOFF_TITLES[hold.reason] ?? HANDOFF_TITLES.other)

function PendingComputerHandoff({ sessionId, bot, hold, actions }) {
  const [sending, setSending] = useState(false)
  const busyRef = useRef(false)
  const titleId = useId()
  const taken = hold.by === 'user'
  const run = (make, settles) => {
    if (busyRef.current) return
    busyRef.current = true
    setSending(true)
    const reset = () => { busyRef.current = false; setSending(false) }
    void Promise.resolve().then(make).then(() => {
      if (!settles) reset()
    }, (error) => {
      reset()
      actions.reportError?.(error, 'handoff')
    })
  }
  const answer = outcome => run(() => actions.computerHoldAnswer(bot.id, { callId: hold.callId ?? hold.id, outcome }), true)
  const takeOver = () => run(async () => {
    await actions.computerTakeover(bot.id)
    actions.showDetails?.(sessionId, 'computer')
  }, false)
  return h('section', { className: 'bt-q bt-computer-card bt-handoff', role: 'group', 'aria-labelledby': titleId },
    h('div', { className: 'bt-q-head' },
      h('div', { className: 'bt-q-text' },
        h('p', { className: 'bt-q-title', id: titleId }, handoffTitle(hold)),
        hold.note ? h('div', { className: 'bt-q-detail' }, hold.note) : null,
        taken ? h('div', { className: 'bt-handoff-state', role: 'status' },
          h('span', { className: 'bt-handoff-dot', 'aria-hidden': true }),
          t('You control the computer')) : null)),
    h('div', { className: 'bt-q-foot' },
      h('button', { type: 'button', disabled: sending, className: 'bt-q-btn', onClick: () => answer('skip') }, t('Skip')),
      taken ? null : h('button', { type: 'button', disabled: sending, className: 'bt-q-btn', onClick: takeOver }, t('Take over the computer')),
      h('button', { type: 'button', disabled: sending, className: 'bt-q-submit', onClick: () => answer('done') }, t("I'm done"))))
}

// Requests stay above the composer even when tool cells mount or unmount.
export function ComputerApprovalDock({ sessionId, useRoster, useComputer, actions }) {
  const bot = useRoster(value => value.byId[sessionId])
  const hold = useComputer?.(map => (bot ? map.holds?.[bot.id] : undefined))
  const ask = useComputer?.(map => (bot ? Object.values(map.asks ?? {}).find(item => item.botId === bot.id) : undefined))
  const showAccess = ask !== undefined && actions.computerAppAnswer
  const showHandoff = hold !== undefined && actions.computerHoldAnswer
  if (!bot || (!showAccess && !showHandoff)) return null
  return h('div', { className: 'bt-computer-approvals' },
    showAccess ? h(PendingAppAccess, { key: ask.id, ask, bot, actions }) : null,
    showHandoff ? h(PendingComputerHandoff, { key: hold.id, sessionId, bot, hold, actions }) : null)
}

// ---- The indicator: who is on the computer, with a Stop for each. ----
export function ComputerIndicator({ useComputer, useRoster, actions }) {
  const live = useComputer?.(map => map) ?? {}
  const roster = useRoster(value => value)
  // Native desktop builds show the paper-styled floating strip outside the window.
  if (typeof globalThis.dsBotApp?.computer === 'function') return null
  const leases = live.leases ?? []
  const waiting = Object.entries(live.bots ?? {}).filter(([, entry]) => entry.waitingFor === 'user-idle')
  if (leases.length === 0 && waiting.length === 0) return null
  const botOf = id => roster.byId[id]
  const nameOf = id => botOf(id)?.name ?? t('a Bot')
  const avatarOf = (id) => {
    const look = lookOf(botOf(id))
    if (typeof look.image === 'string' && look.image.startsWith('data:image/')) return h('img', { className: 'bt-cbar-ava', src: look.image, alt: '' })
    return h('span', { className: 'bt-cbar-ava bt-cbar-ava-dot', style: { background: look.color } }, String(nameOf(id)).slice(0, 1))
  }
  const entries = [
    ...leases.map(entry => ({ key: `l:${entry.botId}`, botId: entry.botId, waiting: false, app: entry.kind === 'foreground' ? t('In the foreground') : entry.appName })),
    ...waiting.map(([botId]) => ({ key: `w:${botId}`, botId, waiting: true, app: t('waits for the computer') })),
  ]
  return h('div', { className: 'bt-cbar', role: 'status' },
    h('span', { className: 'bt-cbar-live', title: t('Computer use') }),
    ...entries.flatMap((entry, index) => [
      index > 0 ? h('span', { key: `s${index}`, className: 'bt-cbar-sep' }) : null,
      h('span', { key: entry.key, className: entry.waiting ? 'bt-cbar-entry bt-cbar-wait' : 'bt-cbar-entry' },
        avatarOf(entry.botId),
        h('span', { className: 'bt-cbar-text' },
          h('b', { className: 'bt-cbar-name' }, nameOf(entry.botId)),
          h('i', { className: 'bt-cbar-app' }, entry.app)),
        entry.waiting
          ? h('button', { type: 'button', className: 'bt-cbar-go', onClick: () => void actions.computerAllowForeground(entry.botId) }, t('Let it continue'))
          : h('button', { type: 'button', className: 'bt-cbar-stop', 'aria-label': t('Stop'), title: t('Stop'), onClick: () => void actions.computerStop(entry.botId) },
              h('span', { className: 'bt-cbar-stopsq' }))),
    ]),
    leases.length > 1 ? h('button', { type: 'button', className: 'bt-cbar-all', onClick: () => void actions.computerStop(null, true) }, t('Stop all')) : null)
}

export const COMPUTER_CSS = `
/* ChemClaw paper-theme styling: all surfaces inherit existing theme tokens. */
.bt-computer-page{display:flex;flex-direction:column;gap:20px}
.bt-computer-page .bt-set-card{background:var(--bt-main);border:1px solid var(--bt-line);border-radius:12px}
.bt-computer-page .bt-set-section h3{letter-spacing:.01em}
.bt-cview{padding:12px;border-radius:12px;background:var(--bt-main);border:1px solid var(--bt-line)}
.bt-level-pick{max-width:200px}
.bt-perm-state{font-size:13px;color:var(--bt-ink-2);margin-right:8px}
.bt-perm-state[data-on]{color:var(--bt-green)}
.bt-cview{display:flex;flex-direction:column;gap:12px}
.bt-cview-head{display:flex;align-items:center;gap:8px}
.bt-cview-state{font-size:13px;font-weight:500}
.bt-cview-state[data-state=user]{color:var(--bt-accent)}
.bt-cview-app{font-size:13px;color:var(--bt-ink-2)}
.bt-cview-shot{max-width:100%;border-radius:8px;border:1px solid var(--bt-line)}
.bt-cview-actions{display:flex;gap:8px}
.bt-cview-steps{display:flex;flex-direction:column;gap:4px}
.bt-cview-step{display:flex;align-items:center;gap:6px;font-size:12.5px;color:var(--bt-ink-2)}
.bt-cview-step[data-ok=no]{color:var(--bt-danger)}
.bt-cview-step-err{font-size:11px}
.bt-cbar{position:absolute;top:8px;left:50%;transform:translateX(-50%);z-index:60;display:flex;align-items:center;gap:8px;max-width:min(760px,calc(100vw - 32px));padding:6px 12px;border-radius:999px;background:var(--bt-main);border:1px solid var(--bt-line);box-shadow:0 3px 16px color-mix(in srgb,var(--bt-ink) 9%,transparent);backdrop-filter:none;font-size:12.5px}
.bt-cbar-live{flex:none;width:7px;height:7px;border-radius:50%;background:var(--bt-danger);box-shadow:0 0 0 3px var(--bt-danger-glow)}
.bt-cbar-sep{flex:none;width:1px;height:14px;background:var(--bt-line);opacity:.7}
.bt-cbar-entry{display:flex;align-items:center;gap:6px;min-width:0}
.bt-cbar-ava{flex:none;width:16px;height:16px;border-radius:50%;object-fit:cover}
.bt-cbar-ava-dot{display:inline-flex;align-items:center;justify-content:center;color:var(--bt-mark-ink);font-size:9px;font-weight:600;line-height:1}
.bt-cbar-text{display:flex;align-items:baseline;gap:5px;min-width:0;overflow:hidden}
.bt-cbar-name{flex:none;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bt-cbar-app{font-style:normal;color:var(--bt-ink-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:120px}
.bt-cbar-stop{flex:none;width:22px;height:22px;border:0;border-radius:50%;background:var(--bt-hover);color:var(--bt-ink-2);cursor:pointer;display:inline-flex;align-items:center;justify-content:center}
.bt-cbar-stopsq{width:8px;height:8px;border-radius:4px;background:currentColor}
.bt-cbar-stop:hover{background:var(--bt-danger);color:var(--bt-mark-ink)}
.bt-cbar-go,.bt-cbar-all{flex:none;border-radius:999px;padding:3px 10px;font:inherit;font-size:12px;cursor:pointer;white-space:nowrap;border:1px solid var(--bt-line-2)}
.bt-cbar-go{background:var(--bt-accent-soft);color:var(--bt-accent);border-color:var(--bt-accent-soft)}
.bt-cbar-all{background:var(--bt-danger-soft);color:var(--bt-danger);border-color:var(--bt-danger-soft)}
.bt-computer-approvals{display:grid;grid-template-columns:minmax(0,1fr);gap:6px;width:calc(100% - 32px);max-width:var(--dsh-composer-card-max-width,748px);max-height:min(40vh,300px);overflow:auto;margin:6px auto 8px}
.bt-q.bt-computer-card{width:100%;max-width:none;min-width:0;margin:0;padding:10px 12px;box-sizing:border-box;gap:8px;background:var(--bt-main);animation:none}
.bt-computer-card .bt-q-text{min-width:0;overflow-wrap:anywhere}
.bt-computer-card .bt-q-foot{flex-wrap:wrap}
.bt-computer-card button:disabled{opacity:.55;cursor:default}
`
