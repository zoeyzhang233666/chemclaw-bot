# 生成出口报价单与形式发票 (Export Quotation & Proforma Invoice)

Generate an **English Quotation** or **Proforma Invoice (PI)** for a chemical export deal from
commercial information the user has confirmed, then check it, typeset it and hand it back for
review.

> 用中文对话，文档一律输出英文。绝不编造商务条件。

## When to use

Trigger on requests such as: 出一份英文报价单 / 做形式发票 / PI / quotation / proforma invoice /
给印尼客户报价 / 报价单模板 / 出口报价 / 外贸报价单 / 把价格和条款做成正式文件 / 报价单和 PI.

## Non-negotiable rules (read before anything else)

1. **Never invent or amend commercial content.** Unit price, payment terms, delivery date,
   validity, discounts, bank details and any clause come from the user, verbatim.
2. **No price ⇒ no formal document.** Without a user-confirmed unit price you may only produce a
   draft with `[ PENDING PRICE ]` placeholders, clearly marked as not valid.
3. **Bank details are never generated.** Unless the user typed and explicitly confirmed the exact
   account, the document shows
   `[ BANK DETAILS TO BE CONFIRMED BY THE SELLER - A/C No. / SWIFT INTENTIONALLY NOT GENERATED ]`.
   See `references/06-banking-boundary.md`.
4. **Dangerous-goods facts need a verified source** (current SDS / official transport table).
   If unverified, the line is blocked with `DG status: TO BE VERIFIED`.
5. **Formal issue requires human sign-off** — reviewer name + title + every line checked in the
   review dialog. Before that the document is DRAFT with a watermark.
6. **Demo data must look like demo data**: `(SIMULATED DEMO)` in party names, `@example-demo.invalid`
   e-mails, placeholder phone numbers, a diagonal `SIMULATED DEMO / NOT FOR TRADE USE` watermark.

## Ask for these fields first (a missing one becomes a placeholder, never a guess)

| Group | Fields |
|---|---|
| Seller | legal English name, address, contact, tax ID / USCI, logo text |
| Buyer | legal English name, address, contact, tax ID (NPWP / GSTIN / VAT / CNPJ) |
| Goods | English product name, CAS No., specification (quantitative), HS code, origin |
| Quantity | quantity + unit (MT / KG / DRUM / BAG / IBC), package count, net & gross per package |
| Price | **unit price (mandatory)**, currency, discount, price-confirmation state |
| Trade term | Incoterms® rule (EXW/FCA/FAS/FOB/CFR/CIF/CPT/CIP/DAP/DPU/DDP) + version + named place |
| Packing | packing description, shipping units (FCL type / air / LCL) |
| Delivery | lead time + its basis (from PO / from advance / fixed date), partial shipment, transhipment |
| Payment | terms code + text (T/T %, L/C sight/usance + opening window), beneficiary wording |
| Validity | valid until date, or valid for N days |
| Documents | invoice, packing list, B/L or AWB, CO, COA, SDS, copies for L/C |
| Bank | display or not; details only if confirmed by the seller |
| DG | status (DG / NOT_REGULATED / UNKNOWN) + UN, PSN, class, PG, packaging, SDS revision |

## Workflow

```
1. Collect  → structured prompt / JSON (schemas/quote.schema.json)
2. Validate → templates/engine.js  (field matrix A–K, amounts, Incoterms cost matrix)
3. Fill UI   → HTML editor (interactive preview, live total, problem list)
4. Review    → reviewer ticks every line, enters name + title
5. Issue     → FORMAL: watermark off, "Original", export DOCX / PDF / JSON / XLSX
```

### 1. Start from a case file

Use `examples/case-ex001-soda-ash-indonesia.json` as the template. Every value is a confirmed
input; the `meta.dataClass` field declares whether it is demo or real.

```bash
python scripts/engine_check.py examples/case-ex001-soda-ash-indonesia.json
```

### 2. Open the interactive editor

Open `dist/deliverables/EX-001_QT-SIM-2610-001_Studio.html` in a browser (single file, no server).
Tabs: 单据 | 双方 | 商品 | 条款 | 银行 | 检查 | 模板.

* English A4 preview on the right, updates as you type.
* Double-click any value on the paper to edit it in place.
* Quantity × price is recomputed live; the price must be re-confirmed after any change.
* 检查 tab lists every error (blocking) and warning (needs an explicit decision), each with its
  field highlighted.
* 模板 tab saves the company template (letterhead, colours, signature) in `localStorage` and
  exports/imports it as JSON.
* Export: print/PDF (browser), HTML, case JSON, CSV.

### 3. Generate Word / PDF / Excel

```bash
python scripts/build_docx.py --case case.json --out QT.docx --doc-type QUOTATION --pdf
python scripts/build_docx.py --case case.json --out PI.docx --doc-type PROFORMA_INVOICE --pdf
python scripts/build_xlsx.py --case case.json --out case_workbook.xlsx
python scripts/build_studio_html.py --data case.json --out studio.html
python scripts/build_all.py            # everything, plus dist/QA_report.md
```

Both Word and PDF are one A4 page per document; the PDF is produced through the bundled
LibreOffice (`QUOTE_LO_CLI` to override), and the builders sanitise glyphs that LibreOffice
cannot render (`— – ≥ ≤ µ`).

### 4. Hand over

Tell the user which files are which, the document state, the errors/warnings left, and what still
needs their confirmation. Never say "ready to send" while the state is DRAFT.

## Deliverable map

```
SKILL.md
references/      01 field schema · 02 Incoterms matrix · 03 amount rules · 04 validation rules
                 05 dangerous goods · 06 banking boundary · 07 quotation vs PI · 08 typesetting
                 09 QA checklist
schemas/         quote.schema.json (data contract), company-template.schema.json
templates/       engine.js (validation + calc), studio.template.html + studio.app.js (editor UI)
scripts/         engine_check.py · engine_bridge.py · build_docx.py · build_xlsx.py
                 build_studio_html.py · make_examples.py · build_all.py · browser_probe.py
examples/        case-ex001 … case-ex006 (CIF/DAP/FCA/CFR/CIP/EXW), demo data only
dist/
  deliverables/  EX-001 Soda Ash → Indonesia: Studio.html, Quotation DOCX+PDF,
                 Proforma Invoice DOCX+PDF, Data Workbook XLSX
  examples/      EX-002 … EX-006: same five artefacts per case
  QA_report.md   engine state, totals, independent arithmetic re-check
```

## Reference numbers from the worked example (EX-001, simulated)

| | |
|---|---|
| Product | SODA ASH (HEAVY), Sodium Carbonate, CAS 497-19-8, HS 283620 |
| Quantity / price | 1,000 MT × USD 217.00/MT |
| Total | USD 217,000.00 — *US Dollars Two Hundred Seventeen Thousand and Zero Cents Only* |
| Trade term | CIF Jakarta (Tanjung Priok), Indonesia, Incoterms® 2020 |
| Packing | 40,000 bags × 25 kg net; 1,008,000 kg gross (1,008.00 MT) |
| Payment | 100% T/T in advance prior to shipment |
| DG | Not regulated for transport; GHS warning H319 (label only) |

## Hard stops

* unit price missing → DRAFT with placeholders only
* `DG status: UNKNOWN` → no shipping document
* price changed after confirmation → `AMOUNT_MISMATCH`, total becomes `PENDING PRICE`
* bank details unconfirmed → placeholder block, always
* simulated data → watermark + `(SIMULATED DEMO)`, never presented as a real offer
