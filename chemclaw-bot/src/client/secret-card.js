// Secret cards: a Bot's request_secret shows a card where the user types a key the
// Bot never sees, or lets the Bot use a key that is already saved. Values only ever
// travel from these inputs to the host; nothing here reads one back.
import { createElement as h, useId, useRef, useState } from 'react'
import { CheckIcon, CloseIcon } from './icons.js'
import { BotMark } from './mark.js'
import { contentText, currentPart } from './text.js'
import { t } from './i18n.js'
import { SPRING_POP, SPRING_SHAPE, spring } from './motion.js'
import { useDockHold } from './card-hold.js'
import { heldCardKey } from './sources.js'

const MIN_VALUE = 4
const NONE = {}

export const KeyIcon = () => h('svg', { width: 15, height: 15, viewBox: '0 0 20 20', fill: 'none', stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true },
  h('path', { d: 'M7 9.5a3.5 3.5 0 1 1 0 .01z' }), h('path', { d: 'M10.4 10.6L17 10.6M14.5 10.6v2.4M16.6 10.6v1.8' }))
const LockIcon = () => h('svg', { width: 14, height: 14, viewBox: '0 0 20 20', fill: 'none', stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true },
  h('path', { d: 'M6.5 9V7a3.5 3.5 0 0 1 7 0v2' }), h('rect', { x: 4.5, y: 9, width: 11, height: 8, rx: 2 }))
const WarnIcon = () => h('svg', { width: 14, height: 14, viewBox: '0 0 20 20', fill: 'none', stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true },
  h('path', { d: 'M10 3.5l7 12.5H3z' }), h('path', { d: 'M10 8.5v3.5M10 14.2h.01' }))

// Password managers ignore a text field masked by CSS, so it never offers to save the
// key; browsers without that CSS fall back to a new-password field.
const MASK_BY_CSS = typeof CSS !== 'undefined' && typeof CSS.supports === 'function' && CSS.supports('-webkit-text-security', 'disc')

const insecure = () => typeof location !== 'undefined' && location.protocol === 'http:'
  && !/^(localhost|127(?:\.\d{1,3}){3}|\[::1\])$/.test(location.hostname)

const scopeLabel = (scope, roster) => {
  if (scope === 'all') return t('All Bots')
  const names = (scope ?? []).map(id => roster.byId[id]?.name).filter(Boolean)
  return names.length === 0 ? t('No Bot') : names.join(t(' and '))
}

export function MaskedInput({ value, onChange, onEnter, label, autoFocus = false }) {
  return h('input', {
    className: 'bt-secret-input',
    type: MASK_BY_CSS ? 'text' : 'password',
    'data-masked': MASK_BY_CSS ? '' : undefined,
    value,
    autoFocus,
    autoComplete: MASK_BY_CSS ? 'off' : 'new-password',
    autoCorrect: 'off',
    autoCapitalize: 'off',
    spellCheck: false,
    'data-1p-ignore': '',
    'data-lpignore': 'true',
    'data-bwignore': '',
    'data-form-type': 'other',
    'aria-label': label,
    placeholder: t('Paste or type the key'),
    onChange: event => onChange(event.target.value),
    onKeyDown: (event) => {
      if (event.key !== 'Enter' || event.nativeEvent.isComposing) return
      event.preventDefault()
      onEnter?.()
    },
  })
}

function ScopeSwitch({ value, onChange, bot }) {
  const options = [['all', t('All Bots')], ['bot', t('Only {name}', { name: bot.name })]]
  return h('div', { className: 'bt-secret-scope', role: 'radiogroup', 'aria-label': t('Who may use it') },
    h('span', { className: 'bt-secret-glide', 'data-at': value === 'all' ? 0 : 1, 'aria-hidden': true }),
    options.map(([id, text]) => h('button', {
      key: id, type: 'button', role: 'radio', 'aria-checked': value === id, className: 'bt-secret-seg', onClick: () => onChange(id),
    }, text)))
}

