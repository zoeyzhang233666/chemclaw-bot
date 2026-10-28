import { createElement as h, useEffect, useId, useState } from 'react'
import { createPortal } from 'react-dom'
import { SKILL_EMOJIS, skillEmoji } from '../shared/skill-presentation.js'
import { Caret, useAnchoredMenu } from './model-menu.js'
import { CheckIcon, CloseIcon } from './icons.js'
import { t } from './i18n.js'

const RECOMMENDATIONS = {
  '内贸采购': ['🏭', '🔍', '🛒', '🏷️', '🧮', '🚚', '📍', '📜', '🛡️', '🪪', '🧪', '⚖️'],
  '外贸采购': ['🚢', '🏭', '🌍', '🔍', '🧮', '💱', '📜', '🛃', '📋', '✅', '🪟', '🛡️'],
  '内贸销售': ['🎯', '🤝', '💬', '✍️', '🗺️', '📈', '🏷️', '📝', '🏗️', '🏢', '🧭', '⭐'],
  '外贸销售': ['🌍', '🎯', '📨', '🤝', '📜', '💱', '🧾', '🧮', '🛃', '✅', '🔎', '🧭'],
  '产业基本面': ['🔭', '🏭', '📈', '🗺️', '🕸️', '🏗️', '📰', '📑', '💰', '📦', '⚙️', '🧭'],
  '价差与量化': ['📊', '📏', '⚖️', '📦', '🔗', '⏱️', '📡', '🧪', '🔬', '🌦️', '🗓️', '↔️'],
  '科学分析': ['🔬', '🧬', '⚗️', '📊', '📐', '🔢', '🧪', '🕸️', '🔗', '🧮', '📑', '💻'],
}
const COMMON = ['📄', '📊', '🔍', '🧮', '💬', '🧬', '🏭', '🎯', '🗺️', '📜', '🎞️', '🧰']

export function SkillEmojiPicker({ item, value = '', onChange, disabled = false }) {
  const { isOpen, shownPlace, leaving, button, menu, open, close } = useAnchoredMenu({ width: 280, followScroll: true })
  const [more, setMore] = useState(false)
  const id = useId()
  const automatic = skillEmoji({ ...item, emoji: '' })
  const category = item.category?.replace(/^期现-/, '')
  const recommended = Object.hasOwn(RECOMMENDATIONS, category) ? RECOMMENDATIONS[category] : COMMON
  const suggestions = [...new Set([value || automatic, automatic, ...recommended, ...COMMON])].slice(0, 12)
  const choices = more ? [...new Set([...suggestions, ...SKILL_EMOJIS])] : suggestions
  useEffect(() => {
    if (isOpen) (menu.current?.querySelector('[aria-pressed="true"]') || menu.current?.querySelector('.bt-skill-emoji-auto'))?.focus({ preventScroll: true })
  }, [isOpen])
  const pick = emoji => { onChange(emoji); close(); button.current?.focus() }
  const navigate = event => {
    if (!event.target.matches('[data-emoji]')) return
    const grid = event.target.parentElement
    const buttons = [...grid.querySelectorAll('[data-emoji]')]
    const index = buttons.indexOf(event.target)
    const columns = getComputedStyle(grid).gridTemplateColumns.split(' ').length
    const next = { ArrowRight: index + 1, ArrowLeft: index - 1, ArrowDown: index + columns, ArrowUp: index - columns, Home: 0, End: buttons.length - 1 }[event.key]
    if (next === undefined) return
    event.preventDefault()
    buttons[Math.max(0, Math.min(next, buttons.length - 1))]?.focus()
  }
  return h('div', { className: 'bt-skill-icon-field', role: 'group', 'aria-labelledby': `${id}-label`,
    onBlur: event => { if (!menu.current?.contains(event.relatedTarget) && !button.current?.contains(event.relatedTarget)) close() } },
    h('span', { id: `${id}-label` }, t('Skill icon')),
    h('button', { ref: button, type: 'button', className: 'bt-skill-icon-trigger', disabled,
      'aria-label': t('Choose skill icon'), 'aria-haspopup': 'dialog', 'aria-expanded': isOpen, 'aria-controls': shownPlace ? `${id}-panel` : undefined,
      onClick: () => { if (isOpen) close(); else { setMore(false); open() } } },
      h('span', { className: 'bt-skill-glyph', 'aria-hidden': true }, value || automatic),
      h('span', { className: 'bt-skill-icon-caption' }, t(value ? 'Custom icon' : 'Automatic match')), h(Caret)),
    h('small', null, t('Matched by purpose. Choose another emoji at any time.')),
    shownPlace ? createPortal(h('div', { ref: menu, id: `${id}-panel`, className: `bt-menu bt-skill-emoji-panel${shownPlace.bottom !== undefined ? ' bt-menu-up' : ''}`,
      role: 'dialog', 'aria-label': t('Choose skill icon'), style: shownPlace, 'data-leaving': leaving || undefined, onKeyDown: navigate },
      h('div', { className: 'bt-skill-emoji-head' }, h('strong', null, t('Choose skill icon')),
        h('button', { type: 'button', className: 'bt-skill-emoji-close', 'aria-label': t('Close icon picker'), onClick: () => { close(); button.current?.focus() } }, h(CloseIcon))),
      h('button', { type: 'button', className: 'bt-skill-emoji-auto', 'aria-pressed': !value, onClick: () => pick('') },
        h('span', { className: 'bt-skill-emoji-preview', 'aria-hidden': true }, automatic), h('span', null, t('Match the skill automatically')), !value ? h(CheckIcon) : null),
      h('span', { className: 'bt-skill-emoji-heading' }, t(more ? 'All icons' : 'Suggested icons')),
      h('div', { className: 'bt-skill-emoji-grid', role: 'group', 'aria-label': t(more ? 'All icons' : 'Suggested icons') }, choices.map(emoji => h('button', {
        key: emoji, type: 'button', className: 'bt-skill-emoji-option', 'data-emoji': emoji, 'aria-pressed': value === emoji,
        'aria-label': t('Use icon {emoji}', { emoji }), onClick: () => pick(emoji),
      }, h('span', { 'aria-hidden': true }, emoji)))),
      h('button', { type: 'button', className: 'bt-skill-emoji-more', 'aria-expanded': more, onClick: () => setMore(value => !value) }, t(more ? 'Fewer icons' : 'More icons'))), document.body) : null)
}

