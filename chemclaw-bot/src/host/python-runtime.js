import { createHash } from 'node:crypto'
import { existsSync } from 'node:fs'
import { chmod, mkdir, readFile, rename, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { unzipSync } from 'fflate'

export const UV_VERSION = '0.13.6'
const RELEASES = {
  'win32-x64': ['x86_64-pc-windows-msvc.zip', 'a2a8820d5eea32f08ef467ef3b7f66883a9b076d5737a2fc2fbb5f458d1bb50f'],
  'win32-arm64': ['aarch64-pc-windows-msvc.zip', 'c2426c0c8e28b53d8c440e47a18d96ad4db51e159866c0e81435b196d7f0081c'],
  'darwin-x64': ['x86_64-apple-darwin.tar.gz', '63ba17fdda55ad1a230d4b37fc6017ffa10c23688c83818bd3bfdf914c652a02'],
  'darwin-arm64': ['aarch64-apple-darwin.tar.gz', '60fbd5c8a1ed681845eea28d9d622fcde03c51e91a43465b64a1e17db1ed3472'],
  'linux-x64': ['x86_64-unknown-linux-gnu.tar.gz', 'f29c3e94ffabd7e6f3ba521dba169a9b7ec12100bf3257087f0f24f6123f3645'],
  'linux-arm64': ['aarch64-unknown-linux-gnu.tar.gz', '229e194255c7958d86d56e8790d969a6f74736592133f0dfd0076f754c642c1d'],
}

export function uvRelease(platform = process.platform, arch = process.arch) {
  const release = RELEASES[`${platform}-${arch}`]
  if (!release) throw new Error('Automatic analysis setup is unavailable on this platform.')
  return { name: `uv-${release[0]}`, sha256: release[1] }
}

export function verifyArchive(data, expected) {
  if (createHash('sha256').update(data).digest('hex') !== expected) throw new Error('Analysis installer verification failed.')
}

export async function provisionUv(root, { run, signal, fetch: request = globalThis.fetch }) {
  const dir = join(root, `uv-${UV_VERSION}`)
  const binary = join(dir, process.platform === 'win32' ? 'uv.exe' : 'uv')
  if (existsSync(binary)) return binary
  const release = uvRelease()
  const response = await request(`https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/${release.name}`, {
    signal: AbortSignal.any([signal, AbortSignal.timeout(180_000)]),
  })
  if (!response.ok) throw new Error('Analysis components could not be downloaded.')
  const data = new Uint8Array(await response.arrayBuffer())
  verifyArchive(data, release.sha256)
  await mkdir(dir, { recursive: true })
  const staging = join(dir, 'uv.pending')
  if (process.platform === 'win32') {
    const files = unzipSync(data, { filter: entry => entry.name === 'uv.exe' })
    if (!files['uv.exe']) throw new Error('Analysis installer is incomplete.')
    await writeFile(staging, files['uv.exe'])
  } else {
    const archive = join(dir, release.name)
    await writeFile(archive, data)
    const entry = `${release.name.slice(0, -7)}/uv`
    await run('tar', ['-xzf', archive, '-C', dir, entry])
    await writeFile(staging, await readFile(join(dir, entry)))
    await chmod(staging, 0o755)
  }
  await rename(staging, binary)
  return binary
}
