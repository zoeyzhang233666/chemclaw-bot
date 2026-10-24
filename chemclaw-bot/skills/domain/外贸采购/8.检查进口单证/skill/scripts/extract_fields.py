# -*- coding: utf-8 -*-
"""extract_fields.py — 从进口单证中提取字段，并给出“文件 + 页码 + 行号 + 原值片段”定位。

设计原则（与核对规范一致）：
  1) 锚点(anchor) 定位标签，格式模板(pattern) 只描述“该字段合法的值长什么样”；
  2) 同一行/同一单元格内，取标签之后最近的合法值 → 天然适配 PDF 行文本、
     DOCX 被拍平的表格、XLSX 单元格；
  3) 每个值必须通过 validator（HS 10 位、CAS 校验位、金额 > 0、重量合理区间等）；
  4) 取不到就输出 null + NOT_FOUND，**绝不猜测**（后续计为【无法判断】或【缺失】）。

用法:
    python scripts/extract_fields.py --input <单证目录|单文件> --out extracted.json
支持 .pdf(需文字层) .docx .xlsx .png/.jpg(需旁挂同名 .ocr.txt)。仅用标准库。
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pdf_text  # noqa: E402


# ================================================================ 读取层
def _unescape(s):
    s = (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
          .replace("&quot;", '"').replace("&apos;", "'").replace("&#160;", " ")
          .replace("_x000D_", " ").replace("_x0009_", "\t"))
    return re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), s)


def read_pdf(path):
    out = []
    for page, lines in pdf_text.page_lines(path):
        for i, (y, t) in enumerate(lines, 1):
            out.append({"page": page, "line": i, "text": t})
    return out


def read_docx(path):
    import zipfile
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    xml = xml.replace("</w:p>", "\n").replace("</w:tc>", "\t")
    xml = re.sub(r"<[^>]+>", "", xml)
    out, n = [], 0
    for raw in xml.split("\n"):
        n += 1
        parts = [_unescape(x).strip() for x in raw.split("\t")]
        txt = " ".join(p for p in parts if p)
        if txt.strip():
            # DOCX 无渲染页码：按正文约 45 段/页估算（定位以段号为准，最终页码以 PDF 渲染为准）
            out.append({"page": max(1, len(out) // 45 + 1), "line": n, "text": txt,
                        "flat": "~".join(p for p in parts if p)})
    return out


def _xlsx_rows(path):
    import zipfile
    rows = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            s = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
            for si in re.findall(r"<si>(.*?)</si>", s, re.S):
                shared.append("".join(_unescape(t) for t in re.findall(r"<t[^>]*>(.*?)</t>", si, re.S)))
        for sh in sorted(n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n)):
            s = z.read(sh).decode("utf-8", "replace")
            for rm in re.finditer(r'<row[^>]*r="(\d+)"[^>]*>(.*?)</row>', s, re.S):
                rnum, body = int(rm.group(1)), rm.group(2)
                cells, formulas = {}, {}
                for cm in re.finditer(r'<c r="([A-Z]+)\d+"([^>]*)>(.*?)</c>', body, re.S):
                    col, attrs, inner = cm.group(1), cm.group(2), cm.group(3)
                    t = (re.search(r't="([^"]+)"', attrs) or [None, "n"])[1]
                    f = re.search(r"<f[^>]*>(.*?)</f>", inner, re.S)
                    if f:
                        formulas[col] = _unescape(f.group(1))
                    if t in ("s", "sharedStrings"):
                        v = re.search(r"<v>(.*?)</v>", inner)
                        val = shared[int(v.group(1))] if v else ""
                    elif t == "inlineStr":
                        val = "".join(_unescape(x) for x in re.findall(r"<t[^>]*>(.*?)</t>", inner, re.S))
                    else:
                        v = re.search(r"<v>(.*?)</v>", inner)
                        val = v.group(1) if v else ""
                    if val != "":
                        cells[col] = val.strip()
                if cells or formulas:
                    rows.append((rnum, cells, formulas))
    return rows


def read_xlsx(path):
    """每行输出 'Cell=value | Cell=value'；# 之后是公式，便于计算校验。"""
    out = []
    for rnum, cells, formulas in _xlsx_rows(path):
        parts = ["%s=%s" % (c, cells[c]) for c in sorted(cells, key=lambda c: (len(c), c))]
        for c, f in formulas.items():
            parts.append("%s#=%s" % (c, f))
        out.append({"page": 1, "line": rnum, "text": " | ".join(parts)})
    return out


