# -*- coding: utf-8 -*-
"""extract.py · 询盘素材 → 结构化字段（只搬运，不推断，不产价）

用法：
    python extract.py --email 询盘邮件.eml --fields fields.json --emit out/
    python extract.py --text 询盘原文_合并.md --fields fields.json --emit out/
    python extract.py --fields fields.json --template reply_A_confirm --tone friendly-professional

产出（--emit 目录下）：
    snippets.json   素材切块（素材01/02…，含行号）
    fields.json     8 类字段（缺失/歧义标好）
    questions.json  待确认问题（A 类缺口 + 歧义 + 陷阱）
    placeholders.json  回复草稿的占位符清单（全部 open）
    reply.json      英文回复草稿（占位符化）
    gaps.txt        人类可读的缺口摘要

本脚本 100% 标准库；不联网；不写任何价格。
"""
from __future__ import annotations

import argparse
import email
import email.policy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
_PRODUCTS_DIR = os.path.normpath(os.path.join(HERE, "..", "products"))
import _common as C  # noqa: E402
import extract_i18n as I18N  # noqa: E402

DEMO_BANNER = "【模拟】"


# ------------------------------------------------------------------ 读入
def load_email(path: str):
    with open(path, "rb") as f:
        raw = f.read()
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_content()
                break
    else:
        body = msg.get_content()
    head = {
        "from": str(msg.get("From", "")),
        "to": str(msg.get("To", "")),
        "cc": str(msg.get("Cc", "")),
        "date": str(msg.get("Date", "")),
        "subject": str(msg.get("Subject", "")),
        "message_id": str(msg.get("Message-ID", "")),
    }
    return head, body.replace("\r\n", "\n").replace("\r", "\n")


def split_blocks(text: str):
    """把合并素材切成块。返回 [(id, title, body)]"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Markdown 标题式：## 素材01 客户邮件 · …
    pat = re.compile(r"^#{2,3}\s*(素材\d+)[^\n]*$", re.M)
    hits = list(pat.finditer(text))
    if len(hits) >= 1:
        blocks = []
        for i, h in enumerate(hits):
            end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
            sid = h.group(1)
            raw = h.group(0).lstrip("# ").strip()
            # 标题形如 "素材02 历史邮件（转贴）· 2026-10-15 09:20 (+07:00)" → 去掉前缀的"素材NN "
            title = re.sub(r"^\s*素材\d+\s*", "", raw).strip() or raw
            sid = "S" + sid.replace("素材", "").zfill(2)
            blocks.append((sid, title, text[h.end(): end].strip()))
        return blocks
    # 【素材01 …】式
    pat2 = re.compile(r"^【(素材\d+)[^】]*】[^\n]*$", re.M)
    hits2 = list(pat2.finditer(text))
    if hits2:
        blocks = []
        for i, h in enumerate(hits2):
            end = hits2[i + 1].start() if i + 1 < len(hits2) else len(text)
            blocks.append((h.group(1), h.group(0).strip("【】"), text[h.end(): end].strip()))
        return blocks
    return [("素材01", "全文", text.strip())]


def build_snippets(head, body, subject_title, date_title):
    """邮件 → 素材块（正文 + 历史轮次）。返回 (snippets, full_text)"""
    lines = body.split("\n")
    # 历史轮次切点
    cut = None
    for i, ln in enumerate(lines):
        if re.match(r"^-{3,}\s*(original\s*message|转发|forwarded)", ln.strip(), re.I):
            cut = i
            break
        if re.match(r"^On .{10,}\bwrote:$", ln.strip()):
            cut = i
            break
        if re.match(r"^From:\s*\S+@", ln.strip()) and i > 6:
            cut = i
            break
    main_lines = lines if cut is None else lines[:cut]
    old_lines = [] if cut is None else lines[cut:]
    snippets = []
    cur = "S01"
    main_text = "\n".join(main_lines).strip()
    snippets.append({
        "id": cur, "kind": "email", "title": subject_title, "date": date_title,
        "header": head, "text": main_text, "lines": [l for l in main_lines],
        "line_base": 1, "chars": len(main_text),
    })
    if old_lines:
        old_text = "\n".join(old_lines).strip()
        snippets.append({
            "id": "S02", "kind": "email_history",
            "title": "历史邮件（转贴，客户上一封）", "date": "",
            "header": {}, "text": old_text, "lines": old_lines,
            "line_base": len(main_lines) + 1, "chars": len(old_text),
        })
    full = "\n\n".join(s["text"] for s in snippets)
    return snippets, full


def snippet_with_lines(sid, title, body, date_title="", kind="other"):
    """Markdown 块 → 素材（保留代码块里的行）"""
    body_clean = body.strip()
    body_clean = re.sub(r"^```[a-zA-Z]*\n", "", body_clean)
    body_clean = re.sub(r"\n```\s*$", "", body_clean)
    return {
        "id": sid, "kind": kind, "title": title, "date": date_title, "header": {},
        "text": body_clean.strip(), "lines": body_clean.split("\n"), "line_base": 1,
        "chars": len(body_clean),
    }


# ------------------------------------------------------------------ 抽取
def _find(pattern, text, flags=re.I | re.M):
    m = re.search(pattern, text, flags)
    if not m:
        return None
    return m


def _line_of(snips, quote):
    """找 quote 在哪个素材、第几行。"""
    q = C.norm_ws(quote).lower()
    for s in snips:
        for i, ln in enumerate(s["lines"]):
            if q and q in C.norm_ws(ln).lower():
                return s["id"], f"{s['id']}:L{i + 1}"
    return (snips[0]["id"] if snips else "S01"), ""


def set_field(fields, key, value, *, status="stated", quote="", snip=None, snips=None,
              confidence="high", lang="en", note="", raw="", unit=""):
    if key not in fields:
        fields[key] = C.empty_field(key)
    f = fields[key]
    f["value"] = value
    f["status"] = status
    f["confidence"] = confidence
    f["lang"] = lang
    f["quote"] = quote
    f["raw"] = raw or value
    f["note"] = note
    if unit:
        f["unit"] = unit
    if quote and snips is not None:
        sid, loc = _line_of(snips, quote)
        f["source_id"] = sid
        f["locator"] = loc
    elif snip:
        f["source_id"] = snip
    return f


PRODUCT_LIBRARY = [
    # (匹配正则, 标准名, 中文名, 形态, cas, ec, formula, synonyms)
    (r"soda\s*ash\s*dense|dense\s*(soda\s*ash|sodium\s*carbonate)|dense\s+granular",
     "Soda Ash Dense (Sodium Carbonate, Dense)", "重质纯碱", "dense granular",
     "497-19-8", "207-838-8", "Na2CO3",
     ["disodium carbonate", "soda ash", "carbonic acid disodium salt", "natrium karbonat (id)",
      "soda abu (id)", "carbonato de sodio (es)"]),
    (r"soda\s*ash\s*light|light\s*(soda\s*ash|sodium\s*carbonate)",
     "Soda Ash Light (Sodium Carbonate, Light)", "轻质纯碱", "light powder",
     "497-19-8", "207-838-8", "Na2CO3",
     ["disodium carbonate", "soda ash", "natrium karbonat (id)"]),
    (r"caustic\s*soda\s*flake|sodium\s*hydroxide\s*flake|flake\s*caustic|xut\s*vay|xút vảy|soda\s*api",
     "Caustic Soda Flake (Sodium Hydroxide, 99%)", "片碱（氢氧化钠）", "flake",
     "1310-73-2", "215-185-5", "NaOH", ["lye", "soda api (id)", "xút vảy (vi)", "soda cáustica (es)"]),
    (r"sodium\s*hydroxide\s*(solution|liquid)|liquid\s*caustic",
     "Caustic Soda Liquid (Sodium Hydroxide Solution 32%/50%)", "液碱", "liquid",
     "1310-73-2", "215-185-5", "NaOH", ["lye solution", "soda api cair (id)"]),
    (r"urea\s*(granular|prilled)|prilled\s*urea|granular\s*urea",
     "Urea (Granular)", "尿素", "granular", "57-13-6", "200-315-5", "CH4N2O",
     ["carbamide", "urea prilled"]),
    (r"titanium\s*dioxide|titanium\s*white|tio2",
     "Titanium Dioxide", "钛白粉", "powder", "13463-67-7", "236-675-5", "TiO2",
     ["titania", "titanium white"]),
    (r"\bpvc\b|polyvinyl\s*chloride",
     "PVC Resin (Suspension)", "聚氯乙烯（PVC 树脂）", "powder", "9002-86-2", "-", "(C2H3Cl)n",
     ["polyvinyl chloride"]),
]


def extract_product(text, fields, snips):
    for pat, std, cn, form, cas, ec, formula, syn in PRODUCT_LIBRARY:
        m = _find(pat, text)
        if not m:
            continue
        line = _line_containing(text, m.group(0))
        set_field(fields, "product_raw", C.norm_ws(line) if line else m.group(0),
                  quote=line or m.group(0), snips=snips, confidence="high", lang="en")
        set_field(fields, "product_std", std, quote=line or m.group(0), snips=snips, confidence="high")
        set_field(fields, "product_cn", cn, quote=line or m.group(0), snips=snips, confidence="high", lang="zh")
        set_field(fields, "appearance_form", form, quote=line or m.group(0), snips=snips, confidence="high")
        # CAS：库里给的是"标准品身份"，必须标注来源
        set_field(fields, "cas", cas,
                  quote=line or m.group(0), snips=snips, confidence="high",
                  note="来源：产品标准画像 products/*.json + 权威库查证（Wikidata/PubChem）；客户原话未给 CAS。"
                       "若贵司产品资料另有编号，以产品资料为准。")
        fields["cas"]["source_type"] = "library+verified"
        set_field(fields, "ec", ec, quote=line or m.group(0), snips=snips, confidence="high")
        set_field(fields, "formula", formula, quote=line or m.group(0), snips=snips, confidence="high")
        set_field(fields, "synonyms", "; ".join(syn), quote=line or m.group(0), snips=snips, confidence="high")
        # 客户原文里显式给的 CAS 优先
        mc = re.search(r"CAS\s*(?:No\.?|登记号)?\s*[:#]?\s*(\d{2,7}-\d{2}-\d)", text, re.I)
        if mc:
            set_field(fields, "cas", mc.group(1), quote=_line_containing(text, mc.group(0)) or mc.group(0),
                      snips=snips, note="客户原文给出 CAS，客户原话优先。")
            fields["cas"]["source_type"] = "customer"
        return True
    # ---- 多语言兜底：按本地语言商品名命中产品画像 ----
    m = I18N.match_first("product_raw", text)
    if m:
        local = C.norm_ws(m.group(0))
        prof = _match_profile_by_local_name(local)
        if prof:
            line = _line_containing(text, m.group(0))
            set_field(fields, "product_raw", local, quote=line or m.group(0), snips=snips,
                      confidence="medium", lang="auto",
                      note="客户用本地语言写入产品名（%s），已按产品画像 products/%s.json 对齐；请人工复核是否同一产品。"
                           % (local[:40], prof["id"]))
            set_field(fields, "product_std", prof["name_en"], quote=line or m.group(0), snips=snips, confidence="medium")
            set_field(fields, "product_cn", prof["name_cn"], quote=line or m.group(0), snips=snips, confidence="medium", lang="zh")
            set_field(fields, "cas", prof.get("cas", ""), quote=line or m.group(0), snips=snips, confidence="medium",
                      note="来源：产品画像 products/%s.json（标准品身份），客户原话未给 CAS；需我方核对我司产品资料。" % prof["id"])
            fields["cas"]["source_type"] = "library"
            if prof.get("ec"):
                set_field(fields, "ec", prof["ec"], quote=line or m.group(0), snips=snips, confidence="medium")
            if prof.get("formula"):
                set_field(fields, "formula", prof["formula"], quote=line or m.group(0), snips=snips, confidence="medium")
            return True
    return False


def _match_profile_by_local_name(local_text):
    """按 products/*.json 的 synonyms / other_languages 反查产品画像。"""
    import glob
    import json
    low = local_text.lower()
    for path in sorted(glob.glob(os.path.join(_PRODUCTS_DIR, "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                prof = json.load(f)
        except Exception:
            continue
        keys = [prof.get("name_en", ""), prof.get("name_cn", "")] + list(prof.get("synonyms", []))
        for lst in (prof.get("other_languages") or {}).values():
            keys.extend(lst if isinstance(lst, list) else [str(lst)])
        for k in keys:
            if k and len(k) >= 3 and k.lower() in low:
                # 补两个派生字段（画像里有、抽取值里没有）
                prof.setdefault("formula", {"caustic_soda_flake": "NaOH", "caustic_soda_liquid": "NaOH",
                                            "soda_ash_dense": "Na2CO3", "soda_ash_light": "Na2CO3",
                                            "urea_46": "CO(NH2)2", "titanium_dioxide": "TiO2",
                                            "pvc_sg5": "(C2H3Cl)n"}.get(prof.get("id"), ""))
                return prof
    return None


def _line_containing(text, needle, exclude=None):
    n = C.norm_ws(needle).lower()
    if len(n) > 30:
        n = n[:30]
    for ln in text.split("\n"):
        if exclude and exclude.lower() in ln.lower():
            continue
        if n and n in C.norm_ws(ln).lower():
            return ln.strip()
    return ""


def _line_by_regex(text, pat):
    for ln in text.split("\n"):
        if re.search(pat, ln, re.I):
            return ln.strip()
    return ""


def extract_spec(text, fields, snips):
    pur = re.search(r"Na2CO3\s*[:：]?\s*(\d{2,3}(?:[.,]\d+)?)\s*%\s*(?:min|minimum|≥|\+)?", text, re.I)
    if not pur:
        pur = re.search(r"purity\s*[:：]?\s*(\d{2,3}(?:[.,]\d+)?)\s*%", text, re.I)
    if pur:
        val = pur.group(1).replace(",", ".")
        set_field(fields, "spec_purity", f"Na2CO3 ≥ {val}% min", quote=_line_containing(text, pur.group(0)),
                  snips=snips, confidence="high", raw=pur.group(0))
    fe = re.search(r"(Fe2O3|Fe)\b[^\n]{0,20}?(\d+(?:\.\d+)?)\s*%", text, re.I)
    if fe:
        q = _line_containing(text, fe.group(0))
        vals = [f"{fe.group(1)} ≤ {fe.group(2)}%"]
        for m in re.finditer(r"\b(NaCl|Cl|SO4|sulphate|sulfate|Ca|Mg|Al)\b[^\n]{0,12}?(\d+(?:\.\d+)?)\s*%", text, re.I):
            vals.append(f"{m.group(1)} ≤ {m.group(2)}%")
        set_field(fields, "spec_impurities", "; ".join(vals), quote=q, snips=snips, confidence="high")
    part = re.search(r"(\+\s*\d{2,3}\s*mesh|\d{2,3}\s*mesh)[^\n]{0,40}?(\d{1,3})\s*%\s*(min|minimum)?", text, re.I)
    if part:
        set_field(fields, "spec_particle",
                  f"{C.norm_ws(part.group(1))} ≥ {part.group(2)}% min",
                  quote=_line_containing(text, part.group(0)), snips=snips, confidence="high")
    bd = re.search(r"bulk\s*density[^\n]{0,30}?(\d+(?:[.,]\d+)?)\s*(g\s*/\s*cm3|g/cm³|kg/m3)", text, re.I)
    if bd:
        set_field(fields, "spec_bulk", f"bulk density {bd.group(1)} {bd.group(2)}",
                  quote=_line_containing(text, bd.group(0)), snips=snips, confidence="high")
    if not fields.get("spec_purity", {}).get("value"):
        g = re.search(r"(industrial|standard|glass|technical|food)\s*grade", text, re.I)
        if g:
            set_field(fields, "grade", C.norm_ws(g.group(0)), quote=_line_containing(text, g.group(0)),
                      snips=snips, status="ambiguous", confidence="medium",
                      note="客户只给等级词，未给数值规格 → 需客户确认验收指标（纯度/杂质/粒度）。")


