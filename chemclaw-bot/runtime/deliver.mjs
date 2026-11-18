import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import ExcelJS from 'exceljs'
import pptxgen from 'pptxgenjs'
import { Document, Packer, Paragraph, HeadingLevel, Table, TableRow, TableCell } from 'docx'
import { PDFDocument, rgb } from 'pdf-lib'
import fontkit from '@pdf-lib/fontkit'

const tableData = table => [table.columns, ...table.rows].map(row => row.map(value => String(value ?? '')))

export async function deliver(report, output, formats = ['xlsx']) {
  mkdirSync(output, { recursive: true })
  const base = String(report.filename ?? 'ChemClaw-report').replace(/[<>:"/\\|?*\x00-\x1f]/g, '-').slice(0, 100)
  const files = []
  const save = (extension, value) => { const path = join(output, `${base}.${extension}`); writeFileSync(path, value); files.push(path) }
  for (const format of formats) {
    if (format === 'xlsx') {
      const book = new ExcelJS.Workbook(); book.creator = 'ChemClaw'
      for (const [i, section] of (report.sections ?? []).entries()) {
        const sheet = book.addWorksheet(`${i + 1}-${section.title ?? 'Analysis'}`.replace(/[\\/*?:\[\]]/g, '-').slice(0, 31))
        sheet.views = [{ state: 'frozen', ySplit: 1 }]
        const data = section.table ? [section.table.columns, ...section.table.rows] : [['内容'], [section.text ?? '']]
        sheet.addRows(data); sheet.getRow(1).font = { bold: true, color: { argb: 'FF126CAC' } }
        sheet.columns.forEach(column => { column.width = 28; column.alignment = { vertical: 'top', wrapText: true } })
        if (section.table) sheet.autoFilter = { from: { row: 1, column: 1 }, to: { row: data.length, column: data[0].length } }
      }
      const sources = book.addWorksheet('数据来源'); sources.addRows([['来源', 'URL', '日期'], ...(report.sources ?? []).map(source => [source.label ?? source, source.url ?? '', source.date ?? ''])]); sources.columns.forEach(column => { column.width = 48 })
      save('xlsx', Buffer.from(await book.xlsx.writeBuffer()))
    } else if (format === 'pptx') {
      const deck = new pptxgen(); deck.layout = 'LAYOUT_WIDE'; deck.author = 'ChemClaw'; deck.title = report.title; deck.lang = 'zh-CN'
      let number = 0
      const page = title => {
        const slide = deck.addSlide(); slide.background = { color: 'F5F4EF' }
        slide.addText(title, { x: 0.6, y: 0.45, w: 12.1, h: 0.9, fontSize: 26, bold: true, color: '126CAC', fontFace: 'Microsoft YaHei', fit: 'shrink' })
        slide.addText(`ChemClaw · ${++number} · ${report.asOf ?? ''}`, { x: 0.6, y: 7.05, w: 12, h: 0.2, fontSize: 10, color: '647789' })
        return slide
      }
      for (const section of [{ title: report.title, text: report.summary }, ...(report.sections ?? [])]) {
        if (section.text || (!section.table && !section.chart)) page(section.title).addText(section.text ?? '', { x: 0.6, y: 1.65, w: 12, h: 4.9, fontSize: 18, color: '183049', fontFace: 'Microsoft YaHei', valign: 'top', fit: 'shrink' })
        if (section.table) {
          const [header, ...rows] = tableData(section.table)
          for (let start = 0; start < Math.max(rows.length, 1); start += 7) page(section.title).addTable([header, ...rows.slice(start, start + 7)], { x: 0.6, y: 1.6, w: 12, fontSize: 12, fontFace: 'Microsoft YaHei', border: { color: 'D9E1E5', pt: 1 }, autoPage: false, margin: 6, rowH: 0.48 })
        }
        if (section.chart) {
          const spec = section.chart
          const series = spec.engine === 'lightweight' ? [{ name: section.title, labels: (spec.data ?? []).map(row => row.time), values: (spec.data ?? []).map(row => row.value) }] : (spec.option?.series ?? []).filter(item => ['line', 'bar'].includes(item.type)).map(item => ({ name: item.name ?? section.title, labels: spec.option.xAxis?.data ?? [], values: item.data }))
          const slide = page(section.title)
          if (series.length) slide.addChart(deck.ChartType.line, series, { x: 0.6, y: 1.6, w: 12, h: 4.9, showLegend: true, showTitle: false, catAxisLabelFontFace: 'Microsoft YaHei', valAxisLabelFontFace: 'Microsoft YaHei', showValue: false })
          else slide.addText('交互图表与地图请查看另行交付的原创网页（如有）；此处可补充业务结论。', { x: 0.6, y: 1.6, w: 12, h: 4, fontSize: 20 })
        }
      }
      page('数据来源与限制').addText([...(report.sources ?? []).map(item => `${item.label ?? item} ${item.url ?? ''} ${item.date ?? ''}`), report.limitations ?? ''].join('\n'), { x: 0.6, y: 1.6, w: 12, h: 5, fontSize: 14, fit: 'shrink' })
      save('pptx', await deck.write({ outputType: 'nodebuffer' }))
    } else if (format === 'docx') {
      const children = [new Paragraph({ text: report.title, heading: HeadingLevel.TITLE }), new Paragraph(report.summary ?? '')]
      for (const section of report.sections ?? []) {
        children.push(new Paragraph({ text: section.title, heading: HeadingLevel.HEADING_1 }), new Paragraph(section.text ?? ''))
        if (section.table) children.push(new Table({ rows: tableData(section.table).map(row => new TableRow({ children: row.map(text => new TableCell({ children: [new Paragraph(text)] })) })) }))
      }
      children.push(new Paragraph({ text: '数据来源与限制', heading: HeadingLevel.HEADING_1 }), ...(report.sources ?? []).map(source => new Paragraph(`${source.label ?? source} ${source.url ?? ''} ${source.date ?? ''}`)))
      save('docx', await Packer.toBuffer(new Document({ sections: [{ children }] })))
    } else if (format === 'pdf') {
      const doc = await PDFDocument.create(); doc.registerFontkit(fontkit)
      const font = await doc.embedFont(readFileSync(new URL('./fonts/NotoSansSC-Regular.otf', import.meta.url)), { subset: false })
      let page, y
      const newPage = () => { page = doc.addPage([595, 842]); y = 790 }
      newPage()
      const paragraph = (text, size = 11) => {
        let line = ''
        const flush = () => { if (y < 50) newPage(); page.drawText(line, { x: 40, y, size, font, color: rgb(0.09, 0.19, 0.29) }); y -= size * 1.7; line = '' }
        for (const char of String(text ?? '')) { if (char === '\n') { flush(); continue } if (font.widthOfTextAtSize(line + char, size) > 510) flush(); line += char }
        if (line) flush()
        y -= 8
      }
      paragraph(report.title, 20); paragraph(report.summary)
      for (const section of report.sections ?? []) { paragraph(section.title, 15); paragraph(section.text); if (section.chart) paragraph('交互图表请查看另行交付的原创网页（如有） 报告。'); if (section.table) for (const row of tableData(section.table)) paragraph(row.join(' | '), 10) }
      paragraph('数据来源与限制', 15); for (const source of report.sources ?? []) paragraph(`${source.label ?? source} ${source.url ?? ''} ${source.date ?? ''}`, 10)
      save('pdf', Buffer.from(await doc.save()))
    } else throw new Error(`Unsupported format: ${format}`)
  }
  return files
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [input, output, formats = 'xlsx'] = process.argv.slice(2)
  if (!input || !output) throw new Error('Usage: node deliver.mjs report.json output-folder xlsx,pptx,docx,pdf')
  const files = await deliver(JSON.parse(readFileSync(input, 'utf8')), resolve(output), formats.split(','))
  console.log(JSON.stringify({ files: files.map(path => ({ path, description: 'ChemClaw research deliverable' })), next: 'Verify files, then call DSH present with these paths.' }, null, 2))
}
