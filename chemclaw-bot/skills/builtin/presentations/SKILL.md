---
name: chemclaw-presentations
description: Create an editable PowerPoint presentation from the user's material, with a clear argument, readable Chinese typography, and traceable data.
license: Apache-2.0
---

Use this workflow when the user needs an editable slide deck, a customer briefing,
or a business presentation. For an interactive browser presentation use the web
slides skill instead.

1. Establish the audience, decision, available source material, and requested
   format from the task. Ask only for information necessary to proceed.
2. Write a short outline with one clear point per slide. Choose chart, table,
   comparison, process, or text layouts according to the information. Do not
   force every slide into the same grid. Use original artwork and licensed assets.
3. Keep text short and Chinese labels readable. Retain units, dates, source
   links, and uncertainty. Never invent business figures to fill a layout.
4. Use ChemClaw's `chem_deliver` tool for a structured presentation. Its `report`
   argument is JSON: `{title,summary,asOf,filename,sections:[{title,text,table:{columns,rows}}],sources:[{label,url,date}],limitations}`.
   Tables are optional; request `formats: "pptx"`, or `"pptx,xlsx"` when the
   presentation has a data backing sheet. This runs bundled libraries without
   installing a separate presentation server or system Node runtime.
5. When the user requires custom layouts, use the packaged PptxGenJS dependency
   through the plugin's runtime. Use editable text and shapes, provide meaningful
   alt text for images, and verify that links, Chinese fonts, and aspect ratio
   match the user's request. Missing converters must be reported truthfully.
6. Inspect the rendered deck if a renderer is available. Otherwise check the
   actual slide contents and text extents, identify the visual-check limitation,
   and avoid claiming a render succeeded. Repair overflow and illegible labels.
7. Verify the final PPTX exists, present it through the documented `present`
   tool, and include a clickable Markdown link in the answer. Keep source
   material and any workbook available with the deck when relevant.