def read_image(path):
    side = os.path.splitext(path)[0] + ".ocr.txt"
    if not os.path.exists(side):
        return None
    lines = open(side, encoding="utf-8").read().splitlines()
    return [{"page": 1, "line": i, "text": ln} for i, ln in enumerate(lines, 1) if ln.strip()]


def read_any(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return read_pdf(path)
    if ext == ".docx":
        return read_docx(path)
    if ext == ".xlsx":
        return read_xlsx(path)
    if ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp"):
        return read_image(path)
    return None


# ================================================================ 分类层
DOC_TYPES = [
    ("PACKING_LIST", "装箱单", [r"PACKING\s*LIST", r"装箱单"]),
    ("PROFORMA_INVOICE", "形式发票", [r"PROFORMA\s*INVOICE", r"形式发票"]),
    ("COMMERCIAL_INVOICE", "商业发票", [r"COMMERCIAL\s*INVOICE", r"商业发票"]),
    ("BILL_OF_LADING", "提单", [r"BILL\s*OF\s*LADING", r"提单", r"OCEAN\s*B/?L"]),
    ("CONTRACT", "采购合同", [r"PURCHASE\s*CONTRACT", r"采购合同", r"SALES\s*CONTRACT"]),
    ("COA", "分析证书", [r"CERTIFICATE\s*OF\s*ANALYSIS", r"分析证书"]),
    ("SDS", "安全技术说明书", [r"SAFETY\s*DATA\s*SHEET", r"安全技术说明书", r"化学品安全技术"]),
    ("COO", "原产地证", [r"CERTIFICATE\s*OF\s*ORIGIN", r"原产地证"]),
    ("INSURANCE", "保险单", [r"INSURANCE\s*POLICY", r"保险单"]),
    ("LICENSE", "进口许可证", [r"IMPORT\s*LICEN[CS]E", r"自动进口许可证", r"两用物项"]),
    ("USAGE_STATEMENT", "用途/成分说明", [r"USAGE\s*DECLARATION", r"成分说明", r"NON[- ]HAZARD"]),
]
KEY_BY_TYPE = {"CONTRACT": "contract_no", "PROFORMA_INVOICE": "pi_no", "COMMERCIAL_INVOICE": "invoice_no",
               "PACKING_LIST": "packing_no", "BILL_OF_LADING": "bl_no", "COA": "coa_no", "COO": "coo_no"}


def classify(lines):
    head_text = "\n".join(l["text"] for l in lines[:8]).upper()
    blob = "\n".join(l["text"] for l in lines).upper()
    hits = []
    for code, cn, pats in DOC_TYPES:
        n = sum(1 for p in pats if re.search(p, blob))
        if n:
            h = sum(1 for p in pats if re.search(p, head_text))
            hits.append((n + 3 * h, code, cn))
    if not hits:
        return None, None, 0
    hits.sort(reverse=True)
    return hits[0][1], hits[0][2], hits[0][0]


# ================================================================ 校验层
def v_hs(s):
    d = re.sub(r"\D", "", s or "")
    return d if len(d) == 10 and d[:2] in ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12",
                                           "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24",
                                           "25", "26", "27", "28", "29", "30", "31", "32", "33", "34", "35", "36",
                                           "37", "38", "39", "40", "41", "42", "43", "44", "45", "46", "47", "48",
                                           "49", "50", "51", "52", "53", "54", "55", "56", "57", "58", "59", "60",
                                           "61", "62", "63", "64", "65", "66", "67", "68", "69", "70", "71", "72",
                                           "73", "74", "75", "76", "78", "79", "80", "81", "82", "83", "84", "85",
                                           "86", "87", "88", "89", "90", "91", "92", "93", "94", "95", "96", "97",
                                           "98", "99") else None


def v_cas(s):
    m = re.fullmatch(r"(\d{2,7})-(\d{2})-(\d)", (s or "").strip())
    if not m:
        return None
    body, chk = m.group(1) + m.group(2), int(m.group(3))
    total = sum((i + 1) * int(c) for i, c in enumerate(reversed(body)))
    return s.strip() if total % 10 == chk else None


def _num(s):
    try:
        return float((s or "").replace(",", ""))
    except ValueError:
        return None


def v_money(s):
    v = _num(s)
    return s.strip() if v is not None and v > 0 else None


