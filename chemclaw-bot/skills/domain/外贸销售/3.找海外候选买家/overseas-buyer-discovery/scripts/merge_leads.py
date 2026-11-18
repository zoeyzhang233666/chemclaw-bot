# -*- coding: utf-8 -*-
"""Merge lane JSON files into build/leads_merged.json: dedupe, tier merge, enrichment, ordering."""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
BUILD = os.path.join(HERE, "build")

CORE = ["core_leads.json", "core_leads_extra.json"]
LANES = ["lane_glass.json", "lane_glass_verify1.json", "lane_detergent.json", "lane_detergent_verify.json",
         "lane_distributor1.json", "lane_trade_records.json", "lane_paper_silicate_textile.json"]

EXCLUDE = ["pupuk", "petrokimia gresik", "sodaashntt", "solvay", "garam", "pertaminapetrochemical",
           "sanyou", "haihua", "yihua", "vanward", "asahimaschemical", "globexventure", "ansac", "tatachemicals",
           "ciner", "wesoda", "sisecam", "ciech", "lionwings", "megasuryamas", "sritex",
           "manuchar", "unilever", "brenntag", "imcd"]

LANE_BY_COMPANY = {
    "asahimasflatglasstbk": "glass",
    "sayapmasutama": "detergent", "kaoindonesia": "detergent", "sinarantjol": "detergent",
    "indosuksessentrausahaisu": "detergent", "mileniummasamanunggal": "detergent",
    "saranaciptamandiri": "detergent", "heavenchemicalindonesia": "detergent",
    "mottoberinginabadi": "detergent", "lambangutama": "detergent",
}
FIX = {"ptmuliaglass": {"merge_into": "ptmuliaindustrindotbk"}}
GLASS_ALIAS = ["muliaglass", "pharmaglassindokemas", "xinyiglassindonesia", "kibingglassindonesia", "iglas", "kedaung", "ardendi"]
GFIX = {"muliaglass": {"merge_into": "ptmuliaindustrindotbk"}}

def is_mulia_group(n):
    return n.startswith("mulia") and not n.startswith("muliakeramik")

TR = {"A": 3, "B": 2, "C": 1}
CONFMO = {"\u9ad8": 0, "\u4e2d": 1, "\u4f4e": 2, "high": 0, "mid": 1, "low": 2}

def norm(s):
    s = (s or "").lower()
    s = re.sub(r"\(.*?\)|（.*?）", "", s)
    s = re.sub(r"\b(pt|pt\.|perseroan terbatas|tbk|ltd|limited|co\.|inc\.|corporation|corp\.?)\b", "", s)
    return re.sub(r"[^a-z0-9\u4e00-\u9fa5]+", "", s)

def load(p):
    try:
        d = json.load(open(os.path.join(RAW, p), encoding="utf-8"))
        return d if isinstance(d, list) else []
    except Exception as e:
        print("  (skip)", p, type(e).__name__)
        return []

items = []
for p in CORE:
    items += load(os.path.join(BUILD, p))
for p in LANES:
    got = load(p)
    if got:
        print("%-46s %3d" % (p, len(got)))
    items += got

