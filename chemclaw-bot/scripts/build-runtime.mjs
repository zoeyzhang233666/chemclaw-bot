import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { cp, lstat, mkdir, mkdtemp, readFile, readdir, realpath, rm, symlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { provisionUv } from '../src/host/python-runtime.js'
import { readRuntimeBundle, requirementsFingerprint, requirementsHash, runtimePython, runtimeTarget, runtimeTar } from '../src/host/runtime-bundle.js'

const execute = promisify(execFile)
const sourceRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const IMPORTS = 'import akshare, pandas; print(akshare.__version__)'

async function bytes(root) {
  const info = await lstat(root)
  if (info.isSymbolicLink()) return 0
  if (info.isFile()) return info.size
  return (await Promise.all((await readdir(root)).map(name => bytes(join(root, name))))).reduce((sum, size) => sum + size, 0)
}

export async function buildRuntimeBundle(packageRoot = sourceRoot) {
  const target = runtimeTarget()
  try {
    const existing = await readRuntimeBundle(packageRoot, target)
    if (existing && requirementsHash(await readFile(existing.archive)) === existing.manifest.sha256) return existing.manifest
  } catch { /* Rebuild stale or incomplete artifacts on the build machine. */ }
  const tools = join(packageRoot, 'runtime', '.build-tools')
  await mkdir(tools, { recursive: true })
  const work = await mkdtemp(join(tmpdir(), 'chemclaw-runtime-build-'))
  const controller = new AbortController()
  const env = { ...process.env, UV_PYTHON_INSTALL_DIR: join(tools, 'interpreters'), UV_CACHE_DIR: join(tools, 'cache'), UV_NO_PROGRESS: '1' }
  const run = (command, args) => execute(command, args, { env, windowsHide: true, timeout: 900_000, maxBuffer: 8_000_000 })
  try {
    const uv = await provisionUv(tools, { run, signal: controller.signal })
    console.log(`Preparing Python for ${target}`)
    await run(uv, ['--no-config', 'python', 'install', '--no-bin', '3.12'])
    const found = (await run(uv, ['--no-config', 'python', 'find', '--managed-python', '3.12'])).stdout.trim()
    const tree = join(work, 'payload')
    const original = await realpath(process.platform === 'win32' ? dirname(found) : dirname(dirname(found)))
    await cp(original, process.platform === 'win32' ? join(tree, 'Scripts') : tree, { recursive: true, verbatimSymlinks: true })
    const python = runtimePython(tree)
    if (process.platform !== 'win32') {
      try { await lstat(python) } catch { await symlink('python3', python) }
    }
    // The copied uv interpreter retains a PEP 668 marker; only this private copy is modified.
    console.log('Installing required market libraries on the build machine')
    await run(uv, ['--no-config', 'pip', 'install', '--system', '--break-system-packages', '--python', python, '-r', join(packageRoot, 'runtime', 'requirements.txt')])
    await run(python, ['-c', IMPORTS])
    const output = join(packageRoot, 'runtime', 'bundled')
    await mkdir(output, { recursive: true })
    const archive = join(output, `${target}.tar.gz`)
    console.log('Packing and verifying relocation')
    await run(runtimeTar(), ['-czf', archive, '-C', tree, '.'])
    // A second location catches absolute interpreter paths before publishing.
    const relocated = join(work, 'relocated')
    await mkdir(relocated)
    await run(runtimeTar(), ['-xzf', archive, '-C', relocated])
    await run(runtimePython(relocated), ['-c', IMPORTS])
    const data = await readFile(archive)
    const manifest = { version: 1, target, python: '3.12', requirements: requirementsFingerprint(await readFile(join(packageRoot, 'runtime', 'requirements.txt'))), sha256: requirementsHash(data), archiveBytes: data.length, unpackedBytes: await bytes(tree) }
    await writeFile(join(output, `${target}.json`), `${JSON.stringify(manifest, null, 2)}\n`)
    return manifest
  } finally {
    if (dirname(work) !== resolve(tmpdir()) || !work.startsWith(join(resolve(tmpdir()), 'chemclaw-runtime-build-'))) throw new Error('Unexpected runtime build directory')
    await rm(work, { recursive: true, force: true, maxRetries: 5 })
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const manifest = await buildRuntimeBundle()
  console.log(`${manifest.target}: ${(manifest.archiveBytes / 1048576).toFixed(1)} MiB bundled; ${(manifest.unpackedBytes / 1048576).toFixed(1)} MiB installed`)
}
