import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

// A throwaway Linux desktop handler records the paths it receives and exits.
// A real file manager can stay alive indefinitely on a headless CI desktop.
export function nativeOpenFixture(work) {
  const entry = join(work, 'native-open.mjs')
  const log = join(work, 'native-open.jsonl')
  const data = join(work, 'xdg-data')
  const config = join(work, 'xdg-config')
  const applications = join(data, 'applications')
  mkdirSync(applications, { recursive: true })
  mkdirSync(config, { recursive: true })
  writeFileSync(entry, '#!/usr/bin/env node\n' +
    "import { appendFileSync } from 'node:fs'\n" +
    'appendFileSync(' + JSON.stringify(log) + ', JSON.stringify(process.argv.slice(2)) + "\\n")\n', { mode: 0o755 })
  const quote = value => '"' + value.replaceAll('\\', '\\\\').replaceAll('"', '\\"').replaceAll('%', '%%') + '"'
  writeFileSync(join(applications, 'chemclaw-test.desktop'),
    '[Desktop Entry]\nType=Application\nName=ChemClaw test handler\nNoDisplay=true\nTerminal=false\n' +
    'Exec=' + quote(process.execPath) + ' ' + quote(entry) + ' %f\nMimeType=inode/directory;text/html;\n')
  writeFileSync(join(config, 'mimeapps.list'),
    '[Default Applications]\ninode/directory=chemclaw-test.desktop\ntext/html=chemclaw-test.desktop\n')
  return {
    entry,
    env: { XDG_DATA_HOME: data, XDG_CONFIG_HOME: config, XDG_CURRENT_DESKTOP: 'X-Generic', BROWSER: entry },
    received: () => readFileSync(log, 'utf8').trim().split('\n').flatMap(line => JSON.parse(line)),
  }
}
