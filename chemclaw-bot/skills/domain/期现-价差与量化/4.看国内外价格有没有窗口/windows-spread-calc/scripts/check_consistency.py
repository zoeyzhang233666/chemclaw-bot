# -*- coding: utf-8 -*-
"""Python 内核 vs 浏览器内核（assets/core.js）逐值比对。

为什么必须有这一步：
  报告里的 KPI、瀑布、曲线、敏感性都是浏览器用 core.js 现算的；Excel 与校验脚本
  用的是 core.py。若两侧公式有 1 行不同，用户就会看到"HTML 数字 ≠ Excel 数字"，
  而这类错误在真实业务里会直接变成报价错误。因此两侧必须逐值一致。

用法：
    python scripts/check_consistency.py [--n 400] [--seed 7]

机制：
  1. 生成 N 组随机参数（覆盖全部术语、CNY/USD 币种、0/正税率、部分抵扣、纯度≠1）；
  2. Python 用 core.import_cost / comparable_price / gap_table 算一遍；
  3. 用 node 跑同样的参数到 core.js，输出 JSON；
  4. 逐字段比对，容差 1e-6（与 core.js 的 r6 舍入一致）。
     任一侧为 None 时只要求两侧同为 None。
"""
import argparse
import json
import os
import random
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
import wio  # noqa: E402

TOL = 1e-6
TERMS = ["EXW", "FCA", "FOB", "CFR", "CIF", "DAP"]
COST_FIELDS = ["goods_cny", "inland_origin", "export_clear", "freight", "insurance", "cif",
               "discharge", "duty", "other_tax", "vat", "vat_credit", "inland_dest", "unload",
               "landed_cash", "cash_out", "net_cash", "unit_net", "taxable"]
COMP_FIELDS = ["dom_quote", "dom_freight_added", "dom_adj", "dom_price", "dom_net_price",
               "dom_vat_in", "cif", "cif_incl_vat", "gap_vs_landed_cash", "gap_vs_net_cash", "gap_vs_cif"]


def gen_cases(n, seed):
    rnd = random.Random(seed)
    cases = []
    for i in range(n):
        cur = "USD" if i % 4 else "CNY"
        fx = round(rnd.uniform(6.2, 7.5), 4) if cur == "USD" else 1.0
        cases.append({
            "price_quote": round(rnd.uniform(300, 1200), 2),
            "currency": cur,
            "term": TERMS[i % len(TERMS)],
            "fx_usdcny": fx,
            "purity": rnd.choice([1.0, 1.0, 0.995, 0.99]),
            "gross_weight_factor": rnd.choice([1.0, 1.0, 1.002]),
            "inland_origin": round(rnd.uniform(0, 30), 2),
            "export_clear": round(rnd.uniform(0, 12), 2),
            "ocean_freight": round(rnd.uniform(0, 130), 2),
            "insurance_rate": rnd.choice([1.0, 1.1, 1.2]),
            "insurance_rate_pct": round(rnd.uniform(0, 0.006), 6),
            "discharge_fee": round(rnd.uniform(0, 40), 2),
            "inland_dest": round(rnd.uniform(0, 200), 2),
            "unload_fee": round(rnd.uniform(0, 20), 2),
            "duty_rate": rnd.choice([0.0, 0.0, 0.02, 0.055, 0.10]),
            "other_tax_rate": rnd.choice([0.0, 0.0, 0.01]),
            "vat_rate": rnd.choice([0.13, 0.13, 0.09, 0.10]),
            "vat_credit_ratio": rnd.choice([1.0, 1.0, 0.8, 0.5, 0.0]),
            "dom_quote": round(rnd.uniform(2500, 9500), 2),
            "dom_tax": rnd.choice(["含税", "含税", "不含税"]),
            "dom_term_incl_freight": rnd.choice([True, True, False]),
            "dom_freight_to_bench": round(rnd.uniform(0, 80), 2),
            "dom_scale_adj": round(rnd.uniform(-40, 40), 2),
        })
    return cases


