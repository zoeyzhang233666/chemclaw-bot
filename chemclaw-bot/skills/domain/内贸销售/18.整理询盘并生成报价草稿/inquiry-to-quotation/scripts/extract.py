# -*- coding: utf-8 -*-
"""从询盘原文抽标准字段 → fields.json（不产生任何价格）。

用法：
    python extract.py 询盘.txt -o fields.json
    python extract.py 微信.txt 邮件.eml -o fields.json --customer "江苏盐城华宇玻璃有限公司" --as-of 2026-10-20

规则驱动，不联网、不调模型。抽不到的字段留空并标 missing / assumed，
由人（销售）在 workbench 里逐项确认——脚本永远不会替客户补需求。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

# ---------------------------------------------------------------- 词表

PRODUCTS: list[tuple[str, list[str]]] = [
    ("重质纯碱", ["重质纯碱", "重灰", "重碱", "重质苏打"]),
    ("轻质纯碱", ["轻质纯碱", "轻灰", "轻碱"]),
    ("纯碱", ["纯碱", "碳酸钠", "Na2CO3", "苏打"]),
    ("SBS", ["SBS", "热塑性弹性体", "苯乙烯-丁二烯"]),
    ("SEBS", ["SEBS"]),
    ("钛白粉", ["钛白粉", "二氧化钛", "TiO2"]),
    ("甲醇", ["甲醇", "木精"]),
    ("液碱", ["液碱", "烧碱", "氢氧化钠"]),
    ("双氧水", ["双氧水", "过氧化氢"]),
    ("冰醋酸", ["冰醋酸", "乙酸", "醋酸"]),
    ("尿素", ["尿素"]),
    ("乙二醇", ["乙二醇", "MEG"]),
    ("聚醚", ["聚醚", "聚醚多元醇"]),
    ("环氧丙烷", ["环氧丙烷", "PO"]),
    ("元明粉", ["元明粉", "硫酸钠"]),
    ("柠檬酸", ["柠檬酸"]),
    ("正丁醇", ["正丁醇"]),
    ("辛醇", ["辛醇", "异辛醇"]),
    ("苯乙烯", ["苯乙烯", "SM"]),
    ("丙酮", ["丙酮"]),
]

PROVINCES = [
    "北京", "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江",
    "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西", "海南", "四川",
    "贵州", "云南", "陕西", "甘肃", "青海", "宁夏", "新疆", "内蒙古", "西藏",
]

UNIT_RE = r"(吨|t|T|公斤|kg|KG|千克|包|袋|桶|槽车|车|件)"

PAYMENT_PATTERNS = [
    (r"款到发货", "款到发货"),
    (r"货到付款|到付", "货到付款"),
    (r"预付\s*(\d+(?:\.\d+)?)\s*%", "预付 {0}%"),
    (r"月结\s*(\d+)\s*天", "月结 {0} 天"),
    (r"账期\s*(\d+)\s*天", "账期 {0} 天"),
    (r"(\d+)\s*天账期", "{0} 天账期"),
    (r"承兑", "银行承兑"),
    (r"现款|现汇|电汇", "现款电汇"),
    (r"滚动付款|滚动结算", "滚动结算"),
]

GRADE_PATTERNS = [
    r"Na2CO3\s*[≥>＞]=?\s*\d+(?:\.\d+)?\s*%",
    r"(?:纯度|含量|主含量|有效含量)\s*[≥>＞:：]?\s*\d+(?:\.\d+)?\s*%",
    r"(?:Fe2O3|Fe₂O₃|铁含量|铁)\s*[≤<＜]=?\s*[\d.]+\s*%",
    r"(?:烧失量|灼烧减量|LOI)\s*[≤<＜]=?\s*[\d.]+\s*%",
    r"(?:水分|含水)\s*[≤<＜]?\s*[\d.]+\s*%",
    r"(?:白度)\s*[≥>＞:：]?\s*\d+(?:\.\d+)?",
    r"\d{2,4}\s*目\s*(?:筛余|通过率)?\s*[≤<＜]?\s*[\d.]+\s*%",
    r"(?:筛余|通过率)\s*[≤<＜]\s*[\d.]+\s*%",
    r"(?:堆积密度|松装密度)\s*[:：=≥]?\s*[\d.~～\-]+\s*(?:g/cm3|g/cm³|kg/m3|kg/m³)",
    r"\d{2,4}\s*目(?!\s*(?:筛余|通过率))",
    r"(?:熔指|MFR|MI)\s*[:：=]?\s*[\d.]+",
    r"(?:软化点)\s*[:：=≥]?\s*[\d.]+\s*℃?",
    r"(?:灰分|挥发分|不溶物)\s*[≤<＜]\s*[\d.]+\s*%",
    r"(?:甲苯|丙酮)?不溶物\s*[≤<]\s*[\d.]+\s*%",
    r"(?:粒度|粒径)\s*[:：]?\s*[\d.~～\-]+\s*(?:目|mm|μm|um)(?!\s*(?:筛余|通过率))",
    r"(?:苯乙烯|结合苯乙烯)\s*(?:含量)?\s*[\d.~～\-]+\s*%",
]

PACK_PATTERNS = [
    r"(\d+(?:\.\d+)?)\s*(?:kg|KG|公斤|千克)?\s*(吨包|编织袋|复合袋|纸塑袋|袋装|袋|桶装|桶|槽车|罐车|散装)",
    r"(吨包|编织袋|复合袋|纸塑袋|槽车|罐车|散装|栈板|托盘|缠膜|打托)",
]

DATE_PATTERNS = [
    r"(\d{1,2})\s*月\s*(上旬|中旬|下旬|底|初)",
    r"(\d{1,2})\s*月\s*(\d{1,2})?\s*[日号]?\s*前",
    r"(本月|下月|这个月|下个月)\s*(上旬|中旬|下旬|底|初)",
    r"(\d+)\s*天内",
    r"款到后\s*(\d+)\s*[个]?\s*(?:工作日|天)",
    r"(现货|尽快|即期|随到随发)",
    r"(\d{4})-(\d{1,2})-(\d{1,2})",
]


# ---------------------------------------------------------------- 素材切块

SECTION_RE = re.compile(r"^\s*(?:【\s*素材\s*(\d+)[^】]*】|#{1,4}\s*素材\s*(\d+)[^\n]*)\s*$", re.M)


def split_sources(text: str) -> list[dict]:
    """按【素材01 …】/### 素材01 标记切块；没有标记就整篇算一块。"""
    lines = text.splitlines()
    blocks: list[dict] = []
    cur = {"id": "", "label": "询盘原文", "lines": []}
    for ln in lines:
        m = SECTION_RE.match(ln)
        if m:
            if cur["lines"] or cur["id"]:
                blocks.append(cur)
            num = m.group(1) or m.group(2)
            cur = {"id": f"素材{int(num):02d}", "label": ln.strip(" #"), "lines": []}
        else:
            cur["lines"].append(ln)
    blocks.append(cur)
    out = []
    for i, b in enumerate([b for b in blocks if "\n".join(b["lines"]).strip() or b["id"]], start=1):
        raw = re.sub(r"[【】#]", "", b["label"]).strip()
        label = re.sub(r"^素材\s*\d+\s*", "", raw).strip() or f"素材{i:02d}"
        out.append({
            "id": b["id"] or f"素材{i:02d}",
            "label": label[:40],
            "body": "\n".join(b["lines"]).strip(),
        })
    return out


