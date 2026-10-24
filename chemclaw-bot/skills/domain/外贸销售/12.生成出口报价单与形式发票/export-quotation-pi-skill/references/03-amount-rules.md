# Amount calculation & rounding rules

## 1. Line amount

```
lineAmount = roundHalfUp( quantity × unitPrice × (1 − discountPct/100), 2 )
```
* `quantity` and `unitPrice` are handled as **decimal strings** where available (engine converts
  with `Number()` on a comma-stripped string), so `1000 × 217` is exact.
* Rounding is **half-up** (`roundHalfUp`) with an epsilon of 1e-9, i.e. 2.675 → 2.68. Banker's
  rounding is never used for trade amounts.
* Discount is a percentage per line; a lump-sum discount must be added as a charge line with a
  negative amount and labelled "Less: discount".

## 2. Charges and total

```
subtotal = Σ lineAmount
extraCharges = Σ charge.amount   where addToTotal ≠ false and amount ≠ ""
total    = subtotal + extraCharges
```
Charges excluded from the total (`addToTotal:false`) are printed as information (e.g. "insurance
for buyer's account") and never change the figure.

## 3. The price-confirmation gate (`amountState`)

| state | meaning | engine behaviour |
|---|---|---|
| `confirmed` | A human confirmed this unit price / total | total printed; if the arithmetic no longer matches `amountConfirmedValue`, an `AMOUNT_MISMATCH` error and `PENDING PRICE` are raised |
| `draft` | Price typed but not confirmed | total printed as a **draft** figure; formal issue blocked |
| `""` (blank price) | Price not available | total renders `PENDING PRICE` placeholder; only a draft document may be produced |

Changing quantity, unit price, discount or currency **invalidates** a previous confirmation —
the user must re-confirm. The engine enforces this; never bypass it.

## 4. Amount in words

Camelot-style English: `US Dollars Two Hundred Seventeen Thousand Only`.
Rules used by `amountInWords()`:
* currency name from `currency.name` (`US Dollar` → `US Dollars`);
* integer part grouped in thousands (million / billion), cents appended as
  `and Cents Fifty Only` when non-zero;
* singular for 1: `One US Dollar Only`.

Always print the amount in words in **both** the quotation and the PI: it is the tie-breaker for
any figure dispute and a common L/C requirement.

## 5. Multi-line and per-unit consistency

* Quotation and PI must show the same unit basis (`USD/MT` for soda ash, `USD/DRUM` for liquids,
  `USD/MT` or `USD/kg` for fine chemicals). A unit change is a new offer.
* When a line uses `DRUM`, `BAG` or `IBC` as the unit, the packing block must repeat the same
  package count; the engine compares `quantity ÷ bag net weight` with package count
  (`BAG_COUNT_CHECK`) and with `totalPackageCount` (`PACKAGE_SUM_MISMATCH`).
* Gross weight is `packageCount × packageWeight`; a mismatch is warned (`WEIGHT_SUM_MISMATCH`).
  Free text such as `"1,008,000 kg (1,008.00 MT)"` is parsed by unit, not by raw digits.

## 6. Currency & exchange-rate lines

* The face currency is fixed by the user and printed on every page.
* A reference rate may be footnoted: `1 CNY = 6.6862 USD as of 2026-10-16 (ECB reference rate;
  reference only — prices are fixed in USD)`. Never let a reference rate look like a contractual
  conversion; never add an FX clause that the seller did not give.
