import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const source = file => readFileSync(new URL(`../src/client/${file}`, import.meta.url), 'utf8')

test('Settings dialog follows the unchanged quick-settings menu order', () => {
  const settings = source('settings.js')
  const sidebar = source('sidebar.js')
  const match = settings.match(/const SETTINGS_PAGES = (\[[^\n]+\])/)
  assert.ok(match, 'Settings page list exists')
  const pages = [...match[1].matchAll(/\['([^']+)', '[^']+'\]/g)].map(result => result[1])
  assert.equal(new Set(pages).size, pages.length, 'each settings page appears once')
  assert.deepEqual(pages.slice(0, 5), ['usage', 'models', 'connectors', 'schedules', 'general'])

  const account = sidebar.slice(sidebar.indexOf('export function AccountLauncher'))
  const menu = account.slice(account.indexOf('const groups = ['), account.indexOf('if (signedIn) groups.push'))
  const labels = ["t('Usage')", "t('Models and API keys')", "t('Connectors')", "t('Automation tasks')", "t('Settings')"]
  const positions = labels.map(label => menu.indexOf(label))
  assert.ok(positions.every(position => position >= 0), 'quick menu retains all five entries')
  assert.ok(positions.every((position, index) => index === 0 || position > positions[index - 1]),
    'quick menu order remains unchanged')
})

test('ChemClaw Settings pages remain reachable and Computer use is wired in', () => {
  const settings = source('settings.js')
  const match = settings.match(/const SETTINGS_PAGES = (\[[^\n]+\])/)
  assert.ok(match)
  const pages = [...match[1].matchAll(/\['([^']+)', '[^']+'\]/g)].map(result => result[1])
  for (const id of ['general', 'models', 'bots', 'groups', 'connectors', 'skills', 'capabilities', 'browser', 'schedules', 'usage', 'secrets', 'feedback', 'about']) {
    assert.ok(pages.includes(id), `missing ChemClaw settings page: ${id}`)
  }
  assert.equal(pages[pages.indexOf('browser') + 1], 'computer')
  assert.match(settings, /import \{ ComputerPage \} from '\.\/computer\.js'/)
  assert.match(settings, /shown === 'computer' \? h\(ComputerPage,/)
})
