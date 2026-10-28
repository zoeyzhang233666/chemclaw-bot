// Sidebar organization prefs: stable category ids, sort modes, and list ordering.
// Labels shown in the UI are translated separately; persistence always uses these ids.

export const SIDEBAR_SORTS = new Set(['recent', 'manual', 'focus'])
export const ROOMS_CATEGORY = 'rooms'
export const AGENTS_CATEGORY = 'agents'
export const SPECIALISTS_CATEGORY = 'specialists'

const LABEL_MAX = 64
const ORDER_MAX = 200

const isId = value => typeof value === 'string' && value.trim() !== '' && value.trim().length <= LABEL_MAX
const cleanIds = list => [...new Set(list.map(item => String(item).trim()).filter(Boolean))].slice(0, ORDER_MAX)

export function botCategoryId(bot) {
  const raw = bot?.templateInfo?.category || bot?.role
  if (typeof raw === 'string' && raw.trim()) return raw.trim().slice(0, LABEL_MAX)
  return SPECIALISTS_CATEGORY
}

function readIdList(value, label) {
  if (!Array.isArray(value) || value.some(item => !isId(item))) throw new Error(label)
  return cleanIds(value)
}

// Validates one sidebar patch. Empty / null fields mean "clear that field".
export function parseSidebarPatch(input) {
  if (input === null) return null
  if (typeof input !== 'object' || Array.isArray(input)) throw new Error('Sidebar prefs must be an object')
  const patch = {}
  if (input.sort !== undefined) {
    if (input.sort === null || input.sort === 'recent') patch.sort = null
    else if (SIDEBAR_SORTS.has(input.sort)) patch.sort = input.sort
    else throw new Error('Sidebar sort must be recent, manual or focus')
  }
  if (input.collapsed !== undefined) {
    if (input.collapsed === null || (Array.isArray(input.collapsed) && input.collapsed.length === 0)) patch.collapsed = null
    else patch.collapsed = readIdList(input.collapsed, 'Sidebar collapsed must be short category ids')
  }
  if (input.categoryOrder !== undefined) {
    if (input.categoryOrder === null || (Array.isArray(input.categoryOrder) && input.categoryOrder.length === 0)) patch.categoryOrder = null
    else patch.categoryOrder = readIdList(input.categoryOrder, 'Sidebar categoryOrder must be short category ids')
  }
  if (input.focus !== undefined) {
    if (input.focus === null || (Array.isArray(input.focus) && input.focus.length === 0)) patch.focus = null
    else patch.focus = readIdList(input.focus, 'Sidebar focus must be short category ids')
  }
  if (input.itemOrder !== undefined) {
    if (input.itemOrder === null) patch.itemOrder = null
    else if (typeof input.itemOrder !== 'object' || Array.isArray(input.itemOrder)) throw new Error('Sidebar itemOrder must be a map of category ids')
    else {
      const map = {}
      for (const [key, value] of Object.entries(input.itemOrder)) {
        if (!isId(key)) throw new Error('Sidebar itemOrder keys must be short category ids')
        if (value === null || (Array.isArray(value) && value.length === 0)) map[key.trim()] = null
        else map[key.trim()] = readIdList(value, 'Sidebar itemOrder values must be short ids')
      }
      patch.itemOrder = map
    }
  }
  return patch
}

export function mergeSidebarPrefs(current, patchInput) {
  const patch = parseSidebarPatch(patchInput)
  if (patch === null) return undefined
  const merged = current && typeof current === 'object' && !Array.isArray(current) ? { ...current } : {}
  if (patch.sort === null) delete merged.sort
  else if (patch.sort !== undefined) merged.sort = patch.sort
  if (patch.collapsed === null) delete merged.collapsed
  else if (patch.collapsed !== undefined) merged.collapsed = patch.collapsed
  if (patch.categoryOrder === null) delete merged.categoryOrder
  else if (patch.categoryOrder !== undefined) merged.categoryOrder = patch.categoryOrder
  if (patch.focus === null) delete merged.focus
  else if (patch.focus !== undefined) merged.focus = patch.focus
  if (patch.itemOrder === null) delete merged.itemOrder
  else if (patch.itemOrder !== undefined) {
    const map = { ...(merged.itemOrder ?? {}) }
    for (const [key, value] of Object.entries(patch.itemOrder)) {
      if (value === null) delete map[key]
      else map[key] = value
    }
    if (Object.keys(map).length) merged.itemOrder = map
    else delete merged.itemOrder
  }
  return Object.keys(merged).length ? merged : undefined
}

function orderIndex(list, id) {
  const at = list?.indexOf(id) ?? -1
  return at < 0 ? Number.MAX_SAFE_INTEGER : at
}

export function sortEntries(entries, { sort = 'recent', itemOrder = {}, categoryId } = {}) {
  const order = itemOrder[categoryId] ?? []
  const manual = sort === 'manual' || (sort === 'focus' && order.length > 0)
  if (!manual) {
    return [...entries].sort((a, b) => Number(Boolean(b.item.pinned)) - Number(Boolean(a.item.pinned)) || b.at - a.at)
  }
  return [...entries].sort((a, b) => {
    const pin = Number(Boolean(b.item.pinned)) - Number(Boolean(a.item.pinned))
    if (pin) return pin
    const byHand = orderIndex(order, a.item.id) - orderIndex(order, b.item.id)
    if (byHand) return byHand
    return b.at - a.at
  })
}

export function sortCategories(groups, { sort = 'recent', categoryOrder = [], focus = [] } = {}) {
  const focusSet = new Set(focus)
  return [...groups].sort((a, b) => {
    if (sort === 'focus') {
      const af = focusSet.has(a.id) ? 0 : 1
      const bf = focusSet.has(b.id) ? 0 : 1
      if (af !== bf) return af - bf
    }
    if (sort === 'manual' || sort === 'focus') {
      const byHand = orderIndex(categoryOrder, a.id) - orderIndex(categoryOrder, b.id)
      if (byHand) return byHand
    }
    return 0
  })
}

export function moveId(list, id, beforeId) {
  const next = list.filter(item => item !== id)
  const at = beforeId === undefined || beforeId === null ? next.length : next.indexOf(beforeId)
  next.splice(at < 0 ? next.length : at, 0, id)
  return next
}
