---
name: chemclaw-delivery
description: Produce traceable chemical-business HTML, charts, spreadsheets, presentations and documents.
license: Apache-2.0
---

Read the task's domain skill for required business fields and evidence.
Choose the best presentation for the audience; examples are not pixel templates
or limits on analytical ability.

**Conversation delivery first (ChemClaw product rule):**
- The global visual delivery contract applies to every user-facing final
  answer, including conceptual explanations and short answers, across all
  installed or newly imported skills. Use an appropriate inline component
  with a brief conclusion; a file link or HTML report alone is insufficient.
  The following table selects components, not which answers qualify. Keep
  existing well-adapted charts/cards as the first choice, and use GenUI for
  relationships they do not cover. Never create observations just to draw.
- Business answers must include the corresponding inline view whenever one of
  these answer shapes applies; do not wait for an explicit chart request.
  Honor the user's explicit request for text only or no charts.

  | Answer shape | Required view |
  | --- | --- |
  | At least two numeric indicators answering current level, affordability or acceptability | `metric`, normally two to four cards |
  | One object with at least three time observations | `line`; `area` for cumulative quantity |
  | At least two objects compared or ranked at one time | `bar`; `hbar` for labels over six characters or more than eight categories |
  | One whole split into three to six parts, with structure/share as the question | `donut` |
  | At least three rows and three columns of multi-field results | `table` |
  | Completeness, progress or quota consumption is part of the conclusion | `progress` |
  | Risks, anomalies, conflicting measurement definitions or missing data | `callout` |
  | Repeated conversion, cost, price comparison or break-even calculation | Inputs and formulas for a local calculator |
  | Confirm parameters before executing | `options`, `confirm` or `form` in a supported chat |

- Choose one primary component from the actual relationship, automatically:
  numeric time observations → `line`/`area`; size comparison → `bar`/`hbar`;
  small composition → `donut`; two numeric variables → `scatter`; matrix →
  `heatmap`; quantified flows → `sankey`; normalized dimensions with explicit
  maxima → `radar`; conversion stages → `funnel`; hierarchy → `treemap`;
  a value against a stated maximum → `gauge`.
- The complete bundled GenUI plugin also supplies `timeline` for dated events
  and milestones, `steps` for ordered steps, `mermaid`/`diagram` for processes,
  dependencies and Gantt schedules, `plot` for functions, `scene3d` for spatial
  explanation, searchable/sortable/expandable `table`, layouts/cards, tabs,
  accordion, forms/controls, quizzes and images/media. Read the current `genui`
  skill for their exact syntax; no need for the user to know component names.
  Capability answers must include current GenUI capabilities rather than an
  older conversation's chart list. Events can use a timeline without numbers.
- Keep existing small numeric views on `show_view`. Deliver richer GenUI in a
  labelled `dsh-ui` JSON fence, inline in Bot and group replies (omit `panel:true`;
  the native panel is for native DSH conversations). Do not send the same data
  through both protocols. Keep theme defaults; avoid hardcoded colors. Local
  filters/sorts/sliders do not call the model; explicit actions/submit do.
- In groups mark `audience: "user"` only for a completed answer intended for the
  human, including an interim @ question to any member. The answer need not be
  the group's last message or come from the admin. Do not draw charts during
  peer delegation, progress or data checking; send findings as text/data there.
- Deliver the useful conclusion and an inline view before lengthy file exports.
  A simple lookup can finish in chat; create a full report/workbook only when
  requested or required by the actual task. For requested reports keep the
  backing data and evidence, but do not block the first useful inline result.
- Never invent a value to complete a picture. Use null for missing chart points,
  with sources, date/spec/region/tax basis and units. Do not connect across gaps.
  Axis tick thinning is automatic; keep complete observation labels and values.

**File format choice:**
- Prefer self-contained **HTML** when the deliverable needs price trend lines,
  interactive tables, filters, or in-page charts.
- Use **PPT / PPTX** (including `chemclaw-presentations` or `chem_deliver` pptx) when the
  user wants a slide deck without interactive trends—price cards and static
  layouts are fine.
- Whenever there is a data backing sheet or row-level detail, also deliver
  **Excel** for a requested file report. An inline factual answer does not need
  an unsolicited workbook before it can be shown.

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
   Omit optional report modules with no usable data, including their headings,
   canvases and reserved space; record the reason once in the limitations or
   data-gap list. Zero is valid data; null is missing. Check the main data marks,
   not just canvas pixels: axes, annotations and reference lines can render while
   the price series is invisible. Verify every chart tab and time window, units,
   filters, narrow layout and print output. Browser checks that cannot run must
   be reported as unverified, never as a passing render check.
6. Verify every file exists, call `present` with paths and descriptions, and
   include clickable Markdown links. Resolve resources from the installed
   skill, never a developer drive.

For existing document conversions use a suitable renderer. Never claim success
when a converter is unavailable.
