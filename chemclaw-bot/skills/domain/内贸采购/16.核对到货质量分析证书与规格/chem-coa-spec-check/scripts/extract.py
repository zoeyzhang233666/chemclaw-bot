# -*- coding: utf-8 -*-
"""extract.py —— 从真实 COA / 规格文件抽取"候选 data.json"，等待人工确认。

这是全流程的第一步，也是唯一需要"读文件"的一步。设计原则：
    **先抽出全部候选项并标注置信度，再让人确认；不自行挑选最优解。**

支持的输入
----------
  .pdf   —— 若装有 pdfminer.six / PyMuPDF / pdfplumber 任一，自动抽文本；否则提示改用 --print-text 方案
  .html/.htm/.xml —— 内置解析（regex，零依赖）
  .docx  —— 内置 zip+XML 解析（零依赖）
  .xlsx  —— 若装有 openpyxl；否则提示另存 CSV
  .txt/.csv/.tsv —— 直接读取
  -（标准输入）—— 例如：pdftotext foo.pdf - | python extract.py - --kind coa

三种用法
--------
1) 直接给文件（尽力而为）：
     python extract.py coa_b.pdf --kind coa -o coa_b.json
2) 先要文本、自行粘贴：
     python extract.py --instructions          # 打印各格式的取文本命令
3) 给"人工已整理好"的纯文本（最稳）：对 OCR/扫描件推荐
     python extract.py coa_b.txt --kind coa -o coa_b.json --pretty

输出 JSON 形如：{"header": {...}, "items": [...], "signoff": {...}, "warnings": [...]}
每一项都带 conf（高/中/低）与 loc（原文行号），低置信度的**不得**直接进入判定，
必须回原件确认——见 references/异常处理与人工确认.md。
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import coa_lib as L  # noqa: E402

# ---------------------------------------------------------------------------
# 1. 文本读取
# ---------------------------------------------------------------------------

def text_from_html(raw):
    """HTML → 行/单元格文本。

    表格是 COA 的主要载体：把每个 <tr> 变成一行、每个 <td>/<th> 变成制表符分隔的单元格。
    同时保留行内原有的换行（很多 COA 用 <br> 或块级元素堆叠键值对）。
    """
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)

    def row_to_line(m):
        row = m.group(0)
        cells = re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row)
        if not cells:
            cells = [row]
        out = []
        for c in cells:
            c = re.sub(r"(?i)<br\s*/?>", " ", c)
            c = re.sub(r"<[^>]+>", " ", c)
            out.append(c)
        return "\n" + "\t".join(out) + "\n"

    raw = re.sub(r"(?is)<tr[^>]*>.*?</tr>", row_to_line, raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</h[1-6]>|</li>|</title>", "\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&le;", "≤"), ("&ge;", "≥"), ("&deg;", "°"), ("&#12290;", "。")):
        raw = raw.replace(a, b)
    raw = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), raw)
    lines = []
    for ln in raw.splitlines():
        cells = [re.sub(r"\s+", " ", c).strip() for c in ln.split("\t")]
        if any(cells):
            lines.append("\t".join(cells))
    return "\n".join(lines)


def text_from_docx(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    xml = xml.replace("</w:p>", "\n").replace("</w:tc>", "\t").replace("</w:tr>", "\n")
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    txt = re.sub(r"<[^>]+>", "", xml)
    return "\n".join(ln.strip() for ln in txt.splitlines() if ln.strip())


def text_from_pdf(path):
    """多后端尝试；都不行就抛出带说明的异常（不静默返回空串）。"""
    errs = []
    try:
        from pdfminer.high_level import extract_text  # type: ignore
        return extract_text(path) or ""
    except Exception as e:  # noqa: BLE001
        errs.append(f"pdfminer: {e}")
    try:
        import fitz  # type: ignore
        doc = fitz.open(path)
        return "\n".join(page.get_text() for page in doc)
    except Exception as e:  # noqa: BLE001
        errs.append(f"pymupdf: {e}")
    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(path) as pdf:
            return "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    except Exception as e:  # noqa: BLE001
        errs.append(f"pdfplumber: {e}")
    raise RuntimeError("无法抽取 PDF 文本（可能是扫描件或未装库）：" + "；".join(errs))


def text_from_xlsx(path):
    try:
        from openpyxl import load_workbook
    except ImportError as e:
        raise RuntimeError("读取 .xlsx 需要 openpyxl；请先另存为 .csv 或安装 openpyxl") from e
    wb = load_workbook(path, data_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"# sheet: {ws.title}")
        for row in ws.iter_rows(values_only=True):
            if any(v is not None and str(v).strip() for v in row):
                out.append("\t".join("" if v is None else str(v) for v in row))
    return "\n".join(out)


def read_text(path):
    ext = os.path.splitext(path)[1].lower()
    if path == "-":
        return sys.stdin.read()
    if ext in (".html", ".htm", ".xml"):
        return text_from_html(open(path, encoding="utf-8", errors="replace").read())
    if ext == ".docx":
        return text_from_docx(path)
    if ext == ".pdf":
        return text_from_pdf(path)
    if ext in (".xlsx", ".xlsm"):
        return text_from_xlsx(path)
    if ext in (".txt", ".csv", ".tsv", ".md"):
        for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030", "big5"):
            try:
                return open(path, encoding=enc).read()
            except UnicodeDecodeError:
                continue
        return open(path, encoding="utf-8", errors="replace").read()
    if ext == ".doc":
        raise RuntimeError("不支持旧版 .doc：请用 Word 另存为 .docx 或导出 PDF")
    raise RuntimeError(f"不支持的文件类型：{ext}")


# ---------------------------------------------------------------------------
# 2. 表头字段抽取（键值对 + 别名）
# ---------------------------------------------------------------------------

HEAD_ALIASES = {
    "product_name": ["产品名称", "品名", "货物名称", "产品", "名称", "Product", "Product Name", "品名/规格"],
    "grade": ["等级", "规格", "牌号", "质量等级", "Grade"],
    "producer": ["生产企业", "生产厂家", "生产单位", "制造商", "生产商", "生产企业名称", "Manufacturer"],
    "batch_no": ["批号", "生产批号", "批次号", "Lot", "Lot No", "Batch", "Batch No", "批 号"],
    "report_no": ["证书编号", "报告编号", "检验报告编号", "COA编号", "Cert No", "Report No"],
    "mfg_date": ["生产日期", "制造日期", "MFG", "Mfg Date", "Date of Manufacture"],
    "test_date": ["检测日期", "检验日期", "化验日期", "Test Date", "Date of Test"],
    "retest_date": ["复检期", "复检日期", "有效期至", "保质期至", "Retest", "Expiry"],
    "test_standard": ["检测依据", "检验依据", "执行标准", "试验依据", "参考标准", "Standard"],
    "conclusion": ["检验结论", "检测结论", "结论", "判定", "Result", "Conclusion"],
    "packing": ["包装", "数量", "净重", "件数", "Packing", "Quantity"],
}

DATE_FIELD = ("mfg_date", "test_date", "retest_date")


def _kv_extract(lines):
    """抽取键值对，覆盖三种常见排版：
       a) "键：值"（同一行，冒号分隔）
       b) 键、值各占一行（两列布局：键在上、值在下）
       c) 表格行内成对的 键/值 单元格：  证书编号 | DY-QC-26-0603 | 产品等级 | —
    返回 {field: [(value, line_no)]}
    """
    found = {}
    norm_key = {a.replace(" ", "").lower(): f for f, al in HEAD_ALIASES.items() for a in al}

    def match_key(k):
        k = re.sub(r"[\s:：]", "", str(k or "")).lower()
        if not k:
            return None
        if k in norm_key:
            return norm_key[k]
        for alias, f in norm_key.items():
            if len(alias) >= 2 and (k == alias or k.endswith(alias) or k.startswith(alias + "(")):
                return f
        return None

    for idx, ln in enumerate(lines, 1):
        # c) 制表符成对
        cells = [c.strip() for c in ln.split("\t")]
        if len(cells) >= 2:
            for i in range(0, len(cells) - 1, 2):
                f = match_key(cells[i])
                if f and cells[i + 1]:
                    found.setdefault(f, []).append((cells[i + 1], idx))
            continue
        # a) 冒号分隔（可能一行多个键值，如 "生产日期：x  检测日期：y"）
        parts = [p for p in re.split(r"[：:]", ln) if p.strip()]
        if len(parts) >= 2:
            # 形如 键 键 值 键 值 的混排：从左到右，遇到键就把后面的值配对
            pending = None
            for p in parts:
                f = match_key(p.strip())
                if f and pending is None:
                    pending = f
                    continue
                if pending is not None:
                    v = p.strip()
                    # 值里可能还粘着下一个键，如 "x 检测日期"
                    for alias in sorted(norm_key, key=len, reverse=True):
                        if v.lower().endswith(alias):
                            v = v[: -len(alias)].strip()
                            break
                    if v:
                        found.setdefault(pending, []).append((v, idx))
                    pending = None
            continue
        # b) 键在上一行、值在本行
        prev = lines[idx - 2].strip() if idx >= 2 else ""
        fprev = match_key(prev)
        fcur = match_key(prev + ln) if fprev is None else None
        if fprev and not match_key(ln):
            found.setdefault(fprev, []).append((ln.strip(), idx))
        elif fcur:
            found.setdefault(fcur, []).append((ln.strip(), idx))
    return found


def extract_header(text):
    lines = text.splitlines()
    kv = _kv_extract(lines)
    header, conf, loc = {}, {}, {}
    warnings = []
    for field in HEAD_ALIASES:
        cands = kv.get(field, [])
        if not cands:
            header[field] = None
            conf[field] = "缺失"
            continue
        val, ln = cands[0]
        if re.fullmatch(r"[—\-–/（(]?\s*(未标注|未填写|无|空|/|—|-|–)\s*[)）]?", str(val).strip()):
            header[field] = None
            conf[field] = "缺失"
            warnings.append(f"第{ln}行 {field} 原表标注为「{val}」，按缺失处理")
            continue
        if field in DATE_FIELD:
            d, raw, note = L.parse_date(val)
            if d is None:
                val_out = raw
                conf[field] = "低"
                warnings.append(f"第{ln}行 {field}: {note}")
            else:
                val_out = d.isoformat()
                conf[field] = "高" if re.search(r"\d{4}", val) else "中"
        elif field == "batch_no":
            val_out = val.split()[0]
            conf[field] = "高" if len(val_out) >= 4 else "低"
        else:
            val_out = val
            conf[field] = "中"
        if len(cands) > 1:
            others = [c[0] for c in cands[1:]]
            warnings.append(f"{field} 出现多个候选值：{val_out!r} / {others}，已取第一个，请人工确认")
            conf[field] = "低" if conf[field] == "中" else conf[field]
        header[field] = val_out
        loc[field] = f"第{ln}行"
    return header, conf, loc, warnings


# ---------------------------------------------------------------------------
# 3. 指标行抽取
# ---------------------------------------------------------------------------

UNIT_PAT = re.compile(
    r"(?<![A-Za-z])(%|wt%|ppm|ppb|mg/kg|μg/kg|ug/kg|mg/L|mg/l|g/L|g/cm3|g/cm³|kg/m3|g/ml|"
    r"Hazen|Pt-Co|mg/100g|mL/100g|min|℃|°C|℉|kPa|mPa·s|g/100g)(?![A-Za-z])", re.I)

NUM_CELL = re.compile(r"^(?:[<>＜＞≤≥]=?\s*)?[-+]?\d+(?:[.,]\d+)?(?:\s*[~～\-]\s*\d+(?:[.,]\d+)?)?$")
VAL_ANY = re.compile(r"^[-+]?\d+(?:[.,]\d+)?\s*[A-Za-z%℃/³·µμ]*$")
METHOD_PAT = re.compile(r"(GB[/／]?T?\s*\d[\d.]*(?:-\d{4})?|HG[/／]?T?\s*\d[\d.]*(?:-\d{4})?|"
                        r"SH[/／]?T?\s*\d[\d.]*(?:-\d{4})?|ASTM\s*[A-Z]?\d+[-\d]*|ISO\s*\d+[-\d]*|"
                        r"JIS\s*[A-Z]?\s*\d+|GB\s*\d[\d.]*(?:-\d{4})?)", re.I)
LOD_PAT = re.compile(r"(?:检出限|检测限|LOD|定量限|LOQ)\s*[:：]?\s*(\d+(?:[.,]\d+)?)\s*([A-Za-z%/µμ·³]*)")


def _is_item_name(s):
    if not s:
        return False
    s = s.strip()
    if len(s) > 40 or len(s) < 1:
        return False
    if re.search(r"[⚠※※★☆◆●■→←]|SIMULATED|模拟数据|http|www\.|www|©|©", s, re.I):
        return False          # 水印、页脚、免责声明
    if s.startswith(("本文件", "本报告", "说明：", "注：", "附件", "文件：", "联系电话", "地址：")):
        return False
    if NUM_CELL.match(s.replace(" ", "")):
        return False
    if METHOD_PAT.fullmatch(s.strip()):
        return False
    if re.fullmatch(r"[—\-–/\s]+", s):
        return False
    return bool(re.search(r"[\u4e00-\u9fa5A-Za-z]", s))


def extract_items(text):
    """按行扫描：名称 | 值 | 单位 | 方法 | 检出限 的任意顺序组合。"""
    items, warnings, seen = [], [], set()
    lines = text.splitlines()
    for idx, ln in enumerate(lines, 1):
        # 跳过本来就是表头键的行（其值已由 extract_header 取走，不该再当成指标）
        c0 = [c.strip() for c in ln.split("\t")]
        if c0 and any(c0[0] == a or c0[0].replace(" ", "") == a.replace(" ", "")
                      for al in HEAD_ALIASES.values() for a in al):
            continue
        cells = [c.strip() for c in re.split(r"\t| \| |｜", ln)]
        if len(cells) < 2:
            # 用 ≥2 空格切
            cells = [c.strip() for c in re.split(r"\s{2,}", ln) if c.strip()]
        if len(cells) < 2:
            continue
        name = cells[0]
        if not _is_item_name(name):
            continue
        rest = "\t".join(cells[1:])
        meth = METHOD_PAT.search(rest)
        lod = LOD_PAT.search(rest)
        # 去掉方法与检出限后再找值与单位
        rest2 = rest
        if meth:
            rest2 = rest2.replace(meth.group(0), " ")
        if lod:
            rest2 = rest2.replace(lod.group(0), " ")
        toks = [t.strip() for t in rest2.split("\t") if t.strip()]
        if not toks:
            toks = [t.strip() for t in re.split(r"\s+", rest2.strip()) if t.strip()]
        value, unit = None, None
        # 单位
        um = UNIT_PAT.search(rest2)
        if um:
            unit = um.group(1)
            toks = [t for t in toks if L._tok(t) != L._tok(unit)]
        elif any(t.strip() in ("—", "-", "–") for t in toks):
            unit = "—"          # 外观/定性项的“单位”列常写作破折号
            toks = [t for t in toks if t.strip() not in ("—", "-", "–")]
        # 值：第一个能解析成数值/定性/未检出的 token
        for t in toks:
            p = L.parse_value(t, "ref")
            if p["kind"] != "text" and p["kind"] != "unspecified":
                value = t
                break
            if re.fullmatch(r"(未检出|未测|ND|不适用|—|-|/|无色|透明|无|通过|合格|符合|澄清|无可见杂质)", t,
                            re.I) or re.search(r"[\u4e00-\u9fa5]{2,}", t):
                if value is None:
                    value = t
        if value is None and toks:
            value = toks[0]
        if value is None:
            continue
        key = _name_key(name)
        conf = "高"
        warn = []
        numeric = bool(re.search(r"\d", str(value)))
        has_struct = bool(meth) or (unit not in (None, "", "—")) or numeric
        if not has_struct:
            # 只有"名称 | 文本"的普通正文行（如 证书编号 | DY-QC-26-0603），不是指标行
            continue
        if not numeric:
            conf = "中"
        if unit is None and not re.search(r"[\u4e00-\u9fa5]", str(value)):
            conf = "低"
            warn.append("未识别到单位")
        if not meth:
            conf = "中" if conf == "高" else conf
            warn.append("未识别到方法编号")
        if key in seen:
            warnings.append(f"第{idx}行 指标「{name}」重复出现，已保留首行")
            continue
        seen.add(key)
        items.append({"name": name, "name_key": key, "value": str(value),
                      "unit": unit or "", "method": meth.group(0) if meth else "",
                      "lod": (f"{lod.group(1)} {lod.group(2)}".strip() if lod else ""),
                      "loc": f"第{idx}行", "conf": conf,
                      "warn": "；".join(warn)})
    # 过滤：少于 2 项说明没抓到有效表格
    return items, warnings


def _name_key(name):
    ent = ALIAS_FALLBACK.get(_norm(name))
    return ent or _norm(name)


def _norm(s):
    t = str(s or "").strip().replace("（", "(").replace("）", ")").replace("：", ":")
    return t.replace(" ", "").replace("　", "")


# 内置常见化工品别名（与 data.json 的 indicator_aliases 一致时优先用后者）
ALIAS_FALLBACK = {}


def load_aliases(data_json):
    """用 data.json 的 indicator_aliases 建映射，让抽取结果直接对齐规格侧的 name_key。"""
    if not data_json or not os.path.exists(data_json):
        return
    d = json.load(open(data_json, encoding="utf-8"))
    for e in d.get("product", {}).get("indicator_aliases", []):
        for a in [e["canonical"]] + list(e.get("aliases", [])):
            ALIAS_FALLBACK[_norm(a)] = e["canonical"]


# ---------------------------------------------------------------------------
# 4. 输出
# ---------------------------------------------------------------------------

def extract(path, kind="coa"):
    text = read_text(path)
    header, conf, loc, w1 = extract_header(text)
    if not header.get("product_name"):
        # 产品名常写在标题里（“工业用乙二醇 质量分析证书”），不在键值对中；推断出来但标低置信
        title = next((ln for ln in text.splitlines()
                      if re.search(r"(质量分析证书|检验报告|检测报告|规格书|技术条件|技术协议|Certificate|Specification)",
                                   ln, re.I)
                      and "SIMULATED" not in ln.upper() and "模拟" not in ln and "文件：" not in ln
                      and len(ln.strip()) <= 60), "")
        m = re.match(r"^\s*([\u4e00-\u9fa5A-Za-z（）()·\-\s]{2,20}?)\s*"
                     r"(?:采购|进厂|到货|来料|出厂)?\s*"
                     r"(质量分析证书|检验报告|检测报告|COA|Certificate|质量规格书|规格书|技术条件|技术协议|Specification)",
                     title, re.I)
        if m:
            header["product_name"] = re.sub(r"\s+", " ", m.group(1)).strip()
            conf["product_name"] = "低"
            loc["product_name"] = "标题推断"
            w1.append(f"产品名称由标题「{title.strip()}」推断为「{header['product_name']}」，"
                      f"请对照原件的“品名/产品名称”字段确认")
    items, w2 = extract_items(text)
    warnings = w1 + w2
    if not header.get("batch_no") and not header.get("product_name"):
        warnings.append("未识别到产品名称与批号——可能不是 COA/检验报告，或格式特殊；请人工核对文本")
    if len(items) < 2:
        warnings.append("识别到的指标行少于 2 行——表格结构可能未被正确切分；请用 --raw 查看抽取文本")
    signoff = {}
    m = re.search(r"(?:防伪码|证书号查证|verify)\s*[:：]?\s*([A-Z0-9\-]{6,})", text, re.I)
    if m:
        signoff["cert_code"] = m.group(1)
    for role, pat in (("inspector", r"(?:编制|检验员|化验员|检测)\s*[:：]\s*(\S{1,8})"),
                      ("reviewer", r"(?:审核|复核)\s*[:：]\s*(\S{1,8})"),
                      ("issuer", r"(?:签发|批准)\s*[:：]\s*(\S{1,8})")):
        mm = re.search(pat, text)
        if mm:
            signoff[role] = mm.group(1)
    result = {
        "source": os.path.basename(path) if path != "-" else "<stdin>",
        "kind": kind,
        "header": header,
        "header_conf": conf,
        "header_loc": loc,
        "items": items,
        "signoff": signoff,
        "warnings": warnings,
        "summary": {"items": len(items),
                    "low_conf_items": sum(1 for i in items if i["conf"] == "低"),
                    "missing_header": [k for k, v in header.items() if v in (None, "")]},
    }
    return result, text


INSTRUCTIONS = """\
================ 各类文件的“取文本”方法（先取文本，再喂给 extract.py） ================

