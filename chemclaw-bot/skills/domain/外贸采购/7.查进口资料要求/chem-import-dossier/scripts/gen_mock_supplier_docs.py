#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_mock_supplier_docs.py — 生成**模拟**供应商文件（演示用）

【重要】所有文件均为虚构，用于演示「上传 → 提取字段 → 核对要件 → 交叉一致性」的流程。
        供应商名称、电话、批号、金额、检测数据全部为编造，不含任何真实企业信息。
        每份文件页眉都有「模拟件」水印与声明。

输出：examples/h2o2-kr-30/mock_supplier_docs/
      01_SDS_EN_mock.pdf          （英文 SDS，故意缺版本号与稳定剂明细）
      02_COA_mock.pdf             （COA，故意缺铁/TOC 检测项与方法编号）
      03_PI_mock.pdf              （PI，故意 CIF/FOB 混用、缺 HS 与港口）
      04_Label_EN_mock.svg        （英文标签，故意无中文要素与中文应急电话）
      05_TDS_mock.md              （TDS 骨架，作为「建议」件的对照）

用法： python scripts/gen_mock_supplier_docs.py [--outdir DIR]
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MOCK_WARN = ("[MOCK DOCUMENT] Simulated record for workflow demonstration only. "
             "NOT a real supplier document. Company names, batch numbers, prices and "
             "test data are entirely fictional.  (Chinese note: 本件为模拟样例，非真实供应商文件)")

SUPPLIER = "HANWOO CHEMICAL CO., LTD. (FICTIONAL)"
ADDR = "12, Namhang-ro, Yeongdo-gu, Busan, Republic of Korea (fictional address)"
TEL = "+82-51-000-0000 (fictional)"
EMAIL = "sales@example-kr-fictional.test"


