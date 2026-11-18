// Sidebar organization prefs: stable category ids, sort modes, and list ordering.
// Labels shown in the UI are translated separately; persistence always uses these ids.

export const SIDEBAR_SORTS = new Set(['recent', 'manual', 'focus'])
export const ROOMS_CATEGORY = 'rooms'
export const AGENTS_CATEGORY = 'agents'
export const SPECIALISTS_CATEGORY = 'specialists'
export const DELIVERY_CATEGORY = '通用交付'

const DELIVERY_ALIASES = new Set(['pdf', '纪要', '方法与复核', '方法与复合'])

export function expertCategoryId(id, sidebar = {}) {
  const name = sidebar.categories?.find(category => category.kind === 'bot' && category.id === id)?.name
  return [id, name].some(value => typeof value === 'string' && DELIVERY_ALIASES.has(value.trim().toLowerCase())) ? DELIVERY_CATEGORY : id
}

const LABEL_MAX = 64
const ORDER_MAX = 200

const isId = value => typeof value === 'string' && value.trim() !== '' && value.trim().length <= LABEL_MAX
const cleanIds = list => [...new Set(list.map(item => String(item).trim()).filter(Boolean))].slice(0, ORDER_MAX)

export function botCategoryId(bot, sidebar = {}) {
  const assigned = sidebar.categoryAssignments?.[`bot:${bot?.id}`]
  if (assigned) {
    const id = expertCategoryId(assigned, sidebar)
    return sidebar.deletedCategories?.includes(id) ? DELIVERY_CATEGORY : id
  }
  const raw = bot?.templateInfo?.category || bot?.role
  const id = typeof raw === 'string' && raw.trim() ? expertCategoryId(raw.trim().slice(0, LABEL_MAX), sidebar) : SPECIALISTS_CATEGORY
  return sidebar.deletedCategories?.includes(id) ? DELIVERY_CATEGORY : id
}

export function roomCategoryId(room, sidebar = {}) {
  const assigned = sidebar.categoryAssignments?.[`room:${room.id}`]
  if (assigned) return sidebar.deletedCategories?.includes(assigned) ? ROOMS_CATEGORY : assigned
  const label = room.templateInfo?.category?.trim()
  const id = label ? `rooms:${label.slice(0, 58)}` : ROOMS_CATEGORY
  return sidebar.deletedCategories?.includes(id) ? ROOMS_CATEGORY : id
}

