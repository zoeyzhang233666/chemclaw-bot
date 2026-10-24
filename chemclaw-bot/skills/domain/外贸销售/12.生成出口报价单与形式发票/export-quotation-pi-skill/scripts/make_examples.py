#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the complete example case set (different products, countries,
currencies, Incoterms rules, payment terms and document types).

Every example is SIMULATED demo data: company names carry "(SIMULATED DEMO)",
contacts use reserved example domains, and bank details are placeholders only.

Usage: python scripts/make_examples.py [--out examples]
"""
import argparse, io, json, os, sys
from copy import deepcopy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = "2026-10-19"
SIM = "SIMULATED DEMO"

HUA_BIN = {
    "name": "Hua Bin Chemical Trading Co., Ltd. (SIMULATED DEMO)",
    "shortName": "SIMULATED CO., LTD.", "logoText": "SIMULATED",
    "address": "Unit 2108, 21/F, Harbor Commerce Tower, Nanshan District, Shenzhen, Guangdong 518000, China",
    "country": "China", "contact": "[Simulated Contact Person]", "phone": "+86 000 0000 0000 (Simulated)",
    "email": "export@example-demo.invalid", "taxId": "USCI SIMULATED-0000000000",
}

SEA = {k: "Seller" for k in ["exportPacking", "loadingCharges", "exportCustoms", "originCharges"]}
BUY = {k: "Buyer" for k in ["destinationCharges", "importCustoms", "unloading"]}
FREIGHT_S = {"mainFreight": "Seller"}


def alloc(**kw):
    base = dict(SEA); base.update(BUY); base.update({"mainFreight": "Buyer", "insurance": "Buyer"})
    base.update(kw)
    return base


DOCS_BASE = [
    {"name": "Bill of Lading (3 originals + 3 copies)"},
    {"name": "Commercial Invoice (1 original + 5 copies)"},
    {"name": "Packing List (1 original + 3 copies)"},
    {"name": "Certificate of Origin"},
    {"name": "Certificate of Analysis (per shipment)"},
    {"name": "Manufacturer's SDS (current revision)"},
]


def case(meta, doc_type, ref, seller, buyer, currency, term, items, packing, total_pkgs,
         gross, freight, delivery, payment, validity, charges, bank_note="placeholders only",
         doc_summary=None, extra=None, docs=None, amount_confirmed=None, view=None, review=None,
         fatal=None, state="READY_FOR_REVIEW", exchange_rate=None):
    subtotal = round(sum((float(i["quantity"]) * float(i["unitPrice"]) if i.get("unitPrice") not in ("", None) else 0)
                         * (1 - float(i.get("discountPct") or 0) / 100) for i in items), 2)
    tot = subtotal + sum(float(c["amount"]) for c in charges if c.get("amount") not in ("", None) and c.get("addToTotal", True))
    d = {
        "meta": {"skillVersion": "1.0.0", "dataClass": "SIMULATED — DEMO DATA / 模拟演示数据",
                 "dataClassNote": "All names, contacts, prices and terms are SIMULATED for skill demonstration. Replace with user-confirmed commercial data before any real use. Bank details are placeholders only.",
                 "caseId": meta["caseId"], "product": meta["product"], "destination": meta["destination"],
                 "preparedAt": TODAY, "preparedBy": "export-quotation-pi skill example generator",
                 "scenario": meta.get("scenario", "")},
        "docType": doc_type,
        "state": {"stage": state, "reviewConfirmed": False},
        "reference": {"text": ref, "quoteNo": ref, "quotationRef": ref + " Rev.0",
                      "buyerInquiryRef": meta.get("inquiryRef", ""), "supplierQuoteRef": meta.get("supplierRef", ""),
                      "exporterReference": meta.get("exporterRef", "TO BE ALLOCATED BEFORE SHIPMENT"),
                      "buyerPoNo": meta.get("poNo", "")},
        "issueDate": TODAY,
        "seller": seller, "buyer": buyer,
        "currency": {"code": currency[0], "name": currency[1], "decimals": currency[2],
                     "exchangeRate": exchange_rate or {"base": "", "rate": "", "asOf": "", "state": "reference", "display": "none"}},
        "tradeTerm": term,
        "items": items,
        "amountState": "confirmed", "amountConfirmedValue": amount_confirmed if amount_confirmed is not None else tot,
        "charges": charges,
        "packing": packing, "totalPackageCount": total_pkgs, "totalGrossWeight": gross, "totalVolume": "",
        "freight": freight, "delivery": delivery, "payment": payment, "validity": validity,
        "documents": docs or DOCS_BASE,
        "bank": {"display": False, "sanitized": True, "detailsConfirmed": False, "bankName": "", "accountName": "",
                 "accountNumber": "", "swift": "", "note": bank_note},
        "view": view or {"logo": True, "signature": True, "watermark": True, "accentColor": "#1B3A5B"},
        "preparation": {"issuedBy": "export-quotation-pi skill v1.0.0",
                        "notice": "SIMULATED DEMO DATA — NOT FOR TRADE USE." + (" " + doc_summary if doc_summary else "")},
        "review": review or {},
    }
    if fatal:
        d["fatal"] = fatal
    if extra:
        d.update(extra)
    return d


def item(id_, name, cas, spec, hs, qty, unit, price, pkgs=None, pkg_gross=None, pkg_net=None,
         dg_status="NOT_REGULATED", dg_basis="Supplier SDS: not classified as dangerous goods for transport (re-verify against current SDS)",
         ghs="", origin="China"):
    q = (float(qty) * float(price)) if price not in ("", None) else 0
    it = {"id": id_, "name": name, "cas": cas, "spec": spec, "hsCode": hs, "origin": origin, "unit": unit,
          "quantity": qty, "unitPrice": price, "discountPct": 0,
          "amountState": "confirmed" if price not in ("", None) else "draft",
          "amountConfirmedValue": round(q, 2),
          "dangerousGoods": {"status": dg_status, "basis": dg_basis, "ghsSummary": ghs}}
    if pkgs:
        it["packageCount"] = pkgs
        it["packageWeight"] = {"value": pkg_gross, "unit": "KG", "net": pkg_net, "basis": "simulated declaration"}
    return it


# =========================================================================== cases
def ex002():
    """DAP Ho Chi Minh City, PVC resin, Vietnam, USD, 40'HQ bags, 3 lots + lot notice."""
    return case(
        {"caseId": "EX-002-PVC-VNM", "product": "PVC Suspension Resin SG-5", "destination": "Vietnam",
         "scenario": "Chinese PVC producer quoting DAP Ho Chi Minh City to a Vietnamese pipe manufacturer; multi-line (SG-5 / SG-8) and a buyer-side demurrage clause.",
         "inquiryRef": "INQ-SIM-VN-2201 (2026-10-15)"},
        "QUOTATION", "QT-SIM-2610-002", HUA_BIN,
        {"name": "Nam Viet Pipe Manufacturing JSC (SIMULATED DEMO)",
         "address": "Lot B-12, Hiep Phuoc Industrial Park, Nha Be District, Ho Chi Minh City 700000, Vietnam",
         "country": "Vietnam", "contact": "[Simulated Buyer Contact]", "position": "Purchasing Director",
         "phone": "+84 00 0000 000 (Simulated)", "email": "sourcing@example-demo.invalid", "npwp": "Tax code SIMULATED-0000000000"},
        ("USD", "US Dollar", 2),
        {"code": "DAP", "version": "2020", "namedPlace": "Buyer's factory, Hiep Phuoc Industrial Park, Nha Be, Ho Chi Minh City",
         "namedPlaceKind": "address", "transportMode": "SEA", "costAllocation": alloc(mainFreight="Seller", destinationCharges="Buyer")},
        [item("L1", "PVC Suspension Resin, Grade SG-5", "9002-86-2",
              "K-value 66-68; volatile matter 0.3% max.; apparent density 0.48-0.55 g/ml; sieve 250 um pass 2% min.",
              "390410", 200, "MT", 690, 8000, 25.2, 25),
         item("L2", "PVC Suspension Resin, Grade SG-8", "9002-86-2",
              "K-value 58-60; volatile matter 0.3% max.; for pipe extrusion",
              "390410", 200, "MT", 710, 8000, 25.2, 25)],
        {"summary": "16,000 bags x 25 kg net in 25 kg paper sacks with PE liner, palletised; 8 x 40'HQ (approx.)",
         "terms": "Standard export packing with shipping marks and 'Made in China' labelling", "bagNetKg": 25,
         "shippingUnits": "approx. 8 x 40'HQ"},
        "16,000", "403,200 kg (403.20 MT)",
        {"estimatedPol": "Shekou, Shenzhen", "estimatedPod": "Cat Lai, Ho Chi Minh City"},
        {"leadTime": "25-35 calendar days after receipt of the confirmed purchase order; delivery to the named place per DAP",
         "basis": "TIMING FROM RECEIPT OF CONFIRMED PURCHASE ORDER", "readyDateMode": "relative", "daysAfterReceipt": 25,
         "partialShipment": "Not allowed", "transhipment": "Allowed"},
        {"code": "LC", "lcType": "at sight", "lcOpenedBy": "within 10 days after confirmation of this proforma invoice", "bank": "Advising bank nominated by the Seller; issuing bank must be first-class and acceptable to the Seller",
         "terms": "Irrevocable L/C at sight, at sight payment, opened through a first-class bank acceptable to the Seller, covering 100% of the total value; L/C must reach the Seller within 10 days after PI confirmation.",
         "amountPct": 0, "beneficiary": "[BANK DETAILS TO BE CONFIRMED BY THE SELLER]", "beneficiaryNote": "[BANK DETAILS TO BE CONFIRMED - A/C No. / SWIFT INTENTIONALLY NOT GENERATED]"},
        {"type": "date", "validUntil": "2026-11-10"},
        [{"name": "Origin terminal handling (THC), Shenzhen", "amount": "", "addToTotal": False, "note": "SIMULATED indicative - confirm with forwarder (DAP: seller bears origin + freight to named place)"}],
        doc_summary="DAP example: buyer still clears import and pays duties.",
        exchange_rate={"base": "CNY", "rate": 6.6862, "asOf": "2026-10-16", "source": "ECB reference rate", "state": "reference", "display": "footnote"},
    )