def py_side(cases):
    out = []
    for c in cases:
        p = dict(c)
        cost = core.import_cost(p)
        dcfg = {k: c[k] for k in ("dom_quote", "dom_tax", "dom_term_incl_freight",
                                  "dom_freight_to_bench", "dom_scale_adj")}
        dcfg["vat_rate"] = c["vat_rate"]
        comp = core.comparable_price(dcfg, cost)
        gaps = core.gap_table(c["dom_quote"], cost, comp)
        out.append({
            "cost": {k: cost.get(k) for k in COST_FIELDS},
            "comp": {k: comp.get(k) for k in COMP_FIELDS},
            "gaps": {g["code"]: g["value"] for g in gaps},
        })
    return out


NODE_SCRIPT = r"""
const path = require('path');
const core = require(process.argv[2]);
const cases = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
const out = cases.map(function(c){
  const cost = core.import_cost(c);
  const dcfg = {dom_quote:c.dom_quote, dom_tax:c.dom_tax, dom_term_incl_freight:c.dom_term_incl_freight,
                dom_freight_to_bench:c.dom_freight_to_bench, dom_scale_adj:c.dom_scale_adj, vat_rate:c.vat_rate};
  const comp = core.comparable_price(dcfg, cost);
  const gaps = {};
  core.gap_table(c.dom_quote, cost, comp).forEach(function(g){ gaps[g.code] = g.value; });
  const CF = %s, KF = %s;
  const o = {cost:{}, comp:{}, gaps:gaps};
  CF.forEach(function(k){ o.cost[k] = cost[k]; });
  KF.forEach(function(k){ o.comp[k] = comp[k]; });
  return o;
});
process.stdout.write(JSON.stringify(out));
"""


def js_side(cases, core_js, tmp_json, tmp_js):
    wio.dump_json(cases, tmp_json)
    src = NODE_SCRIPT % (json.dumps(COST_FIELDS), json.dumps(COMP_FIELDS))
    wio.write_text(tmp_js, src)
    node = os.environ.get("WSC_NODE") or "node"
    try:
        r = subprocess.run([node, tmp_js, core_js, tmp_json],
                           capture_output=True, text=True, encoding="utf-8", timeout=180)
    except FileNotFoundError:
        wio.die("未找到 node，可执行文件路径请用环境变量 WSC_NODE 指定")
    if r.returncode != 0:
        wio.die("node 执行失败：\n" + (r.stderr or "")[:2000])
    return json.loads(r.stdout)


def diff(a, b, path, out, tol):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            diff(a.get(k), b.get(k), path + "." + str(k), out, tol)
        return
    if a is None or b is None:
        if a is not b:
            out.append((path, a, b))
        return
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if abs(float(a) - float(b)) > tol:
            out.append((path, a, b))
        return
    if a != b:
        out.append((path, a, b))


def main():
    ap = argparse.ArgumentParser(description="Python 内核 vs JS 内核 比对")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20261020)
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    core_js = os.path.join(here, "assets", "core.js")
    if not os.path.exists(core_js):
        wio.die("缺少 %s" % core_js)

    tmp = os.path.join(here, "_tmp_consistency")
    os.makedirs(tmp, exist_ok=True)
    cases = gen_cases(args.n, args.seed)
    py = py_side(cases)
    js = js_side(cases, core_js, os.path.join(tmp, "cases.json"), os.path.join(tmp, "run.js"))

    problems = []
    for i, (a, b) in enumerate(zip(py, js)):
        diff(a, b, "case[%d](%s,%s)" % (i, cases[i]["term"], cases[i]["currency"]), problems, TOL)

    for f in ("cases.json", "run.js"):
        p = os.path.join(tmp, f)
        if os.path.exists(p):
            os.remove(p)
    try:
        os.rmdir(tmp)
    except OSError:
        pass

    print("=" * 64)
    print("check_consistency：%d 组随机参数 × %d 字段" % (len(cases), len(COST_FIELDS) + len(COMP_FIELDS) + 4))
    print("=" * 64)
    if problems:
        for p, a, b in problems[:40]:
            print("[FAIL] %s  py=%r  js=%r" % (p, a, b))
        print("不一致 %d 处（容差 %g）" % (len(problems), TOL))
        return 1
    print("[ OK  ] 全部一致（容差 %g）：Python core.py ≡ 浏览器 core.js" % TOL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