def v_qty(s):
    v = _num(s)
    return s.strip() if v is not None and v > 0 else None


def v_weight(s):
    v = _num(s)
    return s.strip() if v is not None and 100 <= v <= 100000000 else None


def v_pkg(s):
    d = re.sub(r"[^\d]", "", s or "")
    if not d:
        return None
    v = int(d)
    return str(v) if 1 <= v <= 5000 else None


def v_text(s):
    t = (s or "").strip(" \t|:：,.")
    return t if 1 < len(t) <= 120 else None


def v_party(s):
    t = (s or "").strip(" \t|:：,.")
    if not re.search(r"(CO\.?,?\s*LTD|LIMITED|COMPANY|CORPORATION|LLC|GMBH|S\.A|INC\.|GROUP|公司)", t, re.I):
        return None
    if re.search(r"^(shall|either|its|the|and|or|one|this|any|all|each)\b", t, re.I):
        return None
    if len(re.findall(r"[A-Z]{3,}", t)) < 2:
        return None
    return t if 6 <= len(t) <= 120 else None


def v_incoterm(s):
    t = (s or "").strip().upper()
    return t if t in ("EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP") else None


def v_currency(s):
    t = (s or "").strip().upper()
    return t if t in ("USD", "EUR", "CNY", "RMB", "SAR", "AED", "JPY", "GBP") else None


def v_code(s):
    t = (s or "").strip(" \t|:：,.")
    return t if re.fullmatch(r"[A-Z0-9][A-Z0-9\-/]{4,}", t) and re.search(r"\d", t) and re.search(r"[A-Z]", t) else None


def v_batch(s):
    t = (s or "").strip(" \t|:：,.")
    return t if re.fullmatch(r"[A-Z0-9][A-Z0-9\-/]{3,}", t) and re.search(r"\d", t) else None


def v_spec(s):
    t = (s or "").strip()
    return t if re.search(r"\d", t) and len(t) <= 30 else None


def v_port(s):
    t = (s or "").strip(" \t|:：,.")
    return t if re.search(r"[A-Z]{3,}", t) and 4 <= len(t) <= 60 else None


def v_pay(s):
    t = (s or "").strip(" \t|:：,.")
    return t if re.match(r"(T/T|L/C|D/P|D/A|O/A|CASH|预付款|货到付款)", t, re.I) else None


def v_date(s):
    t = (s or "").strip()
    return t if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t) or re.fullmatch(r"\d{2}/\d{2}/\d{4}", t) else None


