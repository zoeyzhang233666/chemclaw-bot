import { createElement as h, useMemo } from 'react'
import { skillCategory, skillLabel } from '../shared/skills.js'
import { language, t } from './i18n.js'
import { freePriority } from './surface.js'
import { NATIVE_SKILL_ZH } from './native-skill-copy.js'

export function localizedSkillSnapshot(snapshot, capabilities, locale = language()) {
  const items = new Map(capabilities.filter(item => item.kind === 'skill').map(item => [item.originalName, item]))
  for (const item of capabilities) items.set(item.name, item)
  return { ...snapshot, groups: snapshot.groups.map(group => !['skill', 'chemclaw-skills'].includes(group.source) ? group : {
    ...group, items: group.items.map(candidate => {
      const item = items.get(candidate.name)
      const copy = locale.startsWith('zh') && item?.kind !== 'skill' ? NATIVE_SKILL_ZH[candidate.name] : undefined
      const label = copy?.[0] || (item ? skillLabel(item, locale) : candidate.label || candidate.name)
      const description = copy?.[1] || (item ? item.purpose || item.description : candidate.description)
      // Picks are routed by source and index against the original controller.
      return { ...candidate, name: label, label, description, section: item ? t(skillCategory(item)) : candidate.section }
    }),
  }) }
}

// Keep the host's menu, navigation indices, focus and keyboard behavior. Only
// the display metadata changes; the original source still owns every pick.
export function LocalizedSkillMenu({ baseMenu, useRoster, menu, ...props }) {
  const capabilities = useRoster(state => state.capabilities)
  const localized = useMemo(() => {
    let previous
    let current
    return { subscribe: listener => menu.subscribe(listener), getSnapshot: () => {
      const snapshot = menu.getSnapshot()
      if (snapshot === previous) return current
      previous = snapshot
      current = localizedSkillSnapshot(snapshot, capabilities)
      return current
    } }
  }, [menu, capabilities, language()])
  return h('div', { className: 'bt-skill-menu' }, h(baseMenu, { ...props, menu: localized }))
}

export function installSkillMenu(slots, face, priority) {
  const name = 'conversation.input.overlay'
  let source
  let dispose
  const refresh = () => {
    const entries = slots.entries(name).filter(entry => entry.component !== LocalizedSkillMenu)
    const next = entries.find(entry => entry.locale === 'slash.menu' && typeof entry.inject === 'function')
    if (source === next && dispose) return
    dispose?.()
    source = next
    if (!source) { dispose = undefined; return }
    dispose = slots.register({ ...source.options, name, locale: source.locale, priority: freePriority(entries, { ...source.options, priority }),
      ...(source.store ? { store: source.store } : {}), inject: (...args) => {
        const original = source.inject(...args)
        const own = face()
        return { ...original, ...own, baseMenu: source.component, hooks: { ...original.hooks, ...own.hooks } }
      } }, LocalizedSkillMenu)
  }
  const off = slots.subscribe(name, refresh)
  try { refresh() } catch (error) { off(); throw error }
  return () => { off(); dispose?.() }
}

export function LocalizedSkillReference({ baseReference, useRoster, actions, node, interactive, raw, ...props }) {
  const item = useRoster(state => state.capabilities.find(item => item.kind === 'skill' && (item.name === node.data.name || item.originalName === node.data.name)))
  if (!item) {
    return baseReference
      ? h(baseReference, { ...props, node, interactive, raw })
      : h('span', { title: raw || `/${node.data.name}` }, raw || `/${node.data.name}`)
  }
  const label = skillLabel(item, language())
  return interactive ? h('button', { type: 'button', className: 'bt-umention', title: `/${item.name}`, onClick: () => actions.openSettings('capabilities', item.name) }, label) : h('span', { title: `/${item.name}` }, label)
}

function wrapNativeSkillReference(slots, face, priority) {
  const name = 'conversation.user.text.node'
  let source
  let dispose
  const refresh = () => {
    const entries = slots.entries(name).filter(entry => entry.component !== LocalizedSkillReference)
    const next = entries.find(entry => entry.options?.key === 'skill')
    if (source === next && dispose) return
    dispose?.()
    source = next
    if (!source) { dispose = undefined; return }
    dispose = slots.register({ ...source.options, name, locale: source.locale, priority: freePriority(entries, { ...source.options, priority }),
      ...(source.store ? { store: source.store } : {}), inject: (...args) => {
        const original = source.inject?.(...args) ?? {}
        const own = face()
        return { ...original, ...own, baseReference: source.component, hooks: { ...original.hooks, ...own.hooks } }
      } }, LocalizedSkillReference)
  }
  const off = slots.subscribe(name, refresh)
  try { refresh() } catch (error) { off(); throw error }
  return () => { off(); dispose?.() }
}

export function installSkillReference(slots, face, priority) {
  const name = 'conversation.user.text.node'
  const disposeOwn = slots.register({
    name,
    key: 'chemclaw-skill',
    priority: freePriority(slots.entries(name), { name, key: 'chemclaw-skill', priority }),
    inject: () => face(),
  }, LocalizedSkillReference)
  const disposeNative = wrapNativeSkillReference(slots, face, priority)
  return () => { disposeOwn(); disposeNative() }
}

