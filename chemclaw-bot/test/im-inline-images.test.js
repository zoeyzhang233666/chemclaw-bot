import assert from 'node:assert/strict'
import { test } from 'node:test'
import { extractImVisuals, sanitizeImSvg } from '../src/host/im/inline-images.js'
import { imViewSummary } from '../src/host/im/view-image.js'

test('IM unwraps desktop visuals without changing ordinary fenced code', () => {
  const graphic = { items: [{ type: 'svg', title: 'Trend', svg: '<svg><rect width="5" height="5"/></svg>' }] }
  const ordinary = 'Update\n\n```js\nconsole.log(42)\n```'
  const reply = extractImVisuals(ordinary + '\n\n```dsh-ui\n' + JSON.stringify(graphic) + '\n```')
  assert.equal(reply.text, ordinary)
  assert.deepEqual(reply.visuals, [{ title: 'Trend', code: graphic.items[0].svg }])
})

test('IM SVG rendering accepts static geometry and removes executable or external features', () => {
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100">' +
    '<script>document.write("untrusted")</script><image href="file:///private/image.png"/>' +
    '<rect width="40" height="50" fill="url(https://example.test/resource)" onclick="alert(1)"/>' +
    '<text x="10" y="20">走势 &amp; 数据</text></svg>'
  const result = sanitizeImSvg(svg)
  assert.match(result, /<rect width="40" height="50"\/>/u)
  assert.match(result, /走势 &amp; 数据/u)
  assert.doesNotMatch(result, /script|image|https|onclick|alert/u)
  assert.equal(sanitizeImSvg('<!DOCTYPE svg><svg><rect width="20"/></svg>'), undefined)
})

test('the text fallback includes usable readings even when a chart has missing observations', () => {
  const summary = imViewSummary({ title: '验收示例', view: { type: 'chart', kind: 'line',
    unit: '元/吨', categories: ['09-04', '09-07', '11-20'],
    series: [{ name: '收盘', values: [1093, null, 952] }] } }, 'zh')
  assert.match(summary, /09-04 1093 → 11-20 952 元\/吨/u)
  assert.doesNotMatch(summary, /09-07|View card|chart:/u)
  assert.match(summary, /完整视图见 ChemClaw。$/u)
})