def ex003():
    """FCA Shanghai airport, liquid product (DOP), air, spot with blocked price."""
    return case(
        {"caseId": "EX-003-DOP-AIR-FCA", "product": "Dioctyl Phthalate (DOP)", "destination": "South Korea",
         "scenario": "Air shipment ex-works/airport style quote: FCA Shanghai Pudong airport, DOP packed in 200 L drums; documents for air waybill; sample of 'no unit price confirmed' path (DRAFT with placeholders).",
         "inquiryRef": "INQ-SIM-KR-8812"},
        "QUOTATION", "QT-SIM-2610-003", HUA_BIN,
        {"name": "Hanbit Polymer Air Transport Co. (SIMULATED DEMO)",
         "address": "12F, Simulated Tower, 100 Demo-daero, Gangnam-gu, Seoul 06236, Republic of Korea",
         "country": "South Korea", "contact": "[Simulated Buyer Contact]", "email": "buy@example-demo.invalid",
         "phone": "+82 00 0000 0000 (Simulated)"},
        ("USD", "US Dollar", 2),
        {"code": "FCA", "version": "2020", "namedPlace": "Shanghai Pudong International Airport, Cargo Terminal 2 (Seller premises: Nanshan, Shenzhen)",
         "namedPlaceKind": "airport", "transportMode": "AIR",
         "costAllocation": dict(SEA, originCharges="Buyer", mainFreight="Buyer", insurance="Buyer", destinationCharges="Buyer", importCustoms="Buyer", unloading="Buyer")},
        [item("L1", "Dioctyl Phthalate (DOP), technical grade", "117-81-7",
              "Ester content 99.5% min.; acidity (as KOH) 0.07 mg/g max.; colour (APHA) 30 max.; water 0.1% max.",
              "291732", 40, "DRUM", 0, 200, 230, 200, dg_status="UNKNOWN",
              dg_basis="DRAFT EXAMPLE - dangerous-goods status NOT verified for this example",
              ghs="[DG status to be verified]")],
        {"summary": "200 x 200 L steel drums on pallets (approx. 230 kg gross each), air cargo ready",
         "terms": "UN-approved packaging requirement to be checked by the shipper", "bagNetKg": None,
         "shippingUnits": "air cargo"},
        "200", "46,000 kg (46.00 MT)",
        {"estimatedPol": "PVG - Shanghai Pudong", "estimatedPod": "ICN - Incheon"},
        {"leadTime": "15-20 calendar days after receipt of the confirmed purchase order", "basis": "TIMING FROM PO",
         "readyDateMode": "relative", "daysAfterReceipt": 15, "partialShipment": "Not allowed", "transhipment": "Direct flight only"},
        {"code": "PREPAY", "terms": "30% T/T in advance, 70% against copy of air waybill (simulated terms for demo)",
         "amountPct": 30, "beneficiary": "[TO BE CONFIRMED]", "beneficiaryNote": "[TO BE CONFIRMED BY SELLER]"},
        {"type": "days", "days": 14, "validUntil": ""},
        [],
        doc_summary="DRAFT example — unit price intentionally missing (placeholder path). DG status UNKNOWN blocks formal issue.",
        amount_confirmed=0,
        fatal=[{"code": "DG_UNVERIFIED_EXAMPLE", "where": "items[0].dangerousGoods",
                "msg": "Draft example: DOP DG status must be verified against the SDS before any shipping document is issued."}],
    )


