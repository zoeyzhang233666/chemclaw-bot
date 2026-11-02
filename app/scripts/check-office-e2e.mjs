// A clean-installed ChemClaw must create and inspect real Word/PPT/Excel files
// using the shipped interpreters and the shipped compiled Office CLI.
// Never invoke "node", "python", pip or npm from PATH.
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const PYTHON_CREATE = String.raw`from pathlib import Path
import sys, json
from docx import Document
from pptx import Presentation
from pptx.util import Inches
from openpyxl import Workbook, load_workbook

root = Path(sys.argv[1])
document = Document()
document.add_heading("ChemClaw 甲醇市场简报", 0)
document.add_paragraph("Sample data only, not live prices")
table = document.add_table(rows=2, cols=2)
table.cell(0, 0).text = "产品"
table.cell(0, 1).text = "价格"
table.cell(1, 0).text = "甲醇"
table.cell(1, 1).text = "2400"
document.save(root / "test.docx")

presentation = Presentation()
for label in ["封面", "市场数据", "结论"]:
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    shape = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(1))
    shape.text = label
presentation.save(root / "test.pptx")

workbook = Workbook()
sheet = workbook.active
sheet["A2"], sheet["B2"] = "甲醇", 2400
sheet["A3"], sheet["B3"] = "乙二醇", 4500
sheet["A4"], sheet["B4"] = "合计", "=SUM(B2:B3)"
workbook.save(root / "test.xlsx")
reopened = load_workbook(root / "test.xlsx")
assert reopened.active["B4"].value == "=SUM(B2:B3)"
print(json.dumps({"docx": True, "pptxSlides": len(presentation.slides), "excelFormula": reopened.active["B4"].value}))
`

function paths(resources, platform) {
  const base = join(resources, 'primary-runtime', 'dependencies')
  return {
    node: join(base, 'node', 'bin', platform === 'win32' ? 'node.exe' : 'node'),
    python: join(base, 'python', ...(platform === 'win32' ? ['python.exe'] : ['bin', 'python3'])),
    cli: join(resources, 'app.asar.unpacked', 'node_modules', 'chemclaw-bot', 'office.js'),
    converter: join(resources, 'office-converter', 'node_modules', '@deepseek-ai', 'libreoffice-kit', 'lib', 'cli.js'),
  }
}

export function checkOfficeFiles(resources, {
  platform = process.platform,
  run = spawnSync,
  makeTemp = () => mkdtempSync(join(tmpdir(), 'chemclaw-installed-office-')),
  cleanup = root => rmSync(root, { recursive: true, force: true }),
} = {}) {
  const { node, python, cli, converter } = paths(resources, platform)
  for (const file of [node, python, cli, converter]) {
    if (!existsSync(file)) throw new Error('Installed Office payload missing ' + file)
  }
  const work = makeTemp()
  try {
    const cmd = (exe, args) => {
      const response = run(exe, args, { encoding: 'utf8', windowsHide: true, timeout: 120_000,
        env: { ...process.env, PYTHONPATH: '', PYTHONHOME: '', PYTHONNOUSERSITE: '1' } })
      if (response.error || response.status !== 0) {
        throw new Error('Installed Office command failed: ' + exe + ' ' + args.slice(0, 3).join(' ') +
          '; stderr: ' + String(response.stderr || response.error?.message || response.stdout).slice(0, 1400))
      }
      return String(response.stdout || '')
    }
    const created = JSON.parse(cmd(python, ['-I', '-B', '-c', PYTHON_CREATE, work]).trim())
    assert.equal(created.pptxSlides, 3)
    assert.equal(created.excelFormula, '=SUM(B2:B3)')
    const inspect = (format, action, file) => {
      const result = JSON.parse(cmd(node, [cli, format, action, join(work, file), '--json']))
      assert.equal(result.ok, true, format + ' ' + action + ': ' + JSON.stringify(result))
      return result.data
    }
    inspect('docx', 'read', 'test.docx')
    inspect('pptx', 'inventory', 'test.pptx')
    const excel = inspect('xlsx', 'inventory', 'test.xlsx')
    assert.equal(excel.sheets?.[0]?.formulas, 1)
    // Exercise the exact standalone CLI used by Office skills and the right
    // sidebar conversion chain. A working Python and Office inventory alone
    // cannot prove libreoffice-kit's JS packages and native engine are shipped.
    cmd(node, [converter, 'convert', '--input', join(work, 'test.pptx'), '--output', join(work, 'preview.pdf')])
    const pdf = readFileSync(join(work, 'preview.pdf'))
    assert.ok(pdf.length > 1000 && pdf.subarray(0, 5).toString() === '%PDF-', 'Bundled Office converter did not render a real PDF')
    for (const file of ['test.docx', 'test.pptx', 'test.xlsx']) {
      const result = JSON.parse(cmd(node, [cli, 'check', join(work, file), '--json']))
      assert.equal(result.ok, true, 'OOXML check ' + file + ': ' + JSON.stringify(result))
      assert.deepEqual(result.data.findings, [], 'OOXML findings in ' + file)
    }
    console.log('office-e2e: bundled Node/Python/Office CLI created and validated DOCX/PPTX/XLSX; standalone LibreOffice Kit converted a PPTX into a real PDF')
    return { ok: true, paths: { node, python, cli }, files: 3 }
  } finally { cleanup(work) }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const resources = process.argv[2]
  if (!resources) throw new Error('Usage: node scripts/check-office-e2e.mjs <installed resources directory>')
  checkOfficeFiles(resolve(resources))
}