# ================================================================ 规则层
# field: (锚点正则, 值模板, 校验器)
ANCHOR = r"(?P<anchor>%s)\s*[:：]?"
RULES = {
    "contract_no": (r"(?:Contract\s*(?:No|Ref)\.?|合同号)", r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+){2,}", v_code),
    "pi_no": (r"(?:Proforma\s*Invoice\s*No\.?|PI\s*No\.?|PI\s*号)", r"PI-[A-Z0-9]*(?:-[A-Z0-9]+){1,}", v_code),
    "invoice_no": (r"(?:Invoice\s*No\.?|发票号|商业发票号)", r"[A-Z][A-Z0-9]*-INV-(?:[A-Z0-9]+-)*[A-Z0-9]+", v_code),
    "packing_no": (r"(?:Packing\s*List\s*No\.?|装箱单号)", r"[A-Z][A-Z0-9]*-PL-(?:[A-Z0-9]+-)*[A-Z0-9]+", v_code),
    "bl_no": (r"(?:B/L\s*No\.?|提单号|Bill\s*of\s*Lading\s*No\.?)",
              r"[A-Z]{4}(?:[A-Z]{2,4})?\d{5,}", v_code),
    "coa_no": (r"(?:Certificate\s*No\.?|证书编号|COA\s*No\.?)", r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+){2,}", v_code),
    "coo_no": (r"(?:Certificate\s*of\s*Origin\s*No\.?|原产地证号)", r"[A-Z]{2,}-?\d{4}-?\d{5,}", v_code),
    "po_no": (r"(?:P\.?O\.?\s*No\.?|订单号|Buyer\s*P\.?O\.?)", r"(?:PO|P\.O\.)?-?[A-Z]{2,}-(?:[A-Z0-9]+-)+[A-Z0-9]+", v_code),
    "cas": (r"(?:CAS(?:\s*(?:No\.?|号))?|CAS\s*号码)", r"\d{2,7}-\d{2}-\d", v_cas),
    "hs": (r"(?:HS\s*(?:Code|编码|海关编码)|商品编码|HS)", r"\d{10}", v_hs),
    "spec": (r"(?:Specification|Spec|Grade|Purity|规格|质量指标|含量)", r"≥\s*\d{2}(?:\.\d+)?\s*%\s*(?:wt|min|mass)?", v_spec),
    "quantity": (r"(?:Quantity|Qty|数量)", r"\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:\s*(?:MT|KGS|KG|TONS?))?", v_qty),
    "unit_price": (r"(?:Unit\s*Price|单价)", r"\d{1,3}(?:,\d{3})*\.\d{2}", v_money),
    "amount": (r"(?:Amount|Invoice\s*Value|Total\s*Amount|发票金额|总额|合计|金额)", r"\d{1,3}(?:,\d{3})*\.\d{2}", v_money),
    "currency": (r"(?:Currency|币种)", r"USD|EUR|CNY|RMB|SAR", v_currency),
    "incoterm": (r"(?:Trade\s*Term|Incoterm|Price\s*Term|贸易术语|价格条款)", r"(?:EXW|FCA|FAS|FOB|CFR|CIF|CPT|CIP|DAP|DPU|DDP)", v_incoterm),
    "port_load": (r"(?:Port\s*of\s*Loading|Loading\s*Port|起运港|装货港)",
                  r"[A-Z][A-Z ,()\-]*PORT[A-Z0-9 ,()\-]*|KING\s+ABDULLAH[A-Z0-9 ,()\-]*|JUBAIL[A-Z0-9 ,()\-]*", v_port),
    "port_disch": (r"(?:Port\s*of\s*(?:Discharge|Destination)|Destination\s*Port|目的港|卸货港)",
                   r"[A-Z][A-Z ,()\-]*PORT[A-Z0-9 ,()\-]*", v_port),
    "vessel": (r"(?:Vessel\s*/\s*Voyage|Vessel|船名)\s*(?:/\s*Voyage)?", r"(?:MSC|MAERSK|CMA|COSCO|ONE|EVER|HMM|OOCL|YML)[A-Z0-9 .\-]{2,25}", v_text),
    "voyage": (r"(?:Voyage|航次|V\.)", r"\d{2,4}[A-Z]{1,2}\d?", v_text),
    "packages": (r"(?:Number\s*of\s*Packages|No\.\s*of\s*Packages|Packages|件数|总件数)", r"\d{1,4}", v_pkg),
    "pack_type": (r"(?:Packing|Package\s*Type|包装方式|包装)", r"(?:BULK\s+IN\s+)?(?:ISO\s*TANK\s*CONTAINERS?|ISOTANK|ISO\s*TANKS?|DRUMS?|BAGS?|CARTONS?|PALLETS?)", v_text),
    "net_weight": (r"(?:Net\s*(?:Weight|Wt)|净重)", r"\d{1,3}(?:,\d{3})*(?:\.\d+)?", v_weight),
    "gross_weight": (r"(?:Gross\s*(?:Weight|Wt)|毛重)", r"\d{1,3}(?:,\d{3})*(?:\.\d+)?", v_weight),
    "batch": (r"(?:Batch\s*No\.?|BATCH|批号|Lot\s*No\.?)", r"[A-Z0-9]{2,}(?:-[A-Z0-9]+)*", v_batch),
    "payment": (r"(?:Payment(?:\s*Terms)?|付款方式|付款条件)", r"(?:T/T|L/C|D/P|D/A|O/A)[A-Za-z0-9 %+/().:,]{0,40}", v_pay),
    "seller": (r"(?:Seller|Exporter|Manufacturer|卖方|生产商)",
               r"[A-Z][A-Z0-9 .,&'()\-]{6,}(?:CO\.?,?\s*LTD\.?|LIMITED|COMPANY|CORPORATION|LLC|S\.A)", v_party),
    "shipper": (r"(?:Shipper|发货人)",
               r"[A-Z][A-Z0-9 .,&'()\-]{6,}(?:CO\.?,?\s*LTD\.?|LIMITED|COMPANY|CORPORATION|LLC|S\.A)", v_party),
    "buyer": (r"(?:Buyer|买方|购货单位)", r"[A-Z][A-Z0-9 .,&'()\-]{6,}(?:CO\.?,?\s*LTD\.?|LIMITED|COMPANY|CORPORATION|LLC)", v_party),
    "consignee": (r"(?:Consignee|Receiver|收货人)", r"[A-Z][A-Z0-9 .,&'()\-]{6,}(?:CO\.?,?\s*LTD\.?|LIMITED|COMPANY|CORPORATION|LLC)", v_party),
    "notify": (r"(?:Notify(?:\s*Party)?|通知方|通知人)", r"[A-Z][A-Z0-9 .,&'()\-]{6,}(?:CO\.?,?\s*LTD\.?|LIMITED|COMPANY|CORPORATION|LLC)", v_party),
    "origin": (r"(?:Country\s*of\s*Origin|原产国|原产地)", r"[A-Z][A-Z ]{3,25}", v_text),
    "eta": (r"(?:ETA|ETD|Estimated\s*(?:Time\s*of\s*)?Arrival|预计到港)", r"\d{4}-\d{2}-\d{2}", v_date),
}

