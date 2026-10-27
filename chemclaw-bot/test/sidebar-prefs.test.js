import assert from 'node:assert/strict'
import test from 'node:test'
import {
  botCategoryId, mergeSidebarPrefs, moveId, sortCategories, sortEntries, SPECIALISTS_CATEGORY,
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