export function sidebarCategories(roster, kind) {
  const sidebar = roster.prefs?.sidebar ?? {}
  const categories = new Map()
  const items = kind === 'bot' ? roster.bots.filter(bot => bot.id !== roster.mainBotId) : roster.rooms
  for (const item of items) {
    const id = kind === 'bot' ? botCategoryId(item, sidebar) : roomCategoryId(item, sidebar)
    if (!categories.has(id)) categories.set(id, { id, kind, name: id.startsWith('rooms:') ? id.slice(6) : id })
  }
  for (const category of sidebar.categories ?? []) {
    if (sidebar.deletedCategories?.includes(category.id)) continue
    if (kind === 'bot' && (expertCategoryId(category.id, sidebar) !== category.id || expertCategoryId(category.name) !== category.name)) continue
    if (category.kind === kind) categories.set(category.id, category)
  }
  return [...categories.values()]
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
  if (input.deletedCategories !== undefined) patch.deletedCategories = input.deletedCategories === null || (Array.isArray(input.deletedCategories) && input.deletedCategories.length === 0) ? null : readIdList(input.deletedCategories, 'Sidebar deletedCategories must be short category ids')
  if (input.categories !== undefined) {
    if (input.categories === null) patch.categories = null
    else {
      if (!Array.isArray(input.categories) || input.categories.length > ORDER_MAX) throw new Error('Invalid sidebar categories')
      const ids = new Set()
      patch.categories = input.categories.map(category => {
        if (!category || !isId(category.id) || !isId(category.name) || !['bot', 'room'].includes(category.kind) || ids.has(category.id.trim())) throw new Error('Invalid sidebar category')
        ids.add(category.id.trim())
        return { id: category.id.trim(), name: category.name.trim(), kind: category.kind }
      })
    }
  }
  if (input.categoryAssignments !== undefined) {
    if (input.categoryAssignments === null) patch.categoryAssignments = null
    else {
      if (typeof input.categoryAssignments !== 'object' || Array.isArray(input.categoryAssignments)) throw new Error('Invalid sidebar category assignments')
      if (Object.keys(input.categoryAssignments).length > ORDER_MAX) throw new Error('Too many sidebar category assignments')
      patch.categoryAssignments = Object.fromEntries(Object.entries(input.categoryAssignments).map(([id, category]) => {
        if (!isId(id) || !/^(bot|room):.+/.test(id) || (category !== null && !isId(category))) throw new Error('Invalid sidebar category assignment')
        return [id, category === null ? null : category.trim()]
      }))
    }
  }
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
  if (patch.deletedCategories === null) delete merged.deletedCategories
  else if (patch.deletedCategories !== undefined) merged.deletedCategories = patch.deletedCategories
  if (patch.categories === null) delete merged.categories
  else if (patch.categories !== undefined) merged.categories = patch.categories
  if (patch.categoryAssignments === null) delete merged.categoryAssignments
  else if (patch.categoryAssignments !== undefined) {
    const assignments = { ...merged.categoryAssignments }
    for (const [key, value] of Object.entries(patch.categoryAssignments)) {
      if (value === null) delete assignments[key]
      else assignments[key] = value
    }
    if (Object.keys(assignments).length) merged.categoryAssignments = assignments
    else delete merged.categoryAssignments
  }
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
    return 0
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

export function moveSidebarItem(groups, categoryId, id, beforeId) {
  if (!id || id === beforeId) return undefined
  const source = groups.find(group => group.entries.some(entry => entry.item.id === id))
  const target = groups.find(group => group.id === categoryId)
  if (!source || !target || source.kind !== target.kind || !['bot', 'room'].includes(target.kind)) return undefined
  if (beforeId && !target.entries.some(entry => entry.item.id === beforeId)) return undefined
  const itemOrder = { [target.id]: moveId(target.entries.map(entry => entry.item.id), id, beforeId) }
  const patch = { itemOrder, sort: 'manual', focus: null }
  if (source !== target) {
    itemOrder[source.id] = source.entries.map(entry => entry.item.id).filter(item => item !== id)
    patch.categoryAssignments = { [`${source.kind}:${id}`]: target.id }
  }
  return patch
}

export const categoryFallback = kind => kind === 'bot' ? DELIVERY_CATEGORY : ROOMS_CATEGORY
export const canDeleteCategory = category => ['bot', 'room'].includes(category.kind) && category.id !== categoryFallback(category.kind)

export function deleteSidebarCategory(roster, category, targetId = categoryFallback(category.kind)) {
  const { id, kind } = category
  const sidebar = roster.prefs?.sidebar ?? {}
  const categories = sidebarCategories(roster, kind)
  if (!canDeleteCategory(category) || !categories.some(item => item.id === id)) throw new Error('This category cannot be deleted')
  if (targetId === id || (targetId !== categoryFallback(kind) && !categories.some(item => item.id === targetId))) throw new Error('Choose another category')
  const items = kind === 'bot' ? roster.bots.filter(bot => bot.id !== roster.mainBotId) : roster.rooms
  const categoryOf = item => kind === 'bot' ? botCategoryId(item, sidebar) : roomCategoryId(item, sidebar)
  const ordered = categoryId => sortEntries(items.filter(item => categoryOf(item) === categoryId).map(item => ({ item, at: 0 })), { sort: 'manual', categoryId, itemOrder: sidebar.itemOrder }).map(entry => entry.item.id)
  const moving = ordered(id)
  const assignments = Object.fromEntries(Object.entries(sidebar.categoryAssignments ?? {}).filter(([key, value]) => key.startsWith(`${kind}:`) && value === id).map(([key]) => [key, targetId]))
  for (const itemId of moving) assignments[`${kind}:${itemId}`] = targetId
  return {
    categories: (sidebar.categories ?? []).filter(item => item.id !== id),
    deletedCategories: [...new Set([...(sidebar.deletedCategories ?? []), id])],
    categoryAssignments: assignments,
    itemOrder: { [id]: null, [targetId]: [...new Set([...ordered(targetId), ...moving])] },
    categoryOrder: (sidebar.categoryOrder ?? []).filter(item => item !== id),
    collapsed: (sidebar.collapsed ?? []).filter(item => item !== id && item !== targetId),
    focus: (sidebar.focus ?? []).filter(item => item !== id),
  }
}
