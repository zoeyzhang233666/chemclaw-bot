// Before DSH modules load, resolve its Office-to-PDF provider against the real,
// self-contained LibreOffice Kit directory. Native executables cannot be spawned
// from app.asar virtual paths (ENOENT), even with asarUnpack enabled.
// Limit the redirect to DSH's own Office provider; all other imports keep their
// native Node resolution, including external plugins and their own kit versions.
import { existsSync } from 'node:fs'
import { registerHooks } from 'node:module'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

export function officeKitPhysicalEntry(resources) {
  return join(resources, 'office-converter', 'node_modules', '@deepseek-ai', 'libreoffice-kit', 'lib', 'index.js')
}

export function officeKitResolveHook(resources) {
  const target = pathToFileURL(officeKitPhysicalEntry(resources)).href
  return (specifier, context, nextResolve) => {
    if (specifier === '@deepseek-ai/libreoffice-kit'
      && /(?:^|[/\\])@deepseek-ai[/\\]dsh-office-to-pdf(?:[/\\]|$)/u.test(context.parentURL || '')) {
      return { url: target, shortCircuit: true }
    }
    return nextResolve(specifier, context)
  }
}

export function installOfficeKitHostResolver(resources = process.env.CHEMCLAW_OFFICE_RUNTIME_DIR, {
  exists = existsSync,
  register = registerHooks,
} = {}) {
  if (!resources || !exists(officeKitPhysicalEntry(resources))) return false
  register({ resolve: officeKitResolveHook(resources) })
  return true
}

// Electron HostProcess passes this file with --import so hooks are installed
// before static DSH imports; that order is essential for ESM package resolution.
if (process.env.CHEMCLAW_OFFICE_RUNTIME_DIR) installOfficeKitHostResolver()
