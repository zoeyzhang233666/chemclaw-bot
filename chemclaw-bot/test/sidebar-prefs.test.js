import assert from 'node:assert/strict'
import test from 'node:test'
import {
  botCategoryId, roomCategoryId, sidebarCategories, mergeSidebarPrefs, moveId, moveSidebarItem, sortCategories, sortEntries, SPECIALISTS_CATEGORY, deleteSidebarCategory, categoryFallback,
} from '../src/shared/sidebar-prefs.js'

test('botCategoryId prefers template category then role', () => {
  assert.equal(botCategoryId({ templateInfo: { category: '内贸销售' } }), '内贸销售')
  assert.equal(botCategoryId({ role: 'Writer' }), 'Writer')
  assert.equal(botCategoryId({}), SPECIALISTS_CATEGORY)
})

test('mergeSidebarPrefs stores sort focus and clears defaults', () => {
  assert.equal(mergeSidebarPrefs(undefined, null), undefined)
  assert.deepEqual(mergeSidebarPrefs(undefined, { sort: 'focus', focus: ['内贸销售'] }), { sort: 'focus', focus: ['内贸销售'] })
  assert.equal(mergeSidebarPrefs({ sort: 'focus' }, { sort: 'recent' })?.sort, undefined)
  assert.deepEqual(mergeSidebarPrefs({ focus: ['a'] }, { focus: [] }), undefined)
})

test('mergeSidebarPrefs rejects bad shapes', () => {
  assert.throws(() => mergeSidebarPrefs(undefined, { sort: 'alpha' }), /recent, manual or focus/)
  assert.throws(() => mergeSidebarPrefs(undefined, { collapsed: [1] }), /collapsed/)
})

test('sortCategories puts focus ids first then manual order', () => {
  const groups = [{ id: 'a' }, { id: 'b' }, { id: 'c' }]
  assert.deepEqual(sortCategories(groups, { sort: 'focus', focus: ['c'], categoryOrder: ['b', 'a', 'c'] }).map(g => g.id), ['c', 'b', 'a'])
})

test('sortEntries respects manual item order after pins', () => {
  const entries = [
    { item: { id: '1', pinned: false }, at: 1 },
    { item: { id: '2', pinned: true }, at: 0 },
    { item: { id: '3', pinned: false }, at: 3 },
  ]
  assert.deepEqual(sortEntries(entries, { sort: 'manual', categoryId: 'x', itemOrder: { x: ['3', '1'] } }).map(e => e.item.id), ['2', '3', '1'])
})

test('moveId inserts before a neighbor', () => {
  assert.deepEqual(moveId(['a', 'b', 'c'], 'c', 'a'), ['c', 'a', 'b'])
  assert.deepEqual(moveId(['a', 'b'], 'a'), ['b', 'a'])
})

test('room categories use existing preset business metadata and stay distinct from expert categories', () => {
  assert.equal(roomCategoryId({ templateInfo: { category: '产业研究' } }), 'rooms:产业研究')
  assert.equal(roomCategoryId({}), 'rooms')
  const sidebar = { categoryAssignments: { 'room:team': 'custom:team' } }
  assert.equal(roomCategoryId({ id: 'team', templateInfo: { category: '产业研究' } }, sidebar), 'custom:team')
})

test('categories can be created, renamed and assigned without changing templates, order or collapsed choices', () => {
  const bot = { id: 'bot', templateInfo: { category: '内贸销售' } }
  let sidebar = mergeSidebarPrefs({ collapsed: ['内贸销售'], categoryOrder: ['内贸销售'] }, {
    categories: [{ id: 'custom:1', kind: 'bot', name: 'New business' }],
    categoryAssignments: { 'bot:bot': 'custom:1' },
  })
  assert.equal(botCategoryId(bot, sidebar), 'custom:1')
  sidebar = mergeSidebarPrefs(sidebar, { categories: [{ id: 'custom:1', kind: 'bot', name: 'Renamed' }] })
  const roster = { bots: [bot], rooms: [], prefs: { sidebar } }
  assert.deepEqual(sidebarCategories(roster, 'bot'), [{ id: 'custom:1', kind: 'bot', name: 'Renamed' }])
  assert.deepEqual(sidebar.collapsed, ['内贸销售'])
  assert.deepEqual(sidebar.categoryOrder, ['内贸销售'])
  assert.equal(bot.templateInfo.category, '内贸销售')
  sidebar = mergeSidebarPrefs(sidebar, { categoryAssignments: { 'bot:bot': null } })
  assert.equal(botCategoryId(bot, sidebar), '内贸销售')
})

