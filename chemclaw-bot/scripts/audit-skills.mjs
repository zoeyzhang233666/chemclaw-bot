import { readFileSync, writeFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
const patterns = [/\bcdh_[A-Za-z0-9_-]{24,}/g, /\bsk-[A-Za-z0-9_-]{24,}/g, /\bgh[pousr]_[A-Za-z0-9_]{24,}/g, /Bearer\s+[A-Za-z0-9_-]{28,}/g]
const findings = []
function walk(root) {
  for (const name of readdirSync(root)) {
    const path = join(root, name)
    if (statSync(path).isDirectory()) { walk(path); continue }
    if (!/\.(md|py|json|jsonl|txt|js|html|csv|yml)$/i.test(name)) continue
    let text = readFileSync(path, 'utf8')
    let count = 0
    for (const pattern of patterns) text = text.replace(pattern, () => { count++; return '<API_KEY>' })
    if (count) { findings.push({ file: path, count }); if (process.argv.includes('--sanitize')) writeFileSync(path, text) }
  }
}
walk('skills')
console.log(JSON.stringify({ credentialFindings: findings }, null, 2))
if (findings.length && !process.argv.includes('--sanitize')) process.exitCode = 1