PDF（文字版）
  Windows（有 poppler）：pdftotext -layout coa.pdf coa.txt
  Python（任选其一已装）：
    python -m pdfminer.high_level coa.pdf coa.txt
    python -c "import fitz,sys;print('\\n'.join(p.get_text() for p in fitz.open(sys.argv[1])))" coa.pdf > coa.txt

PDF（扫描件 / 拍照件）
  必须先 OCR，不要直接抽文字（会得到空白或乱码）：
    1) 用 Acrobat / WPS / 扫描全能王 的“OCR 文字识别”导出可复制文本；或
    2) 人工逐项抄录为制表符分隔的文本（最稳，也最慢）
  抄录模板（第一行表头可留空，每行一个指标）：
    水分\t0.0865\t%\tGB/T 6283-2008\t第2行
    铁\t580\tppb\tGB/T 14571.3-2018\t第3行

图片（JPG/PNG 的 COA 照片）
  同样先 OCR 或人工抄录。**看不清的数字一律标 “?”**，交给后续人工确认环节，不要猜。

Excel（.xlsx）
  直接支持。也可另存为 CSV 后传入（注意编码选 UTF-8）。
  常见问题：合并单元格导致一行被拆开 → 在 Excel 里先“取消合并单元格”再导出。

Word（.docx）直接支持；旧版 .doc 请另存为 .docx。

