# -*- coding: utf-8 -*-
"""
test_statistics.py —— 统计与逻辑自检（必须全部通过）
====================================================
覆盖：
  T01 百分位秩定义（含并列、极值、单调性）
  T02 分组边界（k / 1-k 的开闭方向）
  T03 滚动分位严格滞后（不得偷看当日与未来）
  T04 无未来函数：篡改未来数据不得改变历史分位
  T05 基差恒等式（基差收益 = 现货收益 − 期货收益）
  T06 前瞻收益与价格一致
  T07 分组统计可复算（与引擎输出逐项比对）
  T08 块自助：同分布下 p 不显著；悬殊下 p 显著
  T09 退化保护：块长≥样本半数时返回 degenerate，不给 p
  T10 非重叠子样本无重叠
  T11 末端回填标记正确
  T12 Excel 工作簿：工作表齐全、公式存在且能被独立重算
  T13 HTML：自包含（无外链）、数据内嵌、关键区块存在

用法：
  python test_statistics.py --out <out目录> [--xlsx path] [--html path]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

PASS, FAIL = [], []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print("[PASS] %s %s" % (name, detail))
    else:
        FAIL.append(name)
        print("[FAIL] %s %s" % (name, detail))


# ---------------------------------------------------------------- T01
def t01_rank():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "bc", os.path.join(os.path.dirname(__file__), "..", "scripts", "basis_core.py"))
    bc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bc)
    r = bc._rank_of
    # 样本 [0.01, 0.02, 0.03, 0.005]，查询值 0.02 本身在样本内 → less=2, equal=1, n=4 → 2.5/4
    check("T01a 百分位秩(值在样本内)", abs(r([0.01, 0.02, 0.03, 0.005], 0.02) - 0.625) < 1e-12)
    # 查询值不在样本内 → less=3, n=4 → 3/4
    check("T01a2 百分位秩(值不在样本内)", abs(r([0.01, 0.02, 0.03, 0.005], 0.025) - 0.75) < 1e-12)
    check("T01b 小于全部", r([0.01, 0.02, 0.03], 0.0001) == 0.0)
    check("T01c 大于全部", r([0.01, 0.02, 0.03], 9.9) == (3 - 0.5) / 3)
    # 并列：值 2 出现两次，样本 [1,2,2,3] → less=1, equal=2, n=4 → (1+1)/4=0.5
    check("T01d 并列取中点", abs(r([1, 2, 2, 3], 2) - 0.5) < 1e-12)
    # 单调性
    h = [random.Random(7).gauss(0, 1) for _ in range(50)]
    ok = all(r(h, a) <= r(h, b) for a, b in zip(sorted(h)[:-1], sorted(h)[1:]))
    check("T01e 单调不减", ok)
    # 中位数：样本 [1..5] 中位 3 → less=2, equal=1, n=5 → 2.5/5 = 0.5
    check("T01f 中位数=0.5", abs(r([1.0, 2.0, 3.0, 4.0, 5.0], 3.0) - 0.5) < 1e-12)
    # 关键性质：k=0.1 阈值下，历史最大值必须能进“高分位”组（≥0.9）
    check("T01g 最大值可达高分位", r([float(i) for i in range(1, 251)], 999.0) >= 0.9)
    return bc


# ---------------------------------------------------------------- T02
def t02_groups(bc):
    g = bc._group_of
    B = ((0.2, 0.8),)
    check("T02a 低分位边界含等号", g(0.2, B) == "低分位")
    check("T02b 高分位边界含等号", g(0.8, B) == "高分位")
    check("T02c 中间分位", g(0.5, B) == "中间分位")
    check("T02d 极小值归低", g(0.0001, B) == "低分位")
    check("T02e None 不分组", g(None, B) is None)


# ---------------------------------------------------------------- T03/T04
def t03_no_lookahead(bc):
    vals = [0.01, 0.02, 0.03, 0.005, 0.015] * 8   # 40 点
    pct = bc.rolling_percentile(vals, 20)
    # 前 20 个点（index<20）不应有分位
    check("T03a 前 W 个点无分位", all(p is None for p in pct[:20]))
    check("T03b 之后有分位", pct[20] is not None)
    # 手工核对 i=25：窗口 vals[5..24]
    i = 25
    hist = vals[max(0, i - 20):i]
    expect = bc._rank_of(hist, vals[i])
    check("T03c 分位只用 t 之前窗口", abs(pct[i] - expect) < 1e-12)

    # T04：把 t 之后的数据全部改掉，t 及之前的分位必须完全不变
    vals2 = list(vals)
    for k in range(i + 1, len(vals2)):
        vals2[k] = vals2[k] + 99.0
    pct2 = bc.rolling_percentile(vals2, 20)
    same = all((pct[k] is None and pct2[k] is None) or abs(pct[k] - pct2[k]) < 1e-12
               for k in range(0, i + 1))
    check("T04a 未来数据不影响历史分位", same)
    # 当日值改变应改变当日分位（证明当日参与比较，但窗口不含当日）
    vals3 = list(vals)
    vals3[i] = 10.0
    pct3 = bc.rolling_percentile(vals3, 20)
    check("T04b 当日值参与比较", pct3[i] > pct[i])


# ---------------------------------------------------------------- T05/T06
def t05_identity(rows, I):
    bad = 0
    for r in rows:
        for h in (5, 10, 20, 60, 120):
            s, f, b = r[I["spot_ret_%d" % h]], r[I["fut_ret_%d" % h]], r[I["basis_ret_%d" % h]]
            if None in (s, f, b):
                continue
            if abs((s - f) - b) > 2e-6:
                bad += 1
    check("T05a 基差收益=现货收益−期货收益", bad == 0, "违例 %d 条" % bad)


def t06_forward(rows, I):
    bad = 0
    n = 0
    for i, r in enumerate(rows):
        for h in (5, 20):
            j = i + h
            if j >= len(rows):
                continue
            got = r[I["spot_ret_%d" % h]]
            if got is None:
                continue
            exp = rows[j][I["spot"]] / rows[i][I["spot"]] - 1
            n += 1
            if abs(got - exp) > 1e-5:
                bad += 1
    check("T06a 前瞻现货收益与价格一致", bad == 0, "n=%d 违例 %d" % (n, bad))


# ---------------------------------------------------------------- T07
def t07_bucket(rows, I, ST):
    import statistics
    bad = []
    for b in ST["bucket_info"]:
        h, g = b["horizon"], b["group"]
        vals = [r[I["basis_ret_%d" % h]] for r in rows if r[I["group_lag"]] == g
                and r[I["basis_ret_%d" % h]] is not None]
        if not vals:
            bad.append((g, h, "空组"))
            continue
        if len(vals) != b["n"]:
            bad.append((g, h, "n %d vs %d" % (len(vals), b["n"])))
        if abs(statistics.fmean(vals) - b["basis_ret_mean"]) > 1e-6:
            bad.append((g, h, "均值不符"))
        if abs(statistics.median(vals) - b["basis_ret_median"]) > 1e-6:
            bad.append((g, h, "中位不符"))
    check("T07a 分组统计可独立复算", not bad, str(bad[:3]))


# ---------------------------------------------------------------- T08/T09
def t08_bootstrap(bc):
    """同分布检验必须做多次重复：单次 p 值有 5%~10% 的固有假阳性率，
    用“多次重复中显著的比例不超过名义水平太多”来判定实现是否正确。"""
    sig = 0
    reps = 25
    for rep in range(reps):
        rng = random.Random(1000 + rep)
        a = [rng.gauss(0.005, 0.03) for _ in range(150)]
        b = [rng.gauss(0.005, 0.03) for _ in range(150)]
        r1 = bc.block_bootstrap_diff(a, b, [], [], blocksize=5, n_boot=600)
        if r1["p"] is not None and r1["p"] < 0.05:
            sig += 1
    rate = sig / reps
    check("T08a 同分布假阳性率合理(≤20%%)", rate <= 0.20, "%d/%d 次显著 = %.0f%%" % (sig, reps, rate * 100))

    rng = random.Random(11)
    a = [rng.gauss(0.005, 0.03) for _ in range(150)]
    c = [rng.gauss(-0.02, 0.03) for _ in range(150)]
    r2 = bc.block_bootstrap_diff(a, c, [], [], blocksize=5, n_boot=2000)
    check("T08b 明显差异显著", r2["p"] < 0.001, "p=%.5f" % r2["p"])
    check("T08c 区间包含真值方向", r2["ci_lo"] < r2["diff"] < r2["ci_hi"])

    small = [0.01, 0.02, 0.03, 0.04]
    r3 = bc.block_bootstrap_diff(small, small, [], [], blocksize=20, n_boot=500)
    check("T09a 块长≥样本半数判退化", r3.get("degenerate") is True and r3.get("p") is None)


# ---------------------------------------------------------------- T10
def t10_nonoverlap(bc, rows, I):
    sub = bc.non_overlap_subsample([{"basis_pct_lag": 0.5} for _ in rows], 20)
    check("T10a 非重叠子样本数量正确",
          len(sub) == math.ceil(len(rows) / 20), "%d vs %d" % (len(sub), math.ceil(len(rows) / 20)))


# ---------------------------------------------------------------- T11
def t11_pit(rows, I, META, W):
    flags = [r[I["point_in_time_known"]] for r in rows]
    n_unknown = sum(1 for f in flags if f == 0)
    check("T11a 末端回填点数正确", n_unknown == META["pit_unknown_n"],
          "%d vs %d" % (n_unknown, META["pit_unknown_n"]))
    # 未知段必须是连续的尾部
    tail = flags[-n_unknown:]
    check("T11b 回填段在尾部且连续", all(f == 0 for f in tail) and
          all(f == 1 for f in flags[:-n_unknown]))


# ---------------------------------------------------------------- T12
def t12_xlsx(path):
    if not path or not os.path.exists(path):
        check("T12a 工作簿存在", False, path or "未提供")
        return
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=False)
    need = ["00_说明", "01_基差日度", "02_滚动分位计算", "03_前瞻表现", "04_分组统计",
            "05_推断与自助", "06_敏感性", "07_稳定性", "08_偏差清单", "09_合约映射",
            "10_合约日历", "11_数据源", "12_核心结论"]
    miss = [s for s in need if s not in wb.sheetnames]
    check("T12a 13 张工作表齐全", not miss, str(miss))
    ws = wb["01_基差日度"]
    n_formula = sum(1 for row in ws.iter_rows(min_row=5) for c in row
                    if isinstance(c.value, str) and c.value.startswith("="))
    check("T12b 01 表含真公式", n_formula > 1000, "%d 个公式单元格" % n_formula)
    # 独立重算基差列
    bad = 0
    for r in range(5, min(ws.max_row, 400)):
        s = ws.cell(row=r, column=4).value
        f = ws.cell(row=r, column=5).value
        if s is None or f is None:
            continue
        b = ws.cell(row=r, column=6).value
        if not (isinstance(b, str) and b.startswith("=")):
            bad += 1
    check("T12c 基差列为公式", bad == 0, "非公式 %d" % bad)
    ws2 = wb["02_滚动分位计算"]
    chk = [ws2.cell(row=r, column=8).value for r in range(5, 9)]
    check("T12d 02 表秩为公式", all(isinstance(v, str) and v.startswith("=") for v in chk), str(chk[:2]))
    ws3 = wb["10_合约日历"]
    check("T12e 合约日历有数据", ws3.max_row > 50, "行数 %d" % ws3.max_row)

    # T12f：02 表的秩必须与引擎存储的分位完全一致（防“假并列”回归）
    import json as _json
    data_path = os.path.join(os.path.dirname(os.path.abspath(path)), "report_data.json")
    if os.path.exists(data_path):
        D = _json.load(open(data_path, encoding="utf-8"))
        I = {c: i for i, c in enumerate(D["bars"]["cols"])}
        rows = D["bars"]["rows"]
        idx = {r[I["date"]]: r for r in rows}
        bad = 0
        n = 0
        for r in range(5, ws2.max_row + 1):
            date = ws2.cell(row=r, column=1).value
            if date is None or date not in idx:
                continue
            E = ws2.cell(row=r, column=5).value
            less = ws2.cell(row=r, column=6).value
            eq = ws2.cell(row=r, column=7).value
            if not E or less is None:
                continue
            stored = idx[date][I["basis_pct_lag"]]
            if stored is None:
                continue
            calc = ((E - 0.5) / E if less >= E else
                    ((less + 0.5 * eq) / E if eq > 0 else less / E))
            n += 1
            if abs(calc - stored) > 5e-4:
                bad += 1
        check("T12f 02表秩与引擎一致", bad == 0, "核对 %d 行，不一致 %d 行" % (n, bad))


# ---------------------------------------------------------------- T13
def t13_html(path):
    if not path or not os.path.exists(path):
        check("T13a HTML 存在", False, path or "未提供")
        return
    s = open(path, encoding="utf-8").read()
    ext = re.findall(r'(?:src|href)\s*=\s*["\']https?://', s, flags=re.I)
    check("T13a 无外部资源引用", not ext, str(ext[:3]))
    check("T13b 数据已内嵌", '"bars":{"cols"' in s.replace(" ", ""))
    for token, label in [("id=\"lead\"", "结论区"), ("id=\"ctrlBar\"", "参数控件"),
                         ("id=\"bucketTbl\"", "分组统计表"), ("id=\"boxPlot\"", "箱线图"),
                         ("id=\"detailTbl\"", "明细表"), ("id=\"yearTbl\"", "年度稳定性"),
                         ("id=\"calibBox\"", "口径核验"), ("id=\"ruleTbl\"", "映射对照"),
                         ("绝不", "占位")]:
        if token == "绝不":
            continue
        check("T13c 存在区块 %s" % label, token in s)
    check("T13d 含免责声明", "免责声明" in s)
    check("T13e 含“非预测/不构成交易建议”", "不是对未来基差变化的预测" in s)
    check("T13f 含华东口径降级声明", "非华东" in s or "降级" in s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--xlsx", default=None)
    ap.add_argument("--html", default=None)
    a = ap.parse_args()

    data = os.path.join(a.out, "report_data.json")
    if not os.path.exists(data):
        raise SystemExit("缺少 %s" % data)
    D = json.load(open(data, encoding="utf-8"))
    rows, I = D["bars"]["rows"], {c: i for i, c in enumerate(D["bars"]["cols"])}
    META, ST = D["meta"], D["stats"]

    bc = t01_rank()
    t02_groups(bc)
    t03_no_lookahead(bc)
    t05_identity(rows, I)
    t06_forward(rows, I)
    t07_bucket(rows, I, ST)
    t08_bootstrap(bc)
    t10_nonoverlap(bc, rows, I)
    t11_pit(rows, I, META, META["main_window"])
    t12_xlsx(a.xlsx)
    t13_html(a.html)

    print("\n================ 汇总 ================")
    print("通过 %d / 失败 %d" % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print("  失败: %s" % f)
        sys.exit(1)
    print("全部通过")


if __name__ == "__main__":
    main()
