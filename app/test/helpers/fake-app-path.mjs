import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { watchAppPath as watchRealAppPath } from '../../src/app-path.mjs'

export const root = mkdtempSync(join(tmpdir(), 'chemclaw-main-app-path-'))
export const bundle = join(root, 'ChemClaw.app')
const executable = join(bundle, 'Contents', 'MacOS', 'ChemClaw')
mkdirSync(join(bundle, 'Contents', 'MacOS'), { recursive: true })
writeFileSync(executable, 'synthetic executable, never run')

export function watchAppPath(options) {
  return watchRealAppPath({ ...options, platform: 'darwin', packaged: true, execPath: executable, intervalMs: 0 })
}