def _quote(body: str, start: int, end: int, pad: int = 18) -> str:
    a = max(0, start - pad)
    b = min(len(body), end + pad)
    frag = body[a:b].replace("\n", " ").strip()
    return re.sub(r"\s+", " ", frag)


def _hit(blocks: list[dict], pattern: str, flags=0) -> tuple[str, dict, str] | None:
    """在所有素材里找第一个命中，返回 (匹配串, 素材, 出处片段)。"""
    rx = re.compile(pattern, flags)
    for b in blocks:
        m = rx.search(b["body"])
        if m:
            return m.group(0), b, _quote(b["body"], m.start(), m.end())
    return None


# ---------------------------------------------------------------- 各字段提取


def ex_product(blocks):
    best = None
    for canon, aliases in PRODUCTS:
        for alias in aliases:
            for b in blocks:
                idx = b["body"].find(alias)
                if idx < 0:
                    continue
                cand = (b["body"].find(alias), canon, alias, b, idx)
                if best is None or cand[0] < best[0]:
                    best = cand
    if not best:
        return None
    _, canon, alias, b, idx = best
    return canon, b, _quote(b["body"], idx, idx + len(alias))


def ex_grade(blocks):
    hits: list[tuple[str, dict, str]] = []
    for pat in GRADE_PATTERNS:
        h = _hit(blocks, pat)
        if h and h[0] not in [x[0] for x in hits]:
            hits.append(h)
    # 去掉被更长命中包含的短命中（"180 目" vs "粒度 180 目"）
    kept = []
    for h in hits:
        if any(h[0] != o[0] and h[0] in o[0] for o in hits):
            continue
        kept.append(h)
    if not kept:
        return None
    val = "；".join(h[0].strip() for h in kept)
    src = f"{kept[0][1]['id']} · {kept[0][2]}"
    return val, kept[0][1], src