test('empty categories and renamed built-ins remain selectable for new experts and groups', () => {
  const categories = [{ id: '内贸销售', kind: 'bot', name: 'Sales team' }, { id: 'custom:room', kind: 'room', name: 'New group' }]
  const roster = { bots: [{ id: 'b', role: '内贸销售' }], rooms: [], prefs: { sidebar: { categories } } }
  assert.deepEqual(sidebarCategories(roster, 'bot'), [categories[0]])
  assert.deepEqual(sidebarCategories(roster, 'room'), [categories[1]])
})

test('invalid category shapes and duplicate stable ids are refused', () => {
  for (const categories of [{}, [null], [{ id: 'a', kind: 'other', name: 'Name' }], [{ id: 'a', kind: 'bot', name: ' ' }], [{ id: 'a', kind: 'bot', name: 'A' }, { id: ' a ', kind: 'room', name: 'B' }]]) {
    assert.throws(() => mergeSidebarPrefs({}, { categories }), /category|categories/)
  }
  assert.throws(() => mergeSidebarPrefs({}, { categoryAssignments: [] }), /assignments/)
  assert.throws(() => mergeSidebarPrefs({}, { categoryAssignments: { unknown: 'a' } }), /assignment/)
})

test('manual ordering stays stable when new activity arrives, while recent ordering follows activity', () => {
  const entries = [{ item: { id: 'a' }, at: 1 }, { item: { id: 'b' }, at: 10 }]
  assert.deepEqual(sortEntries(entries, { sort: 'manual' }).map(row => row.item.id), ['a', 'b'])
  assert.deepEqual(sortEntries(entries).map(row => row.item.id), ['b', 'a'])
})

test('PDF, minutes and review expert categories consolidate into delivery without changing group categories', () => {
  const bots = ['PDF', 'pdf', '纪要', '方法与复核', '方法与复合'].map((category, index) => ({ id: `b${index}`, templateInfo: { category } }))
  const sidebar = {
    categories: [{ id: 'custom:old', kind: 'bot', name: 'PDF' }, { id: '方法与复核', kind: 'bot', name: 'Review' }],
    categoryAssignments: { 'bot:custom': 'custom:old' },
  }
  bots.push({ id: 'custom', role: 'Custom' })
  assert.ok(bots.every(bot => botCategoryId(bot, sidebar) === '通用交付'))
  const room = { id: 'room', templateInfo: { category: '方法与复核' } }
  const roster = { bots, rooms: [room], prefs: { sidebar } }
  assert.deepEqual(sidebarCategories(roster, 'bot'), [{ id: '通用交付', kind: 'bot', name: '通用交付' }])
  assert.equal(roomCategoryId(room, sidebar), 'rooms:方法与复核')
  assert.equal(bots[0].templateInfo.category, 'PDF')
})

