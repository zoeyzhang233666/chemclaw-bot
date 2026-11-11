// Make the approved original macOS icon match neighboring Launchpad icons.
// The original 1024px RGBA asset remains byte-for-byte untouched.
// Shrink the entire rendered artwork to 80% with TRANSPARENT outside margins.
// This intentionally modifies only the macOS packager's derived resource.
import { spawnSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const appDir = join(dirname(fileURLToPath(import.meta.url)), '..')
const original = join(appDir, 'assets', 'icon-mac.png')
const output = join(appDir, 'build', 'icon-mac-balanced.png')
export const ICON_SIZE = 1024
export const ARTWORK_SIZE = 820
export const OFFSET = (ICON_SIZE - ARTWORK_SIZE) / 2

function checkRgbaPng(png, label) {
  if (png.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a' ||
      png.readUInt32BE(16) !== ICON_SIZE ||
      png.readUInt32BE(20) !== ICON_SIZE ||
      png.readUInt8(25) !== 6) {
    throw new Error(label + ': expected a 1024x1024 RGBA PNG')
  }
}

if (process.platform !== 'darwin') {
  // Windows/Linux never use the Mac icon and must not run the renderer.
  console.log('mac icon: skipped on ' + process.platform)
} else if (process.versions.electron) {
  const { app, BrowserWindow } = await import('electron')
  try {
    checkRgbaPng(readFileSync(original), 'Original approved macOS icon')
    await app.whenReady()
    const win = new BrowserWindow({
      show: false,
      webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true },
    })
    try {
      await win.loadURL('data:text/html;charset=UTF-8,<!doctype html><title>Mac icon</title>')
      const dataUrl = 'data:image/png;base64,' + readFileSync(original).toString('base64')
      const render = async (src, targetSize, artworkSize, inset) => {
        const image = new Image()
        image.src = src
        await image.decode()
        const canvas = document.createElement('canvas')
        canvas.width = canvas.height = targetSize
        const context = canvas.getContext('2d')
        context.clearRect(0, 0, targetSize, targetSize)
        context.imageSmoothingEnabled = true
        context.imageSmoothingQuality = 'high'
        context.drawImage(image, inset, inset, artworkSize, artworkSize)
        return canvas.toDataURL('image/png').split(',')[1]
      }
      const js = '(' + render.toString() + ')(' +
        JSON.stringify(dataUrl) + ',' + ICON_SIZE + ',' + ARTWORK_SIZE + ',' + OFFSET + ')'
      const png = Buffer.from(await win.webContents.executeJavaScript(js, true), 'base64')
      checkRgbaPng(png, 'Generated Mac icon')
      mkdirSync(join(appDir, 'build'), { recursive: true })
      writeFileSync(output, png)
      console.log('mac icon: created 1024px transparent canvas with 820px original artwork')
    } finally {
      win.destroy()
    }
    app.exit(0)
  } catch (error) {
    console.error(error)
    app.exit(1)
  }
} else {
  // Use the project's installed Electron, just like scripts/icon.mjs.
  const electron = createRequire(import.meta.url)('electron')
  const { ELECTRON_RUN_AS_NODE: _ignored, ...env } = process.env
  const result = spawnSync(electron, [fileURLToPath(import.meta.url)], {
    stdio: 'inherit', env,
  })
  if (result.error) throw result.error
  if (result.status !== 0) process.exit(result.status ?? 1)
}
