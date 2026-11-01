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
- In groups, display-only result cards, metrics and charts are shown with the
  completed group reply even if `audience` is omitted; explicitly setting
  `audience: "user"` is optional. Never reject an otherwise valid finished view
  solely for missing `audience`. Use `audience: "team"` only for internal Bot
  delegation/progress that must not produce a public group card. Do not render
  group cards before successful answer completion, and keep group submit controls disabled.
- Deliver the useful conclusion and an inline view before lengthy file exports.
  A simple lookup can finish in chat; create a full report/workbook only when
  requested or required by the actual task. For requested reports keep the
  backing data and evidence, but do not block the first useful inline result.
- Never invent a value to complete a picture. Use null for missing chart points,
  with sources, date/spec/region/tax basis and units. Do not connect across gaps.
  Axis tick thinning is automatic; keep complete observation labels and values.

**Original webpages: no templates, including as fallback.**
- When a standalone webpage is appropriate or requested, author original HTML/CSS/JavaScript for the actual analysis and audience. Choose layouts, visual hierarchy, cards, diagrams, tables, art, chart types and interactions freely. Never require a fixed number of cards, graphs, sections or colors.
- HTML snippets, screenshots and layouts in Skills are **references only**, not a compulsory design. Add only supported visuals that help explain verified facts; do not fabricate numbers, events or images just for polish.
- `chem_deliver` is intentionally **not** an HTML generator. It supports XLSX, PPTX, DOCX and text/table PDF only. To deliver a webpage, write full original HTML using `chem_write_webpage` (which saves it byte-for-byte, without a layout template) or use standard file-writing tools. Call `present` after inspection.
- A webpage may use self-contained CSS, inline SVG, JavaScript, Canvas, licensed libraries and local media. Plan for offline use: include required assets locally or inside the document rather than relying on a public CDN. Do not modify host sandbox security settings.
- If original HTML cannot be produced or validated, explain the limitation honestly; **never silently switch to a standard-looking page, generic template, or automatic HTML fallback.**
- Keep browser QA bounded, particularly in group chats. Prefer the already available preview/browser route; make at most one permitted preview attempt and one targeted repair after a *real* visual failure. If validation is blocked by sandbox, file URL restrictions, localhost, network or denied approval, do not keep switching among Playwright, Chrome, local HTTP servers, data URLs and shell commands. Do not seek extra privileged execution solely to satisfy optional QA; leave security intact. Deliver the real output file with a clear 'browser rendering not verified' note and source/data checks, rather than blocking the final answer. If the file was never created or its content is known invalid, report failure instead of presenting it as complete.
- Use PPT/PPTX for ordinary presentations, and Excel alongside file reports when row-level backing data exists. Respect the format the user specifically requests.

1. Determine business scope, dates, specification, region, units, tax basis, data sources and target audience.
2. Separate verified observations from calculations, hypotheses and missing data. Never invent points to complete a chart.
3. Design each webpage from its content, author its HTML, CSS and JS directly, then save with `chem_write_webpage`. For other exports, use `chem_deliver` with suitable `formats: "xlsx,pptx,docx,pdf"` and structured JSON. The bundled `runtime/deliver.mjs` does not generate HTML.
4. Render and inspect the actual page before presenting: verify main data marks rather than axes only, charts, labels, narrow widths, controls, print output, offline assets and legal notices. Fix issues if possible, and never report a visual test as passed when the browser could not run.
5. Verify real file paths and deliver via `present` with clickable file links. If no actual webpage exists, do not claim a webpage was delivered.

For existing document conversions use a suitable renderer. Never claim success
when a converter is unavailable.