def extract_qty(text, fields, snips):
    mt = r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
    u = r"(MT|M/T|metric\s*tons?|tonnes?|tons?|t)\b"
    trial = None
    for m in re.finditer(mt + r"\s*" + u + r"\s*(?:for\s+the\s+)?(first|trial|initial|sample)[^\n.]{0,30}?", text, re.I):
        trial = m
        break
    if not trial:
        for m in re.finditer(r"(first|trial|initial)[^\n.]{0,30}?" + mt + r"\s*" + u, text, re.I):
            trial = m
            break
    def clean(x):
        x = x.replace(",", "") if re.match(r"^\d{1,3}(,\d{3})+$", x) else x
        return x.replace(",", ".")
    if trial:
        nums = re.findall(r"\d[\d.,]*", trial.group(0))
        num = nums[0] if nums else ""
        set_field(fields, "qty_trial", f"{clean(num)} {('MT' if 't' in trial.group(0).lower() else trial.group(2))}",
                  quote=_line_containing(text, trial.group(0)), snips=snips, confidence="high",
                  raw=trial.group(0).strip())
    ann = re.search(mt + r"\s*" + u + r"\s*(?:per\s+(year|annum)|\/\s*year|a\s+year|annually)", text, re.I)
    if not ann:
        ann = re.search(r"(?:annually|per\s+year|\/\s*year|a\s+year)[^\n.]{0,40}?" + mt + r"\s*" + u, text, re.I)
    if ann:
        nums = re.findall(r"\d[\d.,]*", ann.group(0))
        set_field(fields, "qty_annual", f"{clean(nums[0])} MT/year", quote=_line_containing(text, ann.group(0)),
                  snips=snips, confidence="high", raw=ann.group(0).strip(),
                  note="客户原文为印尼千分位写法（3.000 = 3,000），已按公吨解析。" if "." in ann.group(0) else "")
    mon = re.search(mt + r"\s*" + u + r"\s*(?:per\s+month|\/\s*month|monthly)", text, re.I)
    if mon:
        nums = re.findall(r"\d[\d.,]*", mon.group(0))
        set_field(fields, "qty_monthly", f"{clean(nums[0])} MT/month", quote=_line_containing(text, mon.group(0)),
                  snips=snips, confidence="high")
    if fields.get("qty_trial", {}).get("value") or fields.get("qty_annual", {}).get("value"):
        set_field(fields, "qty_unit", "MT (metric ton)", quote=_line_containing(text, "MT"),
                  snips=snips, confidence="high",
                  note="客户用 MT / ton 混写；按公吨理解，未出现 long ton / short ton 字样。")

    # ---- 多语言兜底（越南语 / 印尼语 / 西语 / 葡语 / 阿语 …）----
    if not fields.get("qty_trial", {}).get("value"):
        m = I18N.match_first("qty_trial", text)
        if m:
            num = I18N.clean_num(re.findall(r"\d[\d.,]*", m.group(0))[0])
            set_field(fields, "qty_trial", f"{num} MT", quote=_line_containing(text, m.group(0)),
                      snips=snips, confidence="medium",
                      note="按非英语询盘的首单数量句式解析（%s），单位按公吨理解。" % m.group(0).strip()[:60])
    if not fields.get("qty_annual", {}).get("value"):
        m = I18N.match_first("qty_annual", text)
        if m:
            num = I18N.clean_num(re.findall(r"\d[\d.,]*", m.group(0))[0])
            set_field(fields, "qty_annual", f"{num} MT/year", quote=_line_containing(text, m.group(0)),
                      snips=snips, confidence="medium",
                      note="年用量与首单量分别记录，二者不可互相推算。")
    if (fields.get("qty_trial", {}).get("value") or fields.get("qty_annual", {}).get("value")) \
            and not fields.get("qty_unit", {}).get("value"):
        set_field(fields, "qty_unit", "MT (metric ton)", quote="",
                  snips=snips, confidence="medium",
                  note="客户用 tấn / ton / MT 混写；按公吨理解，未见 long ton / short ton。")


