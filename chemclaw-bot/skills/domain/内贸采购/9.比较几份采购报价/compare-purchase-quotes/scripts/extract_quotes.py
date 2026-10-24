#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_quotes.py —— 多格式报价文件 → 统一 L1 抽取值（关键词正则 + 待确认队列）

支持：.txt/.csv/.md、.xlsx、.docx、.pdf（需 pymupdf）、图片（需 pytesseract + 中文语言包）
输出：JSON 数组，每条含 file/fields/ignored/missing/ambiguous

用法：
    python extract_quotes.py 报价1.pdf 报价2.xlsx 报价3.png -o result.json
"""
import argparse, json, re, sys, zipfile, pathlib
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# 字段抽取（关键词出现在任意位置均可；正文同上放行「：」「|」分隔）
FIELD_RE = {
    "product": r"(?:产品名称|品名|物料名称|商品名称|货名)[^\n\r，,；;|]{0,3}[：:\s\t]*([^\n\r，,；;|]{2,40})",
    "spec": r"(?:规格|含量|纯度|浓度|牌号|等级)[^\n\r，,；;|\t]{0,10}[：:\s\t]*([^\n\r，,；;|\t]{2,60})",
    "unit": r"(?:计价单位|计量单位)[^\n\r，,；;|\t]{0,3}[：:\s\t]*([^\n\r，,；;|\t]{1,16})",
    "price": r"(?:单价|报价|价格|售价|出厂价)[^\n\r，,；;|\t]{0,10}[：:\s\t]*([0-9][0-9,.]*\s*元(?:\s*[/／]\s*[^\s，,；;|()]{1,10})?)",
    "tax": r"((?:含税|不含税|税\s*率|税率\s*[0-9]{1,2}%|增值税[专普]用?发票)[^\n\r，,；;|\t]{0,40})",
    "pack": r"(?:包装形式|包装方式|包装规格|包装物|包装)[^\n\r，,；;|\t]{0,3}[：:\s\t]*([^\n\r，,；;|\t]{2,40})",
    "pack_fee": r"(?:包装费|桶费|包装物费)[^\n\r，,；;|\t]{0,3}[：:\s\t]*([^\n\r，,；;|\t]{0,40})",
    "freight": r"(?:运费|运输费|运杂费|是否包邮)[^\n\r，,；;|\t]{0,3}[：:\s\t]*([^\n\r，,；;|\t]{0,60})",
    "delivery": r"(?:交货方式|交货地点|交货期|交付方式|提货方式|交货)[^\n\r，,；;|\t]{0,3}[：:\s\t]*([^\n\r，,；;|\t]{2,60})",
    "payment": r"(?:付款方式|付款条件|结算方式|结算周期|账期|款到)[^\n\r，,；;|\t]{0,8}[：:\s\t]*([^\n\r，,；;|\t]{2,60})",
    "moq": r"(?:最小起订量|起订量|起订|MOQ|单笔不低于)[^\n\r，,；;|\t]{0,3}[：:\s\t]*([^\n\r，,；;|\t]{1,30})",
    "validity": r"(?:报价有效期|有效日期|有效期|价保/有效期)[^\n\r，,；;|\t]{0,3}[：:\s\t]*([^\n\r，,；;|\t]{2,50})",
    "quality": r"((?:质量标准|执行标准|质量\s*标准|GB\s*/?\s*T\s*\d+|企业标准)[^\n\r]{0,80})",
    "origin": r"(?:产地|生产企业|生产厂家|品牌)[^\n\r，,；;|\t]{0,3}[：:\s\t]*([^\n\r，,；;|\t]{1,30})",
}

# 容易忽略的费用 —— 单独扫描，没命中即「待确认」
IGNORE_RE = {
    "卸车费": r"卸(?:车|货|装)?费[^\n\r，,；;|]{0,40}",
    "检验费": r"(?:检验费|检测费|化验费|SGS|第三方检测)[^\n\r，,；;|]{0,40}",
    "罐车清洗费": r"(?:清洗费|洗罐|洗车费|蒸汽置换)[^\n\r，,；;|]{0,40}",
    "包装回收费": r"(?:押金|回收|退桶|包装回收)[^\n\r，,；;|]{0,40}",
    "涨价条款": r"(?:调价|涨价|价格浮动|随行就市|价格保护|联动)[^\n\r，,；;|]{0,60}",
    "短有效期": r"(?:当日报价|当日有效|报价日有效|一天内有效)[^\n\r，,；;|]{0,30}",
}

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}

# 字段 → 该字段在「键」行可能出现的写法（用于「键在上一行、值在下一行」的抽取）
FIELD_RE_ALIASES = {
    "product": "产品名称|品名|物料名称|商品名称|货名",
    "spec": "规格/含量|规格|含量|纯度|浓度|牌号|等级",
    "unit": "计价单位|计量单位",
    "price": "单价|报价|价格|售价|出厂价",
    "tax": "税率|发票类型|价税",
    "pack": "包装形式|包装方式|包装规格|包装|包装物",
    "pack_fee": "包装费|桶费|包装物费",
    "freight": "运费|运输费|运杂费",
    "delivery": "交货方式|交货地点|交货期|交付方式|提货方式|交货",
    "payment": "付款方式|付款条件|结算方式|结算周期|账期",
    "moq": "最小起订量|起订量|MOQ|单笔不低于",
    "validity": "报价有效期|有效日期|有效期",
    "quality": "质量标准|执行标准",
    "origin": "产地\\s*/\\s*生产企业|产地|生产企业|生产厂家|品牌",
}


def read_text(path: pathlib.Path) -> str:
    ext = path.suffix.lower()
    if ext in (".txt", ".csv", ".md", ".tsv"):
        for enc in ("utf-8-sig", "gbk", "utf-16"):
            try:
                return path.read_text(encoding=enc)
            except Exception:
                continue
        return path.read_bytes().decode("utf-8", "ignore")
    if ext == ".docx":
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        xml = re.sub(r"</w:p>", "\n", xml)
        return re.sub(r"<[^>]+>", "", xml)
    if ext == ".xlsx":
        out = []
        with zipfile.ZipFile(path) as z:
            shared = []
            if "xl/sharedStrings.xml" in z.namelist():
                root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                for si in root.findall(NS + "si"):
                    shared.append("".join(t.text or "" for t in si.iter(NS + "t")))
            sheets = sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
            for name in sheets:
                root = ET.fromstring(z.read(name))
                for row in root.iter(NS + "row"):
                    vals = []
                    for c in row.findall(NS + "c"):
                        t = c.get("t")
                        v = c.find(NS + "v")
                        isel = c.find(NS + "is")
                        if isel is not None:
                            vals.append("".join(x.text or "" for x in isel.iter(NS + "t")))
                        elif v is not None and v.text is not None:
                            if t == "s" and v.text.isdigit() and int(v.text) < len(shared):
                                vals.append(shared[int(v.text)])
                            else:
                                vals.append(v.text)
                    if vals:
                        # 逐单元格成行（键值对在 Excel 里通常同一行相邻两格），便于「键 值」匹配
                        seg = "\t".join(x for x in vals if x)
                        seg = re.sub(r"(?<![0-9A-Za-z])[·×]{2,}", " ", seg)
                        seg = re.sub(r"[ \t]{2,}", " ", seg)
                        out.append(seg)
        return "\n".join(out)
    if ext == ".pdf":
        try:
            import pymupdf as fitz
        except ImportError:
            try:
                import fitz  # type: ignore
            except ImportError:
                return ""
        doc = fitz.open(path)
        return "\n".join(p.get_text() for p in doc)
    if ext in IMAGE_EXT:
        try:
            import pytesseract
            from PIL import Image
            return pytesseract.image_to_string(Image.open(path), lang="chi_sim+eng")
        except Exception:
            return ""
    return ""


def extract(path: pathlib.Path) -> dict:
    text = read_text(path)
    if not text.strip():
        note = ("图片文件：未安装 OCR（pytesseract + tesseract chi_sim）或有扫描版 PDF，需多模态识别/人工录入"
                if path.suffix.lower() in IMAGE_EXT else "无法抽取文本（可能是扫描版 PDF），需 OCR")
        return {"file": path.name, "status": "NO_TEXT", "note": note, "fields": {},
                "ignored": {k: {"text": None, "status": "MISSING"} for k in IGNORE_RE},
                "missing": list(FIELD_RE), "ambiguous": ["全部字段待人工录入，未做任何默认值"]}

    # 匹配用文本：优先「键：值」片段（键与值之间允许 0~40 个非冒号字符），
    # 把「产品名称 乙二醇…」「规格：…」这类键值对先抽出来，避免表格串行误匹配。
    # 匹配用文本的优先顺序：
    #   ① 带单位的「键 值」片段（值里含 元/公斤/吨/桶，最可能是真实报价）
    #   ② 「键：值」片段（冒号分隔，常见于 Excel 键值对单元格）
    #   ③ 全文（最后的兜底）
    # 候选片段：每行、以及按「；。·」切分后的子句；优先信任「键在最前」的片段
    candidates = []
    for line in text.split("\n"):
        for seg in [line] + re.split(r"[；;。]\s*", line):
            seg = seg.strip()
            if not seg:
                continue
            # 「键\t值」单元格拆分：键 + 值，以及值本身
            parts = [p.strip() for p in seg.split("\t") if p.strip()]
            if len(parts) >= 2:
                candidates.append(f"{parts[0]}\t{parts[1]}")
                candidates.extend(parts)
            candidates.append(seg)
    candidates.append(text)
    LINE_OK = re.compile(r"^[\s·\-]*(产品名称|品名|物料名称|商品名称|规格|含量|纯度|品牌|产地|生产企业|包装形式|"
                         r"包装方式|包装|运费|交货方式|交货地点|交货|付款方式|付款条件|结算方式|"
                         r"最小起订量|起订量|报价有效期|有效期|质量标准|执行标准)")
    candidates.sort(key=lambda s: (0 if LINE_OK.match(s) else 1, len(s)))

    fields = {}
    # 策略零（Excel 表格专用）：对「含键名的表头行」，取下方数据行同列的值
    if "\t" in text:
        rows = [r.split("\t") for r in text.split("\n") if "\t" in r]
        KEYCOLS = {
            "unit": ["计价单位", "单位"],
            "price": ["单价", "报价"],
            "spec": ["质量指标", "规格", "含量"],
            "product": ["品名", "产品名称", "物料名称"],
        }
        for key, kws in KEYCOLS.items():
            for ri, row in enumerate(rows):
                hit_ci = None
                for ci, cell in enumerate(row):
                    c = cell.strip()
                    if key == "unit":
                        ok = c in ("计价单位", "计量单位") or (c == "单位" and ci > 1)
                    else:
                        ok = any(k in c for k in kws)
                    if ok:
                        hit_ci = ci
                        break
                if hit_ci is None:
                    continue
                for rj in range(ri + 1, min(ri + 8, len(rows))):
                    if hit_ci >= len(rows[rj]):
                        continue
                    cand = rows[rj][hit_ci].strip()
                    if not cand or cand in ("单位", "-", "—"):
                        continue
                    if key == "price":
                        mm = re.search(r"([0-9][0-9,.]*)", cand)
                        if not mm:
                            break
                        cand = f"{mm.group(1)} {row[hit_ci]}".strip()
                    elif key == "unit":
                        if not re.search(r"吨|kg|公斤|桶|袋|包|L|升", cand):
                            continue
                    fields.setdefault(key, cand[:120])
                    break
    # 策略一：PDF/表格常见的「键单独一行、值在下一行」结构
    lines = [l.strip() for l in text.split("\n")]
    KEY_ANY = re.compile(r"^(产品名称|品名|物料名称|商品名称|规格/含量|规格|含量|纯度|品牌|产地\s*/\s*生产企业|产地|"
                         r"生产企业|包装形式|包装方式|包装|运费|交货方式|交货地点|交货|付款方式|付款条件|"
                         r"结算方式|最小起订量|起订量|报价有效期|有效期|质量标准|执行标准|计价单位|单价|价格构成)")
    next_line = {}
    for i, l in enumerate(lines[:-1]):
        if KEY_ANY.match(l) and len(l) <= 16:
            nxt = lines[i + 1]
            # 排除「表头」：键本身含括号说明（如「单价（元/公斤）」「数量区间」）或下一行是表头
            if re.search(r"[（(]", l) or re.search(r"区间|单价（|单位\s*\|", nxt):
                continue
            if nxt and len(nxt) <= 90 and not KEY_ANY.match(nxt):
                next_line.setdefault(l, nxt)
    for key, pat in FIELD_RE.items():
        for k, v in next_line.items():
            if re.match(rf"^(?:{FIELD_RE_ALIASES.get(key, '')})\s*$", k) and re.search(pat, k + " " + v):
                fields[key] = v[:120]
                break
    # 策略二：在候选片段中打分（处理「键 值」/「键：值」同行的情况）
    KV_OK = re.compile(r"^\s*(产品名称|品名|物料名称|商品名称|规格|含量|纯度|品牌|产地|生产企业|包装形式|包装方式|"
                       r"包装|运费|交货方式|交货地点|交货|付款方式|付款条件|结算方式|最小起订量|起订量|"
                       r"报价有效期|有效期|质量标准|执行标准)\s*[：:]?\s+\S")
    for key, pat in FIELD_RE.items():
        if key in fields:
            continue
        best, best_score = None, -1
        for src in candidates[:400]:
            for m in re.finditer(pat, src):
                cand = (m.group(1) if m.groups() else m.group(0)).strip()
                if not cand:
                    continue
                score = 0
                if KV_OK.match(src):
                    score += 6
                if re.search(r"元|kg|公斤|吨|桶|/|%|GB|天|万", cand):
                    score += 2
                if 3 <= len(cand) <= 40:
                    score += 2
                if len(src) > 90:
                    score -= 4
                if score > best_score:
                    best, best_score = cand[:120], score
        if best:
            fields[key] = best

    ignored = {}
    for key, pat in IGNORE_RE.items():
        m = re.search(pat, text)
        ignored[key] = {"text": m.group(0).strip()[:120] if m else None,
                        "status": "found" if m else "MISSING"}

    missing = [k for k in FIELD_RE if k not in fields]
    amb = []
    if "price" in fields and not re.search(r"元\s*[/／]\s*吨", fields["price"]):
        # 价格未写明「元/吨」时，若单位字段本身就是「吨」则视为元/吨
        unit_says_ton = "unit" in fields and re.fullmatch(r"吨|ton|t", fields["unit"].strip(), re.I)
        if not unit_says_ton:
            amb.append("计价单位不是「元/吨」，需换算；若为元/桶/袋，净重必须确认")
    if "tax" not in fields:
        amb.append("税费口径未识别：是否含税？税率？发票类型？")
    elif not re.search(r"13%|9%|6%|专票|专用发票|普票", fields.get("tax", "") + text):
        amb.append("税费口径表述不完整（缺税率或票种）")
    if re.search(r"元\s*[/／]\s*(桶|袋|包)", text) and not re.search(r"\d+\s*kg|净重", text):
        amb.append("元/桶（袋/包）计价但未见净重 → 无法折吨")
    if "validity" in fields and not re.search(r"20\d\d-\d\d-\d\d", fields["validity"]):
        amb.append("有效期缺明确起止日期")
    if "spec" not in fields:
        amb.append("规格/含量未识别 → 无法折纯，禁止同口径排名")
    elif not re.search(r"\d{2}(?:\.\d+)?\s*%", fields["spec"]):
        # 尝试从全文里找「含量≥xx.xx%」这类完整表述
        m = re.search(r"(?:含量|纯度|浓度|规格\s*/\s*含量)\s*[^0-9\n]{0,8}([0-9]{2}(?:\.[0-9]+)?)\s*%", text)
        if m:
            fields["spec"] = f"含量≥{m.group(1)}%"
        else:
            amb.append("含量未给出百分比（只有规格描述）→ 折纯需人工确认")
    return {"file": path.name, "status": "OK", "fields": fields, "ignored": ignored,
            "missing": missing, "ambiguous": amb, "text_len": len(text)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()
    res = []
    for i, f in enumerate(args.files, 1):
        p = pathlib.Path(f)
        if not p.exists():
            print(f"[ERROR] 文件不存在：{f}", file=sys.stderr); continue
        r = extract(p)
        r["code"] = f"S{i}"
        res.append(r)
        print(f"[{r['status']}] {p.name}：字段 {len(r['fields'])}/{len(FIELD_RE)}，"
              f"缺失 {len(r['missing'])}，歧义 {len(r['ambiguous'])}", file=sys.stderr)
        for a in r["ambiguous"]:
            print(f"    ? {a}", file=sys.stderr)
        if r["status"] == "NO_TEXT":
            print(f"    ! {r['note']}", file=sys.stderr)
    out = json.dumps(res, ensure_ascii=False, indent=2)
    if args.out:
        pathlib.Path(args.out).write_text(out, encoding="utf-8")
        print(f"written {args.out}", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
