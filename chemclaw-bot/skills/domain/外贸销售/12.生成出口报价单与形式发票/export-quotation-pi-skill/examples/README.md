# Examples index

Every case here is **SIMULATED demo data**: party names carry `(SIMULATED DEMO)`, e-mails use
`@example-demo.invalid`, phone numbers are obviously fake, bank details are placeholders, and the
generated documents carry a diagonal `SIMULATED DEMO / NOT FOR TRADE USE` watermark.

| Case | Product | Buyer country | Rule | Currency | Doc type | Purpose |
|---|---|---|---|---|---|---|
| EX-001 | Soda ash (heavy), 1,000 MT × USD 217 | Indonesia | CIF Jakarta (Tanjung Priok) 2020 | USD | Quotation + PI | **Main worked example**: T/T in advance, 40,000 bags × 25 kg, 1,008 t gross, not DG (GHS H319 label only), bank block as placeholder |
| EX-002 | PVC suspension resin SG-5 + SG-8 | Vietnam | DAP buyer's factory (Hiep Phuoc IP) 2020 | USD | Quotation + PI | Multi-line, 16,000 × 25 kg bags, L/C at sight with full LC terms, DAP keeps import clearance with the buyer |
| EX-003 | Dioctyl phthalate (DOP), 200 × 200 L drums | South Korea | FCA Shanghai Pudong Airport 2020 | USD | Quotation + PI | Air freight, **draft path**: unit price withheld, DG status unverified ⇒ blocked, shows the `[ PRICE ]` placeholders |
| EX-004 | Urea granular 46% N, 500 × 50 kg | India | CFR Tuticorin 2020 | USD | **Proforma Invoice** | Freight included, insurance excluded and stated; GSTIN on the PI; 10% advance + 90% L/C |
| EX-005 | Citric acid monohydrate, food grade, 800 × 25 kg | Germany | CIP Duesseldorf/Duisburg 2020 (multimodal) | EUR | Quotation + PI | EUR quote, ICC (A) insurance included in the unit price, 50/50 payment |
| EX-006 | Titanium dioxide rutile, 2,000 × 25 kg | Brazil | EXW Shenzhen warehouse 2020 | USD | Quotation + PI | **Placeholder path**: no unit price, no payment terms, no validity ⇒ only a draft may be produced |

## Files per case

```
case-exNNN-*.json                          the data (single source of truth)
dist/examples/EXNNN/
  EXNNN_<no>_Quotation.docx / .pdf
  EXNNN_<no>_Proforma_Invoice.docx / .pdf
  EXNNN_<no>_Data_Workbook.xlsx            9-sheet workbook with live formulas
  EXNNN_<no>_Studio.html                   interactive editor, single file
```

## Regenerating

```bash
python scripts/make_examples.py     # rewrites examples/*.json from scripts/make_examples.py
python scripts/build_all.py         # rebuilds dist/ + dist/QA_report.md
```

## What each case demonstrates about the rules

* **EX-001** — the full happy path with a confirmed price; shows how a not-DG chemical still
  carries GHS label notes; the bank block stays a placeholder because no account was confirmed.
* **EX-002** — cost allocation for DAP (buyer clears import) and a complete L/C term set; baseline
  for warning-free commercial terms.
* **EX-003** — the engine blocks a document when (a) the price is missing and (b) the DG status is
  `UNKNOWN`; useful for training the "never invent" behaviour.
* **EX-004** — a PI (not a quotation) for L/C opening, with the CFR insurance exclusion explicit.
* **EX-005** — CIP with multimodal routing and insurance inside the price (no double charge).
* **EX-006** — the minimum viable draft: product and packing confirmed, everything commercial
  missing, so the paper shows `[ PENDING PRICE ]`, `[ PAYMENT TERMS ]`, `[ VALIDITY ]`.