def ex_quantity(blocks):
    """试单量与月用量分开记；报价默认取试单量（月用量只做口径说明）。"""
    trial = None
    monthly = None
    src = ""
    for b in blocks:
        for label, pat in [
            ("月用量", r"(?:月用量|月需求|每月|月耗|月度用量|月均)[^。；;，,\n]{0,10}?(\d+(?:\.\d+)?)\s*" + UNIT_RE),
            ("试单", r"(?:试单|首批|首单|先来|先要|试供|小批|先订|先发)[^。；;，,\n]{0,10}?(\d+(?:\.\d+)?)\s*" + UNIT_RE),
        ]:
            m = re.search(pat, b["body"])
            if not m:
                continue
            item = (f"{label} {m.group(1)} {m.group(2)}", float(m.group(1)), m.group(2))
            if label == "试单" and trial is None:
                trial = item
                src = src or f"{b['id']} · {_quote(b['body'], m.start(), m.end())}"
            elif label == "月用量" and monthly is None:
                monthly = item
                src = src or f"{b['id']} · {_quote(b['body'], m.start(), m.end())}"
    if not trial and not monthly:
        for b in blocks:
            m = re.search(r"(\d+(?:\.\d+)?)\s*" + UNIT_RE, b["body"])
            if m:
                val = f"{m.group(1)} {m.group(2)}"
                return val, (float(m.group(1)), m.group(2)), f"{b['id']} · {_quote(b['body'], m.start(), m.end())}"
        return None
    parts = [x[0] for x in (trial, monthly) if x]
    pick = trial or monthly
    return "；".join(parts), (pick[1], pick[2]), src


def ex_place(blocks):
    # 1) 显式标注
    for b in blocks:
        m = re.search(r"(?:交货地点|交货地|收货地址|收货单位地址|送货地址|到货地)[:：]\s*([^\n；;。]{2,40})", b["body"])
        if m:
            val = re.split(r"[（(]", m.group(1).strip())[0].strip(" ，,。·")
            return val, b, _quote(b["body"], m.start(), m.end())
    # 2) 关键词窗口
    for b in blocks:
        for m in re.finditer(r"(?:送到|发到|运到|送至|送货至|送到我们|到厂|送到厂)", b["body"]):
            win = b["body"][max(0, m.start() - 30): m.end() + 40]
            prov = next((p for p in PROVINCES if p in win), "")
            city = re.search(r"([\u4e00-\u9fa5]{2,6}市)", win)
            site = re.search(r"([\u4e00-\u9fa5A-Za-z0-9]{2,10}(?:厂区|厂|工厂|仓库|基地|工业园))", win)
            parts = [x for x in [prov + "省" if prov and prov not in ("北京", "上海", "天津", "重庆") else prov,
                                 city.group(1) if city else "",
                                 site.group(1) if site else ""] if x]
            if prov or city:
                return "".join(dict.fromkeys(parts)) or win.strip(), b, _quote(b["body"], m.start(), m.end())
    return None


