import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { basename, dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const source = process.argv[2]
if (!source || !existsSync(source)) throw new Error('Usage: node scripts/import-skills.mjs <scenario skills folder>')
const destination = join(root, 'skills', 'domain')
const excluded = /^(node_modules|\.venv|venv|__pycache__|\.git|\.pytest_cache|\.DS_Store)$/i
const skip = path => excluded.test(basename(path)) || /\.(zip|pyc|pyo|exe|log|tgz)$/i.test(path) || /^\.env/i.test(basename(path))
const skills = []
function walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name)
    if (skip(path) || entry.isSymbolicLink()) continue
    if (entry.isDirectory()) walk(path)
    else if (entry.name === 'SKILL.md') skills.push(path)
  }
}
walk(source)
mkdirSync(destination, { recursive: true })
cpSync(source, destination, { recursive: true, filter: path => !skip(path), dereference: false })
const index = skills.map(path => {
  const sourcePath = `skills/domain/${relative(source, path).replaceAll('\\', '/')}`
  const content = readFileSync(path, 'utf8')
  const name = content.match(/^name:\s*["']?([^\r\n"']+)/m)?.[1]?.trim() ?? basename(dirname(path))
  const parts = relative(source, path).split(/[\\/]/)
  return { id: `domain-${skills.indexOf(path) + 1}`, name, category: parts[0], scene: parts[1], sourcePath }
})
writeFileSync(join(root, 'seed', 'domain-skills.json'), `${JSON.stringify(index, null, 2)}\n`)
console.log(`Imported ${index.length} complete scenario skills (scripts, references and assets included).`)
