import assert from 'node:assert/strict'
import { test } from 'node:test'
import { CdpFrameGuard } from '../src/cdp-frame-guard.mjs'

test('reproduces the duplicate-child-frame condition of Playwright FrameManager.frameAttached', () => {
  // Playwright 1.61.1 frames.ts asserts !frames.has(frameId) before adding a
  // child. Emulate the invariant so this regression stays deterministic.
  const frames = new Set(['main'])
  const attach = id => {
    assert.equal(frames.has(id), false, 'Assertion error')
    frames.add(id)
  }
  attach('iframe-1')
  assert.throws(() => attach('iframe-1'), /Assertion error/)
  const reports = []
  const guard = new CdpFrameGuard(record => reports.push(record))
  assert.equal(guard.observeTree({ frame: { id: 'main' } }), true)
  assert.equal(guard.accept('Page.frameAttached', { frameId: 'iframe-1', parentFrameId: 'main' }), true)
  assert.equal(guard.accept('Page.frameAttached', { frameId: 'iframe-1', parentFrameId: 'main' }), false)
  assert.equal(reports.at(-1).reason, 'duplicate-attach')
  assert.equal(JSON.stringify(reports).includes('iframe-1'), false, 'diagnostics do not retain frame identifiers')
})

test('a frame already present in Page.getFrameTree is not attached twice', () => {
  const guard = new CdpFrameGuard()
  assert.equal(guard.observeTree({ frame: { id: 'main' }, childFrames: [{ frame: { id: 'child' } }] }), true)
  assert.equal(guard.accept('Page.frameAttached', { frameId: 'child', parentFrameId: 'main' }), false)
  assert.equal(guard.accept('Page.frameNavigated', { frame: { id: 'child', parentId: 'main', url: 'https://example.com' } }), true)
  assert.equal(guard.accept('Page.frameAttached', { frameId: 'child', parentFrameId: 'main' }), false)
})

test('detach allows a new attach; swaps retain the old frame identity', () => {
  const guard = new CdpFrameGuard()
  guard.observeTree({ frame: { id: 'main' } })
  assert.equal(guard.accept('Page.frameAttached', { frameId: 'child', parentFrameId: 'main' }), true)
  assert.equal(guard.accept('Page.frameDetached', { frameId: 'child', reason: 'swap' }), true)
  assert.equal(guard.accept('Page.frameAttached', { frameId: 'child', parentFrameId: 'main' }), false)
  assert.equal(guard.accept('Page.frameDetached', { frameId: 'child', reason: 'remove' }), true)
  assert.equal(guard.accept('Page.frameAttached', { frameId: 'child', parentFrameId: 'main' }), true)
})

test('out-of-order and malformed frame events are isolated without throwing', () => {
  const reports = []
  const guard = new CdpFrameGuard(record => reports.push(record))
  assert.equal(guard.accept('Page.frameAttached', { frameId: 'child', parentFrameId: 'unknown' }), false)
  assert.equal(guard.accept('Page.frameAttached', { parentFrameId: 'unknown' }), false)
  assert.equal(guard.observeTree({ frame: { id: 'main' }, childFrames: [{ frame: { id: 'main' } }] }), false)
  assert.deepEqual(reports.map(r => r.reason), ['unknown-parent', 'missing-frame-id', 'invalid-frame-tree'])
  assert.equal(guard.observeTree({ frame: { id: 'main' } }), true)
  assert.equal(guard.accept('Page.frameAttached', { frameId: 'child', parentFrameId: 'main' }), true)
  assert.ok(reports.every(report => report.recent.length <= 12))
})