def ex_customer(blocks):
    """全称（带 公司/集团 后缀）才算"已提取"；只抓到简称的一律标"待客户确认"。"""
    full_pats = [
        r"(?:我们|我司|本公司|我们是)\s*([\u4e00-\u9fa5A-Za-z（）()]{3,24}?(?:股份有限公司|有限责任公司|集团有限公司|有限公司|集团|公司))",
        r"([\u4e00-\u9fa5]{2,14}?(?:玻璃|化工|材料|科技|实业|新材|建材|塑胶|橡胶|涂料|制药|食品|印染|纺织)(?:股份)?有限公司)",
        r"([\u4e00-\u9fa5]{2,14}?有限公司)",
    ]
    short_pat = r"([\u4e00-\u9fa5]{2,12}?(?:玻璃|化工|材料|科技|实业|建材|塑胶|橡胶|涂料|新材))(?![^\s，。；、）)]{0,3}有限公司)"
    for pat in full_pats:
        for b in blocks:
            for m in re.finditer(pat, b["body"]):
                val = re.sub(r"^(?:我们|我司|本公司|我们是)", "", m.group(0)).strip()
                if re.search(r"(有限公司|股份有限公司|有限责任公司|集团)$", val):
                    return val, b, _quote(b["body"], m.start(), m.end()), True
    best = None
    for b in blocks:
        for m in re.finditer(short_pat, b["body"]):
            val = re.sub(r"^(?:我们|我司|本公司|我们是)", "", m.group(1).strip())
            if len(val) < 4:
                continue
            if best is None or len(val) > len(best[0]):
                best = (val, b, _quote(b["body"], m.start(), m.end()))
    if best:
        return best[0], best[1], best[2], False
    return None


def ex_contact(blocks):
    m = re.search(r"([\u4e00-\u9fa5]{1,2})(经理|总|工|部长|主任|主管)", " ".join(b["body"] for b in blocks))
    phone = re.search(r"(1[3-9]\d{9}|0\d{2,3}-?\d{7,8})", " ".join(b["body"] for b in blocks))
    if not m and not phone:
        return None
    val = []
    if m:
        val.append(m.group(1) + m.group(2))
    if phone:
        val.append(phone.group(1))
    return " ".join(val), blocks[0], "询盘署名"


def ex_payment(blocks):
    for b in blocks:
        for pat, tpl in PAYMENT_PATTERNS:
            m = re.search(pat, b["body"])
            if m:
                val = tpl.format(*m.groups()) if "{" in tpl else tpl
                return val, b, _quote(b["body"], m.start(), m.end())
    return None


def ex_delivery_date(blocks):
    for b in blocks:
        for pat in DATE_PATTERNS:
            m = re.search(pat, b["body"])
            if m:
                val = m.group(0).strip()
                tail = b["body"][m.end(): m.end() + 3]
                tm = re.match(r"\s*(前|之前|以前|到货|交货|发货)", tail)
                if tm:
                    val += tm.group(1)
                return val, b, _quote(b["body"], m.start(), m.end() + (len(tm.group(1)) if tm else 0))
    return None


