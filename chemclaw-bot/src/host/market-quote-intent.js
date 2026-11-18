// The settlement/market class is a contract, not a chart preference.
// An explicit spot request must never be silently routed into futures OHLC.
export function marketQuoteIntent(text) {
  const query = String(text ?? '')
  const spot = /(?:现货|即期|出厂价|到厂价|到岸现货|离岸现货|\bspot(?:\s+(?:price|market|quote))?\b)/iu.test(query)
  // A quoted 盘面, 期价, or continuous-contract symbol is a futures
  // leg in a spot-futures comparison, never a physical spot observation.
  const futures = /(?:期货|期指|期价|盘面|主力连续|主力合约|连续合约|期货合约|\b(?:futures?|SA0|EG0|PG0|RB0|MA0|SC0)\b)/iu.test(query)
  const shares = /(?:股价|股票|A股|港股|美股|上市公司股价|\b(?:stocks?|shares?|equities|etf)\b)/iu.test(query)
  const basis = /(?:基差|现期价差|\b(?:basis|cash[- ]futures spread)\b)/iu.test(query)
  // "基差" itself entails spot/futures. Keep explicit spot-only
  // negations higher priority, such as "现货不是期货，只看现货".
  const comparison = /(?:比较|对比|价差|基差|叠加|叠在一起|同图|双线|一起看|对照|以及|分别|同时|一并|和|与|及|vs\.?|versus|spread)/iu.test(query)
  const spotOnly = /(?:不要(?:看|用|包含)?|不用|不看|并非|而非|不是|别用|不含|不包含|非)(?:\s*|[，,\s]*)(?:期货|期价|盘面|连续合约|主力合约|futures?)|(?:仅看|只看|只要)(?:真实|实际|国内)?现货|(?:not|no)\s+futures?/iu.test(query)
  if (!spotOnly && (basis || (spot && futures && comparison))) return 'mixed'
  if (spot) return 'spot'
  if (shares) return 'stock'
  if (futures) return 'futures'
  return 'unspecified'
}

const FUTURES_LABEL = /(?:期货|期指|主力连续|连续合约|交割月|futures?|continuous|NYMEX\s*CL|\b(?:PG0|RB0|MA0|SA0|SC0)\b)/iu

// A spot quote must never be pictured using a futures candle or a clearly
// futures-labeled chart/metric. Text-only answers still require model policy.
export function mismatchedSpotPriceView(view, title = '') {
  if (!view || typeof view !== 'object') return false
  if (Array.isArray(view)) return view.some(node => mismatchedSpotPriceView(node, title))
  if (Array.isArray(view.children) && view.children.some(node => mismatchedSpotPriceView(node))) return true
  if (!['chart', 'metric', 'table'].includes(view.type)) return false
  if (view.type === 'chart' && view.kind === 'candlestick') return true
  const labels = [title, view.caption, view.label, view.title, view.unit,
    ...(Array.isArray(view.series) ? view.series.map(series => series?.name) : []),
    ...(Array.isArray(view.columns) ? view.columns.map(column => column?.label) : [])]
  return labels.some(value => typeof value === 'string' && FUTURES_LABEL.test(value))
}

// Rendering scope is narrower than market classification: a short group prompt
// such as "@Writer 基差呢" still describes a mixed market, but must not make
// every legitimate chart in a group satisfy the full 2-line overlay contract.
export function mixedOverlayRequested(text) {
  const query = String(text ?? '')
  if (marketQuoteIntent(query) !== 'mixed') return false
  const namedComparison = /(?:现货|即期|\bspot\b).{0,28}(?:期货|期价|盘面|主力合约|\bfutures?\b)/iu.test(query)
    || /(?:期货|期价|盘面|主力合约|\bfutures?\b).{0,28}(?:现货|即期|\bspot\b)/iu.test(query)
  const chartRequested = /(?:叠加|叠在一起|同图|双线|画图|绘图|走势图|趋势图|历史走势|走势(?:对比|比较|分析)?|基差曲线|基差走势|基差图|\bchart\b|\bplot\b)/iu.test(query)
  return chartRequested && (namedComparison || /(?:基差|现期价差|\bbasis\b)/iu.test(query))
}
