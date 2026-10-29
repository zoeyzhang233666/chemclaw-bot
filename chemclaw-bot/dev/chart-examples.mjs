// Synthetic observations for isolated mock acceptance; never presented as market data.
const chart = (kind, categories, values, extra = {}) => ({ type: 'chart', kind, categories, series: [{ name: 'Synthetic', values }], caption: 'Synthetic acceptance data', ...extra })
export const CHART_EXAMPLES = {
  scatter: chart('scatter', ['Plant A', 'Plant B', 'Plant C', 'Missing'], [3100, 3250, 3180, null], { xValues: [10, 22, 16, 30], xUnit: 'kt', unit: 'CNY/t' }),
  radar: chart('radar', ['Quality', 'Delivery', 'Service', 'Terms'], [85, 70, 92, 76], { maxima: [100, 100, 100, 100], series: [{ name: 'Plant A', values: [85, 70, 92, 76] }, { name: 'Plant B', values: [75, 90, 80, 88] }] }),
  heatmap: chart('heatmap', ['East', 'North', 'South'], [3100, 3200, null], { unit: 'CNY/t', series: [{ name: 'Oct 27', values: [3100, 3200, null] }, { name: 'Oct 28', values: [3150, 3180, 3250] }, { name: 'Oct 29', values: [3180, 3220, 3210] }] }),
  funnel: chart('funnel', ['Leads', 'Qualified', 'Quoted', 'Won'], [120, 82, 48, 18]),
  treemap: chart('treemap', ['Glass', 'Detergent', 'Chemical', 'Other'], [50, 25, 15, 10], { unit: '%' }),
  sankey: { type: 'chart', kind: 'sankey', categories: ['Soda ash', 'Glass', 'Detergent', 'Packaging', 'Construction'], links: [{ source: 0, target: 1, value: 70 }, { source: 0, target: 2, value: 30 }, { source: 1, target: 3, value: 40 }, { source: 1, target: 4, value: 30 }], unit: 'kt', caption: 'Synthetic acceptance data' },
  gauge: chart('gauge', ['Delivery quota'], [72], { max: 100, unit: '%' }),
}

export function chartExampleReply(kind) {
  return { audience: 'user', title: `Synthetic chart: ${kind}`, await_reply: false, view: CHART_EXAMPLES[kind] }
}
