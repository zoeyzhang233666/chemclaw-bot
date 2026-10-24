import { readFileSync, writeFileSync } from 'node:fs'

const path = new URL('../src/client/i18n.js', import.meta.url)
let text = readFileSync(path, 'utf8')
if (text.includes('ChemClaw 数据密钥')) {
  console.log('already present')
  process.exit(0)
}
const marker = "'Add a key': '添加密钥'"
const at = text.indexOf(marker)
if (at < 0) {
  console.error('marker not found')
  process.exit(1)
}
const lineEnd = text.indexOf('\n', at)
const insert = `,
  'ChemClaw data keys': 'ChemClaw 数据密钥',
  'Connect ChemClaw data (keys only)': '接入 ChemClaw 数据（只需填 Key）',
  'MCP addresses are already set. Paste your two API keys below — never into the chat.': 'MCP 地址已预置。在下方粘贴两个 API Key 即可，不要贴进聊天。',
  'Paste the API key for {name}': '粘贴 {name} 的 API Key',
  'Could not save the key': '密钥保存失败',
  Later: '稍后',
  'Open Secrets': '打开密钥页'`
// Insert after the Add a key line's trailing comma if present, else before newline.
let end = lineEnd
if (text[end - 1] === '\r') end -= 1
const before = text.slice(0, end)
const after = text.slice(end)
const hasComma = before.endsWith(',')
const next = hasComma
  ? before.slice(0, -1) + insert + ',' + after
  : before + insert + after
writeFileSync(path, next)
console.log('ok')
