export const SKILL_CATEGORIES = ['内贸销售', '内贸采购', '外贸销售', '外贸采购', '产业基本面', '价差与量化', '通用办公', '科学分析', '基础流程']

export const skillLabel = (item, locale = 'zh') => item.displayName || item.labels?.[locale.startsWith('zh') ? 'zh' : 'en']
  || (item.kind === 'skill' && item.description ? item.description.replace(/^.*? \/ /, '').replace(/^\d+[.、．]\s*/, '') : item.name)

export const skillCategory = item => (item.category ?? '我的安装').replace(/^期现-/, '')
export const isUserSkill = item => item.kind === 'skill' && item.invocation?.userInvocable !== false

export function matchingSkills(items, query = '', category = '', locale = 'zh') {
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean)
  return items.filter(item => item.kind === 'skill'
    && (!category || (category === '我的安装' ? !item.builtinSource : skillCategory(item) === category))
    && words.every(word => [item.name, item.originalName, skillLabel(item, locale), ...Object.values(item.labels ?? {}), item.description, item.purpose, skillCategory(item), ...(item.keywords ?? [])].join(' ').toLowerCase().includes(word)))
}

export function explicitSkillNames(text, items) {
  const names = new Set(items.filter(isUserSkill).map(item => item.name))
  return [...new Set([...String(text).matchAll(/(?:^|\s)\/([a-z][a-z0-9]*(?:-[a-z0-9]+)*)(?=\s|$)/g)].map(match => match[1]).filter(name => names.has(name)))]
}
