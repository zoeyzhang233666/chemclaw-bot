#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render a confirmed case JSON into an English Quotation / Proforma Invoice DOCX (+PDF).

All texts come from the case file. Missing commercial values are rendered as visibly marked
placeholders - nothing is ever invented.

Usage:
  python scripts/build_docx.py --case case.json --out out.docx --doc-type QUOTATION --pdf
"""

_CHEMCLAW_ROOT = next(parent for parent in __import__('pathlib').Path(__file__).resolve().parents if (parent / 'runtime/deliver.mjs').is_file())
import argparse, io, json, os, subprocess, sys

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from engine_bridge import validate  # noqa: E402

NODE = __import__('sys').executable
LO_CLI = os.environ.get("QUOTE_LO_CLI") or (
    str(_CHEMCLAW_ROOT / 'runtime/office-cli.py'))

SERIF, SANS = "Georgia", "Arial"
NAVY, GOLD, MUTED, LINE = "1B3A5B", "B58B3A", "6B7A90", "D8DEE6"
DANGER = "B42318"


def sanitize(obj):
    """Replace typographic glyphs that LibreOffice cannot render reliably in PDF."""
    if isinstance(obj, str):
        return (obj.replace(chr(0x2014), " - ").replace(chr(0x2013), "-")
                   .replace(chr(0x2265), ">=").replace(chr(0x2264), "<=")
                   .replace(chr(0x2248), "approx.").replace(chr(0x00b5), "u"))
    if isinstance(obj, list):
        return [sanitize(x) for x in obj]
    if isinstance(obj, dict):
        return dict((k, sanitize(v)) for k, v in obj.items())
    return obj


# ------------------------------------------------------------------ primitives
def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    el = OxmlElement("w:shd")
    el.set(qn("w:val"), "clear"); el.set(qn("w:color"), "auto"); el.set(qn("w:fill"), fill)
    tcPr.append(el)


def _borders(table, color=None, sz=4):
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement("w:" + edge)
        if color:
            e.set(qn("w:val"), "single"); e.set(qn("w:sz"), str(sz)); e.set(qn("w:color"), color)
        else:
            e.set(qn("w:val"), "none"); e.set(qn("w:sz"), "0")
        borders.append(e)
    tblPr.append(borders)


def no_borders(table):
    _borders(table, None)


def row_borders(table, color=LINE, sz=4):
    _borders(table, color, sz)


def cell_margins(table, top=40, left=80, bottom=40, right=80):
    tblPr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for side, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        e = OxmlElement("w:" + side); e.set(qn("w:w"), str(val)); e.set(qn("w:type"), "dxa")
        mar.append(e)
    tblPr.append(mar)


def set_col_widths(table, widths_cm):
    table.autofit = False
    for row in table.rows:
        for i, w in enumerate(widths_cm):
            if i < len(row.cells):
                row.cells[i].width = Cm(w)
    grid = table._tbl.find(qn("w:tblGrid"))
    if grid is not None:
        for i, gc in enumerate(grid.findall(qn("w:gridCol"))):
            if i < len(widths_cm):
                gc.set(qn("w:w"), str(int(widths_cm[i] * 567)))


def run(p, text, size=8.5, bold=False, color=None, font=SERIF, italic=False):
    r = p.add_run(text)
    r.font.size = Pt(size); r.bold = bold; r.italic = italic; r.font.name = font
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    if color:
        r.font.color.rgb = RGBColor.from_string(color)
    return r


def para(container, text="", size=8.5, bold=False, color=None, font=SERIF, align=None, space_after=0, italic=False):
    p = container.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(0); pf.space_after = Pt(space_after); pf.line_spacing = 1.12
    if align == "r":
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    elif align == "c":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "j":
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if text:
        run(p, text, size, bold, color, font, italic)
    return p


def cell_text(cell, text, size=8.5, bold=False, color=None, font=SERIF, align=None, clear=True):
    if clear:
        cell.text = ""
        p = cell.paragraphs[0]
    else:
        p = cell.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(0); pf.space_after = Pt(0); pf.line_spacing = 1.1
    if align == "r":
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    elif align == "c":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if text:
        run(p, text, size, bold, color, font)
    return p


def compact(doc):
    """Keep table rows from splitting across pages."""
    for t in doc.tables:
        for r in t.rows:
            trPr = r._tr.get_or_add_trPr()
            trPr.append(OxmlElement("w:cantSplit"))


def watermark(section, text):
    """Light diagonal watermark drawn as a page-anchored shape behind the text."""
    hdr = section.header
    hdr.is_linked_to_previous = False
    p = hdr.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = Pt(1)
    run(p, "", 1)
    sp = hdr.add_paragraph()
    sp.paragraph_format.space_after = Pt(0)
    sp.add_run().add_break(WD_BREAK.LINE)
    xml = (
        '<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
        '<w:rPr><w:noProof/></w:rPr>'
        '<w:drawing><wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="1" '
        'behindDoc="1" locked="0" layoutInCell="1" allowOverlap="1">'
        '<wp:simplePos x="0" y="0"/>'
        '<wp:positionH relativeFrom="page"><wp:posOffset>1244600</wp:posOffset></wp:positionH>'
        '<wp:positionV relativeFrom="page"><wp:posOffset>4000000</wp:posOffset></wp:positionV>'
        '<wp:extent cx="4200000" cy="900000"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
        '<wp:wrapNone/><wp:docPr id="91001" name="Watermark"/>'
        '<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
        '<wps:wsp><wps:cNvSpPr txBox="1"/><wps:spPr>'
        '<a:xfrm rot="1905000"><a:off x="0" y="0"/><a:ext cx="4200000" cy="800000"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/>'
        '<a:ln w="19050"><a:solidFill><a:srgbClr val="D9DFE8"/></a:solidFill></a:ln>'
        '</wps:spPr><wps:txbx><w:txbxContent>'
        '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
        '<w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:b/><w:color w:val="CFD7E1"/>'
        '<w:sz w:val="44"/></w:rPr><w:t xml:space="preserve">' + text + '</w:t></w:r></w:p>'
        '</w:txbxContent></wps:txbx><wps:bodyPr rot="0" vert="horz" wrap="square" lIns="0" tIns="0" '
        'rIns="0" bIns="0" anchor="ctr" anchorCtr="0"><a:noAutofit/></wps:bodyPr></wps:wsp>'
        '</a:graphicData></a:graphic></wp:anchor></w:drawing></w:r>'
    )
    p._p.addnext(parse_xml(xml))


def missing(label):
    return "[ %s ]" % label


# ------------------------------------------------------------------ build
def build(case, out_path, doc_type=None, pdf=False, accent=NAVY):
    case = sanitize(case)
    E = validate(case, doc_type)
    is_pi = (doc_type or case.get("docType") or "QUOTATION") == "PROFORMA_INVOICE"
    cur = (case.get("currency") or {}).get("code", "")
    seller = case.get("seller") or {}
    buyer = case.get("buyer") or {}
    tt = case.get("tradeTerm") or {}
    pay = case.get("payment") or {}
    delivery = case.get("delivery") or {}
    packing = case.get("packing") or {}
    freight = case.get("freight") or {}
    bank = case.get("bank") or {}

    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = SERIF
    st.font.size = Pt(8.5)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")

    sec = doc.sections[0]
    sec.page_width = Mm(210); sec.page_height = Mm(297)
    sec.top_margin = Mm(10); sec.bottom_margin = Mm(8)
    sec.left_margin = Mm(14); sec.right_margin = Mm(14)
    sec.header_distance = Mm(6); sec.footer_distance = Mm(4)

    simulated = "SIMULATED" in json.dumps(case.get("meta", {})) or "SIMULATED" in seller.get("name", "")
    if simulated:
        watermark(sec, "SIMULATED DEMO / NOT FOR TRADE USE")

    footer = sec.footer.paragraphs[0]
    sec.footer.is_linked_to_previous = False
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run(footer, "%s   |   %s   |   " % (seller.get("name", ""), case["reference"]["quoteNo"]), 6.8, False, MUTED, SANS)
    fld = OxmlElement("w:fldSimple"); fld.set(qn("w:instr"), "PAGE")
    footer._p.append(fld)
    run(footer, "   |   " + ("Original" if E["state"] == "FORMAL" else "Draft - not a valid offer"), 6.8, False, MUTED, SANS)

    # ---- header
    t = doc.add_table(rows=1, cols=3); no_borders(t); cell_margins(t, 0, 0, 0, 120)
    set_col_widths(t, [2.6, 10.4, 5.2])
    c0, c1, c2 = t.cell(0, 0), t.cell(0, 1), t.cell(0, 2)
    c0.text = ""
    cell_text(c0, seller.get("logoText") or "LOGO", 9, True, GOLD, SANS)
    cell_text(c0, "chemical export", 6.4, False, MUTED, SANS, clear=False)
    c1.text = ""
    cell_text(c1, seller.get("name") or missing("SELLER NAME"), 11.5, True, accent, SERIF)
    for line in [seller.get("address", ""),
                 "Tel: %s   |   E-mail: %s" % (seller.get("phone", ""), seller.get("email", "")),
                 "Tax ID / USCI: %s" % (seller.get("taxId") or "-")]:
        if line and line.strip(" |"):
            cell_text(c1, line, 7.4, False, "33465E", SERIF, clear=False)
    c2.text = ""
    cell_text(c2, "PROFORMA INVOICE" if is_pi else "QUOTATION", 14.5, True, accent, SERIF, align="r")
    cell_text(c2, ("形式发票 / Proforma Invoice" if is_pi else "报价单 / Commercial offer"), 7.2, False, MUTED, SANS, align="r", clear=False)
    cell_text(c2, "No. " + case["reference"]["quoteNo"], 8.2, True, None, SERIF, align="r", clear=False)
    cell_text(c2, "Date: " + (case.get("issueDate") or missing("ISSUE DATE")), 7.6, False, None, SERIF, align="r", clear=False)

    para(doc, "", 2)
    rule = doc.add_table(rows=1, cols=1); no_borders(rule)
    shade(rule.cell(0, 0), accent)
    cell_text(rule.cell(0, 0), "", 2)
    rule.rows[0].height = Pt(2)

    # ---- parties
    para(doc, "", 2)
    t = doc.add_table(rows=1, cols=2); no_borders(t); cell_margins(t, 40, 100, 40, 100)
    set_col_widths(t, [9.1, 9.1])
    parties = [("SELLER / EXPORTER", seller),
               ("BUYER / APPLICANT / CONSIGNEE" if is_pi else "BUYER / CONSIGNEE", buyer)]
    for i, (title, party) in enumerate(parties):
        c = t.cell(0, i); c.text = ""
        cell_text(c, title, 6.6, True, MUTED, SANS)
        cell_text(c, party.get("name") or missing("PARTY NAME"), 9.2, True, accent, SERIF, clear=False)
        for line in [party.get("address", ""), party.get("country", ""),
                     ("Attn: %s %s" % (party.get("contact", ""), party.get("position", ""))).strip(),
                     ("Tel: " + party.get("phone", "")).strip(": "),
                     ("E-mail: " + party.get("email", "")).strip(": ")]:
            if line and line.strip(": "):
                cell_text(c, line, 7.4, False, "33465E", SERIF, clear=False)
        taxid = party.get("npwp") or party.get("taxId")
        if taxid:
            cell_text(c, ("NPWP / Tax ID: " if party.get("npwp") else "Tax ID: ") + taxid, 7.4, False, "33465E", SERIF, clear=False)

    # ---- meta strip
    para(doc, "", 2)
    t = doc.add_table(rows=2, cols=4); no_borders(t); cell_margins(t, 40, 100, 40, 100)
    set_col_widths(t, [4.6, 4.6, 4.6, 4.4])
    vals = [("INCOTERMS " + str(tt.get("version") or "2020"), E.get("tradeTermText") or missing("TRADE TERM")),
            ("CURRENCY", cur or missing("CURRENCY")),
            ("PROFORMA VALID UNTIL" if is_pi else "OFFER VALID UNTIL", E.get("validUntil") or missing("VALIDITY")),
            ("PAYMENT TERMS", pay.get("terms") or missing("PAYMENT TERMS"))]
    for i, (k, v) in enumerate(vals):
        shade(t.cell(0, i), "F4F6F9")
        cell_text(t.cell(0, i), k, 6.2, True, MUTED, SANS)
        cell_text(t.cell(1, i), v, 7.4, i == 0, None, SERIF)
        for r_ in range(2):
            t.cell(r_, i).vertical_alignment = WD_ALIGN_VERTICAL.TOP

    # ---- items
    para(doc, "", 2)
    cols = [0.9, 4.3, 4.9, 2.6, 1.6, 2.2, 2.6]
    t = doc.add_table(rows=1, cols=len(cols)); row_borders(t); cell_margins(t, 40, 60, 40, 60)
    set_col_widths(t, cols)
    heads = ["No.", "DESCRIPTION OF GOODS", "SPECIFICATION", "QUANTITY", "UNIT",
             "UNIT PRICE (%s)" % (cur or "-"), "AMOUNT (%s)" % (cur or "-")]
    for i, h in enumerate(heads):
        shade(t.cell(0, i), accent)
        cell_text(t.cell(0, i), h, 6.6, True, "FFFFFF", SANS, align="c" if i != 1 else None)
    for n, it in enumerate(case.get("items") or [], 1):
        r_ = t.add_row()
        cell_text(r_.cells[0], str(n), 8, False, None, SERIF, align="c")
        cell_text(r_.cells[1], it.get("name") or missing("PRODUCT NAME"), 8.2, True, None, SERIF)
        if it.get("cas"):
            cell_text(r_.cells[1], "CAS No.: " + it["cas"], 7, False, "33465E", SERIF, clear=False)
        if it.get("hsCode"):
            cell_text(r_.cells[1], "HS code: " + str(it["hsCode"]) +
                      ("   |   Origin: " + it["origin"] if it.get("origin") else ""), 7, False, MUTED, SERIF, clear=False)
        cell_text(r_.cells[2], it.get("spec") or missing("SPECIFICATION"), 7.2)
        dg = it.get("dangerousGoods") or {}
        if dg.get("status") == "DG":
            cell_text(r_.cells[2], "DG: UN %s, class %s, PG %s" % (dg.get("unNumber", "-"), dg.get("class", "-"),
                                                                  dg.get("packingGroup", "-")), 6.8, True, DANGER, SERIF, clear=False)
        elif dg.get("status") == "UNKNOWN":
            cell_text(r_.cells[2], "DG status: TO BE VERIFIED", 6.8, True, DANGER, SERIF, clear=False)
        cell_text(r_.cells[3], str(it.get("quantity", "?")), 8, True, None, SERIF, align="r")
        cell_text(r_.cells[4], it.get("unit") or "", 8, False, None, SERIF, align="c")
        price = it.get("unitPrice")
        has_price = price not in ("", None)
        cell_text(r_.cells[5], ("%s" % price) if has_price else missing("PRICE"),
                  8 if has_price else 7.2, False, None if has_price else DANGER, SERIF, align="r")
        amt = (E.get("lineAmounts") or {}).get(str(it.get("id")) or "")
        cell_text(r_.cells[6], amt if amt else "[ PENDING PRICE ]", 8, True, None if amt else DANGER, SERIF, align="r")

    r_ = t.add_row()
    for i in range(len(cols)):
        shade(r_.cells[i], "F4F6F9")
    r_.cells[0].merge(r_.cells[5])
    cell_text(r_.cells[0], "SUB-TOTAL OF GOODS (%s)" % (cur or "-"), 7.6, True, MUTED, SANS, align="r")
    cell_text(r_.cells[6], E.get("subtotalFmt") or "[ PENDING PRICE ]", 8.4, True, None, SERIF, align="r")
    for ch in (case.get("charges") or []):
        if ch.get("amount") in ("", None) or ch.get("addToTotal") is False:
            continue
        r_ = t.add_row()
        r_.cells[0].merge(r_.cells[5])
        cell_text(r_.cells[0], ch.get("name", "Charge"), 7.4, False, None, SERIF, align="r")
        cell_text(r_.cells[6], "{:,.2f}".format(float(ch["amount"])), 8, False, None, SERIF, align="r")
    r_ = t.add_row()
    for i in range(len(cols)):
        shade(r_.cells[i], accent)
    r_.cells[0].merge(r_.cells[5])
    cell_text(r_.cells[0], "TOTAL (%s)" % (cur or "-"), 8.2, True, "FFFFFF", SANS, align="r")
    cell_text(r_.cells[6], E.get("totalFmt") or "[ PENDING PRICE ]", 9.2, True, "FFFFFF", SERIF, align="r")

    # ---- amount in words
    para(doc, "", 1)
    t = doc.add_table(rows=1, cols=1); row_borders(t, GOLD, 6); cell_margins(t, 40, 100, 40, 100)
    p = cell_text(t.cell(0, 0), "", 8.6)
    run(p, "TOTAL AMOUNT IN WORDS:  ", 6.8, True, MUTED, SANS)
    run(p, E.get("words") or "AMOUNT IN WORDS UNAVAILABLE - UNIT PRICE MISSING", 8.6, True, None, SERIF)

    # ---- terms grid
    para(doc, "", 2)
    pkgs = ""
    if case.get("totalPackageCount"):
        pkgs = "{:,}".format(int(str(case["totalPackageCount"]).replace(",", "")))
    terms = [
        ("TRADE TERM", E.get("tradeTermText") or missing("TRADE TERM")),
        ("PARTIAL SHIPMENT", delivery.get("partialShipment") or "-"),
        ("PACKING", packing.get("summary") or missing("PACKING")),
        ("TRANSHIPMENT", delivery.get("transhipment") or "-"),
        ("TOTAL PACKAGES", (pkgs or missing("TBC")) + "   |   GROSS WEIGHT: " + (case.get("totalGrossWeight") or missing("TBC"))),
        ("LEAD TIME", delivery.get("leadTime") or missing("DELIVERY")),
        ("PAYMENT", pay.get("terms") or missing("PAYMENT TERMS")),
        ("ORIGIN / LOADING", "%s   |   DESTINATION: %s" % (freight.get("estimatedPol") or "-", freight.get("estimatedPod") or "-")),
    ]
    t = doc.add_table(rows=0, cols=4); row_borders(t); cell_margins(t, 40, 80, 40, 80)
    set_col_widths(t, [3.2, 6.0, 3.2, 5.8])
    for i in range(0, len(terms), 2):
        r_ = t.add_row()
        for j, (k, v) in enumerate(terms[i:i + 2]):
            shade(r_.cells[j * 2], "F4F6F9")
            cell_text(r_.cells[j * 2], k, 6.4, True, MUTED, SANS)
            cell_text(r_.cells[j * 2 + 1], v, 7.4)

    # ---- bank block
    para(doc, "", 2)
    t = doc.add_table(rows=1, cols=1); row_borders(t, LINE); cell_margins(t, 40, 100, 40, 100)
    c = t.cell(0, 0)
    cell_text(c, "BENEFICIARY BANK DETAILS", 6.4, True, MUTED, SANS)
    show_bank = bank.get("display") is True and bank.get("sanitized") is not True and bank.get("detailsConfirmed") is True
    if show_bank:
        for line in [bank.get("bankName", ""), "Account name: " + bank.get("accountName", ""),
                     "Account No.: " + bank.get("accountNumber", ""), "SWIFT/BIC: " + bank.get("swift", "")]:
            if line.strip(": "):
                cell_text(c, line, 7.6, False, None, SERIF, clear=False)
    else:
        shade(c, "FFF5F4")
        p = cell_text(c, "", 7.6, clear=False)
        run(p, bank.get("note") or "[ BANK DETAILS TO BE CONFIRMED BY THE SELLER - A/C No. / SWIFT INTENTIONALLY NOT GENERATED ]",
            7.6, True, DANGER, SERIF)

    # ---- notes / compliance / transport
    para(doc, "", 2)
    t = doc.add_table(rows=1, cols=2); no_borders(t); cell_margins(t, 0, 0, 0, 120)
    set_col_widths(t, [8.9, 8.9])
    left = t.cell(0, 0); left.text = ""
    cell_text(left, "NOTES & CONDITIONS", 6.8, True, MUTED, SANS)
    notes = ["Prices are firm until %s and subject to written confirmation by the Seller." % (E.get("validUntil") or "the validity stated")]
    for it in case.get("items", []):
        ghs = (it.get("dangerousGoods") or {}).get("ghsSummary")
        if ghs:
            notes.append("%s - %s. Handle with care: use eye protection; avoid dust generation." % (it.get("name"), ghs))
    if case.get("documents"):
        notes.append("Documents: " + "; ".join(d["name"] for d in case["documents"]) + ".")
    fx = (case.get("currency") or {}).get("exchangeRate") or {}
    if fx.get("rate") and fx.get("display") != "none":
        notes.append("Currency reference: 1 %s = %s %s as of %s (%s); prices are fixed in %s." % (
            fx.get("base"), fx.get("rate"), cur, fx.get("asOf", "n/a"),
            "confirmed" if fx.get("state") == "confirmed" else "reference only", cur))
    for i, n in enumerate(notes, 1):
        p = left.add_paragraph()
        p.paragraph_format.space_after = Pt(0.5)
        p.paragraph_format.line_spacing = 1.03
        p.paragraph_format.left_indent = Cm(0.42)
        p.paragraph_format.first_line_indent = Cm(-0.42)
        run(p, "%d.  " % i, 7.5)
        run(p, n, 7.5)
    right = t.cell(0, 1); right.text = ""
    cell_text(right, "DOCUMENTS & COMPLIANCE", 6.8, True, MUTED, SANS)
    for n in ["HS code shown is for reference; the exporter/broker confirms the final classification.",
              "Import duties, VAT or destination charges are for the Buyer unless stated otherwise.",
              "Quality: Certificate of Analysis per shipment; SDS accompanies the goods."]:
        p = right.add_paragraph()
        p.paragraph_format.space_after = Pt(0.2)
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.left_indent = Cm(0.3)
        p.paragraph_format.first_line_indent = Cm(-0.3)
        run(p, "-  ", 7.0)
        run(p, n, 7.0)
    dg_status = [(it.get("dangerousGoods") or {}).get("status") for it in case.get("items", [])]
    if dg_status and all(s == "NOT_REGULATED" for s in dg_status):
        p = right.add_paragraph(); p.paragraph_format.space_before = Pt(3)
        run(p, "TRANSPORT: ", 6.6, True, NAVY, SANS)
        run(p, "Outside DG scope per current supplier SDS; standard export packing; SDS copy in shipment documents.", 7.0)
    elif any(s == "DG" for s in dg_status):
        p = right.add_paragraph(); p.paragraph_format.space_before = Pt(3)
        run(p, "DANGEROUS GOODS: ", 6.8, True, DANGER, SANS)
        run(p, "UN/class/PG as stated; UN-approved packaging and DG documentation required.", 7.5)

    # ---- signature
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    t = doc.add_table(rows=1, cols=2); no_borders(t); cell_margins(t, 0, 0, 0, 200)
    set_col_widths(t, [8.9, 8.9])
    sigs = [("CONFIRMED BY THE BUYER" if is_pi else "ACCEPTED BY THE BUYER", ""),
            ("FOR AND ON BEHALF OF THE SELLER", (case.get("review") or {}).get("signatoryTitle") or "Export Sales Manager")]
    for i, (role, extra) in enumerate(sigs):
        c = t.cell(0, i); c.text = ""
        p = c.paragraphs[0]
        p.paragraph_format.space_before = Pt(0); p.paragraph_format.space_after = Pt(0)
        run(p, "Signature: .......................................  Dated: ................", 8)
        cell_text(c, "Name: ______________________   Position: " + (extra or "____________________"), 7.6, clear=False)
        p3 = c.add_paragraph(); p3.paragraph_format.space_before = Pt(0)
        run(p3, role + " (AUTHORISED SIGNATURE)", 6.4, True, MUTED, SANS)

    compact(doc)
    doc.save(out_path)
    result = {"docx": out_path, "docType": "PROFORMA_INVOICE" if is_pi else "QUOTATION",
              "state": E["state"], "errors": len(E["errors"]), "warnings": len(E["warnings"]),
              "total": E.get("totalFmt"), "words": E.get("words"),
              "placeholders": E.get("placeholderCount", 0)}
    if pdf:
        pdf_path = os.path.splitext(out_path)[0] + ".pdf"
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        r = subprocess.run([NODE, LO_CLI, "convert", "--input", out_path, "--output", pdf_path],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        result["pdf"] = pdf_path if os.path.exists(pdf_path) else None
        if not result.get("pdf"):
            result["pdf_error"] = (r.stderr or r.stdout)[:500]
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--doc-type", default="")
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--accent", default=NAVY)
    a = ap.parse_args()
    case = json.loads(io.open(a.case, encoding="utf-8-sig").read())
    res = build(case, a.out, a.doc_type or None, a.pdf, a.accent)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