def ex004():
    """CFR Tuticorin, urea in 50 kg PP bags, India, USD, PI type."""
    return case(
        {"caseId": "EX-004-UREA-IND-PI", "product": "Urea (Granular)", "destination": "India",
         "scenario": "Proforma Invoice CFR Tuticorin to an Indian agricultural-input importer; granular urea 50 kg PP bags, shipped in breakbulk/20'FCL.",
         "inquiryRef": "INQ-SIM-IN-4471", "poNo": "PO SIM-IND-00147"},
        "PROFORMA_INVOICE", "PI-SIM-2610-004", HUA_BIN,
        {"name": "Deccan Agri Inputs Pvt. Ltd. (SIMULATED DEMO)",
         "address": "Plot 21, SIPCOT Industrial Complex, Tuticorin 628 008, Tamil Nadu, India",
         "country": "India", "contact": "[Simulated Buyer Contact]", "position": "Head - Procurement",
         "phone": "+91 00 0000 0000 (Simulated)", "email": "imports@example-demo.invalid", "npwp": "GSTIN SIMULATED00A00A0Z0"},
        ("USD", "US Dollar", 2),
        {"code": "CFR", "version": "2020", "namedPlace": "Tuticorin Port, Tamil Nadu, India",
         "namedPlaceKind": "port", "transportMode": "SEA",
         "costAllocation": alloc(mainFreight="Seller")},
        [item("L1", "Urea, Granular (Nitrogen fertiliser, 46% N)", "57-13-6",
              "Total nitrogen 46.0% min. (dry basis); biuret 1.0% max.; moisture 0.5% max.; granular 2-4 mm 90% min.",
              "310210", 25, "MT", 412, 500, 50.4, 50, ghs="")],
        {"summary": "500 bags x 50 kg net in PP/PE laminated bags, 1 x 20'FCL (approx. 25.2 MT gross)",
         "terms": "IMDG: urea is not a dangerous good; check stowage segregation against oxidisers", "bagNetKg": 50,
         "shippingUnits": "1 x 20'FCL"},
        "500", "25,200 kg (25.20 MT)",
        {"estimatedPol": "Zhanjiang, Guangdong", "estimatedPod": "Tuticorin, India"},
        {"leadTime": "20-30 calendar days after receipt of the advance payment and confirmed order", "basis": "TIMING FROM RECEIPT OF PO + ADVANCE",
         "readyDateMode": "relative", "daysAfterReceipt": 20, "partialShipment": "Not allowed", "transhipment": "Allowed"},
        {"code": "PREPAY", "terms": "10% T/T advance upon PI confirmation; 90% by irrevocable L/C at sight opened 15 days before the agreed shipment window.",
         "amountPct": 10, "beneficiary": "[TO BE CONFIRMED]", "beneficiaryNote": "[BANK DETAILS INTENTIONALLY OMITTED IN THIS EXAMPLE]"},
        {"type": "date", "validUntil": "2026-11-05"},
        [{"name": "Marine insurance (not included under CFR - for buyer account)", "amount": "", "addToTotal": False, "note": "CFR excludes insurance; the PI must say so clearly."}],
        doc_summary="PI example: CFR = freight included, insurance excluded. Buyer NPWP-style tax ID (GSTIN) shown on PI.",
        extra={"validityNote": "For PI, the unit price is valid until the stated date; a PI is not a tax invoice."},
    )


