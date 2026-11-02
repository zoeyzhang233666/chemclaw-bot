// A standalone Node outside Electron's asar cannot resolve dependencies kept
// inside app.asar. Stage the installed LibreOffice Kit dependency closure beside
// the pinned Node runtime, preserving npm's nested dependency layout and engine.
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { dirname, isAbsolute, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

export const OFFICE_CONVERTER_DIR = 'office-converter'
const appDir = dirname(fileURLToPath(new URL('../package.json', import.meta.url)))

export function officeConverterCli(runtimeDir) {
  return join(runtimeDir, OFFICE_CONVERTER_DIR, 'node_modules', '@deepseek-ai', 'libreoffice-kit', 'lib', 'cli.js')
}

export function platformEngine(platform = process.platform, arch = process.arch) {
  return platform === 'linux' ? '@deepseek-ai/libreoffice-kit-wasm'
    : `@deepseek-ai/libreoffice-kit-${platform}-${arch}`
}

function findPackage(from, name, installed) {
  let base = from
  while (base === installed || base.startsWith(installed + sep) || base === dirname(installed)) {
    const folder = join(base, 'node_modules', name)
    if (existsSync(join(folder, 'package.json'))) return folder
    if (base === dirname(installed)) break
    base = dirname(base)
  }
  return null
}

/**
 * Copy the versioned npm dependency closure from the build installation to a
 * relocatable tree. Missing mandatory deps fail packaging; optional deps must
 * not be silently ignored for the current platform's LibreOffice engine.
 */
export function stageOfficeConverter(output, {
  installed = join(appDir, 'node_modules'),
  platform = process.platform,
  arch = process.arch,
  copy = cpSync,
} = {}) {
  const root = resolve(installed)
  const target = join(resolve(output), OFFICE_CONVERTER_DIR, 'node_modules')
  const kit = join(root, '@deepseek-ai', 'libreoffice-kit')
  const engineName = platformEngine(platform, arch)
  if (!existsSync(join(kit, 'package.json'))) throw new Error('Missing libreoffice-kit in npm installation: ' + kit)
  const engine = findPackage(kit, engineName, root)
  if (!engine) throw new Error('Missing required Office conversion engine ' + engineName + '; rerun npm ci with optional dependencies enabled')
  const queue = [kit]
  const visited = new Set()
  rmSync(dirname(target), { recursive: true, force: true })
  while (queue.length) {
    const dir = queue.shift()
    const rel = relative(root, dir)
    if (!rel || rel.startsWith('..') || isAbsolute(rel)) throw new Error('Office dependency escaped app/node_modules: ' + dir)
    if (visited.has(rel)) continue
    visited.add(rel)
    const pkg = JSON.parse(readFileSync(join(dir, 'package.json'), 'utf8'))
    const dest = join(target, rel)
    mkdirSync(dirname(dest), { recursive: true })
    copy(dir, dest, { recursive: true, dereference: true })
    for (const name of Object.keys({ ...pkg.dependencies, ...pkg.optionalDependencies })) {
      const found = findPackage(dir, name, root)
      if (!found) {
        if (Object.hasOwn(pkg.dependencies ?? {}, name)) throw new Error(`Missing Office dependency ${name} required by ${pkg.name}`)
        continue
      }
      queue.push(found)
    }
  }
  if (!existsSync(officeConverterCli(resolve(output)))) throw new Error('Staged Office CLI is missing')
  if (!existsSync(join(target, relative(root, engine), 'package.json'))) throw new Error('Staged Office engine is missing: ' + engineName)
  console.log('office-converter: staged ' + visited.size + ' packages including ' + engineName)
  return { cli: officeConverterCli(resolve(output)), packages: [...visited], engineName }
}
