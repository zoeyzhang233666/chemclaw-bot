// Bounded, metadata-only CDP frame diagnostics for packaged desktop crashes.
// No raw CDP payloads, URLs, frame IDs, cookies or credentials are written.
import { appendFileSync, mkdirSync, statSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'

const METHODS = new Set(['Page.frameAttached', 'Page.frameDetached', 'Page.frameNavigated', 'Page.getFrameTree'])
const REASONS = new Set(['duplicate-attach', 'conflicting-parent', 'unknown-parent', 'missing-frame-id', 'invalid-frame-tree', 'native-event-error'])
const OUTCOMES = new Set([...REASONS, 'accepted', 'root', 'swap', 'swapped-in', 'DataCloneError', 'TypeError', 'Error'])
const safe = (value, allowed) => allowed.has(value) ? value : 'other'

export function createCdpDiagnosticWriter(path, { maxBytes = 256 * 1024, onError = () => {} } = {}) {
  return (diagnostic) => {
    const safe = {
      at: new Date().toISOString(),
      method: safe(diagnostic?.method, METHODS),
      reason: safe(diagnostic?.reason, REASONS),
      recent: Array.isArray(diagnostic?.recent)
        ? diagnostic.recent.slice(-12).map(item => ({ method: safe(item?.method, METHODS), outcome: safe(item?.outcome, OUTCOMES) }))
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
