import { readFileSync, writeFileSync, renameSync, unlinkSync, existsSync } from 'node:fs'
import { basename, dirname, extname, join } from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const require = createRequire(fileURLToPath(import.meta.url))
const ExcelJS = require('exceljs')
const JSZip = require('jszip')

/** Return whether an .xlsx uses packaging that DSH's browser Excel preview rejects. */
export async function needsXlsxPreviewNormalize(path) {
  if (extname(path).toLowerCase() !== '.xlsx') return false
  if (!existsSync(path)) return false
  try {
    const zip = await JSZip.loadAsync(readFileSync(path))
    const rels = zip.file('xl/_rels/workbook.xml.rels')
    const styles = zip.file('xl/styles.xml')
    if (!rels || !styles) return true
    const relText = await rels.async('string')
    const styleText = await styles.async('string')
    return /Target="\/xl\//.test(relText) || /<patternFill\/>/.test(styleText)
  } catch {
    return false
  }
}

/**
 * Rewrite an .xlsx in place so DSH sidebar Excel preview can parse it.
 * Uses ExcelJS round-trip: values and sheet names are kept; charts/drawings/macros are dropped.
 * @returns {Promise<boolean>} true when the file was rewritten
 */
export async function normalizeXlsxForPreview(path) {
  if (!(await needsXlsxPreviewNormalize(path))) return false
  const book = new ExcelJS.Workbook()
  await book.xlsx.load(readFileSync(path))
  if (book.worksheets.length === 0) throw new Error(`Workbook has no sheets: ${basename(path)}`)
  const bytes = Buffer.from(await book.xlsx.writeBuffer())
  const temp = join(dirname(path), `.${basename(path)}.preview-normalize`)
  writeFileSync(temp, bytes)
  try {
    renameSync(temp, path)
  } catch (error) {
    try { unlinkSync(temp) } catch { /* ignore */ }
    throw error
  }
  return true
}

/** Normalize every .xlsx path listed on a present-style payload. */
export async function normalizePresentFiles(files) {
  if (!Array.isArray(files)) return
  for (const entry of files) {
    const path = typeof entry === 'string' ? entry : entry?.path
    if (typeof path !== 'string' || !path) continue
    try {
      await normalizeXlsxForPreview(path)
    } catch (error) {
      // Keep presenting the original file; preview may still fail, external apps still open it.
      console.warn(`chemclaw-bot: could not normalize ${basename(path)} for preview: ${error.message}`)
    }
  }
}
