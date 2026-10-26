import { matchingSkills, isUserSkill, SKILL_CATEGORIES, skillCategory, skillLabel } from '../shared/skills.js'
import { language, t } from './i18n.js'

export const SKILLS_SOURCE = 'chemclaw-skills'

export function nativeSkillRows(controller, signal) {
  if (!controller) return Promise.resolve([])
  return new Promise(resolve => {
    let off = () => {}
    const finish = rows => { off(); signal?.removeEventListener('abort', aborted); resolve(rows) }
    const aborted = () => finish([])
    const inspect = () => {
      const group = controller.menu.getSnapshot().groups.find(group => group.source === 'skill')
      if (!group || group.status === 'ready') finish(group?.items ?? [])
    }
    off = controller.menu.subscribe(inspect)
    signal?.addEventListener('abort', aborted, { once: true })
    if (signal?.aborted) aborted()
    else inspect()
  })
}

export function skillRows(roster, sessionId, query = '') {
  const bot = roster.byId[sessionId]
  const room = roster.roomsById[sessionId]
  if (!bot && !room) return []
  const assigned = new Set((room ? room.members.map(id => roster.byId[id]).filter(Boolean) : [bot]).flatMap(bot => bot.capabilities ?? []))
  for (const name of [...assigned]) {
    const pack = roster.capabilities.find(item => item.name === name && item.kind === 'pack')
    for (const child of pack?.items ?? []) assigned.add(child)
  }
  return matchingSkills(roster.capabilities ?? [], query, '', language()).filter(isUserSkill)
    .sort((a, b) => Number(assigned.has(b.name)) - Number(assigned.has(a.name)) || (assigned.has(a.name) ? 0 : SKILL_CATEGORIES.indexOf(skillCategory(a)) - SKILL_CATEGORIES.indexOf(skillCategory(b))) || skillLabel(a, language()).localeCompare(skillLabel(b, language()), language(), { numeric: true }))
    .map(item => ({ name: item.name, label: skillLabel(item, language()), description: item.purpose || item.description,
      section: assigned.has(item.name) ? t('Recommended for this conversation') : t(skillCategory(item)), value: item.name }))
}

export function skillSource({ roster, actions, controllerOf }) {
  return {
    trigger: '/', name: SKILLS_SOURCE, order: -20, showGroupTitle: false,
    candidates: async (session, { query, signal }) => {
      const native = new Set((await nativeSkillRows(controllerOf?.(session.sessionId), signal)).map(item => item.name))
      return skillRows(roster.getSnapshot(), session.sessionId, query).filter(item => !native.has(item.name))
    },
    onPick({ candidate }) {
      const snapshot = roster.getSnapshot()
      const item = snapshot.capabilities.find(item => item.name === candidate.name)
      if (!item || !isUserSkill(item)) { actions.reportError(new Error(t('This skill is no longer available for manual use.'))); return undefined }
      return { insert: { source: SKILLS_SOURCE, ref: item.name, label: skillLabel(item, language()), clipboardText: `/${item.name}` } }
    },
    lexicon: session => skillRows(roster.getSnapshot(), session.sessionId).map(item => item.name),
    subscribeLexicon: (_session, listener) => roster.subscribe(listener),
    codec: { clipboardText: name => `/${name}`, serialize: async name => {
      const item = roster.getSnapshot().capabilities.find(item => item.name === name)
      if (!item || !isUserSkill(item)) throw new Error(t('This skill is no longer available for manual use.'))
      return `/${name}`
    } },
    openReference(_session, reference) { actions.openSettings('capabilities', reference.ref); return true },
  }
}
