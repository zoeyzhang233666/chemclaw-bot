"""回填 review.json：为供应商问题补英文（question_en），为风险补英文摘要（title_en）。

英文版本面向海外供应商，须是**可直接发送的英文表述**，因此：
  * 只写英文，不夹中文；
  * 语气为商务函件，问「是否/请提供/能否」，不下法律结论。
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "review.json"
data = json.loads(P.read_text(encoding="utf-8"))

TITLE_EN = {
    "R01": "30% advance payment (USD 768,000) is unsecured and expressly non-refundable",
    "R02": "The L/C is to be issued \"at the Seller's bank\" — the issuing bank direction is reversed",
    "R03": "The balance payment has three mutually inconsistent triggers",
    "R04": "Payment documents include an open-ended catch-all: \"(g) such other documents as the Seller may reasonably require\"",
    "R05": "No provision on L/C amendment delay, discrepancies, or allocation of bank charges",
    "R06": "Quality is benchmarked to the Seller's own standard specification, which the Seller may update at any time",
    "R07": "Annex 1 omits test methods for water, leaves haze/colour blank, and cites ASTM standards without edition years",
    "R08": "Clause 3.1 states the CAS number of MEG as 7732-18-5 (the CAS of water) and mixes molar and mass bases",
    "R09": "Quality claims must be filed within 7 days of vessel arrival — shorter than discharge, sampling and testing",
    "R10": "Quality is final per the Seller's own COA; the third-party inspector is also appointed by the Seller",
    "R11": "No provision on quantity shortage, breakage, leakage or discharge loss, or on related claims",
    "R12": "Replacement is the only remedy for non-conformity; no price reduction, return or termination mechanism",
    "R13": "No mechanism for sampling, sample retention, laboratory selection or cost-sharing for testing at destination",
    "R14": "Clause 10.1 transfers risk on receipt of the original B/L, which conflicts with CIF Incoterms 2020 (on board)",
    "R15": "Title passes only on discharge and acceptance at destination, and destination port charges are shifted to the Buyer",
    "R16": "Insurance is for the Seller's benefit, ICC (C) only, with no agreed insured party/protection term",
    "R17": "Shipment period runs from the Seller's receipt of the advance, with no fixed shipment window or latest shipment date",
    "R18": "Transhipment is \"at the carrier's option\"; no restriction on charter party or house bills of lading",
    "R19": "Liquidated damages for delay are only 0.05%/day capped at 5%, with no termination right",
    "R20": "The Seller's entire liability is capped at the advance payment received (USD 768,000), excluding indirect loss",
    "R21": "One-sided, perpetual confidentiality obligation on the Buyer",
    "R22": "Force majeure is over-broad (market price changes, equipment breakdown) and has no notice, proof or termination mechanism",
    "R23": "Arbitration clause is internally inconsistent: SIAC Rules \"in Singapore\" with the seat stated as the DIFC",
    "R24": "The Seller reserves the right to sue in \"any competent court\" for the advance and the balance",
    "R25": "The relationship with the CISG is not addressed; no mediation or cost-shifting provisions",
    "R26": "Both language versions are \"equally authentic\" but English prevails, while the arbitration agreement is to be construed in Chinese",
    "R27": "Entire agreement clause excludes the proforma invoice and prior exchanges, leaving the referenced specification outside the contract",
    "R28": "SDS/Chinese labelling: SDS only \"after shipment\", Chinese safety labels allocated to the Buyer, no GHS edition or version",
    "R29": "All import licensing risk is allocated to the Buyer, with no cooperation obligation on the Seller",
    "R30": "The Seller is a free-zone trading entity; the actual producer, export-control and sanctions provisions are not addressed",
}

QEN = {
 "R01": ["Can you provide an advance payment guarantee issued by a bank, covering at least the advance amount and valid until 60 days after shipment?",
         "If a guarantee is not available, would you consider reducing the advance to 10% or less, or making payment conditional upon a satisfactory pre-shipment inspection?",
         "Which provisions of the Contract constitute the \"expressly provided\" exceptions to non-refundability? Please list them in writing.",
         "Is the receiving account held by your UAE free-zone entity or by a Saudi entity? Is the account holder the same legal entity as the contracting seller?"],
 "R02": ["Please confirm that the issuing bank will be our account bank (e.g. Bank of China, Zhejiang Branch), and provide the SWIFT code and address of your advising bank.",
         "Please confirm the availability of the credit (negotiation or sight payment), whether confirmation is required, and the expiry date and place of expiry.",
         "Please confirm the latest shipment date and the latest presentation period (we propose 21 days after shipment).",
         "Please clarify whether \"issued at the Seller's bank\" is a drafting error. If not, what is intended?"],
 "R03": ["Please confirm which provision governs payment of the balance: the documentary credit under Clause 8.2 or payment on arrival under Clause 8.4.",
         "If the credit is retained, do you agree that inspection and acceptance operate only as claim grounds, not as refusal grounds under the credit?",
         "If payment on arrival is retained, what security would you require from the Buyer?"],
 "R04": ["Do you agree to delete item (g) \"such other documents as the Seller may reasonably require\" from Clause 8.3?",
         "Do you agree that the bill of lading be a full set of 3/3 originals, clean on board, made out to order and blank endorsed?",
         "Do you confirm that charter party bills of lading and house bills of lading are not acceptable?",
         "Please confirm the consignee and notify party fields, and whether freight is marked \"Freight Prepaid\"."],
 "R05": ["How are L/C amendment and extension charges, and bank charges in each country, to be allocated?",
         "If shipment is delayed, may an extension be requested only with our prior written consent?",
         "What is the time limit for handling and accepting discrepancies under the credit?"],
 "R06": ["Can the quality benchmark be a fixed specification agreed by both parties, rather than the Seller's standard specification?",
         "Do you agree that any revision of the specification requires our prior written consent before it takes effect?",
         "Would you accept GB/T 4649-2018 as a second reference benchmark for inspection in China?",
         "Which prevails in the event of conflict: Annex 1 or Clause 2.1?"],
 "R07": ["Which method applies to the water content figure (e.g. Karl Fischer or GC), and under which standard and edition?",
         "What limits apply to colour (APHA) and haze (NTU), and when will the blank cell in Annex 1 be completed?",
         "Which editions of ASTM E202 and ASTM D7844 apply? How are later revisions treated?",
         "Would you accept adding aldehyde content and acidity (as acetic acid) as inspection items?"],
 "R08": ["Please confirm in writing the CAS Registry Number of the Goods is 107-21-1, and correct the COA, SDS and shipping documents accordingly.",
         "Is purity expressed on a mass basis (% m/m) or a molar basis (mol%)? Which is the acceptance criterion?",
         "Do you agree to state both CAS 107-21-1 and EC 203-473-3 in Clause 3.1 and to align them with Annex 1?"],
 "R09": ["Can the claim period be extended from 7 days after arrival to 30 days after completion of discharge and joint sampling?",
         "Can the starting point be changed to the date of completion of discharge and sealing of samples, or the date we receive the independent inspection report?",
         "Can separate periods apply to quantity shortages and to quality deviations?",
         "If re-testing is required, may the claim period be extended on written request?"],
 "R10": ["May the Buyer take independent samples at the loading port and at the port of destination, with samples jointly sealed and a documented chain of custody?",
         "If the two laboratories disagree, which mechanism applies (e.g. a third laboratory or joint re-test under the same ASTM method)?",
         "Who appoints the independent inspector, how are costs shared, and is our written confirmation required?"],
 "R11": ["What tolerance applies at the port of destination between the B/L quantity and the landed quantity (e.g. 0.5%)?",
         "How is any excess shortage compensated — invoice price, landed cost, or inventory value? May it be set off against the balance?",
         "Who bears the cost and liability for breakage or leakage during discharge?",
         "Who arranges and pays for the draft survey and independent inspection reports at destination?"],
 "R12": ["Would you accept a price-reduction option based on the extent of any deviation from specification?",
         "Who bears storage, demurrage and disposal costs for rejected goods while replacement is pending?",
         "If replacement is not completed within 60 days, are we entitled to terminate and to recover the advance and losses?",
         "Can the balance payment be suspended while replacement is outstanding?"],
 "R13": ["Who takes samples at the port of destination, when, and are samples to be jointly sealed and signed?",
         "What retention period applies (we propose at least six months), and who holds the retained samples?",
         "Which laboratory types are acceptable for re-testing, and how are costs shared?"],
 "R14": ["Do you agree that risk passes in accordance with CIF Incoterms 2020, when the Goods are placed on board at the port of shipment?",
         "Is \"upon the Buyer's receipt of the full set of original bills of lading\" in Clause 10.1 a drafting error?",
         "If risk passes on board, do you agree that the insurance is to be effected for the Buyer's benefit, with cover reviewed accordingly?"],
 "R15": ["Is the CIF price under Clause 5.1 inclusive of destination port charges and terminal handling charges?",
         "When exactly does title pass, and can title transfer be aligned with the risk transfer point?",
         "Who arranges discharge, and how are destination port charges actually incurred and settled?"],
 "R16": ["Can the insurance be effected for the benefit of the Buyer as insured party?",
         "Can the cover be upgraded from ICC (C) to ICC (A), or at least extended to include contamination, commingling and temperature clauses?",
         "Does the cover run from warehouse to warehouse, including inland transport to our plant?",
         "Will the insurance policy be presented as one of the documents under Clause 8.3?"],
 "R17": ["Can the shipment period be replaced by a fixed window (e.g. 1 to 25 November 2026) together with a latest shipment date?",
         "Within how many days after receipt of the advance will you confirm receipt in writing, and does a delay extend the shipment period?",
         "If shipment is not completed within the window, how are liquidated damages calculated?"],
 "R18": ["Is transhipment subject to our prior written consent, and how many transhipments are permitted?",
         "Will the bill of lading be a full form, non-charter party, negotiable bill of lading?",
         "Can the vessel name and estimated schedule be pre-confirmed with us before shipment?"],
 "R19": ["Can liquidated damages be increased to 0.1% per day with a 10% cap?",
         "If delay exceeds 30 days, are we entitled to terminate and recover the advance, interest and costs?",
         "Where liquidated damages do not cover our actual loss, can we claim the balance?"],
 "R20": ["Can the liability cap be increased to the contract value, or at least to 100% of amounts paid?",
         "Can exceptions be added for fraud, wilful misconduct, gross negligence, false SDS/COA, export-control breaches and personal injury?",
         "Can demurrage and storage be treated as direct loss rather than excluded items?",
         "Can refund of the advance be excluded from the cap?"],
 "R21": ["Can the confidentiality obligation be limited to a defined period, e.g. three years after termination?",
         "Can exceptions be added for disclosures required by law, regulators, auditors, banks, advisers or in legal proceedings?",
         "Will the Seller accept a reciprocal confidentiality obligation?"],
 "R22": ["Do you agree to remove market price changes, equipment breakdown and shortage of raw materials from the force majeure definition?",
         "Can a notice period (e.g. 7 days) and evidential documents (e.g. chamber of commerce certificate) be added?",
         "If force majeure continues beyond 60 days, are we entitled to terminate and recover the advance?"],
 "R23": ["Please confirm the seat of arbitration: Singapore or the DIFC.",
         "Is the tribunal to consist of one or three arbitrators, and how are they appointed?",
         "What is the language of the arbitration (English, Chinese or bilingual)?",
         "Which court may hear applications for interim measures?"],
 "R24": ["Do you agree to delete this carve-out?",
         "Alternatively, can it be limited to undisputed amounts and to a specified court (e.g. an agreed court in China)?"],
 "R25": ["Do you agree to state expressly whether the CISG applies or is excluded?",
         "Can a mediation step with a defined time limit be added before arbitration?",
         "Does the unsuccessful party bear legal costs and arbitration costs?"],
 "R26": ["Do you agree that the Chinese version prevails in case of inconsistency?",
         "Who will provide the Chinese translation, and how are translation errors corrected?",
         "How will the second sentence of Clause 14.1 be reconciled with Clause 13.1?"],
 "R27": ["Can the \"Fiber Grade MEG\" standard specification referred to in Clause 2.1 be annexed to the Contract, with a locked version and date?",
         "Do you agree that technical documents confirmed in writing by the Seller form part of the Contract?",
         "Which terms of the proforma invoice (e.g. price and quantity) should be retained?"],
 "R28": ["When will the SDS be provided (before booking, before shipment, or with the goods), and in which languages (English and Chinese)?",
         "Which edition of GHS applies to the SDS?",
         "Will you provide the Chinese safety labels, or reimburse their cost? Which standards will be used?",
         "Is the Goods declared as dangerous goods for export? Please provide the basis and any packing suitability certificate."],
 "R29": ["Will you undertake to provide, within five working days, the materials we need to apply for an automatic import licence (certificate of origin, composition and use description)?",
         "If Chinese regulations change and the licence cannot be obtained, how will the parties proceed?",
         "Are any Saudi export permits or registrations required, and have they been obtained?"],
 "R30": ["Please provide the name of the actual producer of the Goods and its relationship with the Seller.",
         "Will the certificate of origin and the COA be issued by the actual producer or by the Seller?",
         "Do you accept export-control, economic-sanctions and anti-bribery representations and warranties?",
         "Can you provide your free-zone trade licence and, if available, a parent company guarantee?"],
}

for f in data["findings"]:
    if f["id"] in TITLE_EN:
        f["title_en"] = TITLE_EN[f["id"]]

missing = []
for owner_items in data["confirmations"].values():
    for q in owner_items:
        fid = q["finding_id"]
        q_en = QEN.get(fid, [])
        # 每条问题按「问题在清单中的序号」映射英文
        idx = [x for x in owner_items if x["finding_id"] == fid].index(q)
        if idx < len(q_en):
            q["question_en"] = q_en[idx]
        else:
            missing.append((fid, idx))
            q["question_en"] = ""

P.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("findings with title_en:", sum(1 for f in data["findings"] if f.get("title_en")))
tot = sum(len(v) for v in data["confirmations"].values())
print("questions:", tot, "| unmapped:", len(missing), missing[:12])