function SecretHead({ bot, title, detail, name, onClose }) {
  return h('div', { className: 'bt-q-head bt-secret-head' },
    h('span', { className: 'bt-secret-who' }, h(BotMark, { bot, size: 28 }), h('span', { className: 'bt-secret-lock' }, h(LockIcon))),
    h('div', { className: 'bt-q-text' },
      h('p', { className: 'bt-q-title' }, title),
      h('div', { className: 'bt-q-detail' }, h('code', { className: 'bt-secret-name' }, name), detail ? ` · ${detail}` : '')),
    onClose ? h('button', { type: 'button', className: 'bt-q-x', 'aria-label': t('Cancel the request'), title: t('Cancel'), onClick: onClose }, h(CloseIcon)) : null)
}

export function SecretCard({ sessionId, bot, request, roster, actions, inline = false }) {
  const [value, setValue] = useState('')
  const [scope, setScope] = useState('all')
  const [replacing, setReplacing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const busyRef = useRef(false)
  const hold = useDockHold(sessionId, 'secret', request.id, actions, inline)
  const noteId = useId()
  const secret = (roster.secrets ?? []).find(entry => entry.name === request.name)
  const run = (make) => {
    if (busyRef.current) return undefined
    hold()
    busyRef.current = true
    setBusy(true)
    setError('')
    return Promise.resolve().then(make).then(() => setValue(''), failure => setError(failure?.message ?? String(failure))).finally(() => {
      busyRef.current = false
      setBusy(false)
    })
  }
  const cancel = () => run(() => actions.secretCancel(request.id))
  const long = value.trim().length >= MIN_VALUE
  const save = () => { if (long && !busy) void run(() => actions.secretSet({ requestId: request.id, value, scope })) }
  const allow = () => { if (!busy) void run(() => actions.secretAllow(request.id)) }
  const filling = request.kind === 'fill' || replacing
  const warn = insecure() ? h('div', { className: 'bt-secret-warn', role: 'note' }, h(WarnIcon), t('This page is not on HTTPS: the key crosses the network unencrypted.')) : null
  return h('div', { className: 'bt-q bt-secret bt-secret-card', role: 'group', 'aria-describedby': noteId, 'data-kind': request.kind, onFocusCapture: hold, onPointerDownCapture: hold },
    h(SecretHead, {
      bot,
      title: request.kind === 'allow' ? t('Let {bot} use {name}?', { bot: bot.name, name: request.name }) : t('{name} needs a key', { name: bot.name }),
      detail: request.purpose,
      name: request.name,
      onClose: busy ? undefined : cancel,
    }),
    request.kind === 'allow' ? h('div', { className: 'bt-secret-saved' }, h(KeyIcon), t('Saved for {scope}', { scope: scopeLabel(secret?.scope, roster) })) : null,
    filling ? h('div', { className: 'bt-secret-body' },
      h('label', { className: 'bt-q-field bt-secret-field' }, h(MaskedInput, { value, onChange: next => { hold(); setValue(next) }, onEnter: save, label: t('Value of {name}', { name: request.name }), autoFocus: replacing })),
      request.kind === 'fill' ? h(ScopeSwitch, { value: scope, onChange: next => { hold(); setScope(next) }, bot }) : null) : null,
    h('div', { className: 'bt-secret-note', id: noteId },
      t('Saved securely for tools within the authorization scope. The value is not sent as chat text.'),
      filling && value !== '' && !long ? t(' At least {count} characters.', { count: MIN_VALUE }) : ''),
    warn,
    error ? h('div', { className: 'bt-secret-error', role: 'alert' }, error) : null,
    h('div', { className: 'bt-q-foot' },
      request.kind === 'allow' && !replacing ? h('button', { type: 'button', className: 'bt-q-btn', disabled: busy, onClick: () => { hold(); setReplacing(true) } }, t('Replace value')) : null,
      h('button', { type: 'button', className: 'bt-q-btn', disabled: busy, onClick: cancel }, t('Cancel')),
      filling
        ? h('button', { type: 'button', className: 'bt-q-submit', disabled: !long || busy, onClick: save }, busy ? t('Saving…') : t('Save'))
        : h('button', { type: 'button', className: 'bt-q-submit', disabled: busy, onClick: allow }, busy ? t('Allowing…') : t('Allow'))))
}

function SettledSecret({ bot, request, roster }) {
  const canceled = request.status === 'canceled'
  const text = canceled ? t('{bot} asked for {name}', { bot: bot.name, name: request.name })
    : request.status === 'allowed' ? t('Allowed {bot} to use {name}', { bot: bot.name, name: request.name })
      : t('Saved {name}', { name: request.name })
  return h('div', { className: 'bt-q bt-q-settled bt-secret bt-secret-done', role: 'group', 'aria-label': text, 'data-status': request.status },
    h('div', { className: 'bt-q-head' },
      h('span', { className: 'bt-secret-who' }, h(BotMark, { bot, size: 22 })),
      h('div', { className: 'bt-q-text' }, h('p', { className: 'bt-q-title' }, text,
        canceled ? null : h('span', { className: 'bt-secret-scope-tag' }, ` · ${scopeLabel(request.scope, roster)}`))),
      canceled ? h('span', { className: 'bt-q-badge' }, t('Canceled')) : h('span', { className: 'bt-q-check bt-secret-check', title: t('Done') }, h(CheckIcon))))
}

function RequestView({ sessionId, bot, request, roster, actions }) {
  return request.status === 'pending'
    ? h(SecretCard, { key: JSON.stringify([sessionId, request.id, request.kind]), sessionId, bot, request, roster, actions, inline: true })
    : h(SettledSecret, { bot, request, roster })
}

// The card at its request_secret call; a key that was already there gets one line.
export function SecretToolCell({ sessionId, callId, name, done, content, roster, actions, heldCards = NONE }) {
  const bot = roster.byId[sessionId]
  if (!bot) return null
  // Call ids repeat across a Bot's chat parts.
  const request = (roster.secretRequests?.[bot.id] ?? []).find(entry => entry.callId === callId && (entry.sessionId ?? sessionId) === sessionId)
  if (request?.status === 'pending' && heldCards[heldCardKey('secret', request.id)] > 0) return null
  if (request) return h('div', { className: 'bt-q-inline' }, h(RequestView, { sessionId, bot, request, roster, actions }))
  if (done && /already saved/.test(contentText(content))) {
    return h('div', { className: 'bt-event' }, h('span', { className: 'bt-secret-event' }, h(KeyIcon), t('{bot} is using {name}', { bot: bot.name, name: name ?? t('a saved key') })))
  }
  return null
}

// A card whose call the transcript does not draw (an earlier part of the chat, a
// hidden turn, a call outside the loaded history) waits above the composer instead.
// Once editing starts it keeps that component until completion or cancellation.
export function SecretDock({ sessionId, useRoster, useCards, useHeldCards, actions }) {
  const roster = useRoster(value => value)
  const shown = useCards?.(state => state[sessionId]) ?? NONE
  const held = useHeldCards?.(state => state[sessionId]) ?? NONE
  const bot = roster.byId[sessionId]
  if (!bot || currentPart(bot) !== sessionId) return null
  const drawn = entry => entry.callId && entry.sessionId === sessionId && shown[entry.callId] > 0 && !(held[heldCardKey('secret', entry.id)] > 0)
  const waiting = (roster.secretRequests?.[bot.id] ?? []).filter(entry => entry.status === 'pending' && !drawn(entry))
  if (waiting.length === 0) return null
  return h('div', { className: 'bt-q-dock bt-secret-dock' }, waiting.map(request => h(SecretCard, { key: JSON.stringify([sessionId, request.id, request.kind]), sessionId, bot, request, roster, actions })))
}

export const SECRET_CSS = `
.bt-secret-head{align-items:center;gap:10px}
.bt-secret-who{position:relative;flex:none;display:inline-flex}
.bt-secret-lock{position:absolute;right:-5px;bottom:-4px;width:16px;height:16px;border-radius:50%;background:var(--bt-main);color:var(--bt-ink-2);display:inline-flex;align-items:center;justify-content:center;box-shadow:0 0 0 1.5px var(--bt-bubble)}
.bt-secret-lock svg{width:11px;height:11px}
.bt-secret-name{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;line-height:16px;padding:1px 6px;border-radius:5px;background:var(--bt-hover);color:var(--bt-ink)}
.bt-secret-body{display:flex;flex-direction:column;gap:8px}
.bt-secret-field{align-items:center;min-height:36px}
.bt-secret-input{flex:1;width:100%;min-width:0;margin:0;padding:0;border:0;outline:none;background:transparent;color:var(--bt-ink);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:14px;line-height:20px;letter-spacing:.04em}
.bt-secret-input[data-masked]{-webkit-text-security:disc}
.bt-secret-input::placeholder{color:var(--bt-ink-3);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;letter-spacing:0}
.bt-secret-scope{position:relative;display:inline-grid;grid-template-columns:1fr 1fr;align-self:flex-start;padding:2px;border-radius:999px;background:var(--bt-hover)}
.bt-secret-glide{position:absolute;top:2px;bottom:2px;left:2px;width:calc(50% - 2px);border-radius:999px;background:var(--bt-main);box-shadow:0 1px 3px rgba(20,20,20,.08),inset 0 0 0 .5px color-mix(in srgb,var(--bt-ink) 6%,transparent);transition:${spring(SPRING_SHAPE, 'transform')}}
.bt-secret-glide[data-at="1"]{transform:translateX(100%)}
.bt-secret-seg{position:relative;z-index:1;height:28px;padding:0 14px;border:0;border-radius:999px;background:none;color:var(--bt-ink-2);font:inherit;font-size:13px;white-space:nowrap;cursor:pointer;transition:color .16s ease}
.bt-secret-seg[aria-checked=true]{color:var(--bt-ink);font-weight:500}
.bt-secret-seg:focus-visible{outline:2px solid var(--bt-accent);outline-offset:-2px}
/* A key card asks the user to act, so the process group carrying it stays open in every
   work-details mode (same override as .bt-group-replies in styles.js). */
[data-step-process]:has(.bt-secret)>div:first-child{display:none!important}
[data-step-process]:has(.bt-secret)>[data-step-process-body]{display:block!important;content-visibility:visible!important;max-height:none!important;overflow:visible!important;mask-image:none!important;scrollbar-gutter:auto!important}
.bt-secret-ok{display:flex;align-items:center;gap:4px;margin-top:6px;animation:bt-secret-in .22s cubic-bezier(.22,1,.36,1)}
.bt-secret-ok svg{width:13px;height:13px;color:#16a34a}
@keyframes bt-secret-in{from{opacity:0;transform:translateY(-2px)}}
.bt-secret-saved{display:flex;align-items:center;gap:6px;font-size:13px;line-height:18px;color:var(--bt-ink-2)}
.bt-secret-note{font-size:12px;line-height:17px;color:var(--bt-ink-3)}
.bt-secret-note code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11.5px}
.bt-secret-warn{display:flex;align-items:center;gap:6px;padding:6px 10px;border-radius:8px;font-size:12px;line-height:16px;color:#b25e09;background:color-mix(in srgb,#f59e0b 12%,transparent)}
.bt-secret-error{font-size:12px;line-height:16px;color:var(--bt-danger)}
.bt-secret .bt-q-btn:disabled{opacity:.5;cursor:default}
.bt-secret-done .bt-q-head{align-items:center}
.bt-secret-done .bt-q-title{font-size:13px;line-height:18px;color:var(--bt-ink-2);font-weight:500}
.bt-secret-scope-tag{font-weight:400;color:var(--bt-ink-3)}
.bt-secret-check{color:var(--bt-green,#22a06b);animation:bt-secret-pop ${SPRING_POP.duration}ms ${SPRING_POP.easing} backwards}
.bt-secret-done{animation:bt-secret-settle .32s cubic-bezier(.22,1,.36,1) backwards}
@keyframes bt-secret-pop{from{opacity:0;transform:scale(.4)}}
@keyframes bt-secret-settle{from{opacity:.4;transform:scale(.985)}}
.bt-secret-event{display:inline-flex;align-items:center;gap:5px}
.bt-secret-dock{flex-direction:column;align-items:center}
.bt-secret-dock .bt-q{max-width:min(550px,calc(100% - 32px))}
@media (prefers-reduced-motion:reduce){.bt-secret-glide{transition:none}.bt-secret-check,.bt-secret-done,.bt-secret-ok{animation:none}}
`
