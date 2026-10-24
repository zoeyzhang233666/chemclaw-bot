# Quotation vs. Proforma Invoice — what changes

Both documents are generated from the **same** case JSON. The document type only changes the
title, the numbering label, certain captions and a few extra blocks. Commercial values never
change between the two.

## 1. Purposes

| | Quotation | Proforma Invoice |
|---|---|---|
| Purpose | Offer: "this is our price, subject to validity" | Pre-invoice: "this is what we will invoice, use it for your L/C / import permit" |
| Legal nature | Invitation to treat / offer depending on wording | Not a tax invoice; a commitment document used to open a payment instrument |
| Typical next step | Buyer's PO / counter-offer | Buyer pays advance or opens L/C |
| Numbering | `QT-YYYYMM-NNN` | `PI-YYYYMM-NNN` |

## 2. Wording changes applied by the renderer

| Element | Quotation | Proforma Invoice |
|---|---|---|
| Title | `QUOTATION` | `PROFORMA INVOICE` |
| Sub-caption | `报价单 / Commercial offer` | `形式发票 / Proforma Invoice` |
| Validity label | `OFFER VALID UNTIL` | `PROFORMA VALID UNTIL` |
| Buyer block title | `BUYER / CONSIGNEE` | `BUYER / APPLICANT / CONSIGNEE` |
| Signature block (buyer side) | `ACCEPTED BY THE BUYER` | `CONFIRMED BY THE BUYER` |
| Footer status | `Draft - not a valid offer` / `Original` | same |

## 3. Blocks usually added to a PI (when the data exists)

* Buyer tax identity the bank or customs will check — Indonesia: **NPWP**, India: **GSTIN**,
  EU: **VAT / USt-IdNr.**, Brazil: **CNPJ**.
* `Buyer's Purchase Order No.` / `L/C No.` / `L/C opening bank` — only if supplied.
* `Country of origin` per line and the `Made in China` marking statement.
* A note that the PI is **not a tax invoice** and that an official invoice will follow shipment.
* Bank details — the placeholder rule still applies (see `06-banking-boundary.md`).

## 4. Consistency rule (critical)

When a quotation is confirmed and later issued as a PI, the following must be identical, or the
bank will raise a discrepancy or the buyer's import permit will not match:

* seller and buyer legal names and addresses,
* product description, CAS, specification, HS code,
* quantity, unit, unit price, currency, trade term + named place + Incoterms year,
* packing and total value,
* payment terms and validity date.

The engine has no separate "PI validator" — it validates the case and the renderer switches
labels. If a quotation is converted into a PI after negotiation, create a **new case id** and keep
the old JSON, so the document trail stays auditable.

## 5. After the PI: the commercial invoice

The commercial invoice is out of scope of this skill. When it is issued, it must carry the PI
number as reference, the actual shipped quantity, the vessel/flight details, and the final
amount. It is a tax document and must follow the exporter's tax rules (China: export invoice
with the correct tax treatment).
