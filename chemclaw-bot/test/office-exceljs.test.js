// Verify that ChemClaw's pre-existing ExcelJS can edit a multi-sheet workbook
// without dropping formulas, fonts or the original file. Formula recalculation
// is NOT provided by ExcelJS, and must not be represented as verified.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import ExcelJS from 'exceljs'

test('Office Tools inventory reads an existing workbook after ExcelJS edits without formula/style loss', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'chemclaw-excel-'))
  const source = join(dir, '化工测算.xlsx')
  const output = join(dir, '修改后-化工测算.xlsx')
  const original = new ExcelJS.Workbook()
  const main = original.addWorksheet('化工利润')
  original.addWorksheet('报价明细').getCell('A1').value = '乙烯'
  main.getCell('A1').value = 12
  main.getCell('B1').value = { formula: 'A1*2', result: 24 }
  main.getCell('B1').font = { name: '微软雅黑', size: 12, bold: true }
  await original.xlsx.writeFile(source)
  const before = readFileSync(source)

  const edited = new ExcelJS.Workbook()
  await edited.xlsx.readFile(source)
  edited.getWorksheet('化工利润').getCell('A1').value = 14
  await edited.xlsx.writeFile(output)
  assert.deepEqual(readFileSync(source), before)

  const verify = new ExcelJS.Workbook()
  await verify.xlsx.readFile(output)
  assert.equal(verify.worksheets.length, 2)
  const cell = verify.getWorksheet('化工利润').getCell('B1')
  assert.equal(cell.value.formula, 'A1*2')
  assert.equal(cell.font.name, '微软雅黑')
  assert.equal(cell.font.bold, true)
  const cli = fileURLToPath(new URL('../office.js', import.meta.url))
  const inventory = JSON.parse(execFileSync(process.execPath, [cli, 'xlsx', 'inventory', output, '--json'], { encoding: 'utf8' }))
  assert.equal(inventory.ok, true)
  assert.ok(inventory.data.sheets.some(sheet => sheet.name === '化工利润' && sheet.formulas > 0))
})