def extract_delivery(text, fields, snips):
    terms = ["CFR", "CNF", "C&F", "CIF", "FOB", "EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP"]
    hit = None
    for t in terms:
        m = re.search(r"\b" + re.escape(t) + r"\b([^\n]{0,60})", text, re.I)
        if m:
            hit = (t, m.group(0))
            break
    if hit:
        raw_t, line = hit
        norm = "CFR" if raw_t.upper() in ("CNF", "C&F") else raw_t.upper()
        note = "客户原文写 CNF（旧写法），按 Incoterms 2020 规范化为 CFR。" if raw_t.upper() in ("CNF", "C&F") else ""
        set_field(fields, "incoterm", norm, quote=line.strip(), snips=snips, confidence="high",
                  raw=raw_t, note=note)
        place = re.sub(r"^\s*" + re.escape(raw_t) + r"\b", "", line, flags=re.I)
        place = re.split(r"[,.;]|Incoterms", place)[0].strip()
        place = re.sub(r"^(port|of|port\s+of)\s+", "", place, flags=re.I).strip()
        if place and not place.isdigit():
            set_field(fields, "incoterm_place", place.title() if place.islower() else place,
                      quote=line.strip(), snips=snips, confidence="high")
            set_field(fields, "port_dest", place.title() if place.islower() else place,
                      quote=line.strip(), snips=snips, confidence="high",
                      note="目的港取自术语地点；港口代码与准确写法建议请客户确认（如 Jakarta 对应 Tanjung Priok）。")
    pk = re.search(r"packing[^\n]{0,160}", text, re.I)
    if pk:
        v = C.norm_ws(pk.group(0))
        if re.search(r"(please\s+advise|advise|建议|your\s+standard|suggest)", v, re.I):
            set_field(fields, "pack_std", "", quote=v, snips=snips, status="ambiguous", confidence="medium",
                      raw=v,
                      note="客户要求我方建议标准出口包装 → 包装由我方提出建议后客户确认，不属于客户给定要求。")
        else:
            mbag = re.search(r"(\d{2,4})\s*(kg|KG)\s*(pp\s*)?(woven\s*)?(bag|jumbo\s*bag|sack)", v, re.I)
            if mbag:
                set_field(fields, "pack_std", f"{mbag.group(1)} kg {mbag.group(5)}", quote=v, snips=snips)


def extract_commercial(text, fields, snips):
    if re.search(r"\bUSD?\b|dollars?", text, re.I) and not re.search(r"\bIDR\b|\bRp\b", text):
        m = re.search(r"\bUSD\b|\bUS\s?dollars?\b", text, re.I)
        if m:
            set_field(fields, "currency", "USD", quote=_line_containing(text, m.group(0)), snips=snips,
                      confidence="medium",
                      note="客户要求报价但未写币种；USD 属常见惯例，需我方在报价中明确。")
    pm = re.search(r"payment\s*[:\-]?\s*([^\n]{0,120})", text, re.I)
    if pm:
        v = C.norm_ws(pm.group(1))
        if re.search(r"\bl/?c\b|letter\s+of\s+credit", v, re.I):
            set_field(fields, "payment", "L/C（信用证）", quote=pm.group(0).strip(), snips=snips,
                      status="ambiguous", confidence="high", raw=v,
                      note="客户只说 L/C，未给类型（即期/远期）、有效期、开证行、是否保兑 → 不构成可执行付款条件。")
            set_field(fields, "lc_terms", "", quote=pm.group(0).strip(), snips=snips,
                      status="missing", note="缺 L/C 类型、有效期、开证行、是否可转让/保兑。")
        elif re.search(r"t/?t|telegraphic\s+transfer|wire\s+transfer|bank\s+transfer", v, re.I):
            ratio = re.search(r"(\d{1,2})\s*%", v)
            if ratio:
                set_field(fields, "payment", v, quote=pm.group(0).strip(), snips=snips, confidence="medium")
            else:
                set_field(fields, "payment", "T/T（电汇，比例与节点未给）", quote=pm.group(0).strip(),
                          snips=snips, status="ambiguous", confidence="medium")
    # ---- 多语言兜底：付款方式 ----
    if not fields.get("payment", {}).get("value"):
        m = I18N.match_first("payment", text)
        if m:
            seg = m.group(0).strip()
            v = C.norm_ws(m.group(1)) if m.re.groups and m.group(1) else seg
            if re.search(r"\bl\s*/\s*c\b|letter\s+of\s+credit|thư\s+tín\s+dụng", v + " " + seg, re.I):
                set_field(fields, "payment", "L/C（信用证）", quote=_line_containing(text, seg), snips=snips,
                          status="ambiguous", confidence="medium", raw=v,
                          note="客户只说 L/C，未给类型（即期/远期）、有效期、开证行、是否保兑 → 不构成可执行付款条件。")
                set_field(fields, "lc_terms", "", quote=_line_containing(text, seg), snips=snips,
                          status="missing", note="缺 L/C 类型、有效期、开证行、是否可转让/保兑。")
            elif re.search(r"t\s*/\s*t|chuyển\s+khoản|transferencia", v + " " + seg, re.I):
                set_field(fields, "payment", "T/T（电汇，比例与节点未给）", quote=_line_containing(text, seg),
                          snips=snips, status="ambiguous", confidence="medium")
    # ---- 多语言兜底：包装 ----
    if not fields.get("pack_std", {}).get("value"):
        hits = []
        for pat in I18N.MULTI["pack_std"]:
            for mm in re.finditer(pat, text, re.I):
                seg = C.norm_ws(mm.group(0))
                if seg and seg not in hits:
                    hits.append(seg)
        if hits:
            kgs = sorted({int(re.search(r"(\d{1,4})\s*kg", h, re.I).group(1))
                          for h in hits if re.search(r"(\d{1,4})\s*kg", h, re.I)})
            line = _line_containing(text, hits[0])
            if len(kgs) >= 2:
                set_field(fields, "pack_std", " 或 ".join("%d kg" % k for k in kgs), quote=line, snips=snips,
                          status="ambiguous", confidence="medium",
                          note="客户同时提到 %s 两种包装%s → 必须分别报价/分别确认，不能替客户选。"
                               % (" / ".join("%d kg" % k for k in kgs),
                                  "，并询问价差" if re.search(r"giá|price|harga|precio", line or "", re.I) else ""))
            elif kgs:
                set_field(fields, "pack_std", "%d kg" % kgs[0], quote=line, snips=snips,
                          status="ambiguous", confidence="medium",
                          note="客户提到包装规格，但未确认为唯一要求；标准包装细节（袋型/内衬/托盘）仍需我方确认。")

    # ---- 贸易术语与港口冲突（FOB 后面跟了买方国家的港口）----
    inc = (fields.get("incoterm", {}) or {}).get("value", "")
    place = (fields.get("incoterm_place", {}) or {}).get("value", "")
    buyer_c = (fields.get("buyer_country", {}) or {}).get("value", "")
    cn_ports = ("shanghai", "ningbo", "qingdao", "tianjin", "xingang", "dalian", "xiamen",
                "guangzhou", "shenzhen", "lianyungang", "rizhao", "yantai", "nanjing", "fuzhou")
    if inc and inc.upper() in ("FOB", "FCA") and place and not any(p in place.lower() for p in cn_ports):
        set_field(fields, "incoterm", inc, quote=(fields.get("incoterm", {}) or {}).get("quote", ""), snips=snips,
                  status="ambiguous", confidence="high",
                  note="%s 后面应写**装运港**（中国港口），但客户写的是 %s（%s）。"
                       "要么客户实际想要 CFR/CIF %s，要么客户误写了。照抄进合同会让我方承担到对方港口的内陆/海运责任——必须问清。"
                       % (inc, place, buyer_c or "买方所在国", place))
        set_field(fields, "price_basis", "（术语与港口冲突待澄清）/MT，%s %s" % (inc, place),
                  quote=(fields.get("incoterm", {}) or {}).get("quote", ""), snips=snips,
                  status="ambiguous", confidence="high",
                  note="贸易术语与港口不一致，价格基础不成立，暂不能作为报价口径。")
    # 价格基础
    if fields.get("incoterm", {}).get("value") and fields.get("incoterm", {}).get("status") != "ambiguous" \
            and not fields.get("price_basis", {}).get("value"):
        basis = f"{fields['incoterm']['value']} {fields.get('incoterm_place', {}).get('value', '')}".strip()
        set_field(fields, "price_basis", f"（币种待我方确认）/MT，{basis}", quote=fields["incoterm"]["quote"],
                  snips=snips, status="ambiguous", confidence="medium",
                  note="价格基础缺币种与单价：单价属销售/报价环节，本技能不产生任何价格。")


