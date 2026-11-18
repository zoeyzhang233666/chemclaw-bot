# -*- coding: utf-8 -*-
"""extract.py —— 单证识别 + 字段抽取（通用、可解释、不猜）。

三层抽取策略，逐层降级并记录"来源层级"，命中层级直接决定后续的置信度：

L1 定位标记  文本中存在 `field:<id>` 标记 → 直接取回读坐标（本仓库生成的测试件）
L2 键值语义  按 taxonomy 中的别名表，匹配 "标签 … 值" 的同一行/下一行
L3 表格语义  按表头列名（如 Qty / 数量 / Net Weight）定位到各单元格
L4 全文规则  正则兜底（CAS、HS、金额、日期、UN），只用于"无法定位"的取值

任何抽取都保留：
  raw     —— 原文片段（用于人工复核）
  page    —— 页码（1 起）
  bbox    —— 坐标（若能定位）
  source  —— 抽取层级
  conf    —— high / medium / low
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

from taxonomy import DOC_TYPES, FIELD_BY_ID, FIELDS

# ---------------------------------------------------------------------------
# 文本规范化
# ---------------------------------------------------------------------------

# 仅对"连接号类"字符做统一：不同单证常用 - / – / — / ‐ 书写编号，
# 属"不同写法同一事实"，不应误判为冲突。
_DASH_MAP = {"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
             "\u2014": "-", "\u2212": "-", "\u2015": "-"}


def norm_text(s: str) -> str:
    """归一化空白与连接号；保留大小写（公司名比对需要）。"""
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = s.replace("\u00ad", "-").replace("\u200b", "").replace("\ufeff", "")
    for k, v in _DASH_MAP.items():
        s = s.replace(k, v)
    return re.sub(r"\s+", " ", s).strip()


def code_key(s: str) -> str:
    """编号类比较键：去空格/大小写/连接号与标点。"""
    s = norm_text(s).upper()
    return re.sub(r"[^0-9A-Z\u4e00-\u9fff]", "", s)


def text_key(s: str) -> str:
    """文本类比较键：去大小写、标点、常见法律后缀噪声，仅用于"疑似同一实体"判断。"""
    s = norm_text(s).upper()
    s = re.sub(r"\b(CO\.?\s*,?\s*LTD\.?|CO\.,LTD\.?|LIMITED|LTD\.?|INC\.?|PT\.?|" \
               r"P\.?\s*T\.?|COMPANY)\b", " ", s)
    s = re.sub(r"[^0-9A-Z\u4e00-\u9fff]", "", s)
    return s


# ---------------------------------------------------------------------------
# 页面文本
# ---------------------------------------------------------------------------
class PageText:
    """一页的文本 + 行坐标（含定位标记）。"""

    def __init__(self, page_no: int, page: pymupdf.Page):
        self.page_no = page_no
        self.lines: List[Dict[str, Any]] = []
        self.markers: Dict[str, Dict[str, Any]] = {}
        self.text = ""
        self._load(page)

    def _load(self, page: pymupdf.Page) -> None:
        chunks: List[str] = []
        prev_clean = None
        for blk in page.get_text("dict").get("blocks", []):
            if blk.get("type") != 0:
                continue
            for line in blk.get("lines", []):
                spans = line.get("spans", [])
                mi = None
                for i, sp in enumerate(spans):
                    if "field:" in sp.get("text", ""):
                        mi = i
                        break
                if mi is None:
                    txt = norm_text("".join(s.get("text", "") for s in spans))
                    if not txt:
                        prev_clean = None
                        continue
                    self.lines.append({"text": txt, "bbox": list(line["bbox"]),
                                       "size": max(s.get("size", 8) for s in spans)})
                    chunks.append(txt)
                    prev_clean = {"text": txt, "bbox": list(line["bbox"])}
                    continue
                # 标记行
                msp = spans[mi]
                ids = re.findall(r"field:([A-Za-z0-9_.\-]+)", msp.get("text", ""))
                bbox, txt = None, ""
                for sp in reversed(spans[:mi]):
                    t = sp.get("text", "")
                    if not t.strip() or "field:" in t:
                        continue
                    if abs(sp["bbox"][3] - msp["bbox"][3]) < 0.35 * msp.get("size", 8):
                        if -1.0 <= (msp["bbox"][0] - sp["bbox"][2]) <= 8.0:
                            bbox, txt = list(sp["bbox"]), norm_text(t)
                            break
                if bbox is None and prev_clean is not None:
                    bbox, txt = list(prev_clean["bbox"]), prev_clean["text"]
                if bbox is None:
                    bbox = list(line["bbox"])
                for fid in ids:
                    self.markers.setdefault(fid, {"page": self.page_no,
                                                  "bbox": [round(float(v), 1) for v in bbox],
                                                  "text": txt})
                prev_clean = None
        self.text = "\n".join(chunks)


# ---------------------------------------------------------------------------
# 单证分类
# ---------------------------------------------------------------------------
def classify(doc_name: str, pages: List[PageText]) -> Dict[str, Any]:
    """先看文件名，再看首页标题。返回 {doc_type, score, evidence}。"""
    head = (pages[0].text[:1500] if pages else "")
    body = "\n".join(p.text for p in pages)[:6000]
    name_u = norm_text(doc_name).upper()
    head_u = norm_text(head).upper()
    # 标题区（首页前 6 行）权重更高：内部标准/模板的正文里会大量出现"销售合同"
    title_u = " ".join(norm_text(l["text"]).upper()
                       for l in (pages[0].lines[:6] if pages else []))
    best = {"doc_type": "UNKNOWN", "score": 0.0, "evidence": "无匹配特征"}
    for code, meta in DOC_TYPES.items():
        score = 0.0
        hits: List[str] = []
        for alias in meta["aliases"]:
            a = alias.upper()
            if a in name_u:
                score += 3.0
                hits.append("文件名含「%s」" % alias)
            if a in title_u:
                score += 4.0
                hits.append("标题含「%s」" % alias)
            elif a in head_u:
                score += 2.0
                hits.append("首页含「%s」" % alias)
            if a in body.upper():
                score += 0.3
        # 反向抑制：SDS 里也会出现"纯碱""合同"，避免误判
        if code == "SC" and "THIRD PARTY" in body.upper():
            pass
        if score > best["score"]:
            best = {"doc_type": code, "score": round(score, 1),
                    "evidence": "；".join(dict.fromkeys(hits)) or "仅正文弱匹配"}
    if best["score"] < 1.0:
        best["doc_type"] = "UNKNOWN"
    return best


# ---------------------------------------------------------------------------
# 值解析
# ---------------------------------------------------------------------------
_NUM_RX = re.compile(r"[-+]?\d[\d,\s]*(?:\.\d+)?")


def parse_number(raw: str) -> Tuple[Optional[float], Optional[str]]:
    """返回 (数值, 单位)。单位从原文识别，识别不到返回 None（不猜）。"""
    s = norm_text(raw)
    m = _NUM_RX.search(s)
    if not m:
        return None, None
    num_s = m.group(0).replace(",", "").replace(" ", "")
    try:
        val = float(num_s)
    except ValueError:
        return None, None
    unit = None
    tail = s[m.end():].upper()
    head = s[:m.start()].upper()
    for u, pats in (
        ("MT", ("MT", "M/T", "METRIC TON", "TON", "TONS", "TONNE", "吨")),
        ("KG", ("KG", "KGS", "KILOGRAM")),
        ("CBM", ("CBM", "M3", "M³", "立方米")),
        ("BAG", ("BAGS", "BAG", "SACK", "袋")),
        ("USD", ("USD", "US$", "US DOLLARS")),
    ):
        for p in pats:
            if re.search(r"(?<![A-Z])" + re.escape(p) + r"(?![A-Z])", tail) or \
               (p in ("MT", "KG", "CBM") and re.search(r"(?<![A-Z])" + p + r"(?![A-Z])", head)):
                unit = u
                break
        if unit:
            break
    return val, unit


_CAS_RX = re.compile(r"\b(\d{2,7})-(\d{2})-(\d)\b")
_HS_RX = re.compile(r"\b(\d{4}\.?\d{2}\.?\d{2})\b")
_MONEY_RX = re.compile(r"\b\d{1,3}(?:,\d{3})+(?:\.\d{1,4})?\b|\b\d+\.\d{2}\b")


def cas_valid(cas: str) -> bool:
    """CAS 登记号校验位算法：Σ(位×(末位序号)) mod 10 == 校验位。"""
    m = _CAS_RX.search(norm_text(cas))
    if not m:
        return False
    digits = (m.group(1) + m.group(2))
    check = int(m.group(3))
    total = 0
    for i, ch in enumerate(reversed(digits)):
        total += int(ch) * (i + 1)
    return total % 10 == check


# ---------------------------------------------------------------------------
# 抽取器
# ---------------------------------------------------------------------------
FIELD_ALIASES = {f["id"]: [a.upper() for a in f["aliases"]] for f in FIELDS}


# ---------------------------------------------------------------------------
# 结构化行：把"标签 / 值"按 x 坐标配对（单行对、左右分栏对）
# ---------------------------------------------------------------------------
LABEL_ONLY = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9&/.\- ]{0,60}|[\u4e00-\u9fff（）()、，．]{1,30})\s*[:：]?$")
VALUE_ONLY = re.compile(r"^(?:" + "|".join([
    r"\d[\d,\.\s]*", r"US\$?[\d,\.]+", r"USD\s?[\d,\.]+", r"[A-Z]{2,}\d{3,}[\w\-]*",
    r"\d{4}-\d{2}-\d{2}"]) + r")$")


FIELD_NAME_KEYS = None


def _field_name_keys() -> set:
    """所有字段别名的"去数字键"，用于精确识别"这一行就是字段名"。"""
    global FIELD_NAME_KEYS
    if FIELD_NAME_KEYS is None:
        FIELD_NAME_KEYS = set()
        for aliases in FIELD_ALIASES.values():
            for a in aliases:
                FIELD_NAME_KEYS.add(code_key(a))
        # 常见表头/短标签
        for w in ("QTY", "QUANTITY", "UNIT", "UNITPRICE", "AMOUNT", "CURRENCY", "HSCODE",
                  "NODESCRIPTION", "DESCRIPTION", "NETWEIGHT", "GROSSWEIGHT", "MEAS",
                  "PACKAGES", "PKGS", "MARKS", "BATCH", "ITEM", "SPECIFICATION", "PACKING"):
            FIELD_NAME_KEYS.add(w)
    return FIELD_NAME_KEYS


def is_label(s: str) -> bool:
    """判断某行是否为"字段名（标签）"。

    判定优先看"是否等于某个已知字段别名"：因为公司名、地址也可能很短且无数字，
    但它们绝不会与字段别名"全等"，因此不会被误判为标签。
    """
    s = norm_text(s)
    if len(s) < 2 or len(s) > 64:
        return False
    if s.upper().startswith(("DEMO", "PAGE ")):
        return False
    core = re.sub(r"[:：]\s*$", "", s).strip()
    # 原产地证/装箱单常见 "1. Exporter / 出口商"：去掉序号前缀再判断
    core = re.sub(r"^\d{1,2}[.、)．]\s*", "", core).strip()
    key = code_key(core)
    if key and key in _field_name_keys():
        return True
    if re.search(r"\d{4}", core):
        return False
    # 带索引前缀（"2. Consignee"）已经剥掉序号，含短数字（"1. Exporter" 已处理）仍放行
    if not re.match(r"^[A-Za-z\u4e00-\u9fff(（]", core):
        return False
    han = len(re.findall(r"[\u4e00-\u9fff]", core))
    words = [w for w in re.split(r"[\s/&,]+", core) if w]
    if han > 0:
        # 中英混排且英文词很少（"SODA ASH LIGHT(苏打灰,轻质)"）更像品名而非标签
        if re.match(r"^[A-Z0-9][A-Z0-9\s\(\)\-]*[A-Z]{2,}.*[（(]", core) and not LABEL_WORD_RX.search(
                re.split(r"[（(]", core)[0]):
            return False
        # 中英混排（"产品名称 Product name"）常见于 SDS/COA，放宽到 40 字符
        return len(core) <= (40 if re.search(r"[A-Za-z]{3,}", core) else 30) and len(words) <= 5
    # 纯英文：先排除"明显是值"的形态（全大写地名/机构名、含门牌号的地址）
    if _is_namelike_value(core):
        return False
    # 两个及以下的短词（"SODA ASH LIGHT"/"Na2CO3"）更可能是品名/代号，不是标签；
    # 真正的标签通常带字段词（Port of ... / Net Weight / Consignee）。
    if len(words) <= 2 and not LABEL_WORD_RX.search(core):
        return False
    return len(core) <= 32 and len(words) <= 4


LABEL_WORD_RX = re.compile(
    r"\b(NO|NUMBER|DATE|NAME|ADDRESS|PORT|PLACE|TERM|TERMS|VESSEL|VOYAGE|WEIGHT|"
    r"QUANTITY|QTY|PRICE|AMOUNT|VALUE|CURRENCY|ORIGIN|COUNTRY|DESCRIPTION|GOODS|"
    r"PACKAGES?|PKGS?|MARKS?|BATCH|LOT|CONTRACT|INVOICE|CREDIT|SHIPPER|CONSIGNEE|"
    r"NOTIFY|BUYER|SELLER|EXPORTER|IMPORTER|CARRIER|FREIGHT|DESTINATION|LOADING|"
    r"DISCHARGE|RECEIPT|ISSUE|ISSUED|ON|BOARD|SHIPPED|VALIDITY|TOTAL|UNIT|NET|GROSS)\b")


def _is_namelike_value(s: str) -> bool:
    """全大写的地名/公司名/港口名，几乎不可能是字段标签。"""
    letters = re.sub(r"[^A-Za-z]", "", s)
    if not letters:
        return False
    if s != s.upper():
        return False                      # 只有全大写才做这个判断
    if re.search(r"[,\u4e00-\u9fff]", s):
        return True                       # 带逗号/中文括注 → 典型地名（QINGDAO, CHINA）
    if re.search(r"^(MV|MT|M/V|S/S|PT|CV)\b", s):
        return True                       # 船名前缀 / 公司类型前缀
    if re.search(r"^(PORT|PLACE|POINT|CITY|TOWN)\s+OF\s+", s):
        return True                       # "PORT OF WILSON" 这类地名整体形态
    if LABEL_WORD_RX.search(s):
        return False                      # 其余含标签词的全大写短语 → 当标签处理
    return True


def is_sentence(s: str) -> bool:
    """整句型文本（长句、含分号、或典型英文句式）—— 不应当作"值"去配对。"""
    s = norm_text(s)
    if not s:
        return False
    if len(s) >= 46:
        if s[-1] in ".\u3002":
            return True
        if ";" in s or "\uff1b" in s:
            return True
        if len(s.split()) >= 8 and re.search(r"\b(the|and|shall|with|from)\b", s, re.I):
            return True
    if len(re.findall(r"[\u4e00-\u9fff]", s)) >= 24 and re.search(r"[\u3002\uff1b]", s):
        return True
    return False


def _looks_like_fieldname(s: str) -> bool:
    """像不像"字段名"（用于值判定）：中文短标签，或首字母大写的 ≤3 个词。
    全大写的地名/机构名/船名（QINGDAO, CHINA / MV OCEAN PRIDE）不算字段名。"""
    s = norm_text(s)
    if re.search(r"\d", s):
        return False
    if _is_namelike_value(s):
        return False
    words = [w for w in re.split(r"[\s/&,]+", s) if w]
    han = re.findall(r"[\u4e00-\u9fff]", s)
    if han:
        return len(s) <= 12 and len(words) <= 3
    if not words or len(words) > 3:
        return False
    return all(w[:1].isupper() for w in words) and len(s) <= 18


def is_value(s: str) -> bool:
    """判断一段文本是否可能是一个"字段值"。

    顺序：
      1) 纯值形态（数字 / 金额 / 编码 / 日期）→ 是
      2) 句子（句号或分号结尾的长句、中文长句）→ 否
      3) 以冒号结尾 → 否（它是标签）
      4) 像字段名（短、无数字、首字母大写≤3 词）→ 否
      5) 其余：≤40 字符，或含数字且不超过 10 个词 → 是
    """
    s = norm_text(s)
    if not s:
        return False
    if VALUE_ONLY.match(s):
        return True
    if is_sentence(s):
        return False
    if re.search(r"[:\uff1a]\s*$", s):
        return False
    if _looks_like_fieldname(s) or code_key(s) in _field_name_keys():
        return False
    if len(s) <= 40:
        return True
    # 稍长但没有句子特征的公司名/地址（"PT XXX - GUDANG YYY"）仍是值
    if len(s) <= 72 and not re.search(r"[;；]", s) and len(s.split()) <= 9:
        return True
    return bool(re.search(r"\d", s)) and len(s.split()) <= 10


INCOTERM_RX = re.compile(
    r"^\s*(EXW|FCA|FAS|FOB|CFR|CIF|CPT|CIP|DAP|DPU|DDP)\b\s*[\u4e00-\u9fff]", re.I)


def _starts_with_incoterm(s: str) -> bool:
    """「CIF 青岛至雅加达」这类"术语+中文地名"行本身就是个标签，值在下一行。"""
    return bool(INCOTERM_RX.match(norm_text(s)))


# 纯标签 ≠ 值：像 "品名 Description" / "HS Code" 这种"中英字段名"组合，本身不含
# 任何商品/公司/地点信息，出现在值块里说明是表格表头。
_NAME_MIDDLE = ("OF", "AND", "&", "THE", "NO.", "NO")


def _is_pure_label(t: str) -> bool:
    """判断一行文本是否只是"字段名"（可作为标签），而非字段值。"""
    t = norm_text(t)
    if not t or re.search(r"\d", t):
        return False
    if _match_field_raw_any(t) >= 0.99:
        return True
    han = re.findall(r"[\u4e00-\u9fff]+", t)
    lat = re.findall(r"[A-Za-z]{2,}", t)
    if not han or not lat:
        return False
    # 中英各只有 1–2 个词，且英文是字段词 → 表头
    if len(han) == 1 and len(lat) <= 2 and len(t) <= 26:
        return all(LABEL_WORD_RX.search(w.upper()) for w in lat)
    return False


def _match_field_raw_any(t: str) -> float:
    best = 0.0
    for cand in FIELD_BY_ID:
        try:
            best = max(best, _match_field(cand, t))
        except Exception:
            continue
    return best


def _ends_with_colon(s: str) -> bool:
    return bool(re.search(r"[:：]\s*$", s))


def _value_after_label(line: str, aliases: List[str]) -> str:
    """在标签行内、标签之后取值；若标签后有「：」则取冒号后，否则取标签之后。"""
    u = line.upper()
    best = -1
    for a in aliases:
        k = u.find(a.upper())
        if k >= 0:
            best = max(best, k + len(a))
    if best < 0:
        return ""
    rest = line[best:]
    rest = re.sub(r"^[\s:：/\-—|、]+", "", rest).strip()
    return rest


def _seq_no(s: str) -> bool:
    return bool(re.match(r"^\s*\d{1,2}[\.\)、]?\s*$", s))


def _footer(s: str) -> bool:
    return bool(re.search(r"(非真实业务文件|Page \d+ of \d+)", s))


def detect_columns(lines: List[Dict[str, Any]], tol: float = 9.0) -> List[float]:
    """按行首 x 坐标聚集出"列起点"（单证普遍左对齐，箱式布局亦然）。"""
    xs = sorted(ln["bbox"][0] for ln in lines if ln["bbox"])
    cols: List[List[float]] = []
    for x in xs:
        if cols and x - cols[-1][-1] <= tol:
            cols[-1].append(x)
        else:
            cols.append([x])
    # 过滤掉偶发出现的"伪列"（只出现过 1 次、且与主列相距很近）
    out = []
    for c in cols:
        if len(c) >= 2 or not out or (c[0] - out[-1]) > 24:
            out.append(sum(c) / len(c))
    return out


def _nearest_col(x: float, cols: List[float]) -> int:
    best, bd = 0, 1e9
    for k, c in enumerate(cols):
        d = abs(x - c)
        if d < bd:
            best, bd = k, d
    return best


def _has_numeric_right(lines, used, i, ci, cols):
    """同一基线上、比第 1 个右列更靠右的位置是否还有数字（说明存在数字列）。"""
    base = lines[i]["bbox"][1]
    for j, other in enumerate(lines):
        if j == i or j in used or not other["bbox"]:
            continue
        if abs(other["bbox"][1] - base) >= 3.5:
            continue
        cj = _nearest_col(other["bbox"][0], cols)
        if cj >= ci + 2 and re.search(r"\d", other["text"]):
            return True
    return False


def _split_inline(t: str):
    """把「买方 Buyer：PT XXX」拆成 (标签, 值)；无冒号或冒号后为空则返回 None。"""
    m = re.search(r"[:：]\s*(\S.*)$", t)
    if not m or m.start() == 0:
        return None
    lab = t[:m.start()].strip()
    val = t[m.end():].strip()
    if lab and val:
        return lab, val
    return None


def _pretag(lines, cols):
    """为每一行预判"角色"：H=表头标签行 / K=键值标签行 / V=值行 / X=其他。

    做法：先做一遍"只看同行与同列"的配对，凡是"被别人当成标签"的行标记为 H/K；
    被表头行（H）覆盖、且位于标签右方的行也标记为 H（表头值列名）。
    这样后续主循环不会把公司名、地址这类的续行当成标签去"向下取值"。
    """
    n = len(lines)

    def col_of(k):
        return _nearest_col(lines[k]["bbox"][0], cols)

    role = ["X"] * n
    for i in range(n):
        ln = lines[i]
        if not ln["bbox"]:
            continue
        t = norm_text(ln["text"])
        lab = re.sub(r"[:：]\s*$", "", t).strip()
        if not (is_label(lab) or (code_key(lab) in _field_name_keys() and _ends_with_colon(t))):
            continue
        ci = col_of(i)
        # (1) 同行"标签：值"
        sp = _split_inline(t)
        if sp:
            role[i] = "K"
            continue
        # (2) 同行右侧有值 → 本行是标签
        for j in range(n):
            if j == i or not lines[j]["bbox"] or col_of(j) <= ci:
                continue
            if abs(lines[j]["bbox"][1] - ln["bbox"][1]) < 3.5 and \
               lines[j]["bbox"][0] - cols[ci] > 22 and is_value(lines[j]["text"]):
                role[i] = "H" if i + 1 < n and lines[i + 1]["bbox"] and \
                    col_of(i + 1) == ci and lines[i + 1]["bbox"][1] > ln["bbox"][1] else "K"
                break
        else:
            # (3) 下一行是值且同列/邻列
            if i + 1 < n and lines[i + 1]["bbox"] and is_value(lines[i + 1]["text"]):
                cn = col_of(i + 1)
                dy = lines[i + 1]["bbox"][1] - ln["bbox"][3]
                # 唛头/地址这类多行块的首行间距可能较大（约 12–22pt）
                if -2 <= dy <= 22 and cn in (ci, ci + 1):
                    role[i] = "K"
    # 表头行的"值列名"（右侧相邻、非数字、非句子）
    for i in range(n):
        if role[i] != "H" or not lines[i]["bbox"]:
            continue
        ci = col_of(i)
        for j in range(n):
            if j == i or role[j] != "X" or not lines[j]["bbox"]:
                continue
            if col_of(j) > ci and abs(lines[j]["bbox"][1] - lines[i]["bbox"][1]) < 3.5 and \
               not re.search(r"\d", lines[j]["text"]) and len(lines[j]["text"]) <= 40:
                role[j] = "H"
    return role


def _expand_blobs(lines):
    """把 "TOTAL: 1,000 BAGS  NET WT: 1,000,000 KG" 这类一行多字段的文本
    拆成多个虚拟行（同一 y 坐标、按 x 递增），供配对使用。"""
    extra = []
    for ln in lines:
        hits = list(re.finditer(
            r"(件数|包数|总件数|净重|毛重|体积|合计|总金额|NO\.?\s*OF\s*PKGS?|N\.?W\.?|G\.?W\.?|MEAS\.?)\s*[:：]?\s*",
            ln["text"], re.I))
        if len(hits) < 2:
            continue
        for m in hits:
            seg = ln["text"][m.start():]
            nx = re.search(r"\s{2,}", seg)
            seg = seg[:nx.start()] if nx else seg
            if len(seg) < len(m.group(1)) + 1:
                continue
            w = text_width(ln["text"], 8.0, "hei") or 1.0
            x = ln["bbox"][0] + (m.start() / max(len(ln["text"]), 1)) * w
            extra.append({"text": seg.strip(), "bbox": [x, ln["bbox"][1], x + 60, ln["bbox"][3]],
                          "page": ln.get("page"), "virtual": True})
    return extra


def build_pairs(pages):
    """把行序列解析为"标签→值"对。how ∈ same_line / right_column / next_line / row_right。

    规则（按优先级，均基于列对齐）：
      a) 同行「标签：值」                     → same_line
      b) 同行右侧，列号更大、基线相近          → right_column
      c) 下一行，同列（多行续行）              → next_line
      d) 下一行，紧邻右列（标签行 × 值行）      → row_right
    右侧列上的标签只在同行取值；表头行（下一行仍是标签）不做向下配对。
    """
    pairs = []
    for pg in pages:
        lines = [ln for ln in pg.lines if not _seq_no(ln["text"]) and not _footer(ln["text"])]
        cols = detect_columns(lines)
        if not cols:
            continue
        used = set()

        def col_of(k):
            return _nearest_col(lines[k]["bbox"][0], cols)

        def is_header_row(k):
            if k + 1 >= len(lines) or not lines[k + 1]["bbox"]:
                return False
            nxt = lines[k + 1]
            return (col_of(k + 1) <= col_of(k)
                    and is_label(re.sub(r"[:：]\s*$", "", norm_text(nxt["text"])))
                    and nxt["bbox"][1] > lines[k]["bbox"][1])

        role = _pretag(lines, cols)
        for i, ln in enumerate(lines):
            t = norm_text(ln["text"])
            lab = re.sub(r"[:：]\s*$", "", t).strip()
            if not ln["bbox"] or i in used or role[i] not in ("H", "K"):
                continue
            if not (is_label(lab) or _ends_with_colon(t) or _starts_with_incoterm(t)):
                continue
            ci = col_of(i)
            # (a) 同行「标签：值」
            sp = _split_inline(t)
            if sp and is_value(sp[1]):
                pairs.append({"page": pg.page_no, "label": sp[0], "value": norm_text(sp[1]),
                              "bbox": ln["bbox"], "value_bbox": ln["bbox"], "how": "same_line"})
                continue
            # (b) 同行右侧（列号更大、基线相近）
            right = None
            best_dx = None
            raw_txt = t
            for j in range(len(lines)):
                if j == i or j in used or not lines[j]["bbox"] or col_of(j) <= ci:
                    continue
                if abs(lines[j]["bbox"][1] - ln["bbox"][1]) >= 3.5:
                    continue
                # "CAS No." 这类标签本身被 is_value 判为类值文本，但只要右侧还有
                # 真正的值，就仍要继续找。这里只在右侧文本含数字、或不是字段别名时
                # 才接受（否则会把"标签|标签|值"里的标签当成值）。
                if not is_value(lines[j]["text"]):
                    continue
                if re.match(r"^[-—\u2013\u2014/.,\s*]+$", norm_text(lines[j]["text"])):
                    continue      # 占位符/表格空单元格
                if (code_key(lines[j]["text"]) in _field_name_keys()
                        and not re.search(r"\d", lines[j]["text"])):
                    continue
                dx = lines[j]["bbox"][0] - cols[ci]
                if dx <= 22:
                    # 该值所在列没被 detect_columns 识别出来时，退化为"相对本标签
                    # 的 x 有足够水平距离"（例如产地证 "2. Consignee" 与值列）
                    dx = lines[j]["bbox"][0] - ln["bbox"][2]
                if dx <= 22:
                    continue
                if best_dx is None or dx < best_dx:
                    best_dx, right = dx, j
            # 右侧候选若本身是一个"字段标签"（如 Port of Discharge），说明该行是
            # "标签|标签|值" 的多列布局，不能把它当成左侧标签的值。
            if right is not None and is_label(lines[right]["text"]):
                rt = lines[right]["text"]
                if not re.search(r"[\d.,].*\d", rt):
                    right = None            # 纯文字标签（Port of Discharge / 毛重 KG）
                else:
                    # 右侧带数字，但若它是与本标签同义的另一种写法（"Gross Weight"
                    # 旁边是"毛重 KG"），说明这是表头行，不能当值。
                    same = False
                    for cand in FIELD_BY_ID:
                        if _match_field(cand, t) >= 0.8 and _match_field(cand, rt) >= 0.8:
                            same = True
                            break
                    if same:
                        right = None
            if right is not None:
                used.add(right)
                # 值可能是多行名称/地址的首行（"QINGDAO HAIHUA IMPORT &" +
                # 下一行 "EXPORT CO., LTD."）：把紧接的同列续行拼上。
                vtxt = norm_text(lines[right]["text"])
                rn = right + 1
                while rn < len(lines) and rn not in used:
                    nb = lines[rn]["bbox"]
                    if not nb or col_of(rn) != col_of(right):
                        break
                    gap = nb[1] - lines[rn - 1]["bbox"][3]
                    if not (-2 <= gap <= 6):
                        break
                    if not is_value(lines[rn]["text"]):
                        break
                    # 签章/日期等尾注不并入公司名
                    if re.match(r"(AUTHORIZED|SIGNATURE|SIGNED|FOR AND ON|签字|签章|盖章|日期)",
                                lines[rn]["text"].strip().upper()):
                        break
                    # 地址行（含门牌/邮编/INDUSTRIAL/PARK 等）不并入公司名
                    if re.search(r"\b(ROAD|RD\.?|STREET|ST\.?|JL\.?|JALAN|BLOCK|BLOK|"
                                 r"BUILDING|MANSION|FLOOR|ROOM|KAWASAN|INDUSTRIAL|DISTRICT|"
                                 r"INDONESIA|CHINA|BEKASI|JAKARTA)\b|\d{4,}",
                                 lines[rn]["text"].upper()):
                        break
                    # 续行不该是另一个字段标签
                    if is_label(re.sub(r"[:：]\s*$", "", norm_text(lines[rn]["text"]))) and \
                            not re.search(r"\d", lines[rn]["text"]):
                        break
                    vtxt = vtxt + " " + norm_text(lines[rn]["text"])
                    used.add(rn)
                    rn += 1
                    if len(vtxt) > 160:
                        break
                pairs.append({"page": pg.page_no, "label": lab, "value": vtxt,
                              "bbox": ln["bbox"], "value_bbox": lines[right]["bbox"],
                              "how": "right_column"})
                continue
            # (b2) 标签下方若干行内，右侧同一"值列"上的数值
            #      典型：左侧是"单价 Unit Price (...)"附若干说明行，值在同一行右侧
            #      仅在标签本身带"价格/术语"语义时启用（避免把日期串到编号字段）
            if re.search(r"(单价|价格|PRICE|TOTAL|合计|TERM|术语|AMOUNT|金额)", t.upper()):
                hit = None
                for k2 in range(i + 1, min(i + 8, len(lines))):
                    o = lines[k2]
                    if not o["bbox"] or k2 in used:
                        continue
                    dy = o["bbox"][1] - ln["bbox"][3]
                    if dy > 62:
                        break
                    if not col_of(k2) > ci:
                        continue
                    if abs(o["bbox"][1] - ln["bbox"][1]) < 3.5:
                        continue
                    if is_value(o["text"]):
                        hit = k2
                        break
                if hit is not None:
                    used.add(hit)
                    pairs.append({"page": pg.page_no, "label": lab,
                                  "value": norm_text(lines[hit]["text"]),
                                  "bbox": ln["bbox"], "value_bbox": lines[hit]["bbox"],
                                  "how": "row_right"})
                    continue
            # (c)/(d) 下一行：同列续行，或紧邻右列
            if ci > 0 or i + 1 >= len(lines) or (i + 1) in used:
                continue
            nxt = lines[i + 1]
            # 下一行可能是地址续行的首行，_pretag 会把它标成 H/V，这里都接受
            if not nxt["bbox"] or not is_value(nxt["text"]):
                continue
            # 只有 "-" / "—" / "N/A" 这类占位符不能当值（表格空单元格）
            if re.match(r"^[-—\u2013\u2014/.,\s*]+$", norm_text(nxt["text"])):
                continue
            if _is_pure_label(norm_text(nxt["text"])):
                continue          # 下一行是表头标签（品名 Description / HS Code），不是值
            cn = col_of(i + 1)
            dy = nxt["bbox"][1] - ln["bbox"][3]
            # 唛头/地址块首行间距可达 ~22pt（同上 (3) 预判的阈值）
            if not (-2 <= dy <= 22 and nxt["bbox"][0] - ln["bbox"][0] >= -10 and cn in (ci, ci + 1)):
                continue
            vals = [norm_text(nxt["text"])]
            k = i + 2
            xref = nxt["bbox"][0]
            while k < len(lines) and len(vals) < 4:
                nb = lines[k]["bbox"]
                if not nb or k in used or role[k] not in ("V", "X") or not is_value(lines[k]["text"]):
                    break
                d2 = nb[1] - lines[k - 1]["bbox"][3]
                if not (-2 <= d2 <= 6 and abs(nb[0] - xref) <= 6):
                    break
                if re.match(r"(AUTHORIZED|SIGNATURE|SIGNED|FOR AND ON|签字|签章|盖章)",
                            lines[k]["text"].strip().upper()):
                    break
                vals.append(norm_text(lines[k]["text"]))
                used.add(k)
                k += 1
            pairs.append({"page": pg.page_no, "label": lab, "value": " ".join(vals),
                          "bbox": ln["bbox"], "value_bbox": nxt["bbox"],
                          "how": "next_line" if cn == ci else "row_right"})
            for q in range(i + 1, k):
                used.add(q)
            continue
        # (d) 标签下方的多行文本块（唛头 / 收货人地址 / 条款）
        #     标签独占一行，值在其正下方同一起始列，连续 1..8 行。
        blk = []
        k = i + 1
        xref = ln["bbox"][0]
        while k < len(lines) and len(blk) < 8:
            nb = lines[k]["bbox"]
            if not nb or k in used or role[k] not in ("V", "X", "H"):
                break
            if not is_value(lines[k]["text"]):
                break
            # 值块里若出现"品名 Description / HS Code"这类表头标签，说明是表头行而非值
            if _is_pure_label(norm_text(lines[k]["text"])):
                break
            if abs(nb[0] - xref) > 10:
                break
            # 首行间距可放宽（标签与值块之间常空一行），续行必须紧密
            lim = 30 if not blk else 6
            gap = nb[1] - (lines[k - 1]["bbox"][3] if lines[k - 1]["bbox"] else 0)
            if not (-2 <= gap <= lim):
                break
            blk.append(k)
            k += 1
        if blk:
            vtxt = " / ".join(norm_text(lines[q]["text"]) for q in blk)
            pairs.append({"page": pg.page_no, "label": lab, "value": vtxt,
                          "bbox": ln["bbox"], "value_bbox": lines[blk[0]]["bbox"],
                          "how": "below_block"})
            for q in blk:
                used.add(q)
    return pairs


# ---------------------------------------------------------------------------
# 表格区域：用"纯数字/金额列"反推列边界，再结合已知表格列名识别列语义
# ---------------------------------------------------------------------------
NUM_TOKEN = ("num", "money", "int")


def _col_bands(lines: List[Dict[str, Any]]) -> List[Tuple[float, float]]:
    xs: List[Tuple[float, float]] = []
    for ln in lines:
        if ln["bbox"] and re.match(r"^[\d,\.]+$", norm_text(ln["text"])) and len(ln["text"]) <= 16:
            xs.append((ln["bbox"][0], ln["bbox"][2]))
    if not xs:
        return []
    bands: List[List[float]] = []
    for x0, x1 in sorted(xs):
        placed = False
        for b in bands:
            if x0 <= b[1] + 3 and x1 >= b[0] - 3:
                b[0] = min(b[0], x0)
                b[1] = max(b[1], x1)
                placed = True
                break
        if not placed:
            bands.append([x0, x1])
    return [(b[0], b[1]) for b in bands]


def _which_band(x0: float, x1: float, bands: List[Tuple[float, float]]) -> int:
    best, best_ov = -1, 0.0
    for k, (b0, b1) in enumerate(bands):
        ov = min(x1, b1) - max(x0, b0)
        if ov > best_ov:
            best, best_ov = k, ov
    return best


def _longest_token(s: str) -> int:
    return max([len(t) for t in re.findall(r"[\d,]+", s)] or [0])


def _header_clusters(lines, cols, i):
    """把表头行（可能折成 2–3 行）按"列起点聚类"，返回 [{text, rows}]。

    折行表头里，同一个列名的第二行常常与列起点略有偏移（"Gross Weight" /
    "毛重 KG"），因此用 14pt 的容差把它们并入同一簇。
    """
    clusters = []
    base = lines[i]["bbox"][1]
    for j in range(i, min(i + 3, len(lines))):
        o = lines[j]
        if not o["bbox"] or o["bbox"][1] - base > 30:
            break
        if re.search(r"\d", o["text"]) or len(o["text"]) > 34:
            break
        c = None
        for cl in clusters:
            if abs(cl["x"] - o["bbox"][0]) <= 14:
                c = cl
                break
        if c is None:
            clusters.append({"x": o["bbox"][0], "texts": [norm_text(o["text"])],
                             "rows": [j], "lead": j})
            # 表头每一列都必须在前几行内出现（否则说明已经进入正文）
        else:
            c["texts"].append(norm_text(o["text"]))
            c["rows"].append(j)
        base = o["bbox"][1]
    return clusters


def _table_regions(lines, cols):
    """识别表格区域：表头簇（列名 → 列起点） + 下方数据行。"""
    n = len(lines)
    regions = []
    seen = set()
    for i in range(n):
        ln = lines[i]
        if not ln["bbox"]:
            continue
        same = [j for j in range(n)
                if lines[j]["bbox"] and abs(lines[j]["bbox"][1] - ln["bbox"][1]) < 3.5]
        if len(same) < 3:
            continue
        if any(re.search(r"\d", lines[j]["text"]) or is_sentence(lines[j]["text"])
               or len(lines[j]["text"]) > 34 or (lines[j]["bbox"][2] - lines[j]["bbox"][0]) > 96
               for j in same):
            continue
        clusters = _header_clusters(lines, cols, i)
        if len(clusters) < 3:
            continue
        head_rows = sorted({r for cl in clusters for r in cl["rows"]})
        key = (head_rows[0], head_rows[-1])
        if key in seen:
            continue
        seen.add(key)
        last_head = max(head_rows)
        rows, prev_y = [], max(lines[j]["bbox"][3] for j in head_rows)
        for j in range(last_head + 1, n):
            o = lines[j]
            if not o["bbox"]:
                break
            if o["bbox"][1] - prev_y > 70:
                break
            rows.append(j)
            prev_y = o["bbox"][1]
        ndata = sum(1 for j in rows if re.search(r"\d", lines[j]["text"]))
        if ndata >= 2 and rows:
            regions.append({"clusters": clusters, "header_rows": head_rows,
                            "rows": rows})
    return regions


PAGE_CTX = {"page": 0}


def table_candidates(doc_type, pages, pairs):
    """按"表头列名 → 其所在列 → 该列的数据值"抽取表格数值。"""
    usable = {f["id"]: f for f in FIELDS if f.get("fmt") in NUM_TOKEN}
    out = {}
    for pg in pages:
        lines = [ln for ln in pg.lines if not _seq_no(ln["text"]) and not _footer(ln["text"])]
        cols = detect_columns(lines)
        if not cols:
            continue
        PAGE_CTX["page"] = pg.page_no
        for reg in _table_regions(lines, cols):
            for cl in reg["clusters"]:
                htext = " ".join(cl["texts"])
                fids = []
                for cand_id in usable:
                    sc = _match_field(cand_id, htext)
                    if sc >= 0.5:
                        fids.append((sc, cand_id))
                if not fids:
                    continue
                fids.sort(reverse=True)
                for _, fid in fids:
                    if fid in out:
                        continue
                    val = _col_value(lines, reg["rows"], reg["header_rows"], cl["x"], fid,
                                     usable, doc_type)
                    if val:
                        out[fid] = val
                        break
    return out


def _col_value(lines, rows, head_rows, x0, fid, usable, doc_type):
    """在表头列 x0 下方找该列的数值单元格（同列内、跳过折行续行）。"""
    best = None
    for j in rows:
        if j in head_rows:
            continue
        o = lines[j]
        if abs(o["bbox"][0] - x0) > 26:
            continue
        if not re.search(r"\d", o["text"]):
            continue
        if not _value_fits(usable[fid].get("fmt", ""), o["text"], doc_type, fid):
            continue
        best = o
        break
    if best is None:
        return None
    return {"value": norm_text(best["text"]), "page": PAGE_CTX.get("page", 0),
            "bbox": best["bbox"], "how": "table"}


def _alias_hit(alias_u: str, label_u: str) -> bool:
    """别名命中：含中文的别名按"中文段原样子串"；纯英文别名按"字母集合"匹配，
    以兼容 CI 中 "BUYER" 与 "买方 BUYER" 这类中英混写。"""
    han = re.findall(r"[\u4e00-\u9fff]+", alias_u)
    lat = re.findall(r"[A-Z]+", alias_u)
    if han:
        if not all(h in label_u for h in han):
            return False
        if lat:   # 英文词也要按字母集合出现在标签中
            return all(w in re.findall(r"[A-Z]+", label_u) for w in lat)
        return True
    if not lat:
        return False
    if len("".join(lat)) < 3:
        return False
    # 短缩写（Qty / NW / GW / MEAS / Curr）按"整词全等"匹配，避免落入长词
    if len("".join(lat)) <= 4:
        return all(w in re.findall(r"[A-Z]+", label_u) for w in lat)
    return all(w in re.findall(r"[A-Z]+", label_u) for w in lat)


def _match_field(fid: str, label: str) -> float:
    """标签匹配分数 0..1。纯英文短缩写（PI/CO/SDS/GW）不单独作为标签。
    表格列名（Qty / HS Code / Unit…）不作为键值标签匹配，避免与表头混淆。"""
    lab = norm_text(label).upper()
    lab_core = re.sub(r"^[\d\.\s]+", "", lab).strip(" :-—")
    # "CIF 青岛至雅加达" / "CFR TANJUNG PRIOK" 这类以术语开头的行：术语本身即契约
    if fid == "incoterm" and re.match(
            r"^\s*(EXW|FCA|FAS|FOB|CFR|CIF|CPT|CIP|DAP|DPU|DDP)\b", lab_core):
        return 1.0
    if not lab_core:
        return 0.0
    # 注意：表格列名（Qty / Amount / Unit Price）与字段别名同形，是合法匹配来源，
    # 这里不再用 HEADER_WORDS 拦截，改由"取值是否像数字/代码"来把关。
    best = 0.0
    latin = re.findall(r"[A-Z]+", lab_core)
    for a in FIELD_ALIASES.get(fid, []):
        if not _alias_hit(a.upper(), lab_core):
            continue
        ratio = min(1.0, len(a) / max(len(lab_core), 1))
        score = 0.62 + 0.38 * ratio
        # 标签是 "No + 空格 + 字段名" 之类（如 "No.: Invoice No"），允许部分命中
        if latin and re.search(r"[A-Z]{3,}\s*$", lab_core):
            score = max(score, 0.55 * min(1.0, 2 * ratio))
        best = max(best, score)
    return best


def _value_fits(fmt: Optional[str], val: str, doc_type: str = "", fid: str = "") -> bool:
    v = norm_text(val)
    if not v:
        return False
    if fmt in ("num", "money"):
        return bool(_NUM_RX.search(v))
    if fmt == "int":
        return bool(re.match(r"^[\d,\.\s]+", v))
    if fmt == "date":
        return bool(re.search(r"\d{4}[-/年.]\d{1,2}", v))
    if fmt == "cas":
        return bool(_CAS_RX.search(v))
    if fmt == "hs":
        return bool(_HS_RX.search(v))
    if fmt in ("code", "port", "text"):
        return len(v) >= 2
    return True


def _claimed_by_other(fid: str, label: str) -> bool:
    """若另一个字段对该标签的匹配分数明显更高，则本字段让位。"""
    own = _match_field(fid, label)
    for other in FIELD_ALIASES:
        if other == fid:
            continue
        if _match_field(other, label) > own + 0.12:
            return True
    return False

def extract_field(fid: str, pages: List[PageText], doc_type: str,
                  pairs: Optional[List[Dict[str, Any]]] = None,
                  tables: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    # L1 定位标记
    for pg in pages:
        if fid in pg.markers:
            mk = pg.markers[fid]
            if mk["text"]:
                return {"value": mk["text"], "raw": mk["text"], "page": mk["page"],
                        "bbox": mk["bbox"], "source": "L1-marker", "conf": "high"}
    if pairs is None:
        pairs = build_pairs(pages)
    fb = FIELD_BY_ID.get(fid, {})
    fmt = fb.get("fmt")

    # L2 标签→值配对（取最高分；被其他字段命中的标签不得复用 → 减少错配）
    best = None
    for pr in pairs:
        sc = _match_field(fid, pr["label"])
        if sc <= 0.35:
            continue
        if not _value_fits(fmt, pr["value"], doc_type, fid):
            continue
        if _claimed_by_other(fid, pr["label"]):
            continue
        # 值的形态必须与该字段类型相符：文本字段不应取到数字，编号类不应取到纯中文
        if fmt in ("text", "longtext", "en_text") and re.match(r"^[\d\s,.:%\-]+$", pr["value"]):
            continue
        if fmt in ("id", "hs", "code") and is_sentence(pr["value"]):
            continue
        # 金额必须像金额（含小数、货币符号或千分位）；避免把"43"当金额
        if fmt == "money" and re.match(r"^\d{1,2}$", pr["value"].strip()):
            continue   # "43" 这类纯小整数不是金额
        # 值的单位必须与该字段相符
        _U = {"money": (), "num": (), "int": ()}
        if fmt == "money" and re.search(r"\b(CTNR|CNTR|CONTAINERS?|CBM|KG|BAGS?|MT)\b",
                                        pr["value"], re.I):
            continue
        if fmt == "num" and re.search(r"\b(CTNR|CNTR|CONTAINERS?|BAGS?)\b", pr["value"], re.I):
            continue
        # 单据日期不应被"发货日/签单日"这类标签抢走
        if fmt == "date" and fid not in ("date", "onboard_date"):
            continue
        # 件数字段只接受"纯数字"，带 BAGS/袋 等单位的留给 L3/后续解析
        if fmt == "int" and not re.match(r"^\d{1,3}(,\d{3})*$|^\d+$", pr["value"].strip()):
            continue
        # package_type 必须是包装方式，不能是单据编号/重量
        if fid == "package_type":
            v = pr["value"]
            if re.search(r"(No\.?|编号|No：)\s*[A-Z]{2,}-", v) or re.match(r"^\s*[A-Z]{2,}-\d", v):
                continue
            if re.search(r"(净重|毛重|NET|GROSS)\s*\d", v, re.I):
                continue
        # incoterm 必须真的以贸易术语开头；但若"标签本身"已经是术语
        # （"CIF 青岛至雅加达" → 下一行 FREIGHT & INSURANCE...），则从标签取术语
        if fid == "incoterm":
            if re.match(r"^\s*(EXW|FCA|FAS|FOB|CFR|CIF|CPT|CIP|DAP|DPU|DDP)\b",
                        norm_text(pr["label"]).upper()):
                pass
            elif not re.match(r"^\s*(EXW|FCA|FAS|FOB|CFR|CIF|CPT|CIP|DAP|DPU|DDP)\b",
                              pr["value"].upper()):
                continue
        if fmt not in NUM_TOKEN and fid not in ("incoterm",) \
                and _match_field(fid, pr["value"]) >= 0.99:
            continue          # 值本身与字段名一致 → 多半是列标题
        if sc > (best["score"] if best else 0):
            best = {"score": sc, **pr}

    # L3 表格列（仅当 L2 未命中，且目标列不含"负值/单独符号"）
    if best is None and fmt in NUM_TOKEN:
        if tables is None:
            tables = table_candidates(doc_type, pages, pairs)
        tb = tables.get(fid)
        if tb:
            if "value" in tb:            # L3 表头列语义抽取结果
                val = tb["value"]
                return {"value": val, "raw": "table-col:" + fid, "page": tb["page"],
                        "bbox": tb["bbox"], "source": "L3-table", "conf": "medium"}
            val = tb.get("value_map", {}).get(tb.get("own_band"))
            if val:
                return {"value": val, "raw": "table-col:" + fid, "page": tb["page"],
                        "bbox": tb["header_bbox"], "source": "L3-table", "conf": "medium"}

    # L4 全文正则（仅对可强校验的编号/编码类字段）
    if best is None and fid in ("cas_no", "hs_code"):
        for pg in pages:
            m = _CAS_RX.search(pg.text) if fid == "cas_no" else _HS_RX.search(pg.text)
            if m:
                return {"value": m.group(0), "raw": "regex:" + m.group(0), "page": pg.page_no,
                        "bbox": None, "source": "L4-regex", "conf": "low"}

    if best:
        return {"value": _trim_value(fid, fmt, best["value"], best),
                "raw": best["label"] + " → " + best["value"],
                "page": best["page"], "bbox": best.get("value_bbox") or best.get("bbox"),
                "source": "L2-" + best["how"],
                "conf": "high" if best["score"] >= 0.9 else "medium"}
    return None


_NUM_UNIT = {f["id"]: f.get("unit") for f in FIELDS}


def _trim_value(fid: str, fmt: Optional[str], val: str, pr: Dict[str, Any]) -> str:
    """数值字段从混排单元格里切出"数量 + 单位"，避免把后续单元格一起带进来。"""
    v = norm_text(val)
    if fid == "incoterm":
        m = re.match(r"^\s*(EXW|FCA|FAS|FOB|CFR|CIF|CPT|CIP|DAP|DPU|DDP)\b", v.upper())
        if m:
            return m.group(1).upper()
        # 值本身不含术语，但标签以术语开头（"CIF 青岛至雅加达" 的下一行是说明）
        lab = norm_text(pr.get("label", "")).upper()
        m = re.match(r"^\s*(EXW|FCA|FAS|FOB|CFR|CIF|CPT|CIP|DAP|DPU|DDP)\b", lab)
        if m:
            return m.group(1).upper()
        return v
    unit = _NUM_UNIT.get(fid)
    if fmt in NUM_TOKEN:
        m = re.search(r"[\d,]+(?:\.\d+)?\s*(?:MT|M/T|KG|KGS|CBM|BAGS|BAG|TONS?|TON)?", v)
        if m:
            return m.group(0).strip()
    return v

# ---------------------------------------------------------------------------
# 文档对象
# ---------------------------------------------------------------------------
class Document:
    def __init__(self, path: str):
        self._tables = None
        self.path = path
        self.name = os.path.basename(path)
        self.pages: List[PageText] = []
        self.page_count = 0
        self.cls: Dict[str, Any] = {}
        self._pairs: Optional[List[Dict[str, Any]]] = None
        self.fields: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        ext = os.path.splitext(self.path)[1].lower()
        if ext == ".pdf":
            d = pymupdf.open(self.path)
            self.page_count = d.page_count
            for i, p in enumerate(d, 1):
                self.pages.append(PageText(i, p))
            d.close()
        else:
            with open(self.path, "r", encoding="utf-8", errors="ignore") as f:
                txt = f.read()
            self.page_count = 1
            pg = PageText.__new__(PageText)
            pg.page_no = 1
            pg.lines = [{"text": norm_text(l), "bbox": None, "size": 9}
                        for l in txt.splitlines() if l.strip()]
            pg.markers = {}
            pg.text = txt
            self.pages.append(pg)
        self.cls = classify(self.name, self.pages)

    @property
    def pairs(self):
        if self._pairs is None:
            self._pairs = build_pairs(self.pages)
        return self._pairs

    @property
    def tables(self) -> Dict[str, Any]:
        if self._tables is None:
            self._tables = table_candidates(self.doc_type, self.pages, self.pairs)
        return self._tables

    @property
    def doc_type(self) -> str:
        return self.cls.get("doc_type", "UNKNOWN")

    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)


# ---------------------------------------------------------------------------
# 业务归属：这堆文件是不是同一票？
# ---------------------------------------------------------------------------
def _anchor_values(d: Document) -> Dict[str, str]:
    out = {}
    for key in ("contract_no", "ci_no", "pi_no", "bl_no", "co_no"):
        rec = extract_field(key, d.pages, d.doc_type, d.pairs, d.tables)
        if rec:
            out[key] = rec["value"]
    return out


def find_anchor(docs: List[Document]) -> Dict[str, Any]:
    """找被最多单证引用的业务编号（合同号优先），并识别"同族但不同写"的变体。"""
    counts: Dict[str, List[str]] = {}
    for d in docs:
        for key, val in _anchor_values(d).items():
            k = code_key(val)
            if len(k) < 6 or "SALESCONTRACT" in k:
                continue
            counts.setdefault(k, []).append(d.name)
    if not counts:
        return {"anchor": None, "refs": [], "variants": {}}

    def rank(kv):
        k, names = kv
        return (len(set(names)), 1 if k.startswith("SC") or "SC20" in k else 0, len(k))

    anchor, names = max(counts.items(), key=rank)
    variants = {}
    for k, ns in counts.items():
        if k == anchor:
            continue
        # 编辑距离 1–3 且共享前缀 → 视为"同一编号的不同写法"（需要对齐而非判为另一票）
        if _near(k, anchor):
            variants[k] = sorted(set(ns))
    unidentified = [d.name for d in docs if not any(code_key(v) for v in _anchor_values(d).values())]
    return {"anchor": anchor, "refs": sorted(set(names)), "variants": variants,
            "unidentified": unidentified, "all_counts": counts}


def _near(a: str, b: str, maxd: int = 3) -> bool:
    if abs(len(a) - len(b)) > maxd:
        return False
    if a[:6] != b[:6]:
        return False
    # Levenshtein（短串，直接 DP）
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] <= maxd


# ---------------------------------------------------------------------------
# 汇总：一份文件的全部字段
# ---------------------------------------------------------------------------
REGEX_ALLOW = {
    "SC": {"quantity", "net_weight", "gross_weight", "package_count", "volume"},
    "PI": {"quantity", "net_weight", "gross_weight", "package_count", "amount"},
    "CI": {"quantity", "net_weight", "gross_weight", "package_count", "volume", "amount"},
    "PL": {"quantity", "net_weight", "gross_weight", "package_count", "volume"},
    "BL": {"quantity", "net_weight", "gross_weight", "package_count", "volume"},
    "CO": {"quantity", "net_weight", "gross_weight", "package_count"},
    "CUSTOMS": {"quantity", "net_weight", "gross_weight", "package_count", "amount"},
    "COA": {"quantity"},
    "SDS": (),
    "LC": {"quantity", "amount"},
    "DGD": {"package_count", "gross_weight"},
    "INSP": {"quantity"},
}


def _supports(doc_type, fid):
    return fid in REGEX_ALLOW.get(doc_type, set())


def regex_scan(fid, pages, doc_type):
    """L4 兜底：用「标签 + 值」正则整页扫描（仅在前几层都失败时使用）。"""
    pats = {
        # 严格形式优先（带标签或带单位），避免把任意数字误当件数
        "package_count": r"(?:件数|包数|总件数|NO\.?\s*OF\s*(?:PKGS?|PACKAGES?))"
                         r"[^0-9\n]{0,18}(\d{1,3}(?:,\d{3})+|\d{1,6})\s*(?:BAGS?|袋)?"
                         r"|(\d{1,3}(?:,\d{3})+|\d{1,6})\s*BAGS?\b",
        "net_weight": r"(?:净重|N\.?W\.?|NET\s*WEIGHT)[^0-9\n]{0,18}"
                      r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(KG|KGS|MT|T)?",
        "gross_weight": r"(?:毛重|G\.?W\.?|GROSS\s*WEIGHT)[^0-9\n]{0,18}"
                        r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(KG|KGS|MT|T)?",
        "volume": r"(?:体积|尺码|MEAS\.?|MEASUREMENT)[^0-9\n]{0,18}"
                  r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(CBM|M3)?",
        "quantity": r"(?:数量|QTY|QUANTITY)[^0-9\n]{0,18}"
                    r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(MT|KG|T)?",
    }
    pat = pats.get(fid)
    if not pat:
        return None
    # 兜底只在"本单证通常载明该数值"时才用，避免把说明文字里的示例数字当成业务值
    if not _supports(doc_type, fid):
        return None
    rx = re.compile(pat, re.I)
    for pg in pages:
        for ln in pg.lines:
            m = rx.search(ln["text"])
            if not m:
                continue
            num = next(g for g in (m.groups() or ()) if g)
            if fid in ("net_weight", "gross_weight", "volume", "quantity") and m.lastindex and m.lastindex >= 2:
                g2 = m.group(m.lastindex)
                if g2 and re.match(r"^(KG|KGS|MT|T|CBM|M3)$", g2, re.I):
                    num = num + " " + g2
            if not _value_fits((FIELD_BY_ID.get(fid) or {}).get("fmt", ""), num, doc_type, fid):
                continue
            return {"value": norm_text(num), "page": pg.page_no, "bbox": ln["bbox"],
                    "raw": ln["text"], "page_no": pg.page_no, "how": "regex",
                    "source": "L4", "conf": "low"}
    return None


LC_TAGS = {
    "20": "lc_no", "31C": "date", "31D": "expiry", "50": "applicant", "59": "beneficiary",
    "32B": "lc_amount", "44E": "pol", "44F": "pod", "44C": "latest_shipment",
    "45A": "goods_desc", "41A": "presentation", "46A": "doc_required", "47A": "addl_cond",
}


def lc_fields(d):
    """信用证（MT700）专用抽取：SWIFT 字段号 + 右侧值。"""
    out = {}
    for pg in d.pages:
        for i, ln in enumerate(pg.lines):
            m = re.match(r"^\s*(\d{2}[A-Z]?)\s+(.*)$", ln["text"])
            if not m:
                continue
            tag, label = m.group(1), m.group(2)
            key = LC_TAGS.get(tag)
            if not key:
                continue
            val, vb = None, None
            for j in range(i + 1, len(pg.lines)):
                o = pg.lines[j]
                if o["bbox"][0] > ln["bbox"][2] + 4 and abs(o["bbox"][1] - ln["bbox"][1]) < 6:
                    val, vb = o["text"], o["bbox"]
                    break
            if not val:
                continue
            out.setdefault(key, {"value": norm_text(val), "page": pg.page_no,
                                 "bbox": vb or ln["bbox"], "label": ln["text"],
                                 "how": "lc_field", "source": "L2", "conf": "high"})
    return out


def extract_document(d: Document, expected: List[str]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if d.doc_type == "LC":
        out.update(lc_fields(d))
    candidates = list(dict.fromkeys(list(expected) + [f["id"] for f in FIELDS]))
    for fid in candidates:
        rec = extract_field(fid, d.pages, d.doc_type, d.pairs, d.tables)
        if rec is None and fid in expected:
            rec = regex_scan(fid, d.pages, d.doc_type)
        if rec:
            rec.setdefault("source", "L2" if rec.get("how", "").startswith(("same", "right", "next", "row")) else "L4")
            rec.setdefault("conf", "medium" if rec.get("how") != "table" else "medium")
            out[fid] = rec
    return out


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)
