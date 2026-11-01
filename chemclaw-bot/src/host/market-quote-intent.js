// The settlement/market class is a contract, not a chart preference.
// An explicit spot request must never be silently routed into futures OHLC.
export function marketQuoteIntent(text) {
  const query = String(text ?? '')
  const spot = /(?:现货|即期|出厂价|到厂价|到岸现货|离岸现货|\bspot(?:\s+(?:price|market|quote))?\b)/iu.test(query)
  const futures = /(?:期货|期指|主力连续|期货合约|\bfutures?\b)/iu.test(query)
  const shares = /(?:股价|股票|A股|港股|美股|上市公司股价|\b(?:stocks?|shares?|equities|etf)\b)/iu.test(query)
  // Only explicit comparisons are mixed. "现货不是期货" is spot, not mixed.
  const comparison = /(?:比较|对比|价差|基差|以及|分别|同时|一并|和|与|及|vs\.?|versus|spread)/iu.test(query)
  if (spot && futures && comparison && !/(?:不要|不是|不用|并非|而非|别用|不看|非期货|not\s+futures)/iu.test(query)) return 'mixed'
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
