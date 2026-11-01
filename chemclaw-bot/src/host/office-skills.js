// The ChemClaw Office skills: `office` (the routing skill, preferred over the
// platform's own bundled router) and `office-tools` (the CLI that inspects,
// checks and edits Office packages). Registered when a `skills` service exists;
// the sub-fiber stays inactive where it does not, so the plugin runs the same
// in DSH Web, DSH Desktop and the desktop app.
import { existsSync, readFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { dirname, isAbsolute, join, sep } from 'node:path'
import { isSea } from 'node:sea'
import { fileURLToPath } from 'node:url'
import { defineTool } from '@deepseek-ai/dsh-tools'

const PROVIDER = 'chemclaw-office'
const RANK = { office: 550, 'office-tools': 600 }
const ASSETS = join(dirname(fileURLToPath(import.meta.url)), '..', 'office', 'skills')
const CLI = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'office.js')

function parseSkill(raw, path) {
  const frontmatter = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/u.exec(raw)
  const metadata = frontmatter?.[1] ? Object.fromEntries(
    frontmatter[1].split('\n').map(line => /^(\w[\w-]*):\s*(.+)$/.exec(line.trim())?.slice(1) ?? []).filter(p => p.length === 2)) : {}
  if (typeof metadata.description !== 'string' || metadata.description.length === 0) {
    throw new Error(`${PROVIDER}: ${path} has no description`)
  }
  return { description: metadata.description, content: raw.slice(frontmatter[0].length).trim() }
}

// The payload Node is a plain interpreter and cannot read through an asar archive.
export function cliPath(manifest = CLI) {
  return manifest.replace(`${sep}app.asar${sep}`, `${sep}app.asar.unpacked${sep}`)
}

// Discover standalone Node from PATH on source-preview desktops without
// requiring the optional workspace-dependencies tool. An installer must
// still ship a standalone runtime for new users (PR-B).
export function findStandaloneNode(env = process.env, platform = process.platform, run = spawnSync) {
  const paths = env.Path || env.PATH || env.path || ''
  const separator = platform === 'win32' ? ';' : ':'
  const name = platform === 'win32' ? 'node.exe' : 'node'
  for (const item of paths.split(separator)) {
    const folder = item.replace(/^"|"$/g, '')
    if (!isAbsolute(folder)) continue
    const executable = join(folder, name)
    if (!existsSync(executable)) continue
    try {
      const result = run(executable, ['--version'], { encoding: 'utf8', timeout: 1500, windowsHide: true })
      if (result.status === 0 && /^v\d+\.\d+\.\d+/.test(String(result.stdout).trim())) return executable
    } catch { /* PATH candidate does not run as Node. */ }
  }
  return undefined
}

export function officeNode(env = process.env) {
  const bundled = env.CHEMCLAW_OFFICE_NODE
  if (bundled !== undefined && existsSync(bundled)) return { node: bundled }
  if (process.versions.electron === undefined && !isSea()) return { node: process.execPath }
  return { node: findStandaloneNode(env) }
}

function runtimeBlock() {
  const cli = cliPath()
  const { node } = officeNode()
  const paths = node === undefined
    ? `The commands need a standalone Node. Call the \`load_workspace_dependencies\` tool and use its \`node\` value; if that tool is not in the catalog, these commands are unavailable here.`
    : `Run the commands as \`"${node}" "${cli}" …\` in Bash, or \`& "${node}" "${cli}" …\` in PowerShell.`
  return `\n\n## Office tools\n\n${JSON.stringify({ officeTools: { node, cli } }, undefined, 2)}\n\n${paths}`
}

function candidates() {
  return Object.keys(RANK).map(skillName => {
    const directory = join(ASSETS, skillName)
    const locator = join(directory, 'SKILL.md')
    const { description } = parseSkill(readFileSync(locator, 'utf8'), locator)
    return {
      name: skillName, description,
      invocation: { modelInvocable: true, userInvocable: true },
      provider: PROVIDER, source: 'bundled', rank: RANK[skillName],
      resourceBase: { kind: 'directory', path: directory.split(sep).join('/') },
      locator,
    }
  })
}

export function officeProvider() {
  const all = candidates()
  return {
    name: PROVIDER,
    list: () => Promise.resolve(all),
    async get(candidate) {
      const { description, content } = parseSkill(readFileSync(candidate.locator, 'utf8'), candidate.locator)
      return { ...candidate, description, content: content + (candidate.name === 'office-tools' ? runtimeBlock() : '') }
    },
  }
}


/** A read-only real environment check; installed packages alone do not prove
 * DSH mounted their services, and system Python is not the Office payload. */
export function officeEnvironmentStatus(env = process.env, run = spawnSync) {
  const runtimeDir = env.CHEMCLAW_OFFICE_RUNTIME_DIR
  const root = runtimeDir && join(runtimeDir, 'primary-runtime')
  const win = process.platform === 'win32'
  const node = root && join(root, 'dependencies', 'node', 'bin', win ? 'node.exe' : 'node')
  const python = root && join(root, 'dependencies', 'python', ...(win ? ['python.exe'] : ['bin', 'python3']))
  const manifest = root && join(root, 'runtime.json')
  const officeAsset = runtimeDir && join(runtimeDir, 'office-skills', 'office', 'SKILL.md')
  const overlay = env.DSH_HOME && join(env.DSH_HOME, 'profiles', 'office.patch.yml')
  const exists = p => Boolean(p && existsSync(p))
  let pythonImports
  if (exists(python)) {
    try {
      const result = run(python, ['-I', '-B', '-c', 'import docx, pptx, openpyxl; print("OK")'], {
        encoding: 'utf8', windowsHide: true, timeout: 20000,
      })
      pythonImports = { ok: result.status === 0 && String(result.stdout).includes('OK'),
        exitCode: result.status, error: String(result.stderr || result.error?.message || '').slice(0, 1500) }
    } catch (error) { pythonImports = { ok: false, error: String(error.message || error) } }
  }
  const found = {
    runtimeDir: runtimeDir || null,
    manifest: { path: manifest || null, exists: exists(manifest) },
    officeAsset: { path: officeAsset || null, exists: exists(officeAsset) },
    node: { path: node || null, exists: exists(node) },
    python: { path: python || null, exists: exists(python), imports: pythonImports || null },
    overlay: { path: overlay || null, exists: exists(overlay) },
    hostOfficeNode: env.CHEMCLAW_OFFICE_NODE || null,
    nativeToolRegistration: 'Unknown from disk inspection: must actually invoke load_workspace_dependencies.',
  }
  found.payloadComplete = found.manifest.exists && found.officeAsset.exists
    && found.node.exists && found.python.exists && pythonImports?.ok === true
  return found
}

export function install(rt) {
  rt.ctx.inject?.({ skills: null }, ctx => ctx.skills.registerProvider(() => officeProvider()))
  rt.ctx.tools?.register?.(defineTool({
    name: 'chem_office_runtime_status',
    description: 'Read-only diagnostics of ChemClaw bundled Office runtime and DSH overlay, including a real Python module import test; does not install packages or change permissions.',
    parameters: {},
    output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] },
    execute: async () => JSON.stringify(officeEnvironmentStatus()),
  }))
}