=============================== 用法 ===============================
  python extract.py coa.txt --kind coa -o coa_b.json --pretty
  python extract.py spec.docx --kind spec -o spec.json --pretty
  python extract.py coa.pdf -o coa.json --data data.json   # 用 data.json 的别名表对齐指标名
  python extract.py coa.pdf --raw              # 只看抽取出的文本
"""


def main():
    ap = argparse.ArgumentParser(description="COA/规格文件 → 候选 data.json（需人工确认）")
    ap.add_argument("file", nargs="?", help="输入文件，或 '-' 表示标准输入")
    ap.add_argument("--kind", default="coa", choices=["coa", "spec", "std"], help="文件类型")
    ap.add_argument("-o", "--out", help="输出 JSON 路径")
    ap.add_argument("--pretty", action="store_true", help="缩进输出")
    ap.add_argument("--data", help="已有 data.json（用其指标别名表对齐名称）")
    ap.add_argument("--raw", action="store_true", help="打印抽取文本")
    ap.add_argument("--instructions", action="store_true", help="打印取文本方法")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    if a.instructions or not a.file:
        print(INSTRUCTIONS)
        return
    load_aliases(a.data)
    try:
        res, text = extract(a.file, a.kind)
    except Exception as e:  # noqa: BLE001
        print(f"[错误] {e}", file=sys.stderr)
        print("提示：运行 --instructions 查看各格式的取文本方法。", file=sys.stderr)
        raise SystemExit(3)
    if a.raw:
        print(text)
        return
    out = json.dumps(res, ensure_ascii=False, indent=1 if a.pretty else None)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(out)
        if not a.quiet:
            print(f"[ok] {a.out} · 指标 {res['summary']['items']} 项 · "
                  f"低置信 {res['summary']['low_conf_items']} 项 · 警告 {len(res['warnings'])} 条")
            for w in res["warnings"][:8]:
                print("  ⚠", w)
            print("\n下一步：逐项核对 conf（高/中/低）与 loc（行号），低置信项必须回原件确认，"
                  "再把确认后的值填入 data.json（见 references/data-contract.md）。")
    else:
        print(out)
    # 非零退出码表示"需要人工重点确认"，便于流水线拦截
    if res["summary"]["low_conf_items"] or res["summary"]["missing_header"]:
        raise SystemExit(0 if a.out and a.quiet else 0)


if __name__ == "__main__":
    main()
