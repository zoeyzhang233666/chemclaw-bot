# Banking details, payment terms and the safety boundary

This is a hard rule of the skill. It exists because plausible-looking bank details on an
export document are a direct fraud vector (payment-diversion fraud).

## 1. Never generate bank details

* **Never** invent, complete, "correct" or reformat an account number.
* **Never** produce a bank name + account + SWIFT combination that was not typed in by the user
  and explicitly confirmed.
* **Never** copy bank details from an e-mail, a chat message or a previous document. If they were
  pasted in, they still require the seller's written confirmation through an independent channel.

## 2. Placeholder behaviour

When `bank.display !== true`, or `bank.sanitized === true`, or `bank.detailsConfirmed !== true`,
the document prints a red-bordered placeholder:

> `[ BANK DETAILS TO BE CONFIRMED BY THE SELLER - A/C No. / SWIFT INTENTIONALLY NOT GENERATED ]`

The HTML editor also masks any pasted value and requires a "Bank details confirmed by seller"
checkbox before anything is shown.

## 3. What the skill may write about payment

Only what the user confirmed: terms type (T/T, L/C, D/P, D/A, O/A, mixed), the advance percentage,
the LC type and opening window, and any beneficiary wording the seller gave. Example:

> "100% T/T in advance prior to shipment; only actual inward bank charges are for the
> beneficiary account."

This sentence is a common Chinese supplier phrasing and must have been confirmed by the seller —
do not add it because it "sounds standard".

## 4. Payment-term templates (use only when the user selects them)

| Code | Standard text (still requires user confirmation) |
|---|---|
| PREPAY | "100% T/T in advance prior to shipment" |
| MIXED 30/70 | "30% T/T in advance, balance 70% against B/L copy" |
| LC | "Irrevocable L/C at sight covering 100% of the invoice value, opened 30 days before shipment" |
| DP | "D/P at sight through the buyer's bank" |
| OA | "Open account, 30/60/90 days from B/L date" — requires credit insurance or a credit limit |
| DA | "D/A 60 days from B/L date" — the most exposed mode; never suggest it unprompted |

## 5. High-risk markers to warn the buyer-side user about

If any of these appear in the request, warn and do **not** change the document silently:

* a mid-contract change of beneficiary account,
* an account in a different country from the seller,
* a request to process payment through a "partner company",
* a bank whose SWIFT does not match its claimed country,
* an instruction delivered by e-mail only, without another channel.

Suggested wording for the seller's team: "Bank details are never changed by e-mail. Call the
signatory on the number on the contract to verify any change."

## 6. The banking check group (K)

`BANK_SHOWN`, `BANK_NOT_CONFIRMED`, `BANK_SANITIZED` — the engine blocks "display" when the
details are not confirmed and requires an explicit acknowledgement when the seller shows a
placeholder account on an issued document.