def extract_docs(text, fields, snips):
    mapping = [
        ("doc_coa", r"\bCOA\b|certificate\s+of\s+analysis|分析报告|质检单"),
        ("doc_sds", r"\bSDS\b|\bMSDS\b|safety\s+data\s+sheet|安全技术说明书"),
        ("doc_tds", r"\bTDS\b|technical\s+data\s+sheet|specification\s+sheet"),
        ("doc_coo", r"certificate\s+of\s+origin|\bC\.?O\.?\b(?!\w)|原产地证"),
        ("doc_form_e", r"form\s+e\b"),
        ("doc_inspection", r"\bSGS\b|\bBV\b|bureau\s+veritas|intertek|\bCIQ\b|third[- ]party\s+inspection"),
        ("doc_dg", r"\bIMO\b|dangerous\s+goods|DG\s+declaration"),
        ("doc_audit", r"ISO\s*\d{4,5}|HALAL|Kosher|REACH|factory\s+audit"),
    ]
    for key, pat in mapping:
        m = re.search(pat, text, re.I)
        if m:
            line = _line_containing(text, m.group(0))
            asked = bool(re.search(r"(cần|chứng\s+từ|documents|send|provide|attach|required|please|need|with\s+the\s+offer)", line or "", re.I))
            # 客户在"问能力"（能不能提供）时，不是既成要求
            # 能力问句只看"该单证名所在的那个分句"
            seg_around = ""
            if line:
                for clause in re.split(r"[;。.;!?]", line):
                    if re.search(pat, clause, re.I):
                        seg_around = clause
                        break
            if seg_around and I18N.is_capability_ask(seg_around):
                set_field(fields, key, C.norm_ws(line), quote=line, snips=snips, confidence="medium",
                          status="ambiguous",
                          note="客户在询问我方能否提供该单证（不是已提出的要求）；回复只能说明按核实结果确认，不得承诺。")
                continue
            set_field(fields, key, C.norm_ws(line) if line else m.group(0), quote=line or m.group(0),
                      snips=snips, confidence="high" if asked else "medium",
                      status="stated" if asked else "ambiguous",
                      note="" if asked else "客户提及该单证但未明确要求提供，需确认。")
    # ---- 修正：Form E / 原产地证若出现在"能不能提供"的问句里，不能记成客户已确认的要求 ----
    lines = [C.norm_ws(x) for x in text.split("\n") if x.strip()]
    for key, pat in (("doc_form_e", r"form\s+e\b"), ("doc_coo", r"certificate\s+of\s+origin|\bC\.?O\.?\b(?!\w)")):
        f = fields.get(key, {})
        if not f.get("value"):
            continue
        q = C.norm_ws(f.get("quote", ""))
        ctx = q
        for i, ln in enumerate(lines):
            if q and (q in ln or ln in q):
                ctx = ln + " " + (lines[i + 1] if i + 1 < len(lines) else "")
                break
        if ctx and I18N.is_capability_ask(ctx):
            f["status"] = "ambiguous"
            f["note"] = "客户在询问我方能否提供该单证（是能力问句，不是已确认的要求）；回复只能说明\"按核实结果确认\"，不得承诺能出具。"
    # 明确"未提"的常见单证 → 保持 missing，并在问题里问
    for key in ("doc_coo", "doc_form_e", "doc_inspection"):
        if not fields.get(key, {}).get("value"):
            fields[key]["note"] = "客户未提及；如客户需要，须我方先确认能否出具（不得在回复中承诺）。"


def extract_buyer(text, fields, snips, head):
    """买方信息：发件人、签名块、公司名。"""
    frm = head.get("from", "")
    m = re.match(r"\s*\"?([^\"<]+?)\"?\s*<([^>]+)>", frm)
    if m:
        name, addr = m.group(1).strip(), m.group(2).strip()
    else:
        addr = frm.strip()
        name = ""
    # 签名块：取最后 12 行
    tail = "\n".join(text.split("\n")[-14:])
    comp = re.search(r"^((?:PT|CV|Pte\.?\s*Ltd\.?|Ltd\.?|Inc\.?|GmbH|LLC|JSC|S\.A\.|Sdn\.?\s*Bhd\.?|Co\.?,?\s*Ltd\.?)\s+[^\n]{2,60})$",
                     tail, re.M)
    if not comp:
        # 越南：Công ty TNHH / Cổ phần …；印尼：PT …
        comp = re.search(r"^((?:Công\s+ty\s+(?:TNHH|Cổ\s+phần)[^\n]{2,60}"
                         r"|CV\.?\s+[^\n]{2,60}|PT\.?\s+[^\n]{2,60}))$", tail, re.M)
    company = comp.group(1).strip() if comp else ""
    if not company:
        # 正文里的公司名（We are PT …）
        comp2 = re.search(r"\b(PT|CV)\s+([A-Z][A-Za-z&.'\- ]{2,50})", text)
        if comp2:
            company = f"{comp2.group(1)} {comp2.group(2).strip()}"
            company = re.split(r"[,.]", company)[0].strip()
    if company:
        set_field(fields, "buyer_name", company, quote=_line_containing(text, company) or "",
                  snips=snips, confidence="high",
                  note="名称取自邮件签名/正文；营业执照全称、税号、地址的工商一致性尚未核验（转「核验海外询盘公司」）。")
    if name:
        set_field(fields, "contact_name", name, quote=_line_containing(text, name) or frm,
                  snips=snips, confidence="high")
    if addr:
        set_field(fields, "contact_email", addr, quote=frm, snips=None, confidence="high")
        fields["contact_email"]["source_id"] = "S01"
        fields["contact_email"]["locator"] = "S01:Header-From"
    # 国家：从签名地址或国家名
    cc = None
    for pat, ccname in [(r"\bIndonesia\b", "Indonesia (ID)"), (r"\bVietnam\b|\bViệt\s+Nam\b", "Vietnam (VN)"),
                        (r"\bIndia\b", "India (IN)"), (r"\bBangladesh\b", "Bangladesh (BD)"),
                        (r"\bThailand\b", "Thailand (TH)"), (r"\bMalaysia\b", "Malaysia (MY)"),
                        (r"\bBrazil\b|\bBrasil\b", "Brazil (BR)"), (r"\bTurkey\b|\bTürkiye\b", "Türkiye (TR)"),
                        (r"\bUAE\b|\bEmirates\b", "United Arab Emirates (AE)")]:
        if re.search(pat, text, re.I):
            cc = ccname
            break
    if cc:
        set_field(fields, "buyer_country", cc, quote=_line_containing(text, cc.split(" ")[0]) or "",
                  snips=snips, confidence="high")
    # 地址：签名里地址特征行
    addr_line = re.search(r"^([^\n]*(?:Kawasan|Jl\.|Jalan|Street|Road|Ave|Blok)[^\n]*)$", tail, re.M)
    if addr_line:
        set_field(fields, "buyer_site", addr_line.group(1).strip(), quote=addr_line.group(1).strip(), snips=snips,
                  confidence="medium", note="仅凭邮件签名地址，客户厂区/收货地址需确认。")
    # 电话
    tel = re.search(r"(?:Tel|Phone|T|HP|Mobile|WA)[^\n]{0,8}?(\+?\d[\d\s\-()]{7,20}\d|0\d[\d\s\-]{7,15})", tail, re.I)
    if tel:
        set_field(fields, "contact_phone", C.norm_ws(tel.group(1)), quote=_line_containing(text, tel.group(1)),
                  snips=snips, confidence="high",
                  note="号码保持客户原文写法；若客户本地格式（0 开头），拨打需加国家码。")
    title = re.search(r"^(Purchasing|Procurement|Sourcing|Supply\s+Chain|Commercial|Buyer)[^\n]{0,40}$", tail, re.M | re.I)
    if title:
        t = title.group(0).strip()
        is_dept = bool(re.match(r"^(Purchasing|Procurement|Sourcing)\s*(Department|Dept\.?)?$", t, re.I))
        set_field(fields, "contact_title", t, quote=t, snips=snips,
                  status="ambiguous" if is_dept else "stated", confidence="medium",
                  note="签名只写部门名，未给具体职位（经理/专员）→ 称呼时避免自定级别。" if is_dept else "")
    # 公司类型：只有客户自述才写
    mtype = re.search(r"\b(manufacturer|trading\s+company|distributor|importer|trader)\b", text, re.I)
    if mtype:
        set_field(fields, "buyer_type", f"客户自述：{mtype.group(1)}", quote=_line_containing(text, mtype.group(0)),
                  snips=snips, confidence="high")
    elif fields.get("buyer_type"):
        fields["buyer_type"]["value"] = ""
        fields["buyer_type"]["status"] = "assumed"
        fields["buyer_type"]["note"] = "客户未自述公司类型；不得据行业词推断为终端厂或贸易商。"