test('cross-category dragging updates assignment and both orders in one prefs patch', () => {
  for (const kind of ['bot', 'room']) {
    const groups = [
      { id: 'source', kind, entries: [{ item: { id: 'a' } }, { item: { id: 'b' } }] },
      { id: 'target', kind, entries: [{ item: { id: 'c' } }] },
    ]
    const patch = moveSidebarItem(groups, 'target', 'a', 'c')
    const next = mergeSidebarPrefs({ categoryAssignments: { [`${kind}:b`]: 'source' } }, patch)
    assert.equal(next.categoryAssignments[`${kind}:a`], 'target')
    assert.equal(next.categoryAssignments[`${kind}:b`], 'source')
    assert.deepEqual(next.itemOrder, { source: ['b'], target: ['a', 'c'] })
    groups[1].entries = []
    assert.deepEqual(moveSidebarItem(groups, 'target', 'b', null).itemOrder.target, ['b'])
    assert.equal(moveSidebarItem(groups, 'source', 'a', 'b').categoryAssignments, undefined)
    groups[1].kind = kind === 'bot' ? 'room' : 'bot'
    assert.equal(moveSidebarItem(groups, 'target', 'a', null), undefined)
    assert.equal(moveSidebarItem(groups, 'source', 'main', null), undefined)
  }
})

for (const kind of ['bot', 'room']) test(`deleting a ${kind} category moves its contents and preserves target order without deleting identities`, () => {
  const items = ['a', 'b', 'c'].map(id => ({ id, name: id, role: 'Original', templateInfo: { category: 'Original' }, members: ['main', 'expert'] }))
  const category = { id: 'custom:source', name: 'Source', kind }
  const target = { id: 'custom:target', name: 'Target', kind }
  const sidebar = { categories: [category, target], categoryAssignments: Object.fromEntries(items.map(item => [`${kind}:${item.id}`, item.id === 'c' ? target.id : category.id])), itemOrder: { [category.id]: ['b', 'a'], [target.id]: ['c'] }, collapsed: [category.id, target.id], categoryOrder: [category.id, target.id] }
  const roster = { mainBotId: 'main', bots: kind === 'bot' ? items : [], rooms: kind === 'room' ? items : [], prefs: { sidebar } }
  const original = structuredClone(roster)
  const next = mergeSidebarPrefs(sidebar, deleteSidebarCategory(roster, category, target.id))
  assert.deepEqual(roster, original)
  assert.deepEqual(next.itemOrder, { [target.id]: ['c', 'b', 'a'] })
  assert.deepEqual(next.categories, [target])
  assert.ok(next.deletedCategories.includes(category.id))
  assert.deepEqual(next.categoryOrder, [target.id])
  assert.equal(next.collapsed, undefined)
  assert.ok(items.every(item => next.categoryAssignments[`${kind}:${item.id}`] === target.id))
  assert.deepEqual(sidebarCategories({ ...roster, prefs: { sidebar: next } }, kind), [target])
})

for (const kind of ['bot', 'room']) test(`deleted built-in ${kind} categories do not return after new presets arrive`, () => {
  const item = { id: 'a', role: 'Sales', templateInfo: { category: 'Sales' } }
  const roster = { bots: kind === 'bot' ? [item] : [], rooms: kind === 'room' ? [item] : [], prefs: {} }
  const category = sidebarCategories(roster, kind)[0]
  const next = mergeSidebarPrefs({}, deleteSidebarCategory(roster, category))
  const incoming = { id: 'new', role: 'Sales', templateInfo: { category: 'Sales' } }
  assert.equal(kind === 'bot' ? botCategoryId(incoming, next) : roomCategoryId(incoming, next), categoryFallback(kind))
  assert.throws(() => deleteSidebarCategory(roster, category, 'missing'), /another category/)
  assert.throws(() => deleteSidebarCategory(roster, { id: categoryFallback(kind), kind }), /cannot be deleted/)
})

test('deleting an empty category needs no item deletion and rejects malformed deletion state', () => {
  const category = { id: 'custom:empty', name: 'Empty', kind: 'room' }
  const roster = { bots: [], rooms: [], prefs: { sidebar: { categories: [category] } } }
  const next = mergeSidebarPrefs(roster.prefs.sidebar, deleteSidebarCategory(roster, category))
  assert.deepEqual(sidebarCategories({ ...roster, prefs: { sidebar: next } }, 'room'), [])
  assert.throws(() => mergeSidebarPrefs({}, { deletedCategories: [42] }), /deletedCategories/)
  assert.equal(mergeSidebarPrefs({ deletedCategories: ['x'] }, { deletedCategories: [] }), undefined)
})