SEG_SPLIT = "[\\t|;~]+|\\s\\|\\s"
COLMARK = re.compile(r"(?<![A-Za-z0-9])([A-Z]{1,2})[=\-]>?\s*")
# 弱字段：文档类型决定其是否存在，取不到不计为缺失
WEAK = {"coo_no", "origin", "voyage", "vessel", "packing_no", "pi_no", "invoice_no", "contract_no",
        "coa_no", "bl_no", "po_no", "eta", "payment", "incoterm", "currency", "port_load", "port_disch"}
# 不同字段在表格里通常出现的列（XLSX 用），只用于排序，不影响合法性
PREFER_COLS = {"net_weight": ["G", "E", "D", "F"], "gross_weight": ["H", "F", "E", "G"],
               "packages": ["D", "C", "B", "E"], "batch": ["I", "H", "J"], "amount": ["F", "H", "I", "J"]}


def _cells(ln):
    """XLSX 行 'A=label | B=value' -> {列: 值}；非 xlsx 行返回 None。"""
    if " | " not in ln["text"] or not re.match(r"^[A-Z]{1,2}=", ln["text"]):
        return None
    out = {}
    for tok in ln["text"].split(" | "):
        m = re.match(r"^([A-Z]{1,2})=(.*)$", tok)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def _pick_cell(cells, anchor_rx, vrx, validator, prefer_cols):
    """在标签单元格右侧最近的、类型匹配的单元格里取值（优先指定列）。"""
    labels = [c for c, v in cells.items() if anchor_rx.search(v)]
    if not labels:
        return None, None
    lab = labels[0]
    order = [c for c in prefer_cols if c in cells] + sorted(k for k in cells if k not in prefer_cols)
    for c in order:
        if _col_le(lab, c):
            continue
        vm = vrx.search(cells[c])
        if vm and validator(vm.group("v")):
            return validator(vm.group("v")), c
    return None, None


def _col_le(a, b):
    def idx(s):
        n = 0
        for ch in s:
            n = n * 26 + (ord(ch) - 64)
        return n
    return idx(b) <= idx(a)


def _segments(ln):
    parts = re.split(SEG_SPLIT, ln["text"])
    if ln.get("flat"):
        parts += re.split(r"~", ln["flat"])
    return [p.strip() for p in parts if p and p.strip()]


def _header_cursor(lines, vrx, validator):
    """DOCX 表格被拍平成「表头一排 → 数据一排」。
    做法：连续 ≥2 个不含数字的标签 → 登记表头列；随后每个数据段按列序回填；
    列满即重置（同行多条目/多行表格都能自然对齐）。返回 {(line,段): (列名, 值)}。"""
    def is_label(t):
        if not t or len(t) > 45:
            return False
        if re.search(r"(SHALL|THE\s+SELLER|^[0-9]\.|SIMULATED)", t, re.I):
            return False
        return not re.search(r"\d", t) or bool(re.search(r"(No\.?|号)\s*$", t))

    mapping = {}
    heads, cursor = [], 0
    for ln in lines:
        raw = _segments(ln)
        segs = []
        for s in raw:
            if s not in segs:
                segs.append(s)
        labels = [s for s in segs if is_label(s)]
        if segs and len(labels) == len(segs) and len(raw) >= 2:
            heads, cursor = segs, 0
            continue
        if not segs or not heads:
            continue
        if re.match(r"^[0-9]\.\s*[A-Z]", segs[0]):
            heads, cursor = [], 0
            continue
        for seg in segs:
            if cursor >= len(heads):
                heads, cursor = [], 0
                break
            vm = vrx.search(seg)
            if vm and validator(vm.group("v")):
                mapping[(ln["line"], seg)] = (heads[cursor], validator(vm.group("v")))
                cursor += 1
    return mapping


