// Bounded, metadata-only CDP frame diagnostics for packaged desktop crashes.
// No raw CDP payloads, URLs, frame IDs, cookies or credentials are written.
import { appendFileSync, mkdirSync, statSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'

const clean = value => typeof value === 'string' && /^[a-z0-9._-]{1,72}$/iu.test(value) ? value : 'unknown'

export function createCdpDiagnosticWriter(path, { maxBytes = 256 * 1024, onError = () => {} } = {}) {
  return (diagnostic) => {
    const safe = {
      at: new Date().toISOString(),
      method: clean(diagnostic?.method),
      reason: clean(diagnostic?.reason),
      recent: Array.isArray(diagnostic?.recent)
        ? diagnostic.recent.slice(-12).map(item => ({ method: clean(item?.method), outcome: clean(item?.outcome) }))
        : [],
    }
    try {
      mkdirSync(dirname(path), { recursive: true })
      try {
        if (statSync(path).size > maxBytes) writeFileSync(path, '')
      } catch (error) {
        if (error?.code !== 'ENOENT') throw error
      }
      appendFileSync(path, JSON.stringify(safe) + '\n')
    } catch (error) {
      // A missing/read-only disk must not bring down the Electron main process.
      try { onError(error) } catch {}
    }
  }
}