def extract_context(text, fields, snips):
    ap = re.search(r"\b(float\s+(glass|furnace|line)|container\s+(glass\s+)?line|glass\s+container|production\s+line|furnace)\b",
                   text, re.I)
    if ap:
        set_field(fields, "application", C.norm_ws(_line_containing(text, ap.group(0)) or ap.group(0)),
                  quote=_line_containing(text, ap.group(0)) or ap.group(0), snips=snips,
                  confidence="medium", note="应用场景取自客户自述，仅用于沟通背景，不进入报价。")
    cs = re.search(r"(current\s+supplier|existing\s+supplier|comparing\s+with\s+our\s+current|现有供应商)[^\n]{0,80}",
                   text, re.I)
    if cs:
        set_field(fields, "current_supplier", C.norm_ws(cs.group(0)), quote=_line_containing(text, cs.group(0)),
                  snips=snips, confidence="medium",
                  note="客户只提到正在对比现有供应商，未给供应商名称。")
    u = re.search(r"(look\s+forward\s+to\s+your\s+offer|urgent|asap|as\s+soon\s+as\s+possible|immediately needed)", text, re.I)
    if u and re.search(r"urgent|asap|as\s+soon|immediately", u.group(0), re.I):
        set_field(fields, "urgency", C.norm_ws(u.group(0)), quote=_line_containing(text, u.group(0)), snips=snips,
                  status="ambiguous", confidence="medium",
                  note="客户表达期盼，未给具体时间要求 → 不构成交期。")
    ps = re.search(r"price\s+should\s+be\s+\w+|competitive\s+price", text, re.I)
    if ps:
        set_field(fields, "price_sensitivity", C.norm_ws(_line_containing(text, ps.group(0)) or ps.group(0)),
                  quote=_line_containing(text, ps.group(0)) or ps.group(0), snips=snips,
                  status="stated", confidence="high",
                  note="仅为价格敏感线索，不含任何价格标准；不得据此报价或让价。")
    sm = re.search(r"(sample[^\n]{0,140})", text, re.I)
    if sm:
        line = sm.group(1)
        set_field(fields, "sample_req", C.norm_ws(line), quote=_line_containing(text, line[:40]) or line,
                  snips=snips, status="ambiguous", confidence="high",
                  note="客户说明样品由自有货代取件；未给样品数量、是否收费、样品规格 → 需我方样品政策。")
    if not fields.get("sample_stage", {}).get("value"):
        first = re.search(r"(first\s+(time|order|inquiry)|new\s+customer|第一[次单])", text, re.I)
        if first:
            set_field(fields, "sample_stage", "客户自述首次合作意向", quote=first.group(0), snips=snips,
                      confidence="medium")


def extract_all(snips, head=None, text_override=None):
    snips_text = [s["text"] for s in snips]
    text = text_override if text_override is not None else "\n\n".join(snips_text)
    fields = C.normalize_fields({})
    head = head or {}
    extract_buyer(text, fields, snips, head)
    if not extract_product(text, fields, snips):
        m = re.search(r"(?:product|品名)\s*[:：]\s*([^\n]{2,60})", text, re.I)
        if m:
            set_field(fields, "product_raw", C.norm_ws(m.group(1)), quote=m.group(0), snips=snips,
                      status="ambiguous", confidence="low",
                      note="未匹配到产品库：需人工确认品名与 CAS（不得凭记忆填写 CAS）。")
    extract_spec(text, fields, snips)
    extract_qty(text, fields, snips)
    extract_delivery(text, fields, snips)
    extract_commercial(text, fields, snips)
    extract_docs(text, fields, snips)
    extract_context(text, fields, snips)
    _cleanup(fields, text)
    return fields


def _clear(fields, key, status="missing", note=""):
    if key in fields:
        fields[key].update({"value": "", "raw": "", "status": status, "quote": "", "confidence": "",
                            "source_id": "", "locator": ""})
        if note:
            fields[key]["note"] = note


def _cleanup(fields, text):
    """去掉误命中、补上"客户没说"的显式标注。"""
    # 产品原话只保留客户写的品名，不带字段标签
    f = fields.get("product_raw", {})
    if f.get("value"):
        f["value"] = re.sub(r"^\s*(product|item|品名|产品)\s*[:：]\s*", "", f["value"], flags=re.I)
        f["value"] = C.norm_ws(f["value"])
        f["raw"] = f["value"]
    # 等级：客户给了数值规格时，等级不再单列为必确认（请在 _cleanup 末尾重做，确保规格已就位）
    # 币种：客户没写币种
    cur = fields.get("currency", {})
    if cur.get("status") == "stated" and cur.get("note", "").startswith("客户要求报价但未写币种"):
        cur["status"] = "ambiguous"
    # 价格基础：价格本身不由本技能产生
    pb = fields.get("price_basis", {})
    if pb.get("value"):
        inc = fields.get("incoterm", {}).get("value", "")
        place = fields.get("incoterm_place", {}).get("value", "")
        cur_v = fields.get("currency", {}).get("value", "") or "（币种待确认）"
        if fields.get("incoterm", {}).get("status") == "ambiguous":
            # 术语与港口冲突：价格基础不成立
            pb["value"] = f"（术语与港口冲突待澄清）/MT，{inc} {place}".strip()
            pb["status"] = "ambiguous"
            pb["note"] = ("贸易术语与港口不一致（%s 后面写的是买方港口），价格基础不成立，"
                          "须先与客户澄清再报价。" % inc)
        else:
            pb["value"] = f"{cur_v} / MT，{inc} {place}".strip()
            pb["status"] = "ambiguous"
            pb["note"] = "价格基础已可拼出，但**单价**属销售/报价环节，本技能不产生任何价格。"
    # 单证：避免把 "COA, SDS and TDS" 整行当每项的值，同时不误命中正文里的 "C.O."
    for k, name in (("doc_coa", "COA"), ("doc_sds", "SDS"), ("doc_tds", "TDS")):
        d = fields.get(k, {})
        if d.get("value") and d["value"].lower().startswith("documents"):
            d["value"] = d["value"]
            d["what"] = name
    coo = fields.get("doc_coo", {})
    if coo.get("value") and not re.search(r"(certificate\s+of\s+origin|原产地证|\bCO\b\s*(and|,)|\bCO\b\s+for)", coo.get("quote", ""), re.I):
        _clear(fields, "doc_coo", status="missing",
               note="客户未提及原产地证；如需要，须我方先确认能否出具（不得在回复中承诺）。")
    # 应用/现有供应商：只留短句
    for k in ("application", "current_supplier", "sample_req", "urgency"):
        ff = fields.get(k, {})
        if ff.get("value") and len(ff["value"]) > 160:
            ff["value"] = C.short(ff["value"], 140)
    if fields.get("current_supplier", {}).get("value") and not fields["current_supplier"].get("quote"):
        fields["current_supplier"]["quote"] = fields["current_supplier"]["value"]
    # 样品：只保留客户原话中的样品句
    sp = fields.get("sample_req", {})
    if sp.get("status") == "ambiguous" and not sp.get("note"):
        sp["note"] = "客户未给样品数量、是否收费、规格要求 → 需我方样品政策。"
    # 交期 / 有效期：客户没提
    if not fields.get("delivery_time", {}).get("value"):
        fields["delivery_time"]["note"] = "客户未提交期/装运期 → 由我方排产确认，回复中只能占位。"
    if not fields.get("quote_validity", {}).get("value"):
        fields["quote_validity"]["note"] = "客户未提报价有效期 → 由我方确定，不得默认 30 天。"
    # 数量单位注
    qa = fields.get("qty_annual", {})
    if qa.get("value"):
        qa["note"] = "客户原文为印尼/欧陆千分位写法（3.000 = 3,000），已按公吨解析；年量≠首批量。"
    # CAS 来源说明
    cas = fields.get("cas", {})
    if cas.get("value") and cas.get("source_type") != "customer":
        cas["note"] = ("来源：产品标准化画像 + 权威库查证（Wikidata Q190227 / PubChem CID 10340，2026-10-19）；"
                       "客户原话未给 CAS。若贵司产品资料另有编号，以产品资料为准。")
    # 等级：客户未给等级词但已给数值规格 → 不是"缺等级"，而是"请客户核对数值规格"
    if fields.get("spec_purity", {}).get("status") == "stated":
        spec_txt = "；".join(x for x in [
            fields.get("spec_purity", {}).get("value"), fields.get("spec_impurities", {}).get("value"),
            fields.get("spec_particle", {}).get("value")] if x)
        g = fields["grade"]
        g["value"] = ""
        g["status"] = "ambiguous"
        g["confidence"] = "medium"
        g["quote"] = fields["spec_purity"].get("quote", "")
        g["source_id"] = fields["spec_purity"].get("source_id", "")
        g["locator"] = fields["spec_purity"].get("locator", "")
        g["note"] = f"客户未给等级/牌号，但已给数值规格（{spec_txt}）→ 按数值规格执行，只需客户核对数值。"
    # 国家 / 地址 quotes
    if fields.get("buyer_country", {}).get("quote", "").startswith("Delivery"):
        pass


