import { createHash } from 'node:crypto'
import { existsSync } from 'node:fs'
import { mkdir, mkdtemp, readFile, rename, rm, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'

export const runtimeTarget = () => `${process.platform}-${process.arch}`
export const runtimePython = root => join(root, process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
export const requirementsHash = data => createHash('sha256').update(data).digest('hex')
export const requirementsFingerprint = data => requirementsHash(Buffer.from(data.toString('utf8').replace(/\r\n/g, '\n')))

export async function readRuntimeBundle(packageRoot, target = runtimeTarget()) {
  const dir = join(packageRoot, 'runtime', 'bundled')
  try {
    const manifest = JSON.parse(await readFile(join(dir, `${target}.json`), 'utf8'))
    if (manifest.target !== target || manifest.version !== 1 || !/^[a-f0-9]{64}$/.test(manifest.sha256)) throw new Error('Invalid bundled market components.')
    const expected = requirementsFingerprint(await readFile(join(packageRoot, 'runtime', 'requirements.txt')))
    if (manifest.requirements !== expected) throw new Error('Bundled market components do not match this plugin version.')
    return { manifest, archive: join(dir, `${target}.tar.gz`) }
  } catch (error) {
    if (error.code === 'ENOENT') return undefined
    throw error
  }
}

export async function unpackRuntimeBundle(bundle, root, { run, verify }) {
  const { manifest } = bundle
  const destination = join(root, 'python')
  const marker = join(root, 'bundled-market.json')
  try {
    if (JSON.parse(await readFile(marker, 'utf8')).sha256 === manifest.sha256) {
      await verify(runtimePython(destination))
      return runtimePython(destination)
    }
  } catch { /* A missing or damaged installation is restored from the local archive. */ }
  const data = await readFile(bundle.archive)
  if (requirementsHash(data) !== manifest.sha256) throw new Error('Bundled market components failed verification.')
  await mkdir(root, { recursive: true })
  const staging = await mkdtemp(join(root, 'market-staging-'))
  if (dirname(staging) !== resolve(root) || !staging.startsWith(join(resolve(root), 'market-staging-'))) throw new Error('Unexpected runtime staging directory')
  try {
    // Materialize the archive for tar when the plugin is inside Electron's ASAR.
    const archive = join(staging, 'market.tar.gz')
    const tree = join(staging, 'python')
    await mkdir(tree)
    await writeFile(archive, data)
    await run(process.platform === 'win32' ? 'tar.exe' : 'tar', ['-xzf', archive, '-C', tree])
    await verify(runtimePython(tree))
    const previous = existsSync(destination) ? join(staging, 'previous') : undefined
    if (previous) await rename(destination, previous)
    try { await rename(tree, destination) } catch (error) {
      if (previous) await rename(previous, destination)
      throw error
    }
    await writeFile(marker, JSON.stringify({ sha256: manifest.sha256 }))
    return runtimePython(destination)
  } finally { await rm(staging, { recursive: true, force: true, maxRetries: 5 }) }
}
