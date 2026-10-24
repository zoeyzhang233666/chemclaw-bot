# -*- coding: utf-8 -*-
"""validate.py —— 交付前硬性校验（不合规直接非零退出）。

校验分三层：
  A. 结构层：data.json 必需字段、指标行完整性、批号唯一性
  B. 语义层：判定状态只允许六种；"无法判断/规格未约定"必须有原因；不符合必须有偏离；
             单位与限值必须能被解析；日期必须可解析
  C. 合规层：输出中不得出现"建议收货/建议退货/同意接收"等替用户下结论的表述；
             模拟数据必须有标记

用法：
    python validate.py data.json
    python validate.py data.json --render out.html out.xlsx   # 连成品一起查
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import coa_lib as L    # noqa: E402
import engine          # noqa: E402

# 合规红线：这些词表示"替用户做了收货/处置决定"
FORBIDDEN_DECISION = [
    r"建议收货", r"建议退货", r"建议拒收", r"同意接收", r"予以拒收", r"退换货处理",
    r"接收该批货", r"可以接收", r"不得接收", r"判定为不合格批次", r"拒收该批",
]
# 允许出现在"免责说明"里的上下文词（整句含这些词时放行）
EXEMPT_CTX = ["不作", "不构成", "不代表", "不直接", "不含", "不涉及", "不得", "需要", "由", "决策", "共同"]

REQUIRED_META = ["title", "as_of", "target_coa_batch"]
REQUIRED_PRODUCT = ["name", "indicator_aliases"]
REQUIRED_COA = ["batch_no", "header", "items"]


class Report:
    def __init__(self):
        self.rows = []

    def add(self, level, code, msg, hint=""):
        self.rows.append({"level": level, "code": code, "msg": msg, "hint": hint})

    def ok(self, code, msg):
        self.rows.append({"level": "通过", "code": code, "msg": msg, "hint": ""})

    def errors(self):
        return [r for r in self.rows if r["level"] == "错误"]

    def warns(self):
        return [r for r in self.rows if r["level"] == "警告"]

    def dump(self):
        icons = {"通过": "✓", "警告": "!", "错误": "✗"}
        for r in self.rows:
            line = f'[{icons.get(r["level"], " ")}] {r["code"]}：{r["msg"]}'
            if r["hint"]:
                line += f"\n      → {r['hint']}"
            print(line)
        e, w = len(self.errors()), len(self.warns())
        print(f"\n合计：通过 {len(self.rows) - e - w} · 警告 {w} · 错误 {e}")
        return 0 if e == 0 else 1


def check_structure(data, rep):
    for k in REQUIRED_META:
        if not data.get("meta", {}).get(k):
            rep.add("错误", "META", f"meta.{k} 缺失", "补全后再生成报告；target_coa_batch 决定哪个批次是重点批次")
    p = data.get("product", {})
    for k in REQUIRED_PRODUCT:
        if not p.get(k):
            rep.add("错误", "PRODUCT", f"product.{k} 缺失")
    if not p.get("indicator_aliases"):
        rep.add("错误", "ALIAS", "product.indicator_aliases 为空",
                "没有别名表，名称相似与否无法判定，会导致大量误判")
    keys = {}
    for e in p.get("indicator_aliases", []):
        for a in [e["canonical"]] + list(e.get("aliases", [])):
            k = a.strip()
            if k in keys and keys[k] != e["canonical"]:
                rep.add("错误", "ALIAS_DUP", f"别名「{k}」同时挂在 {keys[k]} 与 {e['canonical']} 下",
                        "同一别名只能对应一个指标，否则匹配会产生歧义")
            keys[k] = e["canonical"]
    if not data.get("specs") and not data.get("standards"):
        rep.add("错误", "SPEC", "既没有采购规格，也没有适用标准",
                "无规格时所有指标都会落“规格未约定”，核对失去意义")
    coas = data.get("coas", [])
    if not coas:
        rep.add("错误", "COA", "coas 为空")
    bns = [c.get("batch_no") for c in coas]
    if len(set(bns)) != len(bns):
        rep.add("错误", "BATCH", f"批号重复：{bns}")
    tgt = data.get("meta", {}).get("target_coa_batch")
    if tgt and tgt not in bns:
        rep.add("错误", "TARGET", f"target_coa_batch={tgt} 不在 coas 中（现有 {bns}）")
    for c in coas:
        for k in REQUIRED_COA:
            if k not in c:
                rep.add("错误", "COA_FIELD", f"COA {c.get('batch_no')} 缺 {k}")
        for it in c.get("items", []):
            for k in ("name", "name_key", "value", "unit"):
                if k not in it:
                    rep.add("错误", "ITEM", f"COA {c.get('batch_no')} 指标行缺字段 {k}：{it}")
        h = c.get("header", {})
        for k in ("mfg_date", "test_date"):
            if h.get(k):
                d, raw, note = L.parse_date(h[k])
                if d is None:
                    rep.add("警告", "DATE", f"COA {c.get('batch_no')} {k}={raw!r} 无法解析", note)
    if not rep.errors():
        rep.ok("STRUCT", f"结构完整：{len(coas)} 份 COA，{len(data.get('specs', []))} 份规格，"
                         f"{len(data.get('standards', []))} 份标准，别名 {len(keys)} 个")


def check_semantics(res, data, rep):
    illegal = 0
    n = 0
    for b, rows in res["results"].items():
        for r in rows:
            n += 1
            if r["status"] not in L.STATUS_SET:
                rep.add("错误", "STATUS", f"{b}/{r['name']} 判定词非法：{r['status']!r}",
                        f"判定只能是 {'/'.join(L.STATUS_SET)}")
                illegal += 1
                continue
            if not r["reason"]:
                rep.add("错误", "REASON", f"{b}/{r['name']} 缺少判定理由")
            if r["status"] == L.ST_FAIL:
                if r["deviation"].get("pct") is None and L.unit_token(r["coa_unit"])[0] != "定性":
                    rep.add("警告", "DEV", f"{b}/{r['name']} 不符合但没有偏离百分比",
                            "数值型不符合应给出偏离；定性不符合可在报告中说明")
            if r["status"] == L.ST_UNKNOWN:
                bad = [k for k, ok, _ in r["comparability"] if not ok]
                if not bad and not (r.get("notes") and any("检出限" in s or "结构" in s for s in r["notes"])):
                    rep.add("警告", "COMP", f"{b}/{r['name']} 落“无法判断”但可比性五维全通",
                            "通常是因为检出限/数值结构等原因，建议在 notes 中写明依据")
            if r["status"] in (L.ST_UNKNOWN, L.ST_UNSPEC) and not r["reason"]:
                rep.add("错误", "WHY", f"{b}/{r['name']} 落「{r['status']}」但没有说明原因")
            # 单位与限值可解析
            if r["spec_limit"] not in (None, ""):
                p = L.parse_value(r["spec_limit"], "limit")
                is_desc = L.unit_token(r["spec_unit"])[0] == "定性" or p["kind"] == "text"
                if p["kind"] == "text" and not is_desc:
                    rep.add("警告", "LIMIT", f"{b}/{r['name']} 限值「{r['spec_limit']}」只能定性判断",
                            "若非描述性指标，检查是否漏写了数值/符号")
    if not illegal:
        rep.ok("SEMANTIC", f"语义合规：{n} 条判定全部落在六种状态内，均有理由")


def check_compliance(res, rep, files=None):
    # 1) 异议清单与函件不得出现收货结论
    texts = [res.get("draft", "")] + list(res.get("drafts", {}).values())
    texts += [p["facts"] + p["ask"] for p in res["objections"]["points"]]
    hit = []
    for t in texts:
        for pat in FORBIDDEN_DECISION:
            for m in re.finditer(pat, t):
                s = max(0, m.start() - 12)
                ctx = t[s:m.end() + 12]
                if any(x in ctx for x in EXEMPT_CTX):
                    continue
                hit.append((pat, ctx))
    if hit:
        for pat, ctx in hit[:6]:
            rep.add("错误", "DECISION", f"出现收货决定类表述「{pat}」：…{ctx}…",
                    "报告只给事实与判断，收货决定由人共同决策")
    else:
        rep.ok("DECISION", "异议与函件草稿中未出现收货/退货结论表述")

    # 2) 模拟数据必须标记
    if data_sim := res["meta"].get("simulated"):
        if not res["meta"].get("sim_note"):
            rep.add("警告", "SIM", "simulated=true 但未写 sim_note")
        else:
            rep.ok("SIM", "模拟数据已标记，且带禁用说明")

    # 3) 成品文件不含未替换占位符 / 明显错误
    for f in files or []:
        if not os.path.exists(f):
            rep.add("错误", "FILE", f"文件不存在：{f}")
            continue
        if f.endswith((".html", ".htm")):
            raw = open(f, encoding="utf-8", errors="replace").read()
            # 只检查正文文本：内联 JS/CSS 里的 {} 是正常语法，不算占位符
            body = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)
            text_only = re.sub(r"(?s)<[^>]+>", " ", body)
            if re.search(r">\s*None\s*<", body):
                rep.add("错误", "HTML_NONE", f"{os.path.basename(f)} 出现 None 字样")
            if "NaN" in text_only or "undefined" in text_only:
                rep.add("错误", "HTML_NAN", f"{os.path.basename(f)} 出现 NaN/undefined")
            if re.search(r"\{\{[^}]{0,40}\}\}|\{[a-z_][a-z0-9_]{2,30}\}", text_only):
                rep.add("警告", "PLACEHOLDER", f"{os.path.basename(f)} 疑似残留模板占位符")
            if res["meta"].get("simulated") and "SIMULATED" not in text_only:
                rep.add("警告", "HTML_SIM", f"{os.path.basename(f)} 缺少模拟数据水印")
            # 判定词必须与 kpis 对上（防止渲染层漏行）
            k = res["kpis"]
            if k["total"] != len(res["results"][res["target_batch"]]):
                rep.add("错误", "COUNT", "kpis.total 与明细行数不一致")
            else:
                rep.ok("HTML", f"{os.path.basename(f)} 正文无 None/NaN/占位符，计数一致 "
                               f"({k['total']} 项)")


def check_coverage(res, rep):
    """覆盖率体检：告诉用户"这份报告能回答多大比例的问题"，而不是暗示全部可判。"""
    k = res["kpis"]
    if k["total"] == 0:
        rep.add("错误", "EMPTY", "没有任何可比对指标")
        return
    if k["verifiable_ratio"] < 50:
        rep.add("警告", "COVERAGE",
                f"可量化核验比例仅 {k['verifiable_ratio']:.0f}%（符合+不符合 ÷ 总数）",
                "说明规格方法/单位/检出限缺失过多，建议先补规格条款再核对")
    else:
        rep.ok("COVERAGE", f"可量化核验比例 {k['verifiable_ratio']:.0f}%，"
                           f"其余 {k['untested'] + k['unknown'] + k['unspec']} 项需补充条件或人工确认")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--render", nargs="*", default=None, help="同时校验成品文件（html/xlsx）")
    ap.add_argument("--strict", action="store_true", help="存在警告也返回非零")
    a = ap.parse_args()
    data = json.load(open(a.data, encoding="utf-8"))
    rep = Report()
    check_structure(data, rep)
    if rep.errors():
        print("结构未通过，后续语义检查已跳过：\n")
        return rep.dump()
    try:
        res = engine.run(data)
    except Exception as e:  # noqa: BLE001
        rep.add("错误", "ENGINE", f"引擎运行失败：{type(e).__name__}: {e}")
        return rep.dump()
    check_semantics(res, data, rep)
    check_compliance(res, rep, a.render)
    check_coverage(res, rep)
    rc = rep.dump()
    if a.strict and rep.warns():
        return 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