def ex_packaging(blocks):
    found: list[tuple[str, dict, str]] = []
    for b in blocks:
        for pat in PACK_PATTERNS:
            for m in re.finditer(pat, b["body"]):
                txt = m.group(0).strip()
                if txt in [x[0] for x in found]:
                    continue
                found.append((txt, b, _quote(b["body"], m.start(), m.end())))
    kept = [x for x in found if not any(x[0] != o[0] and x[0] in o[0] for o in found)]
    if not kept:
        return None
    return "；".join(x[0] for x in kept[:4]), kept[0][1], f"{kept[0][1]['id']} · {kept[0][2]}"


def ex_tax_hint(blocks):
    hints = []
    for b in blocks:
        for pat, label in [
            (r"13\s*%\s*(?:增值税)?\s*(?:专用发票|专票)", "含税 13% 专票"),
            (r"9\s*%\s*(?:增值税)?\s*(?:专用发票|专票)", "含税 9% 专票"),
            (r"不含税", "不含税"),
            (r"普票|普通发票", "普票"),
            (r"含税", "含税（税率未写明）"),
        ]:
            m = re.search(pat, b["body"])
            if m:
                item = f"{b['id']} 提到「{m.group(0)}」→ {label}"
                if item not in hints:
                    hints.append(item)
    return hints


def ex_freight_hint(blocks):
    hints = []
    for b in blocks:
        for pat, label in [
            (r"送到|运到|送到厂|到厂价|含运费|包运|送货上门", "客户要求送到厂 → 倾向到厂价"),
            (r"出厂价|自提|不含运费|运费另计|上门提货", "提到出厂价/自提 → 倾向不含运费"),
            (r"送到站|到站价", "提到送到站"),
        ]:
            m = re.search(pat, b["body"])
            if m:
                item = f"{b['id']} 提到「{m.group(0)}」→ {label}"
                if item not in hints:
                    hints.append(item)
    return hints


def ex_unreadable(blocks):
    out = []
    for b in blocks:
        for m in re.finditer(r"[0-9]\s*\?\s*[0-9]", b["body"]):
            out.append(f"{b['id']}：数字被遮挡/模糊「{_quote(b['body'], m.start(), m.end(), 10)}」，需确认")
        if "无法辨认" in b["body"] or "看不清" in b["body"] or "语音未转写" in b["body"]:
            out.append(f"{b['id']}：素材自述有无法辨认内容（语音/遮挡/手写），需用户确认后补录")
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------- 组装


def build_doc(files: list[Path], customer: str = "", as_of: str = "", inquiry_no: str = "") -> dict:
    blocks: list[dict] = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        for b in split_sources(text):
            b["file"] = f.name
            blocks.append(b)

    doc = C.new_doc(customer=customer, inquiry_no=inquiry_no, as_of=as_of)
    doc["meta"]["sources"] = [
        {"id": b["id"], "type": b["label"], "file": b["file"], "chars": len(b["body"])} for b in blocks
    ]

    def put(key, hit, confidence="高"):
        if not hit:
            return
        val, b, src = hit
        row = doc["fields"][key]
        row["value"] = val
        row["status"] = "extracted"
        row["confidence"] = confidence
        row["source"] = src if src.startswith(b["id"]) else f"{b['id']} · {src}"

    put("product", ex_product(blocks))
    put("grade", ex_grade(blocks), "高")
    q = ex_quantity(blocks)
    if q:
        val, qty, src = q
        row = doc["fields"]["quantity"]
        row["value"] = val
        row["status"] = "extracted"
        row["confidence"] = "高"
        row["source"] = src
        if qty:
            doc["price"]["quote_quantity"] = qty[0]
            doc["price"]["quote_quantity_unit"] = "吨" if qty[1].lower() in ("t", "吨") else qty[1]
    put("place", ex_place(blocks))
    cu = ex_customer(blocks)
    if cu:
        val, b, src, full = cu
        row = doc["fields"]["customer"]
        row["value"] = val
        row["source"] = src if src.startswith(b["id"]) else f"{b['id']} · {src}"
        if full:
            row["status"] = "extracted"
            row["confidence"] = "高"
        else:
            row["status"] = "tbc"
            row["confidence"] = "低"
            row["note"] = "疑似简称，开票主体全称待确认"
        if not doc["meta"].get("customer"):
            doc["meta"]["customer"] = val
    put("payment", ex_payment(blocks))
    put("delivery_date", ex_delivery_date(blocks), "中")
    put("packaging", ex_packaging(blocks), "中")

    c = ex_contact(blocks)
    if c:
        doc["meta"]["customer_contact"] = c[0]
    if customer:
        doc["meta"]["customer"] = customer

    tax_hints = ex_tax_hint(blocks)
    freight_hints = ex_freight_hint(blocks)
    doc["gate"]["tax_mode"]["hint"] = "；".join(tax_hints)
    doc["gate"]["freight_mode"]["hint"] = "；".join(freight_hints)
    doc["unreadable"] = ex_unreadable(blocks)

    # 有效期待确认：assume 字段抽到就用，抽不到留默认假设并显式标记
    for key in C.FIELD_KEYS:
        row = doc["fields"][key]
        if C.FIELD_BUCKET[key] == "assume" and row["status"] != "extracted":
            row["status"] = "assumed"
            row["note"] = "询盘未提及，按我方默认假设"
    return doc