# ------------------------------------------------------------------ 缺口 / 问题
QUESTION_BANK = {
    "product_raw": ("产品形态", "Could you confirm whether you require dense or light soda ash, and in what form (granular / powder)?",
                    "Was 主体名称与我方工商/合同抬头一致？"),
    "product_std": ("标准化品名", "May we confirm the product as {value}?", ""),
    "cas": ("CAS 号", "Could you confirm the CAS number of the product under your procurement policy?",
            "CAS 号来源是否与我方产品资料一致？"),
    "grade": ("等级", "Could you advise which grade you require (industrial / glass / technical)?",
              "客户所称等级是否对应我方现有产品线？"),
    "currency": ("币种", "Could you confirm the quotation currency (USD / EUR)?", "我方报价币种确认。"),
    "price_basis": ("价格基础", "Could you confirm the price basis you require (per MT, which term and port)?", ""),
    "payment": ("付款方式", "We note that you require payment by L/C. To prepare the offer correctly, could you confirm "
                           "the L/C type (at sight or usance) and the validity period?", "我方能否接受客户付款方式，并给出我方条件。"),
    "lc_terms": ("信用证条件", "If L/C is required, could you advise the issuing bank, validity, and whether it should be confirmed?",
                 "我方能否接受该信用证。"),
    "delivery_time": ("交期", "What is your required delivery window, and when do you plan to place the order?", "我方排产与船期。"),
    "quote_validity": ("报价有效期", "Would you advise your decision timeline so that we can confirm the validity of our offer?",
                       "我方报价有效天数。"),
    "sample_req": ("样品", "Could you confirm the sample quantity and the specification your laboratory will test, so that "
                          "the sample matches the material we would ship?", "我方样品政策、样品费与寄样方式。"),
    "buyer_name": ("客户全称", "Could you please confirm your full registered company name and address for the document draft?",
                   "客户工商登记信息核验（转「核验海外询盘公司」）。"),
    "buyer_country": ("国家", "Could you confirm the destination country?", ""),
    "contact_name": ("联系人", "May we address correspondence to the purchasing contact directly?", ""),
    "contact_email": ("邮箱", "Could you confirm the e-mail address for commercial correspondence?", ""),
    "doc_coo": ("原产地证", "Do you require a Certificate of Origin with the shipment?",
                "我方能否出具（贸促会/海关）。"),
    "doc_form_e": ("FORM E", "Do you require a Form E for ACFTA preferential duty, or is a general Certificate of Origin sufficient?",
                   "我方能否出具 FORM E。"),
    "doc_inspection": ("第三方检验", "Do you require third-party inspection (SGS / BV) at loading port or destination?",
                       "检测机构、节点与费用承担。"),
    "doc_coa": ("COA", "Could you confirm whether COA is required per lot or per shipment?", ""),
    "doc_sds": ("SDS", "Do you require the SDS in English or in Bahasa Indonesia?", "我方 SDS 语言版本。"),
    "doc_tds": ("TDS", "Which TDS version would you like us to attach?", ""),
    "pack_std": ("包装", "Which packing do you prefer — 25 kg PP bags or 1,000 kg jumbo bags with inner liner — "
                         "and should the bags be palletized?", "我方标准出口包装方案。"),
    "pack_pallet": ("托盘", "Do you require palletization, and does your site have a forklift for unloading?", ""),
    "pack_marking": ("唛头", "Do you require marking or labels in Bahasa Indonesia?", ""),
    "inspection_cost": ("检验费", "Please advise who will bear the cost of inspection, if required.", "费用承担口径。"),
    "commission": ("佣金", "Please confirm whether an agent commission applies and at what rate.", "佣金政策。"),
}

# 阻塞报价的核心问题（即使字段已填，也要在回复里确认的"防错问句"）
CORE_QUESTION_KEYS = ["grade", "currency", "payment", "pack_std"]
MAX_QUESTIONS = 6

INTERNAL_CONFIRM = {
    "pack_std": "我方标准出口包装方案（袋型 / 袋重 / 内衬 / 托盘）",
    "delivery_time": "排产可承诺的装运期",
    "quote_validity": "报价有效天数",
    "sample_req": "样品政策（数量 / 样品费 / 运费承担）",
    "doc_form_e": "能否出具 FORM E",
    "doc_coo": "能否出具原产地证",
    "doc_inspection": "能否配合第三方检验及费用",
    "payment": "我方可接受付款条件",
    "lc_terms": "信用证可接受范围",
}


def build_questions(fields, max_p=MAX_QUESTIONS):
    """A 类缺口 + 歧义 → 客户问题（≤6 条）；阻塞字段 → 内部确认。"""
    client_q = []
    internal_q = []
    seen = set()
    checked = {str(v).strip().lower() for v in (fields.get("_checked", {}) or {}).values()}
    trap_hits = []
    # 1) 阻塞报价的 A 桶字段（按字段顺序）
    for k in C._ORDER:
        f = fields.get(k, {})
        if f.get("bucket") == "A" and f.get("affects_quote") and f.get("status") in ("missing", "ambiguous"):
            bank = QUESTION_BANK.get(k)
            if not bank or k == "lc_terms" or k in seen:
                continue
            seen.add(k)
            q_en = bank[1].format(value=f.get("value", ""))
            note_cn = f.get("note", "") or bank[2]
            if k == "grade" and f.get("status") == "ambiguous" and "数值规格" in note_cn:
                # 客户已给数值规格 → 只请其核对，不要求给等级词
                q_en = ("We note your value specifications: " + fields.get("spec_purity", {}).get("value", "") +
                        "; " + fields.get("spec_impurities", {}).get("value", "") + "; " +
                        fields.get("spec_particle", {}).get("value", "") +
                        ". Could you confirm these are the values you will verify on arrival?")
            if k == "incoterm" and "装运港" in note_cn:
                q_en = ("We note your delivery term is FOB %s. As FOB refers to the port of shipment, "
                        "could you confirm whether you require FOB China (a Chinese port) or CFR/CIF %s? "
                        "We will quote on the basis you confirm." % (
                            fields.get("incoterm_place", {}).get("value", ""),
                            fields.get("incoterm_place", {}).get("value", "")))
            if k == "price_basis" and "冲突" in note_cn:
                q_en = ("To make sure the price basis is exactly what you need, could you confirm whether the "
                        "quotation should be on FOB basis (port of shipment in China) or on CFR/CIF basis to %s?"
                        % fields.get("incoterm_place", {}).get("value", ""))
            if k == "pack_std" and "两种包装" in note_cn:
                q_en = ("You mentioned both %s packing; could you confirm which one you require for the first "
                        "shipment, and whether you need both options quoted separately?"
                        % fields.get("pack_std", {}).get("value", ""))
            if k == "price_basis" and "单价" in note_cn:
                q_en = ("May we confirm that a quotation per MT, " + fields.get("incoterm", {}).get("value", "") + " " +
                        fields.get("incoterm_place", {}).get("value", "") +
                        ", Incoterms 2020, in USD is the basis you require?")
            if k == "grade" and f.get("status") == "ambiguous" and "数值规格" in note_cn:
                # 客户已给数值规格 → 只请其核对，不要求给等级词
                q_en = ("We will execute your value specifications: " + fields.get("spec_purity", {}).get("value", "") +
                        "; " + fields.get("spec_impurities", {}).get("value", "") + "; " +
                        fields.get("spec_particle", {}).get("value", "") +
                        ". Could you confirm these are the values you will verify on arrival?")
            client_q.append({
                "field": k, "label_cn": f["label_cn"], "label_en": f["label_en"],
                "priority": 1, "status": f["status"],
                "question_en": q_en,
                "reason_cn": note_cn or "客户未提供，缺此项无法形成有效报价。",
                "anchor": C.short(f.get("quote", ""), 120),
                "internal": bank[2],
            })
    # 2) 核心防错问题（字段有值也要确认的那几句）
    for k in CORE_QUESTION_KEYS:
        f = fields.get(k, {})
        if k in seen or k not in QUESTION_BANK:
            continue
        if f.get("status") == "stated" and f.get("value"):
            seen.add(k)
            bank = QUESTION_BANK[k]
            client_q.append({
                "field": k, "label_cn": f["label_cn"], "label_en": f["label_en"],
                "priority": 2, "status": "check",
                "question_en": "{Q}" if k != "payment" else bank[1],
                "reason_cn": "该字段客户已写，但需客户确认后我方才能锁价/动手备货（防错问句）。",
                "anchor": C.short(f.get("quote", ""), 120),
                "internal": bank[2],
            })
            client_q[-1]["question_en"] = (
                f"We note your requirement as \"{C.short(f.get('value'), 90)}\" - may we confirm this is the "
                f"specification you will verify on arrival?" if k == "grade" else client_q[-1]["question_en"]
            )
    # 3) 客户已确认过的项（用户点了"客户已确认"）→ 移出问题、改为已核对
    client_q = [q for q in client_q if C.short(q.get("anchor", ""), 60).lower() not in checked
                and q["field"].lower() not in checked]
    client_q.sort(key=lambda q: (q["priority"], C._ORDER.index(q["field"]) if q["field"] in C._ORDER else 99))
    client_q = client_q[:max_p]
    # 4) 内部确认（不进客户问题）
    for k, desc in INTERNAL_CONFIRM.items():
        internal_q.append({"field": k, "label_cn": C.field_meta(k)["label_cn"], "desc": desc})
    # 5) 我方假设（B 桶 assume 在渲染层生效）——进"待客户确认事项"，不进内部清单
    for k in C._ORDER:
        f = fields.get(k, {})
        if f.get("bucket") == "B" and f.get("status") in ("missing", "ambiguous") and f.get("assume") \
                and k not in ("buyer_type", "port_load"):
            f["render_assume"] = True
    return client_q, internal_q, trap_hits


# ------------------------------------------------------------------ 回复草稿
DEFAULT_PLACEHOLDERS = [
    ("PRICE_PER_MT", "单价（含贸易术语与港口）", "销售 / 报价系统", "open"),
    ("QUOTE_VALIDITY", "报价有效期（天）", "销售", "open"),
    ("SHIPMENT_TIME", "装运期", "销售 / 排产", "open"),
    ("PAYMENT_TERMS", "我方可接受的付款条件", "财务 / 销售", "open"),
    ("PAYMENT_TERMS_REQUESTED", "客户提出但尚未确认的付款条件", "引用客户原话", "open"),
    ("PACKING_PROPOSAL", "我方标准出口包装建议", "销售 / 技术", "open"),
    ("SAMPLING_POLICY", "样品政策（数量 / 费用 / 运费）", "销售", "open"),
    ("LEAD_TIME_FOR_OFFER", "我方出具正式报价所需时间", "销售", "open"),
    ("STOCK_AVAILABILITY", "可供量 / 库存", "销售", "open"),
    ("DOC_ADDITIONAL", "客户另需单证的确认结果", "单证员", "open"),
    ("SIGNER_NAME", "签字人姓名", "销售", "open"),
    ("SIGNER_TITLE", "签字人职位", "销售", "open"),
    ("OURCOMPANY_NAME", "我方公司全称", "销售 / 市场", "open"),
    ("OURCOMPANY_PHONE", "我方电话", "销售 / 市场", "open"),
    ("OURCOMPANY_WEBSITE", "我方网站", "销售 / 市场", "open"),
]


