# AGENTS.md · inquiry-to-quotation

If you are an agent operating in this folder, read `SKILL.md` first. It is the contract.

Hard rules:

1. **Never invent, suggest, estimate, or backfill a commercial price.** No default price, no reference
   price, no range, no “market price”, no last-deal price. `price.unit_price` stays `null` until the
   salesperson explicitly provides a price and an acknowledgement.
2. **Never guess a missing field.** If the inquiry does not contain it, mark `status: "missing"` or
   `"tbc"` with a `source`/`note`. Do not use industry practice, similar customers, or “usually” to fill it.
3. **Two buckets are not interchangeable.** A-class (must fill before quoting) blocks generation.
   B-class (can proceed on assumption) must be rendered with “（我方假设 · 待客户确认）”.
4. **Stop at the gate.** After extracting fields, show them for confirmation. Do not generate a
   priced quote until A-class is complete, tax/freight basis is chosen by the user, a positive unit
   price is entered, and the confirmation is checked (`--ack` in scripts).
5. **Demo prices are not recommendations.** `examples/example-1-soda-ash-glass/fields_demo.json`
   contains 1,180 CNY/t only to demonstrate layout. Never reuse it as a default.

Useful commands:

```bash
python scripts/extract.py input.txt -o fields.json --as-of 2026-10-19 --inquiry-no INQ-20261019-01
python scripts/build_workbench.py fields.json -o 询盘工作台.html --demo-text-file input.txt
python scripts/build_xlsx.py fields.json -o 报价工作簿.xlsx
python scripts/selfcheck.py fields.json --html 询盘工作台.html --xlsx 报价工作簿.xlsx
```

Deliverables: interactive HTML, Excel workbook, Markdown quote draft, fields JSON. Keep files local;
the HTML is client-side only.
