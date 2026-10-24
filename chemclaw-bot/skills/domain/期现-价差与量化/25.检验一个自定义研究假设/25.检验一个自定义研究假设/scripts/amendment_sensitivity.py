# -*- coding: utf-8 -*-
"""amendment_sensitivity.py — 预登记修订（v2.2）：两种额外口径的敏感性分析。

背景（必须诚实说明）：正式检验在 v2.2 的**主口径**下结论为「样本不足」（信号 10 个）。
这里做出两个**事前就能想到、写进修订记录**的补充口径，用来判断"样本不足"是否只是口径选择造成的：

  AM-1  weekly 去重：同一段连降里的每一周都算一个观测（不再只取状态转变周）。
        代价：相邻观测的 10 日窗口高度重叠，独立信息量远低于名义 N。
  AM-2  允许窗口内含一次近月换月（只做标记）。
        代价：期货/基差变化里混入合约切换跳变（100ppi 近月列逐月切换）。

这两个口径的结论如果与主口径一致（都不支持"走强"），那"样本不足"就不是口径问题；
如果它们显著为正，也不能因此宣布假设成立——只能记为"待更多独立样本验证"。
输出 build/amendment.json，供页面与 Excel 引用。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import study_engine as E  # noqa: E402
import hypothesis_stats as S  # noqa: E402

DESIGN = "build/research_design.formal.json"
OUT = "build/amendment.json"


def run_variant(name, overrides, note, status="REAL"):
    d = E.load_design(DESIGN)
    d.update(overrides)
    res, rows = E.run_study(d, "data/port_inventory_weekly.csv", "data/100ppi_sf.csv",
                            "data/futures/MA0_60min.csv", status=status, demo_note=note)
    return res, rows


def main():
    out = {"generated_at": None, "variants": []}
    from datetime import datetime
    out["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    specs = [
        ("MAIN", {}, "主口径（v2.2）：状态转变去重 + 剔除窗口内换月"),
        ("AM-1", {"dedup": "weekly"}, "修订 AM-1：weekly 去重（每周都算一个观测）"),
        ("AM-2", {"exclude_roll": False}, "修订 AM-2：允许窗口内含近月换月（仅标记）"),
        ("AM-3", {"dedup": "weekly", "exclude_roll": False}, "修订 AM-3：weekly + 允许换月"),
    ]
    for tag, ov, note in specs:
        res, rows = run_variant(tag, ov, note)
        rec = {"tag": tag, "note": note, "verdict": res["verdict"],
               "n_signal": res["sample"]["n_signal"], "n_control": res["sample"]["n_control"],
               "evaluable": res["meta"]["evaluable_states"],
               "skipped": res["meta"]["skipped"],
               "tests": res["tests"],
               "stability": res.get("stability", {}),
               "diagnostics": res.get("diagnostics", {}),
               "message": res.get("message", "")}
        out["variants"].append(rec)
        print(tag, res["verdict"], rec["n_signal"], "/", rec["n_control"], "tests", len(res["tests"]))
    json.dump(out, open(OUT, "w", encoding="utf-8-sig"), ensure_ascii=False, indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
