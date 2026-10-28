import assert from 'node:assert/strict'
import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { test } from 'node:test'
import { MarkdownText } from '../ui/src/primitives.js'

const render = (text) => renderToStaticMarkup(h(MarkdownText, { text, variant: 'compact' }))

test('a single tilde in a date range stays literal, not strikethrough', () => {
  const html = render('不是单边: 10/20~10/22 连续三天阴跌、10/26~10/27 回落')
  assert.equal(html.includes('<del>'), false)
  assert.match(html, /10\/20~10\/22/)
  assert.match(html, /10\/26~10\/27/)
})

test('double-tilde strikethrough still renders', () => {
  const html = render('keep ~~old~~ price')
  assert.match(html, /<del>old<\/del>/)
})

test('table cells render asterisk bold as strong, without leftover markers', () => {
  const html = render([
    '| 日期 | 绝对基差(对结算) |',
    '| --- | --- |',
    '| 2026-10-26 | **-856.5** |',
    '| 2026-10-27 上午 | **-588.0** |',
  ].join('\n'))
  assert.match(html, /<strong>-856\.5<\/strong>/)
  assert.match(html, /<strong>-588\.0<\/strong>/)
  assert.equal(html.includes('**'), false)
})