def ex005():
    """CIP Duisburg, toluene? Use a non-DG: citric acid monohydrate in 25 kg bags, EUR, multi-modal."""
    return case(
        {"caseId": "EX-005-CITRIC-DEU-CIP", "product": "Citric Acid Monohydrate", "destination": "Germany",
         "scenario": "CIP Duisburg by multimodal route (sea + rail) for a German food-ingredient distributor; EUR quote; premium insurance (ICC A) per CIP.",
         "inquiryRef": "INQ-SIM-DE-1199"},
        "QUOTATION", "QT-SIM-2610-005", HUA_BIN,
        {"name": "Rheinland Food Ingredients GmbH (SIMULATED DEMO)",
         "address": "Industriestrasse 12, 47059 Duisburg, Germany",
         "country": "Germany", "contact": "[Simulated Buyer Contact]", "position": "Einkauf / Purchasing",
         "phone": "+49 000 000000 (Simulated)", "email": "einkauf@example-demo.invalid", "npwp": "USt-IdNr. SIMULATEDDE000000000"},
        ("EUR", "Euro", 2),
        {"code": "CIP", "version": "2020", "namedPlace": "Duesseldorf / Duisburg logistics hub, Germany",
         "namedPlaceKind": "place", "transportMode": "MULTIMODAL",
         "insuranceBasis": "Institute Cargo Clauses (A), 110% of the insured value, in EUR (CIP 2020 requires wider cover; confirm the policy)",
         "costAllocation": alloc(mainFreight="Seller", insurance="Seller", destinationCharges="Seller")},
        [item("L1", "Citric Acid Monohydrate, food grade", "5949-29-1",
              "Assay (dry basis) 99.5-100.5%; water 7.5-9.0%; heavy metals 5 ppm max.; meets E330 / FCC grade; GMO-free",
              "291814", 20, "MT", 1180, 800, 25.15, 25)],
        {"summary": "800 bags x 25 kg net in food-grade PE-lined paper bags, palletised on EUR pallets, shrink-wrapped",
         "terms": "Food-grade hygiene certificate, pallet markings per EU requirements", "bagNetKg": 25,
         "shippingUnits": "1 x 40'HQ"},
        "800", "20,120 kg (20.12 MT)",
        {"estimatedPol": "Shekou, Shenzhen", "estimatedPod": "Hamburg; rail to Duisburg",
         "volumeCheck": None, "quotedVolume": None},
        {"leadTime": "35-45 calendar days after receipt of the confirmed purchase order", "basis": "TIMING FROM PO",
         "readyDateMode": "relative", "daysAfterReceipt": 35, "partialShipment": "Allowed", "transhipment": "Allowed"},
        {"code": "PREPAY", "terms": "50% T/T as advance and 50% before shipment against packing list and pre-shipment inspection report",
         "amountPct": 50, "beneficiary": "[TO BE CONFIRMED]", "beneficiaryNote": "[BANK DETAILS INTENTIONALLY OMITTED IN THIS EXAMPLE]"},
        {"type": "days", "days": 21, "validUntil": ""},
        [{"name": "Marine/transit insurance (ICC A) borne by Seller — already included in the CIP unit price", "amount": "", "addToTotal": False,
          "note": "Do not double-charge insurance: write 'insurance included in unit price' on the face of the document."}],
        doc_summary="CIP example: seller bears freight and ICC(A) insurance to the named place; buyer clears import.",
    )


