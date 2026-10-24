# Incoterms® 2020 matrix for chemical export quotations

Always print the rule + version + named place exactly as confirmed:
`CIF Cost, Insurance and Freight, Jakarta (Tanjung Priok), Indonesia, Incoterms® 2020`.

## 1. Rule name (short form and full form)

| Code | Full English name | Typical mode |
|---|---|---|
| EXW | Ex Works | any |
| FCA | Free Carrier | any |
| FAS | Free Alongside Ship | sea |
| FOB | Free On Board | sea |
| CFR | Cost and Freight | sea |
| CIF | Cost, Insurance and Freight | sea |
| CPT | Carriage Paid To | any |
| CIP | Carriage and Insurance Paid To | any |
| DAP | Delivered at Place | any |
| DPU | Delivered at Place Unloaded | any |
| DDP | Delivered Duty Paid | any |

Source for the names: ICC Incoterms® 2020 rules (wording as published on the ICC / Wikipedia
"Incoterms" reference pages). DDP is widely rendered as
"Delivered Duty Paid (named place of destination)"; the ICC trade-data element for DDP is
"Delivered Duty Paid".

## 2. Cost allocation matrix

"Seller" = the cost is normally borne by the seller under that rule.

| Cost | EXW | FCA | FAS | FOB | CFR | CIF | CPT | CIP | DAP | DPU | DDP |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Export packing | S | S | S | S | S | S | S | S | S | S | S |
| Loading at origin | B | S | S | S | S | S | S | S | S | S | S |
| Export customs clearance | B | S | S | S | S | S | S | S | S | S | S |
| Origin terminal / inland to port | B | B* | S | S | S | S | S | S | S | S | S |
| Main carriage (freight) | B | B | B | B | S | S | S | S | S | S | S |
| Cargo insurance | B | B | B | B | B | **S** | B | **S** | B | B | B |
| Destination terminal / delivery | B | B | B | B | B | B | S* | S* | S | S | S |
| Import customs & duties | B | B | B | B | B | B | B | B | B | B | **S** |
| Unloading at destination | B | B | B | B | B | B | B | B | B | S | S |

\* nuance worth stating on the document: FCA — costs after loading on the buyer's vehicle are
for the buyer; CPT/CIP — the named place decides where the seller's carriage obligation ends.

## 3. Insurance rules (must be stated on the face of the document)

* CIF / CIP: the seller insures. **CIF = minimum cover (Institute Cargo Clauses (C)), CIP =
  wider cover (ICC (A))** unless the contract says otherwise. State cover + sum insured, e.g.
  "All Risks (ICC A), 110% of the CIF value".
* CIP is expressible for multimodal transport; CIF/CFR/FOB/FAS are for sea and inland waterway
  only. Do not pair CIF with an airport named place.
* Under CFR the document must say insurance is **for the buyer's account**.

## 4. Places and units

* Sea rules (FAS/FOB/CFR/CIF): named place must be a **port**, followed by the seaport handling
  charges that the seller bears ("THC destination for buyer's account" if applicable).
* FCA: "FCA Shanghai Pudong International Airport" or "FCA Seller's warehouse, Shenzhen" —
  the named place determines the hand-over point; if it is the seller's premises the seller loads.
* DAP/DPU/DDP: named place is a **destination** address, not a port; DAP/DDP place unloading
  duties on the buyer.
* DDP: add a line that duties/taxes at destination are included; if VAT withholding applies in
  the buyer's country, say who bears it. Many chemical sellers avoid DDP for this reason.

## 5. Contract wording that must accompany non-rule costs

The engine warns when a cost is allocated against the rule (`COST_ALLOC_*`). Either fix the
allocation or add explicit wording, e.g.:

> "In deviation from CIF 2020, the Seller also bears destination terminal handling at Jakarta
> (USD ____ per container); all other costs follow CIF Incoterms® 2020."

Never silently change the rule. Quotation and PI must carry the same rule, named place and
Incoterms version, otherwise the buyer's L/C documents will mismatch the invoice.

## 6. Chemical-specific notes per rule

| Situation | Practical note |
|---|---|
| IMO class 8 / 9 cargo | Add "Freight includes IMO surcharge; DG declaration and DGD prepared by seller" only if the forwarder confirmed it. |
| Bulk liquid / flexitank | CIF/CFR quotes usually exclude tank cleaning and demurrage; state them. |
| Powder in bags (soda ash, TiO2, urea) | Palletisation and fumigation (ISPM-15) costs — state who bears them. |
| Hazardous for air (FCA to airport) | FCA airport quotes exclude screening/DG handling unless quoted. |
| DAP/DDP to inland China-adjacent countries | Rail/multimodal: use CPT/CIP not CFR/CIF. |
