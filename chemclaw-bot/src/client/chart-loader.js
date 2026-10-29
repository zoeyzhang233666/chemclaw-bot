import { CHART_ENGINE_ROUTE } from '../shared/chart-engine.js'

let pending

export function loadChartEngine() {
  if (window.ChemClawChartEngine?.create) return Promise.resolve(window.ChemClawChartEngine)
  if (pending) return pending
  pending = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    const finish = error => {
      clearTimeout(timer)
      script.remove()
      script.onload = script.onerror = null
      if (error) { pending = undefined; reject(error) }
      else resolve(window.ChemClawChartEngine)
    }
    const timer = setTimeout(() => finish(new Error('Chart engine timed out')), 12_000)
    script.src = CHART_ENGINE_ROUTE
    script.async = true
    script.onload = () => finish(window.ChemClawChartEngine?.create ? undefined : new Error('Chart engine unavailable'))
    script.onerror = () => finish(new Error('Chart engine unavailable'))
    document.head.appendChild(script)
  })
  return pending
}