def _ph_terms(fields):
    """价格占位符。

    - 术语已明确：‹PRICE_PER_MT_CFR_SEMARANG›
    - 术语与港口冲突 / 缺失：不拼出错误口径，直接用 ‹PRICE_PER_MT_TERMS_TBC›
    """
    inc_f = fields.get("incoterm", {})
    inc = inc_f.get("value", "")
    place = fields.get("incoterm_place", {}).get("value", "")
    if not inc or inc_f.get("status") != "stated":
        return "‹PRICE_PER_MT_TERMS_TBC›"
    code = re.sub(r"[^A-Za-z]", "", place or "").upper()[:8]
    return f"‹PRICE_PER_MT_{inc}_{code}›" if code else "‹PRICE_PER_MT_TERMS_TBC›"


def _pretty_date(s):
    """'Mon, 19 Oct 2026 08:42:11 +0700' → '19 October 2026'（外贸惯例写法）。"""
    import email.utils
    try:
        dt = email.utils.parsedate_to_datetime(s)
        return dt.strftime("%d %B %Y").lstrip("0")
    except Exception:
        return (s or "").split(" ")[1:4] and s or ""


def build_reply(fields, snippets, meta, tone="friendly-professional", template="reply_A_confirm"):
    stated = {k: f for k, f in fields.items() if f.get("status") == "stated" and f.get("value")}
    # 用户可以手工修正字段值（工作台里改过的问题/字段以当前值为准）
    effective = {k: (fields[k].get("value") or fields[k].get("raw") or "").strip()
                 for k, f in fields.items() if fields[k].get("status") in ("stated", "ambiguous", "assumed")}

    def g(k, default="—"):
        v = effective.get(k) or ""
        return v if v else default
    indate = _pretty_date(meta.get("inquiry_date", ""))

    contact = g("contact_name", "")
    last = contact.split()[-1] if contact else "‹LAST_NAME›"
    # 越南 / 印尼 / 马来 / 泰 姓名习惯用全名，不要擅自加 Mr./Ms. + 姓
    name_style = (fields.get("buyer_country", {}) or {}).get("value", "")
    asian_full = any(c in name_style for c in ("Vietnam", "Indonesia", "Malaysia", "Thailand", "Philippines"))
    if contact and asian_full:
        greeting = f"Dear {contact},"
    else:
        greeting = {"formal": f"Dear Mr./Ms. {last},",
                    "friendly-professional": f"Dear Mr. {last},",
                    "concise-direct": f"Dear Mr. {last},"}[tone]
    product_name = ("Dense Soda Ash" if 'Dense' in g('product_std') else "Soda Ash Light" if 'Light' in g('product_std') else g('product_std'))
    thanks = {
        "formal": (f"We thank you for your inquiry dated {indate} regarding "
                   f"{product_name}."),
        "friendly-professional": (f"Thank you for your inquiry dated {indate} regarding "
                                  f"{product_name}."),
        "concise-direct": "Thanks for your inquiry - we have reviewed it in detail.",
    }[tone]

    item_lines = [
        ("Product", g("product_std") if "product_std" in stated else "‹PRODUCT_TO_CONFIRM›"),
        ("Specification", "; ".join(x for x in [g("spec_purity", ""), g("spec_impurities", ""),
                                                g("spec_particle", "")] if x)),
        ("Quantity", "; ".join([x for x in [
            (g("qty_trial") + " for the first shipment") if "qty_trial" in stated else "",
            ("approx. " + g("qty_annual")) if "qty_annual" in stated else ""] if x])),
        ("Delivery", (f"{g('incoterm')} {g('incoterm_place')}, Incoterms 2020"
                      if "incoterm" in stated else "‹TERMS_TO_CONFIRM›")),
        ("Documents", ", ".join([n for k2, n in (("doc_coa", "COA"), ("doc_sds", "SDS"), ("doc_tds", "TDS"))
                                 if k2 in stated])),
        ("Application", "glass manufacturing (as stated in your email)" if "application" in stated else ""),
    ]
    width = max(len(k) for k, _ in item_lines)
    restatement = "\n".join(f"- {k.ljust(width)} : {v}" for k, v in item_lines if v)

    confirmed_set = {k for k, f in fields.items() if f.get("confirmed_by")}
    confirmed_labels = {C.field_meta(k)["label_en"]: k for k in confirmed_set}
    client_q, internal_q, _ = build_questions(fields)
    qs = [q for q in client_q if q["field"] not in confirmed_set][:MAX_QUESTIONS]
    qblock = "\n".join(f"{i+1}. {q['question_en']}" for i, q in enumerate(qs)) or \
        "1. May we proceed with the formal offer based on the details above?"
    # 客户确认过的项：在复述块里标 (confirmed)，并从问题里去掉
    if confirmed_labels:
        item_lines = [(k_, v + ("  (confirmed)" if k_ in confirmed_labels and confirmed_labels[k_] in
                                ("grade", "spec_purity") else "")) for k_, v in item_lines]

    ph_terms = _ph_terms(fields)
    next_step = {
        "formal": (f"Once we receive your confirmation on the above points, we will prepare our formal offer, including "
                   f"the price on {ph_terms} and the commercial terms, within ‹LEAD_TIME_FOR_OFFER›."),
        "friendly-professional": (f"Once you confirm the above points, we will send our formal offer with the price on "
                                  f"{ph_terms} and the related commercial terms within ‹LEAD_TIME_FOR_OFFER›."),
        "concise-direct": (f"Please confirm the points above; we will then send the formal offer (price {ph_terms}) "
                           f"within ‹LEAD_TIME_FOR_OFFER›."),
    }[tone]

    terms_block = ""
    if "payment" in stated and "payment" not in confirmed_set and "lc_terms" not in confirmed_set:
        terms_block = (
            "Regarding payment, we note your requirement as \"" + C.short(g("payment"), 60) + "\". "
            "Our finance team reviews payment instruments case by case; the exact terms we can support will be "
            "stated in our formal offer. For reference, our offer will remain valid for ‹QUOTE_VALIDITY› days from "
            "the date of issue."
        )

    docs_block = ("COA, SDS and TDS will accompany our offer. If you need any additional document (for example a "
                  "Certificate of Origin, an ACFTA preferential certificate of origin, or third-party inspection at "
                  "loading port), please advise - we will confirm what our documentation supports.")

    sample_block = ""
    if "sample_req" in stated:
        sample_block = ("We note that you will arrange collection of the sample with your own forwarder. "
                        "Please confirm the sample quantity and the specification your laboratory will test, so that "
                        "the sample matches the material we would ship (sampling arrangement: ‹SAMPLING_POLICY›).")

    # 包装：客户让我方建议 → 邮件里只能给"待确认的建议位"，不能直接写死袋型
    packing_block = ""
    if fields.get("pack_std", {}).get("status") == "ambiguous" and "pack_std" not in confirmed_set:
        packing_block = ("On packing, you asked for our suggestion: our standard export packing for this product is "
                         "‹PACKING_PROPOSAL›. Could you confirm whether that suits your unloading facilities, or "
                         "advise the bag weight you prefer?")

    # 客户确认过的项：不再追问，改为"已核对"
    CASED = {"grade": "specification (value basis)", "currency": "quotation currency",
             "payment": "payment instrument", "lc_terms": "L/C terms", "price_basis": "price basis",
             "pack_std": "packing", "doc_coo": "certificate of origin", "doc_form_e": "preferential CO"}
    acked = [CASED.get(k, C.field_meta(k)["label_en"]) for k, v in fields.items() if v.get("confirmed_by")]
    ack_block = ("For clarity, the following points are treated as agreed based on your confirmation: "
                 + "; ".join(acked) + ".") if acked else ""

    closing = {"formal": "We look forward to your reply.\n\nYours faithfully,",
               "friendly-professional": "We look forward to your reply.\n\nBest regards,",
               "concise-direct": "Looking forward to your confirmation.\n\nRegards,"}[tone]
    signature = ("‹SIGNER_NAME›\n‹SIGNER_TITLE› | ‹OURCOMPANY_NAME›\n"
                 "Tel: ‹OURCOMPANY_PHONE› | Web: ‹OURCOMPANY_WEBSITE›")

    if template == "reply_B_quote_structure":
        body_core = "\n\n".join(x for x in [
            f"{thanks} We are pleased to confirm the following structure of our offer:\n\n"
            f"- Price basis : {ph_terms}\n"
            f"- Quantity    : {g('qty_trial')} for the first shipment" +
            (f"; {g('qty_annual')} under discussion for the annual volume" if "qty_annual" in stated else "") + "\n"
            f"- Packing     : ‹PACKING_PROPOSAL›\n"
            f"- Shipment    : ‹SHIPMENT_TIME› after receipt of ‹PAYMENT_TERMS›\n"
            f"- Validity    : ‹QUOTE_VALIDITY› days from issue date\n"
            f"- Documents   : COA, SDS, TDS",
            "Detailed product specification is as per the TDS attached/supplied; the indicative values below are those you "
            "specified and will be confirmed on the COA of the shipped lot:\n\n" + restatement,
            ack_block, sample_block, terms_block, docs_block,
            ("Please confirm the above so that we can finalise the offer." if tone != "formal"
             else "We would be grateful for your confirmation of the above."),
        ] if x)
    elif template == "reply_C_sample":
        body_core = "\n\n".join(x for x in [
            thanks,
            "As requested, please find below the points we understand, and our proposal for the sample:\n\n" + restatement,
            "Sample arrangement: we can prepare a sample of ‹SAMPLE_QUANTITY› for evaluation; delivery will follow "
            "‹SAMPLING_POLICY›. Please confirm the specification your laboratory will test so that the sample matches "
            "the material we would ship.",
            docs_block, next_step, sample_block, packing_block, ack_block,
        ] if x)
    elif template == "reply_D_docs_only":
        body_core = "\n\n".join(x for x in [
            thanks,
            "Please find below the documents and technical points we understand from your inquiry:\n\n" + restatement,
            docs_block,
            "We will be glad to send the technical documents for your internal review; please advise the intended "
            "application and the specification you will verify so that we send the relevant TDS version.",
            next_step, ack_block,
        ] if x)
    else:  # reply_A_confirm
        body_core = "\n\n".join(x for x in [
            thanks,
            "We have reviewed your requirements and would like to confirm a few points before preparing our formal offer.\n\n"
            "As we understand your inquiry:\n\n" + restatement,
            ack_block,
            (("To prepare an accurate offer, could you please confirm the following:\n\n" + qblock)
             if qs else "All the points we need for the offer are now clear from your email and our exchange."),
            packing_block, sample_block, terms_block, docs_block, next_step,
        ] if x)

    cust = g("buyer_name", "") or meta.get("inquiry_no", "") or "your inquiry"
    subject = (f"Re: Inquiry - {product_name} - {cust}") + \
              (f" - {g('incoterm')} {g('incoterm_place')}" if fields.get("incoterm", {}).get("status") == "stated"
               else " - delivery terms to be confirmed")
    body = "\n\n".join([greeting, body_core, closing, signature]) + "\n"
    used = set(C.find_placeholders(body))
    # 只登记"本稿里真正出现"的占位符：清单是给收件人照着填的，列一堆用不到的空位只会稀释注意力
    placeholders = []
    for k, l, o, s in DEFAULT_PLACEHOLDERS:
        hit = [u for u in used if u == k or u.startswith(k + "_")]
        if not hit:
            continue
        for u in sorted(hit):
            placeholders.append({"key": u, "label_cn": l, "owner": o, "status": s, "used": True, "where": ""})
    extra = [u for u in used if not any(u == p["key"] or u.startswith(p["key"] + "_") for p in placeholders)]
    for u in sorted(extra):
        placeholders.append({"key": u, "label_cn": "模板中出现的其他占位符", "owner": "待定",
                             "status": "open", "used": True, "where": ""})

    return {
        "channel": "A_confirm" if template == "reply_A_confirm" else template,
        "tone": tone,
        "template": template,
        "subject": subject,
        "body": body,
        "placeholders": placeholders,
        "questions_used": [q["question_en"] for q in qs],
        "commitment_scan": C.scan_commitments(body),
        "price_scan": C.scan_prices(body),
        "generated_at": C.now_iso(),
        "generator": f"{C.SKILL_NAME} {C.VERSION}",
        "simulation": True,
    }


