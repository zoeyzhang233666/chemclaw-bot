# Field schema — Quotation / Proforma Invoice

The single source of truth for a case is one JSON document (`schemas/quote.schema.json`).
The HTML editor, the Excel workbook and the Word/PDF builders all read and write the same keys.
**Only user-confirmed values belong in these fields.** If a value was not confirmed, leave it
empty (`""`) or record the placeholder text — never fill it with a plausible guess.

## 1. Root

| Key | Type | Required | Notes |
|---|---|---|---|
| `meta` | object | yes | Provenance & data-class banner |
| `docType` | `"QUOTATION"` \| `"PROFORMA_INVOICE"` | yes | Drives title, numbering label and PI-only blocks |
| `state` | object | yes | `{stage, reviewConfirmed, confirmedBy, confirmedAt}` |
| `reference` | object | yes | Document numbers (never auto-invented) |
| `issueDate` | date | yes | `YYYY-MM-DD`; must be a date the seller confirmed |
| `seller` | party | yes | Exporter / beneficiary |
| `buyer` | party | yes | Consignee / importer |
| `currency` | object | yes | `USD` / `EUR` / `CNY` … + decimals |
| `tradeTerm` | object | yes | Incoterms® rule, named place, version, allocation |
| `items` | array | yes | ≥ 1 pricing line |
| `amountState` | `"confirmed"` \| `"draft"` | yes | Price-confirmation gate |
| `amountConfirmedValue` | number | yes | The total the seller explicitly confirmed |
| `charges` | array | no | Freight, insurance, other charges |
| `packing` | object | yes | Packing description, bag/package net, shipping units |
| `totalPackageCount` | string | yes | Package total — must equal Σ line package counts |
| `totalGrossWeight` | string | yes | e.g. `"1,008,000 kg (1,008.00 MT)"` |
| `freight` | object | yes | Estimated POL/POD, mode |
| `delivery` | object | yes | Lead time text + basis |
| `payment` | object | yes | Payment code, free text, LC/DP detail |
| `validity` | object | yes | `{type: "date"|"days", validUntil, days}` |
| `documents` | array | yes | Documents to be provided |
| `bank` | object | yes | **Placeholder only** unless explicitly confirmed |
| `view` | object | yes | Watermark, logo, accent colour |
| `review` | object | no | Reviewer sign-off {name, signatoryTitle, itemsChecked, formalApproved} |
| `fatal` | array | no | Blocking entries (e.g. unverified DG, missing price gate) |

## 2. `meta`

```json
{"skillVersion":"1.0.0","dataClass":"SIMULATED — DEMO DATA / 模拟演示数据",
 "dataClassNote":"...","caseId":"EX-001-SODA-ASH-IDN","product":"Soda Ash (Heavy)",
 "destination":"Indonesia","preparedAt":"2026-10-19","preparedBy":"...","scenario":"..."}
```
`dataClass` must say SIMULATED for every demo file. Real cases use `"USER-CONFIRMED"`.

## 3. `reference`

`quoteNo` (required), `quotationRef`, `buyerInquiryRef`, `supplierQuoteRef`, `exporterReference`,
`buyerPoNo`. Leave `exporterReference` as `"TO BE ALLOCATED BEFORE SHIPMENT"` when shipping has
not been booked — do not invent container/seal/AWB numbers.

## 4. Parties

```json
{"name":"...","address":"...","country":"...","contact":"...","position":"...",
 "phone":"...","email":"...","taxId":"...","npwp":"...","shortName":"...","logoText":"..."}
```
`name` and `address` are mandatory. `npwp` is the Indonesian tax ID (NPWP) and is required for
Indonesian import documents; Indian buyers show GSTIN; EU buyers show VAT / USt-IdNr.
Demo parties always carry `(SIMULATED DEMO)` and use `@example-demo.invalid` addresses.

## 5. Trade term

```json
{"code":"CIF","version":"2020","namedPlace":"Jakarta (Tanjung Priok), Indonesia",
 "namedPlaceKind":"port|airport|place|address","transportMode":"SEA|AIR|RAIL|ROAD|MULTIMODAL",
 "insuranceBasis":"All Risks (ICCA), 110%",
 "costAllocation":{"exportPacking":"Seller","loadingCharges":"Seller","exportCustoms":"Seller",
   "originCharges":"Seller","mainFreight":"Seller","insurance":"Seller",
   "destinationCharges":"Buyer","importCustoms":"Buyer","unloading":"Buyer"}}
```
`version` is the Incoterms® edition — **2020** unless the user says otherwise. The named place is
printed verbatim after the rule name. `costAllocation` is checked against the Incoterms matrix
(`references/incoterms-matrix.md`); deviations are warnings that need explicit commercial wording.

## 6. Items

```json
{"id":"L1","name":"SODA ASH (HEAVY), Sodium Carbonate","cas":"497-19-8","spec":"...",
 "hsCode":"283620","origin":"China","unit":"MT","quantity":1000,"unitPrice":217,"discountPct":0,
 "amountState":"confirmed","amountConfirmedValue":217000,
 "packageCount":40000,"packageWeight":{"value":25.2,"unit":"KG","net":25},
 "dangerousGoods":{"status":"NOT_REGULATED|DG|UNKNOWN","unNumber":"","properShippingName":"",
   "class":"","packingGroup":"","unPackagingCode":"","msdsVersion":"","basis":"...","ghsSummary":"..."}}
```
* `unitPrice` mandatory — without it the document may only be a DRAFT with placeholders.
* `amountState` must be `confirmed` **and** `amountConfirmedValue` must equal
  `quantity × unitPrice × (1 − discount/100)`; otherwise the total renders as `PENDING PRICE`.
* `status":"UNKNOWN"` is an error: no shipping document may be issued.
* `ghsSummary` is the *label* hazard text (e.g. `GHS: Warning — H319`), not a transport class.

## 7. Charges

```json
{"name":"Ocean freight Shekou → Jakarta","amount":"","addToTotal":true,
 "note":"SIMULATED - to be quoted by forwarder", "basis":"actual|estimated"}
```
Blank amount = not yet quoted: it is excluded from the total and flagged. Under CFR/CIF a blank
freight amount is a warning, because the seller bears that cost.

## 8. Payment

```json
{"code":"PREPAY|LC|DP|DP_DA|OA|MIXED","terms":"free text (verified by the seller)",
 "amountPct":30,"lcType":"at sight","lcOpenedBy":"within 10 days ...",
 "bank":"advising / issuing bank requirement",
 "beneficiary":"[BANK DETAILS TO BE CONFIRMED]","beneficiaryNote":"..."}
```
Fields follow the engine's canonical names (`lcType`, `lcOpenedBy`, `bank`).

## 9. Validity

`{"type":"date","validUntil":"2026-11-18"}` or `{"type":"days","days":30}`.
A quotation without validity cannot be sent; a PI states "valid until" as the price-lock date.

## 10. Bank block

```json
{"display":false,"sanitized":true,"detailsConfirmed":false,"bankName":"","accountName":"",
 "accountNumber":"","swift":"","note":"[BANK DETAILS TO BE CONFIRMED BY SELLER …]"}
```
The renderers print the bank box **only** when `display === true` **and** `sanitized === false`
**and** `detailsConfirmed === true`. Otherwise a placeholder bar is printed. This is a hard rule
(see `references/banking-boundary.md`).
