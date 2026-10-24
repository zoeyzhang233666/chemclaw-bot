import { readFileSync, writeFileSync } from 'node:fs'

const src = new URL('../../ds-bot/src/client/', import.meta.url)
const dst = new URL('../src/client/', import.meta.url)
const files = ['i18n.js', 'about.js', 'settings.js', 'feedback.js', 'providers-page.js', 'sidebar.js']

const setupInsert = `  'Add a key': '添加密钥',
  'ChemClaw data keys': 'ChemClaw 数据密钥',
  'Connect ChemClaw data (keys only)': '接入 ChemClaw 数据（只需填 Key）',
  'MCP addresses are already set. Paste your two API keys below — never into the chat.': 'MCP 地址已预置。在下方粘贴两个 API Key 即可，不要贴进聊天。',
  'Paste the API key for {name}': '粘贴 {name} 的 API Key',
  'Could not save the key': '密钥保存失败',
  Later: '稍后',
  'Open Secrets': '打开密钥页',
`

for (const name of files) {
  let text = readFileSync(new URL(name, src), 'utf8')
  text = text.split('DS Bot').join('ChemClaw')
  if (name === 'i18n.js') {
    text = text.replace("export const NAMESPACE = 'ds-bot'", "export const NAMESPACE = 'chemclaw-bot'")
    text = text.replace(/  'Add a key': '[^']*',\n/, setupInsert)
  }
  if (name === 'sidebar.js') {
    text = text.replace(
      /return h\('span', \{ style: \{ fontWeight: 600, fontSize: 14 \} \}, '[^']*'\)/,
      "return h('span', { style: { fontWeight: 600, fontSize: 14 } }, 'ChemClaw')",
    )
  }
  writeFileSync(new URL(name, dst), text)
  console.log('wrote', name)
}

const i18n = readFileSync(new URL('i18n.js', dst), 'utf8')
console.log({
  updating: i18n.includes('正在更新 ChemClaw'),
  setup: i18n.includes('ChemClaw 数据密钥'),
  namespace: i18n.includes("NAMESPACE = 'chemclaw-bot'"),
  broken: /�/.test(i18n),
})
