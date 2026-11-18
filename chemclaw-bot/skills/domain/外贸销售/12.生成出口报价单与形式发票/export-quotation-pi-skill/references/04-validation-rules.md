# Completeness & consistency checks (groups A–K)

`templates/engine.js` runs these groups on every edit. Errors block formal issue; warnings require
explicit confirmation; each item carries a field pointer so the HTML editor can highlight it.

| Group | Name | What it covers |
|---|---|---|
| A | Header & parties | document number, issue date, seller name/address, buyer name/address, destination country |
| B | Trade term | Incoterms code, 2020 version, named place, mode pairing (sea rules ↔ sea transport) |
| C | Goods | product English name, CAS format `\d{2,7}-\d{2}-\d`, HS code 6/8/10 digits, specification text, origin |
| D | Quantity & price | quantity > 0, unit, unit price present, price-confirmation gate, discount range |
| E | Packing & weight | packing summary, bag/package net weight, package count vs quantity, Σ packages, gross weight |
| F | Delivery | lead time text, basis (from PO / from advance / fixed date), partial shipment, transhipment |
| G | Payment | payment code, terms text, LC sub-fields (type / opening deadline / bank), advance % |
| H | Validity | validity date or days present, not in the past, matches the negotiation stage |
| I | Documents | commercial invoice, packing list, B/L or AWB, COA, SDS, invoice copies for L/C |
| J | Dangerous goods | status verified (DG / NOT_REGULATED / UNKNOWN), UN number, PSN, class, PG, packaging, SDS rev. |
| K | Banking boundary | bank details display/sanitized/confirmed flags, beneficiary wording |

## Severity rules

| Code | Severity | Meaning |
|---|---|---|
| `ITEM_PRICE` / `LINE_PRICE_MISSING` | error | unit price absent — no formal document |
| `AMOUNT_MISMATCH` | error | confirmed amount ≠ computed — price must be re-confirmed |
| `PACKAGE_SUM_MISMATCH` | error | document package total ≠ Σ line package counts |
| `BAG_COUNT_CHECK` / `BAG_TOTAL_CHECK` | error | quantity ÷ bag net ≠ package count |
| `DG_UNKNOWN` | error | DG status not verified |
| `DG_UN`, `DG_PSN`, `DG_CLASS` | error | DG confirmed but transport data missing |
| `VALIDITY_DATE` | error | no validity at all |
| `PAYMENT_TERMS` | error | no payment terms |
| `WEIGHT_SUM_MISMATCH` | warning | stated gross weight ≠ packages × unit weight |
| `INSURANCE_BASIS` | warning | CIF/CIP without cover + sum insured |
| `FREIGHT_AMOUNT` | warning | seller-borne freight without an amount |
| `COST_ALLOC_<cost>` | warning | allocation deviates from the Incoterms rule |
| `LC_TYPE` / `LC_OPENING_DATE` / `LC_BANK` | warning | LC sub-terms incomplete |
| `DG_BASIS`, `DG_PG`, `DG_PACKAGE`, `DG_MSDS` | warning | DG caveats |
| `SALES_TERM_*`, `DELIVERY_*` | warning | soft commercial gaps |

## Deviation policy

* A warning is **not** generic consent. When the user accepts one, record it in
  `review.acknowledged` with the reviewer's name and the free-text reason, and keep that record
  with the case JSON.
* Errors are never auto-accepted. Fix the data or leave the document in DRAFT.

## Weight / bag parsing

`totalGrossWeight` may be free text: `"1,008,000 kg (1,008.00 MT)"`, `"1008 MT"`, `"1,008 t"`.
The engine's `parseWeight()` reads the **first unit token** and the **first number**, so
`1000 MT` = 1,000,000 kg and `25,200 kg (25.20 MT)` = 25,200 kg. Never type `1008` alone.

## English text checks

* The item description must be the English trade name (INCI/chemical name + grade), e.g.
  `SODA ASH (HEAVY), Sodium Carbonate`, not a Chinese name and not a brand alone.
* Specification must be quantitative (`Na2CO3 99.2% min.`), not marketing (`high quality`).
* Units: `MT`, `KG`, `L`, `DRUM`, `BAG`, `IBC`, `FCL`; write `MT` not `ton` when the price basis
  is a metric tonne.
* Numbers use comma thousands and a dot decimal (`1,008,000.00`), never a space.
