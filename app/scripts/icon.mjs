// Draws the shared ChemClaw cloud outline and writes assets/icon.svg,
// assets/icon.png (1024 px) and assets/icon.ico (Windows, 16 to 256 px).
// Usage: npm run icon. It runs itself again inside Electron, which turns the SVG into PNGs.
import { spawnSync } from 'node:child_process'
import { CLOUD_OUTLINE } from '../../chemclaw-bot/src/shared/brand.js'
import { mkdirSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = fileURLToPath(import.meta.url)
const assets = join(dirname(here), '..', 'assets')
const ICO_SIZES = [16, 20, 24, 32, 36, 40, 48, 64, 72, 96, 128, 256]


// Fill the taskbar canvas with the outline; small sizes need a heavier stroke.
function iconSvg(size = 1024) {
  const stroke = size <= 32 ? 2.8 : 2.3
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="1 0 31 31">
<path d="${CLOUD_OUTLINE}" transform="translate(0 1)" fill="none" stroke="#F16A45" stroke-width="${stroke}" stroke-linecap="round" stroke-linejoin="round"/>
</svg>\n`
}

// PNG entries in an .ico file, which Windows reads since Vista.
function icoFile(images) {
  const head = Buffer.alloc(6 + 16 * images.length)
  head.writeUInt16LE(1, 2)
  head.writeUInt16LE(images.length, 4)
  let offset = head.length
  images.forEach(({ size, png }, index) => {
    const at = 6 + 16 * index
    head.writeUInt8(size >= 256 ? 0 : size, at)
    head.writeUInt8(size >= 256 ? 0 : size, at + 1)
    head.writeUInt16LE(1, at + 4)
    head.writeUInt16LE(32, at + 6)
    head.writeUInt32LE(png.length, at + 8)
    head.writeUInt32LE(offset, at + 12)
    offset += png.length
  })
  return Buffer.concat([head, ...images.map(image => image.png)])
}

// Inside Electron: a page draws each SVG on a canvas of its exact size, so every size is
// drawn from the vectors rather than scaled down from a large bitmap.
async function renderInElectron(jobs) {
  const { BrowserWindow } = await import('electron')
  const page = new BrowserWindow({ show: false })
  await page.loadURL('data:text/html,<!doctype html><title>icon</title>')
  const draw = async (list) => Promise.all(list.map(async ({ svg, size }) => {
    const image = new Image()
    image.src = `data:image/svg+xml,${encodeURIComponent(svg)}`
    await image.decode()
    const canvas = document.createElement('canvas')
    canvas.width = size
    canvas.height = size
    canvas.getContext('2d').drawImage(image, 0, 0, size, size)
    return canvas.toDataURL('image/png').slice('data:image/png;base64,'.length)
  }))
  const pngs = await page.webContents.executeJavaScript(`(${draw.toString()})(${JSON.stringify(jobs)})`)
  page.destroy()
  return pngs.map(data => Buffer.from(data, 'base64'))
}

if (process.versions.electron) {
  const jobs = [{ svg: iconSvg(), size: 1024 }, ...ICO_SIZES.map(size => ({ svg: iconSvg(size), size }))]
  // Not awaited at the top: Electron is ready only after the main module has run.
  const { app } = await import('electron')
  app.whenReady().then(() => renderInElectron(jobs)).then(([large, ...small]) => {
    writeFileSync(join(assets, 'icon.png'), large)
    writeFileSync(join(assets, 'icon.ico'), icoFile(ICO_SIZES.map((size, index) => ({ size, png: small[index] }))))
    app.exit(0)
  }).catch((error) => {
    console.error(error)
    app.exit(1)
  })
} else {
  mkdirSync(assets, { recursive: true })
  writeFileSync(join(assets, 'icon.svg'), iconSvg())
  // A terminal inside an Electron-based editor may set ELECTRON_RUN_AS_NODE, which would keep Electron plain Node.
  const { ELECTRON_RUN_AS_NODE: _runAsNode, ...env } = process.env
  const electron = createRequire(import.meta.url)('electron')
  const run = spawnSync(electron, [here], { stdio: 'inherit', env })
  if (run.status !== 0) process.exit(run.status ?? 1)
  console.log('icon: wrote assets/icon.svg, assets/icon.png and assets/icon.ico')
}