export const SKILL_EMOJI_CSS = `
.bt-skill-icon-field{display:flex;flex-direction:column;gap:8px;font-size:12px;color:var(--bt-ink-2);min-width:0}
.bt-skill-icon-field>small{font-size:11px;color:var(--bt-ink-3);line-height:1.6}
.bt-skill-icon-trigger{display:flex;align-items:center;gap:10px;width:220px;max-width:100%;padding:8px;border:1px solid var(--bt-line);border-radius:12px;background:var(--bt-card);color:var(--bt-ink);font:inherit;text-align:left;cursor:pointer}
.bt-skill-icon-trigger:hover,.bt-skill-icon-trigger[aria-expanded=true]{background:var(--bt-hover);border-color:var(--bt-line-2)}
.bt-skill-icon-trigger:disabled{opacity:.5;cursor:default}
.bt-skill-icon-trigger .bt-skill-glyph{width:36px;height:36px;font-size:24px;border-radius:8px}
.bt-skill-icon-caption{flex:1;min-width:0}
.bt-menu.bt-skill-emoji-panel{padding:12px;gap:10px;overflow-y:auto;scrollbar-width:thin}
.bt-skill-emoji-head{display:flex;align-items:center;justify-content:space-between;gap:12px}
.bt-skill-emoji-head strong{font-size:13px;font-weight:500}
.bt-menu .bt-skill-emoji-close{width:26px;min-height:26px;padding:4px;justify-content:center;color:var(--bt-ink-3)}
.bt-menu .bt-skill-emoji-auto{gap:8px;font-size:12px;line-height:1.6;border:1px solid transparent;border-radius:8px;padding:8px}
.bt-skill-emoji-auto>span:nth-child(2){flex:1}
.bt-menu .bt-skill-emoji-auto[aria-pressed=true]{background:var(--bt-hover);border-color:var(--bt-line)}
.bt-skill-emoji-preview,.bt-skill-emoji-option>span{font-family:"Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",sans-serif;font-size:22px;line-height:1}
.bt-skill-emoji-heading{font-size:11px;line-height:1.5;color:var(--bt-ink-3)}
.bt-skill-emoji-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px;max-height:240px;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;padding:2px;box-sizing:border-box}
.bt-menu .bt-skill-emoji-option{justify-content:center;padding:0;min-height:36px;aspect-ratio:1;border:1px solid transparent;border-radius:8px}
.bt-menu .bt-skill-emoji-option[aria-pressed=true]{background:color-mix(in srgb,var(--bt-accent) 9%,var(--bt-main));border-color:color-mix(in srgb,var(--bt-accent) 45%,var(--bt-line))}
.bt-menu .bt-skill-emoji-more{justify-content:center;min-height:30px;font-size:11px;color:var(--bt-ink-3);border-top:1px solid var(--bt-line);border-radius:0;padding:10px 4px 0}
.bt-skill-icon-trigger:focus-visible,.bt-skill-emoji-panel button:focus-visible{outline:2px solid var(--bt-accent);outline-offset:1px}
@media(pointer:coarse){.bt-skill-emoji-grid{grid-template-columns:repeat(5,minmax(0,1fr))}.bt-menu .bt-skill-emoji-option,.bt-menu .bt-skill-emoji-auto,.bt-menu .bt-skill-emoji-more{min-height:44px}.bt-menu .bt-skill-emoji-close{width:44px;min-height:44px}}
`