# ---------------------------------------------------------------- CLI 输出


def print_report(doc: dict) -> None:
    meta = doc["meta"]
    print(f"\n询盘编号 {meta['inquiry_no']}　as_of {meta['as_of']}　客户 {meta['customer'] or '待确认'}")
    print("素材：")
    for s in meta["sources"]:
        print(f"  {s['id']}　{s['type']}　{s['file']}　{s['chars']} 字")

    for bucket in ("must", "assume"):
        rows = [doc["fields"][k] for k in C.FIELD_KEYS if C.FIELD_BUCKET[k] == bucket]
        print(f"\n【{C.BUCKET_LABEL[bucket]}】")
        for r in rows:
            val = r["value"] or (r["assume_default"] if bucket == "assume" else "")
            mark = {"extracted": "✔", "missing": "✖", "assumed": "△", "tbc": "?"}.get(r["status"], "·")
            print(f"  {mark} {r['label']:<8}{val or '—'}")
            if r["source"]:
                print(f"      出处：{r['source'][:70]}")

    print("\n【税费 / 运费口径（需你确认）】")
    for key, label in C.GATE_SPEC:
        g = doc["gate"][key]
        print(f"  ? {label}：待你选择" + (f"　线索：{g['hint'][:80]}" if g.get("hint") else ""))

    for item in doc["unreadable"]:
        print(f"  ! {item}")

    bl = C.blockers(doc)
    print("\n【生成报价草稿的阻塞项】")
    for i, b in enumerate(bl, 1):
        print(f"  {i}. {b}")
    if not bl:
        print("  无（可生成）")


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="询盘原文 → 标准字段 JSON（不含价格）")
    ap.add_argument("files", nargs="+", help="询盘文本文件（.txt/.md/.eml，UTF-8）")
    ap.add_argument("-o", "--out", default="fields.json")
    ap.add_argument("--customer", default="")
    ap.add_argument("--as-of", default="", dest="as_of")
    ap.add_argument("--inquiry-no", default="", dest="inquiry_no")
    ap.add_argument("--json", action="store_true", help="只打印 JSON，不打印确认表")
    args = ap.parse_args(argv)

    paths = [Path(p) for p in args.files]
    missing = [p for p in paths if not p.exists()]
    if missing:
        print("找不到文件：" + ", ".join(str(p) for p in missing), file=sys.stderr)
        return 2

    doc = build_doc(paths, customer=args.customer, as_of=args.as_of, inquiry_no=args.inquiry_no)
    C.save_doc(doc, args.out)
    if args.json:
        print(json.dumps(doc, ensure_ascii=False, indent=1))
    else:
        print_report(doc)
        print(f"\n已写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
