import assert from 'node:assert/strict'
import { test } from 'node:test'
import { marketQuoteIntent, mismatchedSpotPriceView } from '../src/host/market-quote-intent.js'
import { marketHistoryRequest } from '../src/host/visual-delivery.js'

test('physical chemical spot intent takes precedence over exchange K-line routing', () => {
  for (const question of [
    '原油现货价格', '纯碱现货价格', '原油现货最近一个月走势',
    '轻质纯碱出厂价', '中国华东重质纯碱到厂价',
    'WTI spot price', '布伦特原油现货，不要期货报价',
    '现货和期货不是一回事，只看现货价格',
    '甲醇现货近一个月行情', '液化石油气现货最新价格',
  ]) {
    assert.equal(marketQuoteIntent(question), 'spot', question)
    assert.equal(marketHistoryRequest(question), false, question)
  }
  for (const question of [
    '液化气期货最近一个月价格', '原油期货价格', '纯碱期货日K', 'WTI futures prices',
    '螺纹钢期货走势',
  ]) {
    assert.equal(marketQuoteIntent(question), 'futures', question)
    assert.equal(marketHistoryRequest(question), true, question)
  }
  for (const question of ['万华化学最近一个月股价', '中国石油601857股票行情']) {
    assert.equal(marketQuoteIntent(question), 'stock', question)
    assert.equal(marketHistoryRequest(question), true, question)
  }
  assert.equal(marketQuoteIntent('比较纯碱现货和期货的价差'), 'mixed')
  assert.equal(marketQuoteIntent('原油价格'), 'unspecified', 'do not invent a spot or futures market when undefined')
})

test('futures candles and futures-labeled cards cannot be displayed as a spot price', () => {
  const future = { type: 'chart', kind: 'candlestick', bars: [] }
  const labeled = { type: 'chart', kind: 'line', caption: 'SA0 纯碱主力连续', categories: ['1'], series: [] }
  const card = { type: 'metric', label: '纯碱期货结算价', value: 1850 }
  const spot = { type: 'chart', kind: 'line', caption: '华北重质纯碱现货出厂价 元/吨', categories: ['1'], series: [] }
  const metric = { type: 'metric', label: '华东纯碱现货', value: '已核实的报价' }
  assert.equal(mismatchedSpotPriceView(future), true)
  assert.equal(mismatchedSpotPriceView(labeled), true)
  assert.equal(mismatchedSpotPriceView(card), true)
  assert.equal(mismatchedSpotPriceView(spot), false)
  assert.equal(mismatchedSpotPriceView(metric), false)
  assert.equal(mismatchedSpotPriceView({ type: 'row', children: [spot, labeled] }), true)
  assert.equal(mismatchedSpotPriceView(spot, '原油期货价格'), true)
})
