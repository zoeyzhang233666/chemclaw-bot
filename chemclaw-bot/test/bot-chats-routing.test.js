import assert from 'node:assert/strict'
import { test } from 'node:test'
import { heuristicTitle, seedChatFromBot, ensureBotChats, syncMirror, chatBySession } from '../src/host/bot-chats.js'

test('heuristic titles drop fillers and keep a meaningful phrase', () => {
  assert.equal(heuristicTitle('请帮我看一下丙烯酸行情'), '看一下丙烯酸行情')
  assert.equal(heuristicTitle('Hello please summarize the PVC market this week'), 'summarize the PVC market this week')
  assert.ok((heuristicTitle('a'.repeat(200))?.length ?? 0) <= 80)
})

test('syncMirror copies only the active chat tip onto bot.sessionId', () => {
  const bot = {
    id: 'b1',
    name: 'Writer',
    chats: [
      { id: 'b1', sessionId: 'tip-a', segments: [{ sessionId: 'old' }] },
      { id: 'c2', sessionId: 'tip-b', segments: [] },
    ],
    activeChatId: 'c2',
  }
  syncMirror(bot)
  assert.equal(bot.sessionId, 'tip-b')
  assert.deepEqual(bot.segments, [])
  bot.activeChatId = 'b1'
  syncMirror(bot)
  assert.equal(bot.sessionId, 'tip-a')
  assert.equal(bot.segments[0].sessionId, 'old')
})

test('chatBySession finds archived tips without using activeChatId', () => {
  const bot = {
    id: 'b1',
    chats: [
      { id: 'b1', sessionId: 'tip-a', segments: [{ sessionId: 'old-a' }] },
      { id: 'c2', sessionId: 'tip-b', segments: [] },
    ],
    activeChatId: 'c2',
  }
  assert.equal(chatBySession(bot, 'old-a')?.id, 'b1')
  assert.equal(chatBySession(bot, 'tip-b')?.id, 'c2')
})

test('ensureBotChats seeds once from legacy tip fields', () => {
  const bot = { id: 'b1', name: 'Writer', sessionId: 'tip', segments: [{ sessionId: 'old' }] }
  assert.equal(ensureBotChats(bot), true)
  assert.equal(ensureBotChats(bot), false)
  assert.equal(bot.chats[0].sessionId, 'tip')
  assert.deepEqual(seedChatFromBot({ id: 'x', name: 'X', sessionId: 's' }).sessionId, 's')
})
