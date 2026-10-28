import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { DICTIONARY, installLocale, t } from '../src/client/i18n.js'

const client = name => readFileSync(new URL(`../src/client/${name}`, import.meta.url), 'utf8')

test('Copy expert strings exist in Chinese', () => {
  assert.equal(DICTIONARY.zh['Copy expert'], '复制专家')
  assert.equal(DICTIONARY.zh['Choose a Bot to copy…'], '选择要复制的专家…')
})

test('NewChat offers Copy expert under Create new Bot and duplicates on pick', () => {
  const text = client('new-chat.js')
  assert.match(text, /mode === 'copy'/)
  assert.match(text, /setCopy\(true\)/)
  assert.match(text, /label: t\('Copy expert'\)/)
  assert.match(text, /hint: copying \? t\('Copy expert'\)/)
  assert.match(text, /actions\.duplicateBot\(bot\.id\)/)
  // Order: Create new Bot, then Copy expert, then Create group chat
  const createBot = text.indexOf("label: t('Create new Bot')")
  const copyExpert = text.indexOf("label: t('Copy expert')")
  const createGroup = text.indexOf("label: t('Create group chat')")
  assert.ok(createBot >= 0 && copyExpert > createBot && createGroup > copyExpert)
})
