// The native Office engine requires the dynamically linked Visual C++ runtime.
// Use the engine's exported packaging manifest and Windows application-local
// deployment, so an old or partially serviced system runtime cannot break it.
import { createHash } from 'node:crypto'
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, isAbsolute, join, relative, resolve } from 'node:path'

export const officeCrtLock = JSON.parse(readFileSync(new URL('./office-crt.lock.json', import.meta.url), 'utf8'))

function within(root, path) {
  const destination = resolve(root, path)
  const rel = relative(resolve(root), destination)
  if (!rel || rel === '..' || rel.startsWith('../') || rel.startsWith('..\\') || isAbsolute(rel)) {
    throw new Error('Office CRT path escapes its package: ' + path)
  }
  return destination
}

function executable(engineRoot) {
  const { name } = JSON.parse(readFileSync(join(engineRoot, 'package.json'), 'utf8'))
  const manifestPath = createRequire(join(engineRoot, 'package.json')).resolve(name + '/prebuilds.json')
  within(engineRoot, relative(engineRoot, manifestPath))
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
  if (manifest.platform !== 'win32-x64' || manifest.engine?.kind !== 'native' || typeof manifest.engine.executable !== 'string') {
    throw new Error('Office CRT requires a Windows x64 native packaging manifest')
  }
  return { manifest, file: within(engineRoot, manifest.engine.executable) }
}

const digest = file => createHash('sha256').update(readFileSync(file)).digest('hex')

/** Stage only the locked release CRT files; never distribute debug_nonredist. */
export function stageOfficeCrt(engineRoot, archiveRoot, license, lock = officeCrtLock) {
  const { manifest, file } = executable(engineRoot)
  const destination = dirname(file)
  const files = Object.entries(lock.files).map(([name, sha256]) => {
    if (!/^[a-z0-9_]+\.dll$/u.test(name)) throw new Error('Invalid Office CRT filename: ' + name)
    const source = within(archiveRoot, lock.directory + '/' + name)
    const target = within(destination, name)
    if (Object.hasOwn(manifest.files ?? {}, relative(engineRoot, target).replaceAll('\\', '/'))) {
      throw new Error('Office CRT would overwrite a versioned engine file: ' + name)
    }
    if (digest(source) !== sha256) throw new Error('Office CRT checksum mismatch: ' + name)
    return { source, target }
  })
  if (digest(license) !== lock.license.sha256) throw new Error('Office CRT license checksum mismatch')
  // Check the entire input before modifying the staged engine.
  for (const { source, target } of files) copyFileSync(source, target)
  const notices = join(engineRoot, 'licenses', 'chemclaw-visual-cpp')
  mkdirSync(notices, { recursive: true })
  copyFileSync(license, join(notices, 'Microsoft-VC-Runtime-License.docx'))
  writeFileSync(join(notices, 'provenance.json'), JSON.stringify(lock, null, 2) + '\n')
  writeFileSync(join(notices, 'NOTICE.txt'),
    'Microsoft Visual C++ Runtime ' + lock.version + ' (x64)\n' +
    'Copyright (c) Microsoft Corporation. All rights reserved.\n' +
    'Unmodified release redistributable binaries. Microsoft Software License Terms apply; see the accompanying license.\n' +
    lock.redistribution + '\n')
  verifyOfficeCrt(engineRoot, lock)
  return { directory: destination, files: files.length, version: lock.version }
}

export function verifyOfficeCrt(engineRoot, lock = officeCrtLock) {
  const destination = dirname(executable(engineRoot).file)
  for (const [name, sha256] of Object.entries(lock.files)) {
    if (digest(within(destination, name)) !== sha256) throw new Error('Packaged Office CRT checksum mismatch: ' + name)
  }
}