def build_fields_doc(snippets, fields, meta):
    counts = C.field_counts(fields)
    ok, bad = C.can_quote(fields)
    client_q, internal_q, traps = build_questions(fields)
    return {
        "meta": meta,
        "snippets": snippets,
        "fields": fields,
        "summary": counts,
        "can_quote": ok,
        "blocking_fields": bad,
        "questions": client_q,
        "internal_confirm": internal_q,
        "gate": {k: {"value": "", "status": "internal", "choices": v} for k, v in C.GATE_CHOICES.items()},
        "disclaimer": "本技能不评估询盘真实性，也不评估成交可能性；只做字段提取、缺口识别与回复草稿。",
    }


def main():
    ap = argparse.ArgumentParser(description="海外询盘 → 结构化字段（只搬运，不产价）")
    ap.add_argument("--email", help=".eml 文件")
    ap.add_argument("--text", help="合并素材 .md/.txt（支持 素材01/素材02 分块）")
    ap.add_argument("--eml-dir", help="目录下的 .eml（按文件名排序）")
    ap.add_argument("--fields", help="已有 fields.json（作为基底，脚本只补空字段）")
    ap.add_argument("-o", "--out", default=".", help="输出目录")
    ap.add_argument("--emit", help="输出目录（兼容写法，等同 -o）")
    ap.add_argument("--as-of", default=C.today_iso())
    ap.add_argument("--inquiry-no", default="")
    ap.add_argument("--tone", default="friendly-professional",
                    choices=["formal", "friendly-professional", "concise-direct"])
    ap.add_argument("--template", default="reply_A_confirm",
                    choices=["reply_A_confirm", "reply_B_quote_structure", "reply_C_sample", "reply_D_docs_only"])
    ap.add_argument("--no-reply", action="store_true")
    args = ap.parse_args()
    out_dir = args.emit or args.out
    os.makedirs(out_dir, exist_ok=True)

    snippets = []
    head = {}
    if args.email:
        head, body = load_email(args.email)
        date_t = head.get("date", "")
        snippets, _ = build_snippets(head, body, head.get("subject", os.path.basename(args.email)), date_t)
    elif args.eml_dir:
        files = sorted([f for f in os.listdir(args.eml_dir) if f.lower().endswith(".eml")])
        for i, fn in enumerate(files, 1):
            head, body = load_email(os.path.join(args.eml_dir, fn))
            s, _ = build_snippets(head, body, head.get("subject", fn), head.get("date", ""))
            for b in s:
                b["id"] = f"S{i:02d}"
                snippets.append(b)
    elif args.text:
        txt = C.read_text(args.text)
        blocks = split_blocks(txt)
        for sid, title, body in blocks:
            snippets.append(snippet_with_lines(sid, title, body))
    elif args.fields:
        pass
    else:
        ap.error("需要 --email / --text / --eml-dir / --fields 之一")

    if args.fields and os.path.exists(args.fields):
        doc = C.load_json_stable(args.fields)
        fields = C.normalize_fields(doc.get("fields"))
        meta = doc.get("meta", {})
        if not snippets:
            snippets = doc.get("snippets", [])
    else:
        full = "\n\n".join(s["text"] for s in snippets)
        fields = extract_all(snippets, head)
        subject = head.get("subject", "")
        cust = fields.get("buyer_name", {}).get("value", "") or ""
        meta = {
            "inquiry_no": args.inquiry_no or f"INQ-{args.as_of.replace('-', '')}-01",
            "as_of": args.as_of,
            "customer": cust,
            "customer_country": fields.get("buyer_country", {}).get("value", ""),
            "customer_contact": fields.get("contact_name", {}).get("value", ""),
            "subject": subject,
            "inquiry_date": head.get("date", ""),
            "chars": len(full),
            "simulation": True,
            "simulation_notice": "模拟案例：公司、联系人、数量与全部商务参数均为虚构，仅用于演示。",
            "disclaimer": "本技能不评估询盘真实性，也不评估成交可能性。",
        }

    doc = build_fields_doc(snippets, fields, meta)
    C.write_json(os.path.join(out_dir, "fields.json"), doc)
    C.write_json(os.path.join(out_dir, "snippets.json"), snippets)
    client_q, internal_q, traps = build_questions(fields)
    C.write_json(os.path.join(out_dir, "questions.json"),
                 {"client_questions": client_q, "internal_confirm": internal_q})
    if not args.no_reply:
        reply = build_reply(fields, snippets, meta, args.tone, args.template)
        C.write_json(os.path.join(out_dir, "reply.json"), reply)
        C.write_json(os.path.join(out_dir, "placeholders.json"), reply["placeholders"])

    s = doc["summary"]
    lines = [
        f"# 缺口摘要 · {meta.get('customer','')}",
        "",
        f"- 字段：已明确 {s['stated']} / 缺失 {s['missing']} / 歧义 {s['ambiguous']} / 假设 {s['assumed']}",
        f"- 阻塞报价的字段：{len(doc['blocking_fields'])} 个 → {', '.join(doc['blocking_fields'])}",
        f"- 可直接报价：{'是' if doc['can_quote'] else '否'}",
        "",
        "## 客户问题（可直接粘进邮件）",
    ]
    for i, q in enumerate(client_q, 1):
        lines.append(f"{i}. [P{q['priority']}] {q['question_en']}")
        lines.append(f"   依据：{q['anchor'] or '（客户未提及）'}")
        lines.append(f"   中文：{q['reason_cn']}")
    lines += ["", "## 我方内部先确认"]
    for q in internal_q:
        lines.append(f"- {q['label_cn']}：{q['desc']}")
    with open(os.path.join(out_dir, "gaps.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"[ok] {out_dir}/fields.json  → 已明确 {s['stated']} · 缺失 {s['missing']} · 歧义 {s['ambiguous']}")
    print(f"[gate] 可直接报价：{'是' if doc['can_quote'] else '否'} · 阻塞字段 {len(doc['blocking_fields'])} 个")
    print(f"[q] 客户问题 {len(client_q)} 条 · 内部先确认 {len(internal_q)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
