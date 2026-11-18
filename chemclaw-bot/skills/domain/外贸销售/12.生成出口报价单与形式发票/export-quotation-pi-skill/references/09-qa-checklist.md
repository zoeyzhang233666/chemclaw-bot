# QA checklist — run before anything leaves the building

## 1. Automated (run these)

```bash
python scripts/make_examples.py                 # regenerate the case set
python scripts/engine_check.py examples/case-ex001-soda-ash-indonesia.json
python scripts/build_all.py                     # all docs + workbook + HTML + QA_report.md
python scripts/browser_probe.py --html dist/deliverables/EX-001_QT-SIM-2610-001_Studio.html \
       --wait 1800 --return-none                # headless DOM smoke test
```

`scripts/build_all.py` writes `dist/QA_report.md` with, per case: document type, Incoterms rule,
engine state, error/warning counts, total and an **independent arithmetic re-check** (computed in
plain JavaScript from the same JSON, not through the engine).

## 2. Amount

- [ ] `Σ (quantity × unit price × (1 − discount))` equals the printed sub-total.
- [ ] Extra charges that are shown as included are actually in the total; excluded ones are
      labelled "for buyer's account" or "not included".
- [ ] Amount in words matches the figure exactly (`... and Zero Cents Only` for round amounts).
- [ ] The price was **explicitly confirmed** after the last change of quantity or price
      (`amountState == "confirmed"` and the value equals the computed total).

## 3. Consistency

- [ ] Quotation and PI carry the same product, quantity, price, Incoterms rule, named place and
      Incoterms year.
- [ ] Packing text agrees with quantity: `qty ÷ bag net = packages`, `Σ line packages =
      total packages`.
- [ ] Gross weight = packages × unit gross weight.
- [ ] Currency appears once per figure column, and the amount column header carries it.
- [ ] Lead time basis is stated (from PO / from advance / fixed date) — never a bare "30 days".
- [ ] Validity date is in the future and matches what sales actually agreed.

## 4. Terms

- [ ] Incoterms rule is legal for the mode: `CIF/CFR/FOB/FAS` = sea only; `CIP/CPT/DAP/DDP/FCA/EXW`
      = any mode.
- [ ] Insurance: CIF/CIP state cover + percentage; CFR/FOB state insurance is for buyer's account.
- [ ] Payment terms complete; for L/C: sight/usance, opening window, bank requirement.
- [ ] Documents list matches the payment instrument (an L/C usually requires more copies).

## 5. Dangerous goods / chemicals

- [ ] DG status verified against the current SDS; `UNKNOWN` never issued.
- [ ] If DG: UN number, PSN, class, PG, packaging code, SDS revision all present.
- [ ] GHS label phrases are in NOTES, not in the transport column.
- [ ] HS code format valid; origin stated; "Made in China" marking mentioned where relevant.

## 6. Safety & data hygiene

- [ ] **No invented bank account.** The bank block is a placeholder unless the seller confirmed
      the exact details in writing.
- [ ] **No invented payment terms, delivery dates or clauses.**
- [ ] Missing price ⇒ the total reads `[ PENDING PRICE ]` and the document is not issued.
- [ ] Simulated demo data is clearly marked: watermark + "(SIMULATED DEMO)" + footer status.
- [ ] The case JSON with real data is not published in a shared drive without the seller's consent.

## 7. Print / export

- [ ] PDF is 1 page (or page 2 contains real content, never only the signature).
- [ ] No glyph boxes (`鈥`, `Ã`, `?`), no truncated specification text.
- [ ] Table rows are not split across pages.
- [ ] The Word file opens with correct fonts on a machine without Georgia (falls back to a serif).
- [ ] The Excel workbook recalculates: open → all formulas show a value, not `#REF!`.

## 8. Human review (mandatory gate)

- [ ] Reviewer opened the document, compared it with the buyer's inquiry, and ticked every line.
- [ ] Reviewer name + title recorded in `review` (`name`, `signatoryTitle`, `itemsChecked`,
      `formalApproved`).
- [ ] Only then: switch to FORMAL, drop the watermark, export the "Original".