E = {}
E["ptmuliaindustrindotbk"] = {
    "region_short": "Jawa Barat / DKI Jakarta",
    "why_related": "\u5370\u5c3c\u6700\u5927\u7684\u672c\u571f\u73bb\u7483\u96c6\u56e2\u4e4b\u4e00\uff0c\u56db\u4e2a\u4e1a\u52a1\u90e8\uff08\u6d6e\u6cd5\u73bb\u7483\u3001\u74f6\u7f50\u3001\u73bb\u7483\u7816\u3001\u6c7d\u8f66\u5b89\u5168\u73bb\u7483\uff09\u5747\u4f9d\u8d56\u9500\u9499\u7845\u73bb\u7483\u7194\u7a91\uff1b\u7eaf\u78b1\u662f\u5176\u7b2c\u4e09\u5927\u539f\u6599\u3002\u5e74\u62a5\u81ea\u62ab\u5e74\u7528\u91cf 13.7 \u4e07\u5428\uff0c\u662f\u672c\u6b21\u552f\u4e00\u53d6\u5f97\u4f01\u4e1a\u7ea7\u7528\u91cf\u53e3\u5f84\u7684\u7ec8\u7aef\u7528\u6237\uff1b\u91c7\u8d2d\u4e3b\u4f53\u5e94\u4e3a\u751f\u4ea7\u5b50\u516c\u53f8 PT Muliaglass\u3002",
    "verify_channel": "\u516c\u53f8\u79d8\u4e66/\u6295\u8d44\u8005\u5173\u7cfb\u90ae\u7bb1 -> \u91c7\u8d2d\u90e8\uff1b\u4e0e IDX \u5e74\u62a5\u4ea4\u53c9\u6838\u5bf9\uff1b\u603b\u673a\u8f6c\u91c7\u8d2d",
    "contact_struct": {"website": "https://muliaindustrindo.com", "phone": "(+6221) 22513000",
                       "email": "corsec@muliagroup.co.id (company secretary / investor relations)",
                       "address": "Atrium Mulia 8th Floor, Jl. H.R. Rasuna Said Kav. B 10-11, Jakarta 12910",
                       "social": "", "note": "\u4e0a\u5e02\u516c\u53f8\uff1b\u9996\u89e6\u5efa\u8bae\u516c\u53f8\u79d8\u4e66\u6e20\u9053\u8f6c\u91c7\u8d2d\u90e8\uff0c\u4e0d\u8981\u76f4\u63a5\u8054\u7cfb\u4e2a\u4eba",
                       "verified_on": "2026-10-19"},
}
E["ptasahimasflatglasstbk"] = {
    "region_short": "Banten / Jawa Timur",
    "why_related": "\u5370\u5c3c\u4e3b\u8981\u6d6e\u6cd5\u73bb\u7483\u4e0e\u6c7d\u8f66\u5b89\u5168\u73bb\u7483\u5382\uff08AGC \u4f53\u7cfb\uff09\uff0c\u7194\u7a91\u5de5\u827a\u5fc5\u7136\u6d88\u8017\u91cd\u8d28\u7eaf\u78b1\uff0c\u4e14\u53ef\u6301\u7eed\u53d1\u5c55\u62a5\u544a\u5c06 soda abu \u5217\u4e3a\u6279\u6599\u6210\u5206\u3002\u5df2\u88ab\u4e2d\u56fd\u540c\u884c\uff08\u5510\u5c71\u4e09\u53cb\u516c\u5f00\u5ba2\u6237\u540d\u5355\uff09\u8986\u76d6\uff0c\u5c5e\u5df2\u88ab\u7ade\u54c1\u670d\u52a1\u7684\u9ad8\u4ef7\u503c\u8d26\u6237\u3002",
    "verify_channel": "\u5b98\u7f51/IDX \u5e74\u62a5 -> \u91c7\u8d2d\u90e8\uff1bAGC \u96c6\u56e2\u662f\u5426\u96c6\u4e2d\u91c7\u8d2d\u9700\u786e\u8ba4",
}

merged = {}
for it in items:
    if not isinstance(it, dict) or not it.get("company"):
        continue
    n = norm(it["company"])
    if re.sub(r"[^a-z0-9]+", "", n) in GLASS_ALIAS:
        it["lane"] = "glass"
    if any(e in n for e in EXCLUDE) and not is_mulia_group(n):
        continue
    if n not in merged:
        merged[n] = dict(it)
        continue
    a = merged[n]
    if TR.get(it.get("evidence_tier"), 0) > TR.get(a.get("evidence_tier"), 0):
        a["evidence_tier"] = it.get("evidence_tier")
        a["evidence_summary"] = it.get("evidence_summary")
        a["evidence_period"] = it.get("evidence_period") or a.get("evidence_period")
    a["evidence_urls"] = list(dict.fromkeys((a.get("evidence_urls") or []) + (it.get("evidence_urls") or [])))
    a["contact"] = list(dict.fromkeys((a.get("contact") or []) + (it.get("contact") or [])))
    a["open_questions"] = list(dict.fromkeys((a.get("open_questions") or []) + (it.get("open_questions") or [])))
    if not a.get("contact_struct") and it.get("contact_struct"):
        a["contact_struct"] = it["contact_struct"]

