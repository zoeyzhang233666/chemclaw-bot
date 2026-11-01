// ChemClaw-specific Office CLI regression: Chinese paths, untouched inputs and real runtime invocation.
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { copyFileSync, mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test } from 'node:test'

const ROOT = fileURLToPath(new URL('../', import.meta.url))
const cli = (...args) => {
  try { return JSON.parse(execFileSync(process.execPath, [join(ROOT, 'office.js'), ...args, '--json'], { encoding: 'utf8' })) }
  catch (error) { if (error.stdout) return JSON.parse(error.stdout); throw error }
}
const input = name => join(ROOT, 'test', 'fixtures', 'office', name)
const directory = () => mkdtempSync(join(tmpdir(), 'chemclaw-中文-'))

test('DOCX: Chinese file and text; editing writes a distinct output without touching original', () => {
  const dir = directory()
  const src = join(dir, '化工报告.docx')
  const output = join(dir, '修改后-化工报告.docx')
  copyFileSync(input('sample.docx'), src)
  const before = readFileSync(src)
  const original = cli('docx', 'read', src)
  assert.ok(original.ok && original.data.blocks.some(block => block.type === 'table'))
  const edit = cli('docx', 'edit', src, '-o', output, '--ops', JSON.stringify([
    { replace: { find: 'north region', with: '上海化工园区' } },
    { set_cell: { table: 1, row: 2, col: 2, text: '中文单元格' } },
  ]))
  assert.equal(edit.ok, true, JSON.stringify(edit))
  assert.deepEqual(readFileSync(src), before)
  const data = cli('docx', 'read', output).data
  assert.ok(data.blocks.some(block => block.text?.includes('上海化工园区')))
  assert.ok(data.blocks.find(block => block.type === 'table').rows.some(row => row.some(cell => cell.text === '中文单元格')))
  assert.deepEqual(cli('check', output, '--against', src).data.findings, [])
})

test('PPTX: inventory, slide reordering/duplication and source preservation with Chinese paths', () => {
  const dir = directory()
  const src = join(dir, '原始演示文稿.pptx')
  const output = join(dir, '新版演示文稿.pptx')
  copyFileSync(input('sample.pptx'), src)
  const before = readFileSync(src)
  const inventory = cli('pptx', 'inventory', src)
  assert.equal(inventory.ok, true)
  assert.ok(inventory.data.slides.length >= 2)
  const edited = cli('pptx', 'slides', src, '-o', output, '--order', '2,1,1')
  assert.equal(edited.ok, true, JSON.stringify(edited))
  assert.deepEqual(readFileSync(src), before)
  assert.equal(cli('pptx', 'inventory', output).data.slides.length, 3)
  assert.deepEqual(cli('check', output, '--against', src).data.findings, [])
})

test('XLSX: reads formulas and named sheets without changing workbook on Chinese paths', () => {
  const dir = directory()
  const src = join(dir, '行业测算-工作簿.xlsx')
  copyFileSync(input('sample.xlsx'), src)
  const before = readFileSync(src)
  const inv = cli('xlsx', 'inventory', src)
  assert.equal(inv.ok, true)
  assert.ok(inv.data.sheets.length > 0)
  assert.ok(inv.data.sheets.some(sheet => sheet.formulas > 0))
  const first = inv.data.sheets[0].name
  assert.equal(cli('xlsx', 'read', src, '--sheet', first).ok, true)
  assert.deepEqual(readFileSync(src), before)
})
