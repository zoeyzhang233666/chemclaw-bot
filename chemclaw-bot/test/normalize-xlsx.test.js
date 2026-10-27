import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, readFile, copyFile, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { needsXlsxPreviewNormalize, normalizeXlsxForPreview } from '../runtime/normalize-xlsx.mjs'

const require = createRequire(join(fileURLToPath(new URL('..', import.meta.url)), 'package.json'))
const JSZip = require('jszip')
const root = fileURLToPath(new URL('../..', import.meta.url))
const openpyxlSample = join(root, '.chemclaw-tools', 'office48-synthetic.xlsx')

async function packageFlags(path) {
  const zip = await JSZip.loadAsync(await readFile(path))
  const rels = await zip.file('xl/_rels/workbook.xml.rels').async('string')
  const styles = await zip.file('xl/styles.xml').async('string')
  return {
    absoluteSheetTarget: /Target="\/xl\//.test(rels),
    emptyPatternFill: /<patternFill\/>/.test(styles),
  }
}

test('openpyxl workbooks are marked for preview normalize', async () => {
  assert.equal(await needsXlsxPreviewNormalize(openpyxlSample), true)
  const before = await packageFlags(openpyxlSample)
  assert.equal(before.absoluteSheetTarget, true)
  assert.equal(before.emptyPatternFill, true)
})

test('normalize rewrites absolute sheet targets and empty pattern fills in place', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'chemclaw-xlsx-'))
  const path = join(dir, 'sample.xlsx')
  await copyFile(openpyxlSample, path)
  assert.equal(await normalizeXlsxForPreview(path), true)
  assert.equal(await needsXlsxPreviewNormalize(path), false)
  const after = await packageFlags(path)
  assert.equal(after.absoluteSheetTarget, false)
  assert.equal(after.emptyPatternFill, false)
})

test('already compatible workbooks are left alone', async () => {
  const ExcelJS = require('exceljs')
  const dir = await mkdtemp(join(tmpdir(), 'chemclaw-xlsx-'))
  const path = join(dir, 'exceljs.xlsx')
  const book = new ExcelJS.Workbook()
  book.addWorksheet('Sheet1').addRows([['a', 'b'], [1, 2]])
  await writeFile(path, Buffer.from(await book.xlsx.writeBuffer()))
  assert.equal(await needsXlsxPreviewNormalize(path), false)
  assert.equal(await normalizeXlsxForPreview(path), false)
})
