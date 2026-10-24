---
name: chemclaw-delivery
description: Produce traceable chemical-business HTML, charts, spreadsheets, presentations and documents.
license: Apache-2.0
---

Read the task's domain skill for required business fields and evidence.
Choose the best presentation for the audience; examples are not pixel templates
or limits on analytical ability.

**Format choice (ChemClaw product rule):**
- Prefer self-contained **HTML** when the deliverable needs price trend lines,
  interactive tables, filters, or in-page charts.
- Use **PPT / PPTX** (including `ppt-master` or `chem_deliver` pptx) when the
  user wants a slide deck without interactive trends—price cards and static
  layouts are fine.
- Whenever there is a data backing sheet or row-level detail, also deliver
  **Excel**. Do not ship charts alone without the workbook when numbers exist.

1. Resolve scope, specification, units, date, tax and delivery terms.
2. Separate source records, calculations and judgments. Mark missing values;
   never populate charts with invented facts or example data.
3. Prefer the `chem_deliver` tool for ordinary reports: supply report JSON and
   comma-separated formats. It runs bundled libraries inside the Host without
   requiring a system Node or Python installation. Then inspect and call present.
   Use the bundled `runtime/deliver.mjs` for self-contained HTML, XLSX, PPTX,
   DOCX and text/table PDF from structured JSON. Invoke `node <plugin>/runtime/deliver.mjs input.json output-folder html,xlsx,pptx,docx,pdf`.
   For a PDF with charts, print the HTML with the browser; the bundled PDF adapter
   embeds Chinese fonts and tables and points to the interactive HTML for charts.
   The input is `{title, summary, asOf, filename, sections:[{title,text,table:{columns:[],rows:[]},chart:{engine:'echarts',option:{}}}],sources:[{label,url,date}],limitations}`.
   `chart` and `table` are optional. Financial charts use `engine:'lightweight',data:[{time:'YYYY-MM-DD',value:123}]`.
   Maps supply a licensed `geoJSON` and `mapName` within the chart specification.
   Use ECharts for comparisons, distributions, networks and maps; Lightweight
   Charts for time series. Preserve their notices.
4. Custom HTML must embed licensed libraries and data, use responsive grids,
   explicit chart heights, ResizeObserver, wrapped labels, accessible tables,
   readable Chinese fonts and print styles. Without reliable coordinates,
   show region counts instead of invented map pins.
5. Inspect rendering for clipped text, blank maps and unreadable legends.
   Verify workbook formulas and PPT overflow. Improve on example designs.
6. Verify every file exists, call `present` with paths and descriptions, and
   include clickable Markdown links. Resolve resources from the installed
   skill, never a developer drive.

For existing document conversions use a suitable renderer. Never claim success
when a converter is unavailable.