def ex006():
    """EXW; buyer arranges everything; 'no price' entirely — full placeholder quote."""
    return case(
        {"caseId": "EX-006-EXW-BRA", "product": "Titanium Dioxide (Rutile)", "destination": "Brazil",
         "scenario": "EXW Shenzhen warehouse quote, buyer's forwarder handles all transport. Demonstrates a 'no price yet' draft: only a placeholder quote may be produced.",
         "inquiryRef": "INQ-SIM-BR-0031"},
        "QUOTATION", "QT-SIM-2610-006", HUA_BIN,
        {"name": "Comercio de Insumos Demo Ltda. (SIMULATED DEMO)",
         "address": "Rua Exemplo 100, Galpao 3, Distrito Industrial, Guarulhos, SP 07220-000, Brasil",
         "country": "Brazil", "contact": "[Simulated Buyer Contact]", "email": "compras@example-demo.invalid",
         "phone": "+55 00 0000-0000 (Simulated)"},
        ("USD", "US Dollar", 2),
        {"code": "EXW", "version": "2020", "namedPlace": "Seller's warehouse, Nanshan District, Shenzhen, China",
         "namedPlaceKind": "address", "transportMode": "MULTIMODAL",
         "costAllocation": {k: "Buyer" for k in ["exportPacking", "loadingCharges", "exportCustoms", "originCharges", "mainFreight", "insurance", "destinationCharges", "importCustoms", "unloading"]}},
        [item("L1", "Titanium Dioxide, Rutile grade (chloride process)", "13463-67-7",
              "TiO2 93.0% min.; rutile content 97% min.; TiO2 in hydrochloric bath < 1.8% (typical); surface treated Al2O3/SiO2",
              "320611", 50, "MT", "", 2000, 25.2, 25)],
        {"summary": "2,000 bags x 25 kg net in paper sacks; buyer's forwarder collects from the named place",
         "terms": "Export packing can be upgraded at cost if the buyer requires unmarked cargo", "bagNetKg": 25,
         "shippingUnits": "buyer's forwarder"},
        "2000", "50,400 kg (50.40 MT)",
        {"estimatedPol": "(buyer's choice)", "estimatedPod": "Santos, Brazil"},
        {"leadTime": "Based on stock availability — to be confirmed by the seller in writing", "basis": "TO BE CONFIRMED",
         "readyDateMode": "relative", "daysAfterReceipt": 10, "partialShipment": "Not specified", "transhipment": "Not specified"},
        {"code": "", "terms": "", "amountPct": None, "beneficiary": "", "beneficiaryNote": "[PAYMENT TERMS TO BE CONFIRMED]"},
        {"type": "date", "validUntil": ""},
        [],
        doc_summary="PLACEHOLDER EXAMPLES: unit price and payment terms are missing (draft only). EXW: buyer bears practically all costs and risk.",
        amount_confirmed=0,
    )


def builds():
    return {"ex002_dap_pvc_vietnam": ex002(), "ex003_fca_air_dop_korea_draft": ex003(),
            "ex004_cfr_urea_india_pi": ex004(), "ex005_cip_citric_germany": ex005(), "ex006_exw_tio2_brazil_placeholder": ex006()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "examples"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for name, c in builds().items():
        p = os.path.join(a.out, "case-" + name.replace("_", "-") + ".json")
        io.open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(c, ensure_ascii=False, indent=2) + "\n")
        print("wrote", p)


if __name__ == "__main__":
    main()
