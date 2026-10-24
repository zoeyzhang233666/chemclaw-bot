import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../skills/domain')
let changed = 0
function walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) { walk(path); continue }
    if (!/\.(md|py|json|jsonl|txt|js|html|csv)$/i.test(name)) continue
    const text = readFileSync(path, 'utf8')
    const slash = value => value.replaceAll('\\', '/')
    const domain = slash(relative(dirname(path), root)) || '.'
    let next = text
    for (const source of ['D:\\chemclaw场景分类上下文\\skills', 'D:/chemclaw场景分类上下文/skills']) {
      next = next.replaceAll(source.replaceAll('\\', '\\\\'), domain).replaceAll(source, domain)
    }
    next = next.replace(/[A-Z]:(?:\\{1,2}|\/)Users(?:\\{1,2}|\/)[^\r\n"'<>`]{1,200}?(?:default-workspace|workspace)(?:\\{1,2}|\/)/g, './')
    next = next.replace(/\/mnt\/(?:data|work)(?:\/)?/g, './output/')
    if (next !== text) { writeFileSync(path, next); changed++ }
  }
}
walk(root)
console.log(`Made ${changed} packaged text resources portable; originals are unchanged.`)
