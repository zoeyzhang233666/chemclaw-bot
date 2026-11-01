---
name: office
description: Create, edit, inspect, or convert Office documents, spreadsheets, presentations, and PDFs. Load to choose the relevant workflow.
---

# Office task routing for ChemClaw

Use ChemClaw's existing `ppt-master`, `chem_deliver`, docx, ExcelJS and other installed skills when creating new Office files. For editing and inspecting existing Office files, use `office-tools` and a format-specific skill when available. Only call a `skill` tool if it actually exists in the current tool catalog.

- Create, read, or edit: the available `office-docx` (Word), `office-pptx` (PowerPoint), or `office-xlsx` (Excel) skill, or ChemClaw's existing `docx` / `ppt-master` / `ExcelJS` tooling. Do not claim an unavailable skill exists.
- Inspect package structure, check package health, or edit content in place — `office-tools`, used together with the format skill: block-level docx reading, comments, tracked changes accept/reject, pptx inventory, layout checks, slide reorder/duplicate/cleanup, xlsx inventory, package checks, contact sheets.
- Images, visual inspection, or tasks primarily about layout, spacing, sizing, or alignment: `office-render`, even without an explicit visual-check request.
- Refresh spreadsheet formula results: `office-recalculate`.
- Export an Office file to PDF: `office-export-pdf`.

Honor requests to skip rendering. New files, content edits, formulas, and incidental formatting such as bold headers or number formats need no render unless visual inspection is requested. Do not reload skills.

Skills not present in the catalog are unavailable in this environment.