# --- apply FIX (merge aliases / drop) ---
for k in list(merged):
    fx = FIX.get(k) or FIX.get(re.sub(r"[^a-z0-9]+", "", k))
    if not fx:
        continue
    if fx.get("drop"):
        merged.pop(k, None)
        continue
    tgt = fx.get("merge_into")
    if tgt and tgt in merged:
        a, b = merged[tgt], merged.pop(k)
        a["evidence_urls"] = list(dict.fromkeys((a.get("evidence_urls") or []) + (b.get("evidence_urls") or [])))
        a["open_questions"] = list(dict.fromkeys((a.get("open_questions") or []) + (b.get("open_questions") or [])))
        a["alt_names"] = (a.get("alt_names") or "") + "\uff1b\u540c\u96c6\u56e2\uff1a" + b.get("company", "")
        if TR.get(b.get("evidence_tier"), 0) > TR.get(a.get("evidence_tier"), 0):
            a["evidence_tier"] = b.get("evidence_tier")
for k, v in merged.items():
    fx = FIX.get(k) or FIX.get(re.sub(r"[^a-z0-9]+", "", k)) or {}
    if fx.get("lane"):
        v["lane"] = fx["lane"]
    if fx.get("type"):
        v["type"] = fx["type"]
    key = re.sub(r"[^a-z0-9]+", "", k)
    if key.startswith("pt"):
        key = key[2:]
    if key in LANE_BY_COMPANY:
        v["lane"] = LANE_BY_COMPANY[key]

for k, v in merged.items():
    if k in E:
        v.update(E[k])

LANE_LABEL = {"glass": "\u73bb\u7483\u5236\u9020", "detergent": "\u6d17\u6da4\u5242/\u65e5\u5316",
              "distributor": "\u5316\u5de5\u5206\u9500/\u8d38\u6613", "silicate": "\u6c34\u73bb\u7483/\u7845\u9178\u94a0",
              "pulp_paper": "\u7eb8\u6d46\u9020\u7eb8", "textile_ceramic": "\u7eba\u7ec7/\u9676\u74f7"}
REG_MAP = [("Jawa Barat", "Jawa Barat"), ("Bekasi", "Jawa Barat"), ("Cikarang", "Jawa Barat"), ("Bogor", "Jawa Barat"),
           ("Tangerang", "Banten"), ("Cilegon", "Banten"), ("Banten", "Banten"), ("Jawa Timur", "Jawa Timur"),
           ("Surabaya", "Jawa Timur"), ("Sidoarjo", "Jawa Timur"), ("Pasuruan", "Jawa Timur"),
           ("Jakarta", "DKI Jakarta"), ("Semarang", "Jawa Tengah"), ("Jawa Tengah", "Jawa Tengah"),
           ("Central Java", "Jawa Tengah"), ("Medan", "Sumatera Utara")]

out = sorted(merged.values(), key=lambda v: ({"A": 0, "B": 1, "C": 2}.get(v.get("evidence_tier"), 3),
                                              CONFMO.get(v.get("confidence", ""), 3),
                                              -(len(v.get("evidence_urls") or []))))
for i, v in enumerate(out, start=1):
    v["id"] = i
    lane = v.get("lane") if v.get("lane") in LANE_LABEL else "distributor"
    v["lane"], v["lane_label"] = lane, LANE_LABEL[lane]
    if not v.get("region_short"):
        reg = v.get("region") or ""
        for k2, r2 in REG_MAP:
            if k2.lower() in reg.lower():
                v["region_short"] = r2
                break
    v.setdefault("region_short", "\u672a\u6807\u6ce8")
    v.setdefault("evidence_tier", "C")
    c = v.get("confidence", "")
    v["confidence"] = {"high": "\u9ad8", "mid": "\u4e2d", "low": "\u4f4e"}.get(c, c) or "\u4e2d"
    v.setdefault("type", "\u5f85\u786e\u8ba4")
    if not v.get("why_related"):
        v["why_related"] = v.get("product_relation", "")
    v.setdefault("verify_channel", "\u5b98\u7f51/\u5e74\u62a5 -> \u603b\u673a\u8f6c\u91c7\u8d2d\u90e8")

json.dump(out, open(os.path.join(BUILD, "leads_merged.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
from collections import Counter
print("MERGED:", len(out))
print("tier:", dict(Counter(v["evidence_tier"] for v in out)))
print("type:", dict(Counter(v["type"] for v in out)))
print("lane:", dict(Counter(v["lane"] for v in out)))

