# -*- coding: utf-8 -*-
"""make_letter.py — 由 report.json 生成英文要更正函（只写已确证的问题，不写不可比项）。

  python scripts/make_letter.py --report report.json --out letter.txt [--batch manifest.json]
                                [--signer "公司名" --uscc "统一社会信用代码"]
"""
import argparse, json, os, sys
from datetime import date

FIELD_EN = {
    "批号": "Batch No. differs between documents",
    "付款方式": "Payment terms differ between the Contract, Proforma Invoice and Commercial Invoice",
    "规格/含量": "Specification (purity) differs between documents",
    "数量(MT)": "Quantity differs between documents",
    "金额": "Invoice amount does not equal Unit Price x Quantity",
    "收货人": "Consignee name differs between documents",
    "毛重/净重": "Gross and net weight are not logically consistent",
    "HS 编码": "HS code differs between documents",
    "CAS 号": "CAS number differs between documents",
    "单价": "Unit price differs between documents",
    "币种": "Currency differs between documents",
    "贸易术语": "Incoterm differs between documents",
    "单证齐全性": "Document not received",
}

ACTION_EN = {
    "不一致": "Please issue a corrected document (or a signed amendment) so that this item reads "
              "identically in all documents concerned.",
    "计算错误": "Please re-issue the Commercial Invoice so that Amount equals Unit Price x Quantity, "
                "and confirm the correct total payable.",
    "缺失": "Please send the missing document by courier (original) and by e-mail (scan) so that we "
            "can complete the customs declaration and document presentation.",
}


def en_title(f):
    t = f.get("title", "")
    if "缺少" in t:
        return "Document not received: " + t.split("缺少", 1)[1].strip()
    for k, v in FIELD_EN.items():
        if f.get("field_cn") == k:
            return v
    return f.get("field_cn", "Discrepancy")


def build(report, batch, signer=None, uscc=None, today=None):
    b = batch or report.get("batch", {})
    L = []
    L.append("Subject: Request for Correction of Import Documents — Case %s" % b.get("case_no", ""))
    L.append("Our Ref.: %s    Date: %s" % (b.get("case_no", ""),
                                           today or b.get("letter_date") or date.today().isoformat()))
    L.append("")
    L.append("Dear Sir or Madam,")
    L.append("")
    L.append("Reference is made to our purchase of %s (CAS %s), HS Code %s, quantity %s MT at "
             "USD %s/MT %s, vessel %s, ETD %s, ETA %s."
             % (b.get("product_en", ""), b.get("cas", ""), b.get("hs", ""),
                ("%.3f" % b["quantity_mt"]) if b.get("quantity_mt") else "",
                ("%.2f" % b["unit_price_usd"]) if b.get("unit_price_usd") else "",
                b.get("incoterm", ""), b.get("vessel_voyage", ""), b.get("etd", ""), b.get("eta", "")))
    L.append("")
    L.append("Upon cross-checking the full set of shipping documents, we have identified the following")
    L.append("points that require your correction or confirmation before we can proceed with payment,")
    L.append("customs declaration and vessel arrival arrangements. Please treat this as urgent.")
    L.append("")

    n = 0
    for f in report.get("findings", []):
        if f.get("status") not in ("不一致", "计算错误", "缺失"):
            continue
        if f.get("severity") == "提示":
            continue          # 提示级（如 CFR 下无需保险单）不写入要更正函
        n += 1
        tag = {"不一致": "DISCREPANCY", "计算错误": "ARITHMETIC", "缺失": "MISSING"}[f["status"]]
        L.append("%d. [%s] %s" % (n, tag, en_title(f)))
        if f.get("status") == "缺失":
            L.append("   Basis of requirement: %s" % (f.get("detail", "").strip() or
                                                      "as required for import declaration / L/C presentation"))
        else:
            for l in f.get("locations", []):
                L.append('     - %s%s: "%s"' % (l.get("file", ""),
                                                (", page %s" % l["page"]) if l.get("page") else "",
                                                l.get("value", "")))
        L.append("   Action requested: " + ACTION_EN.get(f["status"], "Please correct as indicated."))
        L.append("")

    for p in report.get("pending", []):
        n += 1
        L.append("%d. [TO BE CONFIRMED] %s" % (n, en_title(p)))
        for l in p.get("locations", []):
            L.append('     - %s%s: "%s"' % (l.get("file", ""),
                                            (", page %s" % l["page"]) if l.get("page") else "",
                                            l.get("value", "")))
        L.append("   Action requested: Please confirm in writing which route applies to this shipment, so")
        L.append("   that we may align our payment instruction and advise our bank accordingly.")
        L.append("")

    L.append("Please note that no items that are legitimately different by the nature of the documents")
    L.append("(e.g. Proforma Invoice versus Commercial Invoice amounts, standard-shipment data in")
    L.append("Section 14 of the SDS) have been raised in this letter.")
    L.append("")
    L.append("Please return the corrected documents within three (3) working days, quoting our")
    L.append("reference number above. Kindly reply to this e-mail with the amended files attached.")
    L.append("")
    L.append("Yours faithfully,")
    L.append("______________________")
    L.append(signer or b.get("buyer", ""))
    if uscc or b.get("uscc"):
        L.append("USCC: %s" % (uscc or b.get("uscc")))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--out", default="letter.txt")
    ap.add_argument("--batch", default=None, help="manifest.json（取批次信息）")
    ap.add_argument("--signer", default=None)
    ap.add_argument("--uscc", default=None)
    a = ap.parse_args()
    rep = json.load(open(a.report, encoding="utf-8"))
    batch = json.load(open(a.batch, encoding="utf-8")).get("batch", {}) if a.batch else rep.get("batch", {})
    txt = build(rep, batch, a.signer, a.uscc)
    open(a.out, "w", encoding="utf-8").write(txt + "\n")
    print("wrote", a.out, len(txt), "chars")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
