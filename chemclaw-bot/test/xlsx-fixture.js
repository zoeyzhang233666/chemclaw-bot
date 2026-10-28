import ExcelJS from 'exceljs'
import { strFromU8, strToU8, unzipSync, zipSync } from 'fflate'

// Synthetic opaque Office parts catch lossy workbook reserialization.
export async function previewWorkbook() {
  const book = new ExcelJS.Workbook()
  const sheet = book.addWorksheet('Data')
  sheet.addRow([2, 3, { formula: 'A1+B1', result: 5 }])
  const parts = unzipSync(new Uint8Array(await book.xlsx.writeBuffer()))
  const rels = 'xl/_rels/workbook.xml.rels'
  parts[rels] = strToU8(strFromU8(parts[rels]).replace('Target="worksheets/sheet1.xml"', 'Target="/xl/worksheets/sheet1.xml"'))
  const styles = 'xl/styles.xml'
  parts[styles] = strToU8(strFromU8(parts[styles]).replace('<patternFill patternType="none"/>', '<patternFill/>'))
  parts['xl/charts/chart1.xml'] = strToU8('<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"/>')
  parts['xl/drawings/drawing1.xml'] = strToU8('<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"/>')
  parts['xl/vbaProject.bin'] = strToU8('synthetic opaque VBA payload; never executed')
  return Buffer.from(zipSync(parts))
}
