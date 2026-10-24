# Dangerous goods & chemical transport notes

## 1. Never guess the classification

The dangerous-goods status comes from **verified product data** only: the manufacturer's current
SDS (section 14), a UN/IMDG lookup, or an IATA DGR entry. If it is not verified, set
`dangerousGoods.status = "UNKNOWN"`. The engine then raises `DG_UNKNOWN` (error) and no shipping
document may be issued.

| status | meaning | document wording |
|---|---|---|
| `DG` | Confirmed dangerous good, transport data known | `DANGEROUS GOODS: UN <no.>, <class>, PG <pg>; UN-approved packaging; DGD/DG declaration required` |
| `NOT_REGULATED` | SDS states not dangerous for transport | `TRANSPORT: Not classified as dangerous goods for transport (basis: supplier SDS rev. <x>)` |
| `UNKNOWN` | Not verified | `DG status: TO BE VERIFIED` (red placeholder) |

## 2. What must be recorded for a DG line

`unNumber`, `properShippingName`, `class`, `packingGroup`, `unPackagingCode`,
`msdsVersion`. Missing any of these is flagged. Do **not** copy IMDG data from memory — take it
from the SDS or an official table at the time of quoting.

## 3. GHS hazard wording vs transport classification

Label hazards (CLP/GHS phrases such as `H319 Causes serious eye irritation`) are **not** the
transport class. A product can carry a GHS warning pictogram and still be `NOT_REGULATED` for
transport. Print both separately:

* line item: "DG: UN … class … PG …" only when transport-regulated;
* notes: "GHS: Warning - H319 …" as handling information.

## 4. Packaging & weight rules used in the checks

| Product form | Typical packing | Check |
|---|---|---|
| Powder in bags (soda ash, TiO2, urea, citric acid) | 25 kg / 50 kg PP or paper bags | `quantity ÷ bagNet` must equal package count |
| Liquids in drums (DOP, solvents) | 200 L / 180-230 kg drum | drum count × net volume = quantity |
| IBC / flexitank | 1000 L IBC, 20-24 t flexitank | state net per unit |
| Bulk (urea, soda ash in bulk vessel) | `BULK` unit | no package count; state vessel stowage |

Gross weight = packageCount × unit gross weight. Example: 40,000 bags × 25.2 kg =
1,008,000 kg (1,008.00 MT) for a 1,000 MT net soda-ash order.

## 5. Documents to reference for chemicals

Commercial invoice, packing list, B/L (or AWB), certificate of origin, certificate of analysis,
manufacturer's SDS, and — when applicable — DGD / DG declaration, MSDS, insurance certificate,
fumigation/ISPM-15 certificate (wooden pallets), food-grade statement, halal/kosher statement,
REACH registration statement (EU), TSCA statement (US).

## 6. Transport-mode caveats to state on the quotation

* Sea: "IMO surcharge included / excluded", "DG cargo requires advance booking".
* Air: "DG cargo subject to airline acceptance; screening and DG handling fees for buyer's
  account unless quoted".
* Multimodal CIP: CIP covers any transport mode; CIF/CFR/FOB only sea and inland waterways.
* Warm-climate chemicals: state storage conditions if the SDS requires them (e.g. urea and
  soda ash are hygroscopic).

## 7. Example (EX-001, soda ash heavy)

```
dangerousGoods: {status: "NOT_REGULATED",
                 basis: "Supplier SDS: not classified as dangerous goods for transport",
                 ghsSummary: "GHS: Warning - H319 Causes serious eye irritation (P264, P265, P280, P305+P351+P338); not a transport hazard (verify by SDS)"}
```
PubChem CID 10340 (sodium carbonate, Na2CO3, MW 105.988) confirms the GHS label "Warning" and
H319 with P264+P265, P280, P305+P351+P338, P337+P317. These are label statements only.