FIELD_TO_HEAD = {
    "cas": ("CAS",), "hs": ("HS", "HS CODE", "海关编码"), "quantity": ("QUANTITY", "数量"),
    "unit_price": ("UNIT PRICE", "单价"), "amount": ("AMOUNT", "金额"),
    "net_weight": ("NET WEIGHT", "净重"), "gross_weight": ("GROSS WEIGHT", "毛重"),
    "packages": ("NUMBER OF PACKAGES", "NO. OF PACKAGES", "PACKAGES", "件数"),
    "batch": ("BATCH NO", "BATCH", "LOT NO", "批号"), "incoterm": ("TRADE TERM", "INCOTERM", "贸易术语"),
    "port_load": ("LOADING PORT", "PORT OF LOADING", "起运港"),
    "port_disch": ("DESTINATION PORT", "PORT OF DISCHARGE", "目的港", "卸货港"),
    "payment": ("PAYMENT", "付款方式"), "pack_type": ("PACKING", "包装"),
    "spec": ("SPECIFICATION", "GRADE", "PURITY", "规格", "含量"),
}


def extract_doc(path):
    lines = read_any(path)
    fname = os.path.basename(path)
    if lines is None:
        return {"file": fname, "type": "UNKNOWN", "type_cn": "格式不支持", "fields": {},
                "missing_fields": [], "issues": [{"code": "UNSUPPORTED_FORMAT", "detail": os.path.splitext(path)[1]}]}
    if not lines:
        return {"file": fname, "type": "UNKNOWN", "type_cn": "无文字层（需 OCR）", "fields": {},
                "missing_fields": [], "issues": [{"code": "NEEDS_OCR", "detail": "无文字层，不得凭图像猜测字段"}]}
    code, cn, score = classify(lines)
    fields, missing = {}, []

    for name, (anchor, tmpl, validator) in RULES.items():
        arx = re.compile(ANCHOR % anchor, re.I)
        vrx = re.compile("(?<![-\\w.])(?P<v>%s)(?![-\\w])" % tmpl, re.I)
        found = None
        # 优先级：1) 同一行锚点后的合法值（跳过 xlsx 的 'A=' 列标记）；2) 同段；
        #         3) 跨行：锚点独占一行时取其后 1~2 行的第一个合法值
        for ln in lines:
            cells = _cells(ln)
            if cells:
                v, col = _pick_cell(cells, arx, vrx, validator,
                                    PREFER_COLS.get(name, ["B", "C", "F", "G", "D", "E", "H"]))
                if v:
                    found = {"value": v, "page": ln["page"], "line": ln["line"],
                             "snippet": ("%s=%s" % (col, cells.get(col, "")))[:150], "via": "cell"}
                    break
                continue
            text = COLMARK.sub(" ", ln["text"])
            m = arx.search(text)
            if not m:
                continue
            rest = text[m.end():]
            for vm in vrx.finditer(rest):
                v = validator(vm.group("v"))
                if v:
                    found = {"value": v, "page": ln["page"], "line": ln["line"],
                             "snippet": text[max(0, m.start() - 5):m.end() + len(rest[:40])][:150],
                             "via": "same-line"}
                    break
            if found:
                break
            for seg in _segments(ln):
                sm = arx.search(seg)
                if not sm:
                    continue
                for vm in vrx.finditer(seg[sm.end():]):
                    v = validator(vm.group("v"))
                    if v:
                        found = {"value": v, "page": ln["page"], "line": ln["line"],
                                 "snippet": seg[:150], "via": "same-segment"}
                        break
                if found:
                    break
            if found:
                break
        if not found:
            for i, ln in enumerate(lines):
                if not arx.search(COLMARK.sub(" ", ln["text"])):
                    continue
                for nxt in lines[i + 1:i + 3]:
                    nt = COLMARK.sub(" ", nxt["text"]).strip()
                    vm = vrx.search(nt)
                    # 跨行取值要求：整段就是一个完整值（避免从"200.000 MT"里抠出 "200"）
                    if vm and vm.group("v").strip() == nt:
                        v = validator(vm.group("v"))
                        if v:
                            found = {"value": v, "page": nxt["page"], "line": nxt["line"],
                                     "snippet": nt[:150], "via": "next-lines"}
                            break
                    m2 = re.match(r"^(?:USD\s*)?(?P<v>%s)" % tmpl, nt, re.I)
                    if m2:
                        v = validator(m2.group("v"))
                        if v:
                            found = {"value": v, "page": nxt["page"], "line": nxt["line"],
                                     "snippet": nt[:150], "via": "next-lines"}
                            break
                if found:
                    break
        if name in WEAK and not found:
            continue          # 弱字段允许缺失，不提示
        if found:
            fields[name] = found
        else:
            missing.append({"field": name, "code": "NOT_FOUND", "detail": "未找到该字段的可信取值"})

    # ---- 表头列兜底（DOCX 表格拍平场景）：只接受表头名与字段语义匹配的列
    hcache = {}
    for name, (anchor, tmpl, validator) in RULES.items():
        if name not in FIELD_TO_HEAD:
            continue
        vrx = re.compile("(?<![-\\w.])(?P<v>%s)(?![-\\w])" % tmpl, re.I)
        if name not in hcache:
            hcache[name] = _header_cursor(lines, vrx, validator)
        want = FIELD_TO_HEAD[name]
        for (line_no, val_seg), (head, val) in sorted(hcache[name].items()):
            hu = head.upper()
            if any(w in hu for w in want):
                prev = fields.get(name)
                if prev and prev.get("via") in ("header-column", "next-lines"):
                    continue
                fields[name] = {"value": val, "page": 1, "line": line_no,
                                "snippet": ("表头「%s」→ %s" % (head, val_seg))[:150], "via": "header-column"}
                break
        if name not in fields and name not in WEAK:
            if not any(m["field"] == name for m in missing):
                missing.append({"field": name, "code": "NOT_FOUND", "detail": "未找到该字段的可信取值"})

    # 商品名（中英文）单独处理：允许直接命中常见品名
    for key, pat in (("product_en", r"[A-Z][A-Z ()]{3,40}GLYCOL[A-Z0-9 (),.\-]{0,40}"),
                     ("product_cn", r"[\u4e00-\u9fa5]{2,10}(?:\(|\uff08)?[\u4e00-\u9fa5]{0,6}(?:\)|\uff09)?")):
        if key in fields:
            continue
        if key == "product_en":
            for ln in lines:
                m = re.search(pat, ln["text"])
                if m and len(m.group(0).strip()) > 8:
                    fields[key] = {"value": m.group(0).strip(), "page": ln["page"], "line": ln["line"],
                                   "snippet": ln["text"][:150], "via": "product-name"}
                    break
        else:
            for ln in lines:
                m = re.search(r"乙二醇(?:\uff08[^\uff09]{1,8}\uff09|\([^)]{1,8}\))?", ln["text"])
                if m:
                    fields[key] = {"value": m.group(0), "page": ln["page"], "line": ln["line"],
                                   "snippet": ln["text"][:150], "via": "product-name"}
                    break
        if key not in fields:
            missing.append({"field": key, "code": "NOT_FOUND", "detail": "未找到品名"})

    return {"file": fname, "type": code or "UNKNOWN", "type_cn": cn or "无法识别", "type_score": score,
            "lines": len(lines), "fields": fields, "missing_fields": missing, "issues": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default="extracted.json")
    args = ap.parse_args()
    if os.path.isdir(args.input):
        files = [os.path.join(args.input, f) for f in sorted(os.listdir(args.input))
                 if os.path.isfile(os.path.join(args.input, f)) and not f.startswith("~$")
                 and not f.lower().endswith((".json", ".md", ".py"))]
    else:
        files = [args.input]
    docs = []
    for f in files:
        d = extract_doc(f)
        key = KEY_BY_TYPE.get(d["type"])
        d["doc_no_key"] = key
        d["doc_no"] = (d["fields"].get(key) or {}).get("value") if key else None
        docs.append(d)
    out = {"documents": docs, "doc_count": len(docs),
           "principle": "值为 null / 出现在 missing_fields 表示未识别。未识别一律不得猜测，应计为【无法判断】或【缺失】。"}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    for d in docs:
        print("%-44s %-18s no=%-20s fields=%2d missing=%2d" %
              (d["file"][:44], d["type"], str(d["doc_no"])[:20], len(d["fields"]), len(d["missing_fields"])))
    print("wrote", args.out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()


