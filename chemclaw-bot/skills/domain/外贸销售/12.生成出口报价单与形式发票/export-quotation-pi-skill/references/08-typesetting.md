# Typesetting & document design standard

The document must look like an export document that a European or South-East Asian buyer can
accept without editing: A4, one page wherever possible, navy/gold trade colours, English body text
in a serif face, labels in a small sans face.

## 1. Page

| Item | Value |
|---|---|
| Size | A4 210 × 297 mm |
| Margins | top 10 mm, bottom 8 mm, left/right 14 mm (Word), 16 mm (HTML preview) |
| Usable width | ~182 mm |
| Target length | **1 page**; a 2nd page only for extra notes, never for the signature alone |
| Footer | seller name · document number · page x · status (Draft / Original) |

## 2. Colour system

| Token | Hex | Use |
|---|---|---|
| Navy | `1B3A5B` | seller name, table header, TOTAL row, title |
| Gold | `B58B3A` | accent rule, amount-in-words border, logo text |
| Slate | `6B7A90` | small caps labels |
| Border | `D8DEE6` | table lines, bank box |
| Danger | `B42318` | placeholders (missing price, bank), DG warnings |
| Simulated tint | `DDE3EA` | watermark text |

## 3. Type scale

| Element | Face | Size | Weight |
|---|---|---|---|
| Seller name | Georgia | 11.5 pt | bold |
| Document title | Georgia | 14.5 pt | bold |
| Party names | Georgia | 9.2 pt | bold |
| Table header | Arial | 6.6 pt | bold, white on navy |
| Body / terms | Georgia | 7.4–8.5 pt | regular |
| Labels | Arial | 6.2–6.8 pt | bold, slate |
| TOTAL amount | Georgia | 9.2 pt | bold |
| Amount in words | Georgia | 8.6 pt | bold |

Sans body text under 7 pt becomes unreadable after printing; keep body text at 7.4 pt or larger.

## 4. Layout skeleton (top to bottom)

1. **Header** — logo/nickname (left) · seller name + address + contact + tax ID (centre) ·
   document title + number + date (right), followed by a 2 pt navy rule.
2. **Parties** — two equal columns, seller left, buyer right; label in small caps above the name.
3. **Meta strip** — 4 cells (Incoterms + named place / currency / validity / payment terms).
4. **Items table** — No. · Description (+CAS, HS, origin) · Specification · Quantity · Unit ·
   Unit price · Amount; then sub-total, extra charge rows and a navy TOTAL row.
5. **Amount in words** — gold-bordered single-cell bar.
6. **Terms grid** — 4 columns × 4 rows: trade term, partial shipment, packing, transhipment,
   total packages + gross weight, lead time, payment, origin/destination.
7. **Bank block** — placeholder (red tint) unless confirmed.
8. **Notes & conditions** (numbered, left) and **documents & compliance** + transport notice (right).
9. **Signature block** — buyer and seller, signature line, name, position.

## 5. Watermark for demo data

Every simulated document carries a light diagonal watermark
`SIMULATED DEMO / NOT FOR TRADE USE` behind the text, and the footer status reads
"Draft - not a valid offer". A real, confirmed document has no watermark and the footer reads
"Original".

## 6. HTML preview parity

The HTML editor renders the same paper at A4 width (210 mm) with the same type scale, so what the
sales rep sees online is what the Word/PDF export will print. The HTML adds an editable overlay
(double-click any field), a watermark toggle, and live recalculated figures.

## 7. Things that break the look (avoid)

* More than 2 decimal places in the amount column.
* A specification paragraph longer than ~5 lines — move extras to NOTES.
* Mixed currencies without a footnote.
* Signature block pushed to page 2 (use `w:cantSplit` + tighter spacing, as the DOCX builder does).
* Emoji, Chinese punctuation or full-width characters inside English sentences.
* `鈥?` or `Ã` mojibake — the builders sanitise `— – ≥ ≤ µ ≈` to ASCII before writing, because
  LibreOffice substitutes a CJK font for those glyphs in Georgia.
