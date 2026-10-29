import { createElement as h, useEffect, useId, useRef, useState } from 'react'
import { t } from './i18n.js'
import { seriesPalette } from './inks.js'
import { saveImage } from './widget-chart.js'
import { loadChartEngine } from './chart-loader.js'
import { advancedChartData, advancedChartOption, advancedChartTable, tableCsv } from './chart-options.js'

export function chartTheme(element) {
  const style = getComputedStyle(element)
  const token = name => style.getPropertyValue(name).trim()
  const colors = seriesPalette(token('--bt-accent'), document.body.hasAttribute('data-ds-dark-theme')).map(color => {
    const name = color.match(/^var\(([^)]+)\)$/)?.[1]
    return name ? token(name) : color
  })
  return { ink: token('--bt-ink'), muted: token('--bt-ink-2'), line: token('--bt-line'), card: token('--bt-main'),
    font: style.fontFamily, colors, narrow: element.clientWidth < 380 }
}

function DataTable({ table }) {
  return h('div', { className: 'bt-widget-table' }, h('table', null,
    h('thead', null, h('tr', null, table.columns.map((label, at) => h('th', { key: at, scope: 'col' }, label === 'Source' || label === 'Target' ? t(label) : label)))),
    h('tbody', null, table.rows.map((row, at) => h('tr', { key: at }, row.map((value, col) => h(col === 0 ? 'th' : 'td', {
      key: col, scope: col === 0 ? 'row' : undefined, className: typeof value === 'number' ? 'bt-num' : undefined,
    }, value === null ? t('No data') : String(value))))))))
}

export function AdvancedChart({ node, lookup, registerChart, refreshCharts }) {
  const data = advancedChartData(node, lookup)
  const signature = JSON.stringify(data)
  const table = advancedChartTable(data, t('Value'), t('Series'))
  const box = useRef(null)
  const plot = useRef(null)
  const chart = useRef(null)
  const action = useRef(null)
  const [asTable, setAsTable] = useState(false)
  const [disabled, setDisabled] = useState(() => document.body.dataset.btAdvancedCharts === 'off')
  const [visible, setVisible] = useState(false)
  const [ready, setReady] = useState(false)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [copied, setCopied] = useState(false)
  const menuKey = useId()
  const labelId = useId()
  const label = node.caption || t('Chart')
  const showingTable = asTable || disabled || !data.drawable || !ready || failed
  const copyTimer = useRef(null)

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') { setVisible(true); return undefined }
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) { setVisible(true); observer.disconnect() }
    }, { rootMargin: '240px' })
    observer.observe(box.current)
    return () => observer.disconnect()
  }, [])
  useEffect(() => {
    const update = () => setDisabled(document.body.dataset.btAdvancedCharts === 'off')
    update()
    const observer = new MutationObserver(update)
    observer.observe(document.body, { attributes: true, attributeFilter: ['data-bt-advanced-charts'] })
    return () => { observer.disconnect(); clearTimeout(copyTimer.current) }
  }, [])

  useEffect(() => {
    if (disabled || !visible || !data.drawable) return undefined
    let alive = true
    let instance
    let size
    let theme
    let lastTheme
    const redraw = () => {
      if (!alive || !instance || !plot.current) return
      try {
        const current = chartTheme(plot.current)
        const key = JSON.stringify(current)
        if (lastTheme !== key) { instance.setOption(advancedChartOption(data, current), { notMerge: true }); lastTheme = key }
        instance.resize()
        return true
      } catch { setFailed(true); setReady(false); return false }
    }
    setFailed(false)
    setReady(false)
    void loadChartEngine().then(engine => {
      if (!alive || !plot.current) return
      instance = engine.create(plot.current)
      chart.current = instance
      if (!redraw()) return
      setReady(true)
      size = new ResizeObserver(redraw)
      size.observe(box.current)
      theme = new MutationObserver(redraw)
      theme.observe(document.body, { attributes: true, attributeFilter: ['data-ds-dark-theme', 'class', 'style', 'data-bt-motion'] })
      theme.observe(document.head, { subtree: true, childList: true, characterData: true })
    }).catch(() => { if (alive) { setFailed(true); setReady(false) } })
    return () => { alive = false; size?.disconnect(); theme?.disconnect(); instance?.dispose(); chart.current = null }
  }, [signature, disabled, visible, attempt])

  action.current = {
    label: node.caption || null, asTable: showingTable, failed,
    canToggle: !disabled && data.drawable && ready && !failed,
    toggleTable: () => setAsTable(value => !value),
    copy: () => { void navigator.clipboard?.writeText(tableCsv(table)).then(() => { setCopied(true); clearTimeout(copyTimer.current); copyTimer.current = setTimeout(() => setCopied(false), 1500) }).catch(() => {}) },
    save: () => { const svg = plot.current?.querySelector('svg'); if (svg) saveImage(svg, 'chart.png') },
  }
  useEffect(() => registerChart?.(menuKey, {
    get label() { return action.current.label }, get asTable() { return action.current.asTable },
    get canSave() { return Boolean(chart.current) && !action.current.failed },
    get canToggle() { return action.current.canToggle },
    toggleTable: () => action.current.toggleTable(), copy: () => action.current.copy(), save: () => action.current.save(),
  }), [registerChart, menuKey])
  useEffect(() => refreshCharts?.(), [refreshCharts, showingTable, label])

  return h('figure', { ref: box, className: 'bt-chart bt-advanced-chart', 'data-kind': node.kind },
    h('span', { id: labelId, hidden: true }, label),
    h('div', { className: 'bt-advanced-plot-wrap', 'data-table': showingTable || undefined },
      h('div', { ref: plot, className: 'bt-advanced-plot', role: 'img', 'aria-labelledby': labelId, 'aria-hidden': showingTable || undefined })),
    showingTable ? h(DataTable, { table }) : null,
    failed ? h('div', { className: 'bt-advanced-status', role: 'status' }, t('Chart unavailable. Your data is shown as a table.'),
      h('button', { type: 'button', onClick: () => { setAsTable(false); setAttempt(value => value + 1) } }, t('Retry'))) : null,
    !data.drawable ? h('div', { className: 'bt-advanced-status', role: 'status' }, t('This data is shown as a table to preserve missing values or axis limits.')) : null,
    copied ? h('span', { className: 'bt-chart-copied', role: 'status' }, t('Copied')) : null,
    node.caption ? h('figcaption', { className: 'bt-view-caption' }, node.caption) : null)
}

export const ADVANCED_CHART_CSS = `
.bt-advanced-chart{width:100%}
.bt-advanced-plot-wrap{position:relative;min-width:0}
.bt-advanced-plot{width:100%;height:300px;min-width:0;font-family:inherit}
.bt-advanced-plot-wrap[data-table]{position:absolute;inset:0 0 auto;visibility:hidden;pointer-events:none}
.bt-advanced-status{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12px;color:var(--bt-ink-2)}
.bt-advanced-status button{padding:0;border:0;background:none;color:var(--bt-accent);font:inherit;cursor:pointer;text-decoration:underline;text-underline-offset:2px}
`