# ============================================================ PDF 极简写出
def _pdf_escape(s: str) -> str:
    return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def write_pdf(path: str, pages: list[list[tuple[str, int, str]]], title: str):
    """pages: [[(text, font_size, style), ...], ...]  style: 'B'|''|'M'"""
    objs: list[bytes] = []

    def add(b: bytes) -> int:
        objs.append(b)
        return len(objs)

    # 字体：Helvetica（不含中文字形，因此正文用英文 + 罗马字标注；中文用图像替代不现实，改为英文+拼音式说明）
    f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    f3 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")

    content_ids = []
    for pg in pages:
        ops = []
        y = 800
        for text, size, style in pg:
            font = {"B": "F2", "M": "F3"}.get(style, "F1")
            if text == "":
                y -= size
                continue
            ops.append(f"BT /{font} {size} Tf 1 0 0 1 48 {y} Tm ({_pdf_escape(text)}) Tj ET")
            y -= size + 5
        stream = "\n".join(ops).encode("latin-1", "replace")
        cid = add(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
        content_ids.append(cid)

    page_ids = []
    pages_obj_index = len(objs)  # 占位
    for cid in content_ids:
        pid = add(
            b"<< /Type /Page /Parent " + str(pages_obj_index + len(content_ids) + 1).encode() +
            b" 0 R /MediaBox [0 0 595 842] /Contents " + str(cid).encode() + b" 0 R "
            b"/Resources << /Font << /F1 " + str(f1).encode() + b" 0 R /F2 " + str(f2).encode() +
            b" 0 R /F3 " + str(f3).encode() + b" 0 R >> >> >>"
        )
        page_ids.append(pid)

    kids = " ".join(f"{p} 0 R" for p in page_ids)
    pages_id = add(b"<< /Type /Pages /Count " + str(len(page_ids)).encode() + b" /Kids [" +
                   kids.encode() + b"] >>")
    cat_id = add(b"<< /Type /Catalog /Pages " + str(pages_id).encode() + b" 0 R >>")
    info_id = add(b"<< /Title (" + _pdf_escape(title).encode("latin-1", "replace") +
                  b") /Producer (chem-import-dossier mock generator) >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, b in enumerate(objs, start=1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + b + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (b"trailer\n<< /Size " + str(len(objs) + 1).encode() + b" /Root " +
            str(cat_id).encode() + b" 0 R /Info " + str(info_id).encode() + b" 0 R >>\nstartxref\n" +
            str(xref).encode() + b"\n%%EOF\n")
    with open(path, "wb") as f:
        f.write(bytes(out))


def banner(extra_note=""):
    return [
        ("*** " + MOCK_WARN + " ***", 8, "M"),
        ("=" * 96, 8, "M"),
    ] + ([("NOTE: " + extra_note, 8, "M")] if extra_note else [])


# ============================================================ 1. SDS
def gen_sds(path):
    p1 = banner() + [
        ("", 6, ""),
        ("SAFETY DATA SHEET", 20, "B"),
        ("(In accordance with GHS / Regulation (EC) No 1907/2006 format)", 9, ""),
        ("", 8, ""),
        ("Product name            : HYDROGEN PEROXIDE AQUEOUS SOLUTION 30%", 10, ""),
        ("Trade name              : HANWOO H2O2 30", 10, ""),
        ("CAS No.                 : 7722-84-1 (hydrogen peroxide)", 10, ""),
        ("UN No.                  : 2014", 10, ""),
        ("Supplier                : " + SUPPLIER, 10, ""),
        ("Address                 : " + ADDR, 10, ""),
        ("Telephone               : " + TEL, 10, ""),
        ("Emergency telephone     : " + TEL + "  (English only)", 10, ""),
        ("Revision date           : (not stated)", 10, "B"),
        ("Version                 : (not stated)", 10, "B"),
        ("", 6, ""),
        ("--- SECTION 1: IDENTIFICATION OF THE SUBSTANCE/MIXTURE AND OF THE COMPANY ---", 10, "B"),
        ("Product identifier      : Hydrogen peroxide aqueous solution 30%", 9, ""),
        ("Relevant identified use: Industrial use, metal surface treatment,", 9, ""),
        ("                          electronics wet process (diluted on site)", 9, ""),
        ("Uses advised against   : Food, pharmaceutical, medical disinfection", 9, ""),
        ("", 4, ""),
        ("--- SECTION 2: HAZARDS IDENTIFICATION ---", 10, "B"),
        ("GHS classification      : Oxidizing liquid, Category 2", 9, ""),
        ("                          Acute toxicity (oral), Category 4", 9, ""),
        ("                          Skin irritation, Category 2", 9, ""),
        ("                          Serious eye damage, Category 1", 9, ""),
        ("                          STOT single exposure, Category 3 (respiratory)", 9, ""),
        ("Pictograms              : GHS03 (flame over circle), GHS05 (corrosion)", 9, ""),
        ("Signal word             : DANGER", 9, "B"),
        ("Hazard statements       : H272, H302, H315, H318, H335", 9, ""),
        ("Precautionary statements: P210, P220, P280, P305+P351+P338, P310", 9, ""),
    ]
    p2 = banner() + [
        ("", 4, ""),
        ("--- SECTION 3: COMPOSITION / INFORMATION ON INGREDIENTS ---", 10, "B"),
        ("Chemical name                CAS No.       Concentration    Classification", 9, "M"),
        ("Hydrogen peroxide            7722-84-1     30.0 % (w/w)     Oxid. Liq. 2; Acute Tox.4;", 9, "M"),
        ("                                                            Skin Irrit.2; Eye Dam.1; STOT SE3", 9, "M"),
        ("Phosphate based stabiliser   (not given)   < 0.1 %          Not classified", 9, "M"),
        ("Water                        7732-18-5      Balance          Not classified", 9, "M"),
        ("", 4, ""),
        ("NOTE (for demonstration): the stabiliser is described only by generic class.", 8, "M"),
        ("Exact chemical name, CAS number and precise percentage are not disclosed", 8, "M"),
        ("in this mock document - this is intentionally left incomplete.", 8, "M"),
        ("", 6, ""),
        ("--- SECTION 9: PHYSICAL AND CHEMICAL PROPERTIES ---", 10, "B"),
        ("Appearance              : Colourless, clear liquid", 9, ""),
        ("Odour                   : Slightly pungent", 9, ""),
        ("pH                      : 2 - 4", 9, ""),
        ("Melting / freezing point: approx. -25 degC", 9, ""),
        ("Boiling point           : approx. 106 degC", 9, ""),
        ("Density                 : approx. 1.11 g/cm3 at 20 degC", 9, ""),
        ("Water solubility        : Fully miscible", 9, ""),
        ("", 6, ""),
        ("--- SECTION 14: TRANSPORT INFORMATION ---", 10, "B"),
        ("UN number               : 2014", 9, ""),
        ("UN proper shipping name : HYDROGEN PEROXIDE, AQUEOUS SOLUTION, with not less than", 9, ""),
        ("                          20% but not more than 60% hydrogen peroxide", 9, ""),
        ("                          (stabilized as necessary)", 9, ""),
        ("Transport hazard class  : 5.1", 9, ""),
        ("Subsidiary hazard      : 8", 9, ""),
        ("Packing group           : II", 9, ""),
        ("Environmental hazards   : Not a marine pollutant", 9, ""),
        ("IMDG / ADR / IATA       : Refer to current modal regulations", 9, ""),
        ("", 6, ""),
        ("--- SECTIONS 4,5,6,7,8,10,11,12,13,15,16 ---", 10, "B"),
        ("Present in original document; omitted here for brevity of the mock file.", 9, ""),
        ("", 6, ""),
        ("*** END OF MOCK SAFETY DATA SHEET ***  This document is fictional and", 8, "M"),
        ("was generated for workflow demonstration only. ***", 8, "M"),
    ]
    write_pdf(path, [p1, p2], "MOCK SDS - Hydrogen Peroxide 30% (fictional)")


# ============================================================ 2. COA
def gen_coa(path):
    pg = banner() + [
        ("", 6, ""),
        ("CERTIFICATE OF ANALYSIS", 20, "B"),
        ("", 6, ""),
        ("Supplier        : " + SUPPLIER, 10, ""),
        ("Product         : HYDROGEN PEROXIDE AQUEOUS SOLUTION 30%", 10, ""),
        ("CAS No.         : 7722-84-1", 10, ""),
        ("Batch No.       : L2609A", 10, "B"),
        ("Batch size      : 20,000 kg", 10, ""),
        ("Manufacture date: 2026-09-28", 10, ""),
        ("Shelf life      : 6 months from manufacture date", 10, ""),
        ("Standard        : Company Standard (internal)", 10, ""),
        ("", 8, ""),
        ("Test item                Unit        Specification      Result       Method", 9, "M"),
        ("-" * 96, 9, "M"),
        ("H2O2 content             % (m/m)     30.0 - 31.0        30.4         (not stated)", 9, "M"),
        ("Stability                %           min. 97            99.2         (not stated)", 9, "M"),
        ("Colour                   Pt-Co       max. 10            5            (not stated)", 9, "M"),
        ("Appearance               -           clear liquid       pass         visual", 9, "M"),
        ("pH                       -           2.0 - 4.5          3.1          (not stated)", 9, "M"),
        ("Residue after evaporation%           max. 0.05          0.02         (not stated)", 9, "M"),
        ("", 4, ""),
        ("Iron (Fe)                -           (not tested)       -            -", 9, "M"),
        ("Chloride                 -           (not tested)       -            -", 9, "M"),
        ("TOC                      -           (not tested)       -            -", 9, "M"),
        ("", 8, ""),
        ("NOTE (for demonstration): Fe / chloride / TOC are commonly required by", 8, "M"),
        ("electronics-grade users, and test method numbers are missing - both are", 8, "M"),
        ("intentional gaps in this mock COA.", 8, "M"),
        ("", 10, ""),
        ("Conclusion      : The above batch conforms to the company specification.", 10, ""),
        ("", 12, ""),
        ("Issued by       : QA Manager  (signature)", 10, ""),
        ("Date            : 2026-10-10", 10, ""),
        ("", 10, ""),
        ("*** END OF MOCK COA ***  Fictional document, generated for demonstration. ***", 8, "M"),
    ]
    write_pdf(path, [pg], "MOCK COA - Batch L2609A (fictional)")


# ============================================================ 3. PI
def gen_pi(path):
    pg = banner() + [
        ("", 6, ""),
        ("PROFORMA INVOICE", 20, "B"),
        ("", 6, ""),
        ("PI No.          : HW-PI-2609-118", 10, "B"),
        ("Date            : 2026-09-18", 10, ""),
        ("Seller          : " + SUPPLIER, 10, ""),
        ("                  " + ADDR, 10, ""),
        ("Buyer           : [BUYER NAME WITHHELD]  (demo)", 10, ""),
        ("", 8, ""),
        ("Item  Description                              Qty      Unit price    Amount", 9, "M"),
        ("-" * 96, 9, "M"),
        ("1     HYDROGEN PEROXIDE AQUEOUS SOLUTION 30%    20,000   USD 1.18      USD 23,600.00", 9, "M"),
        ("      Packing: in 30 kg HDPE drums               kg       CIF Busan", 9, "M"),
        ("", 4, ""),
        ("Total amount    : USD 23,600.00", 10, "B"),
        ("", 6, ""),
        ("TERMS", 11, "B"),
        ("Trade term      : FOB Busan", 10, ""),
        ("Payment         : T/T 30% deposit, balance 70% via CIF Busan", 10, ""),
        ("Port of loading : (not stated)", 10, ""),
        ("Port of discharge: (not stated)", 10, ""),
        ("Country of origin: (not stated)", 10, ""),
        ("HS code         : (not stated)", 10, ""),
        ("Country of origin and HS code are to be completed by the buyer.", 8, "M"),
        ("", 6, ""),
        ("NOTE (for demonstration): the trade term appears three times in this mock", 8, "M"),
        ("document and does not agree (CIF Busan / FOB Busan / CIF Busan). This", 8, "M"),
        ("inconsistency is intentional and is one of the findings of the dossier.", 8, "M"),
        ("", 10, ""),
        ("*** END OF MOCK PROFORMA INVOICE ***  Fictional, for demonstration only. ***", 8, "M"),
    ]
    write_pdf(path, [pg], "MOCK PI HW-PI-2609-118 (fictional)")


# ============================================================ 4. 英文标签 SVG
def gen_label(path):
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="520" height="700" viewBox="0 0 520 700">
  <defs>
    <pattern id="mockstripe" width="14" height="14" patternTransform="rotate(45)"
             patternUnits="userSpaceOnUse">
      <rect width="14" height="14" fill="#fbf3d9"/>
      <rect width="7" height="14" fill="#f3e5b8"/>
    </pattern>
  </defs>
  <rect x="0" y="0" width="520" height="700" fill="#ffffff" stroke="#222" stroke-width="2"/>
  <!-- 模拟水印带 -->
  <rect x="0" y="0" width="520" height="46" fill="url(#mockstripe)" stroke="#c9a94a" stroke-width="1"/>
  <text x="260" y="20" font-family="Helvetica,Arial" font-size="12" font-weight="bold"
        fill="#7a5a10" text-anchor="middle">MOCK DOCUMENT</text>
  <text x="260" y="36" font-family="Helvetica,Arial" font-size="9" fill="#7a5a10"
        text-anchor="middle">Fictional label for workflow demonstration only</text>

  <!-- 品名 -->
  <text x="30" y="86" font-family="Helvetica,Arial" font-size="11" fill="#555">PRODUCT NAME</text>
  <text x="30" y="112" font-family="Helvetica,Arial" font-size="22" font-weight="bold" fill="#111">
    HYDROGEN PEROXIDE 30%</text>

  <!-- 象形图 -->
  <g transform="translate(30,132)">
    <!-- GHS03 氧化剂 -->
    <g transform="translate(0,0)">
      <polygon points="60,8 112,98 8,98" fill="#fff" stroke="#d0021b" stroke-width="7"/>
      <circle cx="60" cy="76" r="15" fill="none" stroke="#111" stroke-width="3"/>
      <path d="M60 40 C52 54 68 56 60 70" fill="none" stroke="#111" stroke-width="3"/>
      <text x="60" y="120" font-family="Helvetica,Arial" font-size="9" fill="#333"
            text-anchor="middle">GHS03</text>
    </g>
    <!-- GHS05 腐蚀性 -->
    <g transform="translate(140,0)">
      <polygon points="60,8 112,98 8,98" fill="#fff" stroke="#d0021b" stroke-width="7"/>
      <path d="M38 84 L50 60 L56 72 L64 56 L76 84" fill="none" stroke="#111" stroke-width="3"/>
      <path d="M66 52 L78 40" stroke="#111" stroke-width="3"/>
      <path d="M74 44 L82 36 L78 50 Z" fill="#111"/>
      <text x="60" y="120" font-family="Helvetica,Arial" font-size="9" fill="#333"
            text-anchor="middle">GHS05</text>
    </g>
  </g>

  <!-- 信号词 -->
  <text x="30" y="290" font-family="Helvetica,Arial" font-size="11" fill="#555">SIGNAL WORD</text>
  <text x="30" y="322" font-family="Helvetica,Arial" font-size="30" font-weight="bold"
        fill="#d0021b">DANGER</text>

  <!-- H 码 -->
  <text x="30" y="352" font-family="Helvetica,Arial" font-size="11" fill="#555">
    HAZARD STATEMENTS</text>
  <g font-family="Helvetica,Arial" font-size="12" fill="#111">
    <text x="30" y="372">H272  May intensify fire; oxidiser.</text>
    <text x="30" y="390">H302  Harmful if swallowed.</text>
    <text x="30" y="408">H315  Causes skin irritation.</text>
    <text x="30" y="426">H318  Causes serious eye damage.</text>
    <text x="30" y="444">H335  May cause respiratory irritation.</text>
  </g>

  <!-- 供应商 -->
  <line x1="30" y1="470" x2="490" y2="470" stroke="#bbb" stroke-width="1"/>
  <text x="30" y="490" font-family="Helvetica,Arial" font-size="11" fill="#555">SUPPLIER</text>
  <g font-family="Helvetica,Arial" font-size="12" fill="#111">
    <text x="30" y="510">{SUPPLIER}</text>
    <text x="30" y="528">{ADDR}</text>
    <text x="30" y="546">Tel: {TEL}</text>
  </g>

  <!-- 故意缺陷说明 -->
  <rect x="30" y="566" width="460" height="86" fill="#fdf6e3" stroke="#e0b84a" stroke-width="1"/>
  <text x="42" y="586" font-family="Helvetica,Arial" font-size="10" font-weight="bold"
        fill="#8a5a00">INTENTIONAL DEFECTS IN THIS MOCK LABEL</text>
  <g font-family="Helvetica,Arial" font-size="9.5" fill="#6b4a00">
    <text x="42" y="604">- English only; no Chinese product name, no Chinese H/P statements</text>
    <text x="42" y="620">- No 24-hour emergency telephone reachable within China</text>
    <text x="42" y="636">- No separate "composition and concentration" field</text>
  </g>
</svg>
'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


# ============================================================ 5. TDS 骨架
def gen_tds(path):
    txt = f"""# （模拟件）技术数据表 / Technical Data Sheet

> **{MOCK_WARN}**

- 供应商：{SUPPLIER}
- 产品：HYDROGEN PEROXIDE AQUEOUS SOLUTION 30%
- 本文件用于演示「建议件（非必须件）」的形态，无需报关时随附。

## 一、典型指标（示例数据，虚构）

| 项目 | 单位 | 典型值 | 备注 |
|---|---|---|---|
| H₂O₂ 含量 | % (m/m) | 30.4 | 见 COA |
| 稳定度 | % | 99.2 | — |
| 色度 | Pt-Co | ≤ 5 | — |
| pH | — | 3.1 | — |
| 铁（Fe） | mg/kg | **（本模拟件未提供）** | 下游电子工序常用控制项 |
| 氯化物 | mg/kg | **（本模拟件未提供）** | — |
| TOC | mg/kg | **（本模拟件未提供）** | — |

> **演示意图**：本 TDS 故意留空铁/氯化物/TOC，用于在底稿中作为「P1 缺口：下游关键指标缺失」的证据。

## 二、储存与操作（示例）

- 阴凉通风处，避免阳光直射与高温；容器须可排气。
- 与还原剂、酸、碱、金属粉末、可燃物分开存放。
- 稀释时把过氧化氢加入水中，不得反向。

## 三、包装

- 30 kg HDPE 桶（带排气盖），每托 20 桶。

---

**{MOCK_WARN}**
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=os.path.join(ROOT, "examples", "h2o2-kr-30", "mock_supplier_docs"))
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    jobs = [
        ("01_SDS_EN_mock.pdf", gen_sds),
        ("02_COA_mock.pdf", gen_coa),
        ("03_PI_mock.pdf", gen_pi),
        ("04_Label_EN_mock.svg", gen_label),
        ("05_TDS_mock.md", gen_tds),
    ]
    for name, fn in jobs:
        p = os.path.join(a.outdir, name)
        fn(p)
        print(f"  {name:26s} {os.path.getsize(p):>8,d} bytes")
    print(f"\n已生成 {len(jobs)} 份模拟件 → {a.outdir}")
    print("提醒：这些文件均为虚构，仅用于演示，不得作为真实贸易资料使用。")


if __name__ == "__main__":
    main()
