import assert from 'node:assert/strict'
import { test } from 'node:test'
import { seriesPalette } from '../src/client/inks.js'

const second = (accent, dark = false) => seriesPalette(accent, dark)[1]

test('a warm Paper accent takes blue as the second series color', () => {
  assert.equal(second('#d97757'), 'var(--bt-ink-blue)')
  assert.equal(second('#e08a6d', true), 'var(--bt-ink-blue)')
})

test('a blue or indigo accent skips blue and falls to tangerine', () => {
  assert.equal(second('#4d6bfe'), 'var(--bt-ink-tangerine)')
  assert.equal(second('#082DFF'), 'var(--bt-ink-tangerine)')
  assert.equal(second('#1e86ff'), 'var(--bt-ink-tangerine)')
})

test('a tangerine accent skips tangerine and takes blue', () => {
  assert.equal(second('#FF6900'), 'var(--bt-ink-blue)')
})

test('series zero is always the accent token', () => {
  assert.equal(seriesPalette('#d97757')[0], 'var(--bt-accent)')
})

test('a gray accent keeps the full team order', () => {
  assert.equal(second('#141416'), 'var(--bt-ink-blue)')
  assert.equal(second('#0d0d0d'), 'var(--bt-ink-blue)')
})

test('an unreadable accent falls back to the full team order', () => {
  assert.equal(second(''), 'var(--bt-ink-blue)')
  assert.equal(second(undefined), 'var(--bt-ink-blue)')
})
