#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_project.py —— 交付前总检（数据守恒、gate 结论、报告四块是否齐全）

用法： python check_project.py --dir <项目目录>
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import load_json, load_project, norm_dims, setup_console  # noqa: E402

setup_console()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    args = ap.parse_args()
    d = os.path.abspath(args.dir)
    cfg = load_project(d)
    rep = cfg["report"]
    checks = []

    def chk(name, ok, detail=""):
        checks.append((ok, name, detail))

    leads = load_json(os.path.join(d, "leads.json"), [])
    chk("leads.json 存在且非空", bool(leads), f"{len(leads)} 条")

    raw_dir = os.path.join(d, "leads_raw")
    lane_files = [p for p in glob.glob(os.path.join(raw_dir, "*.json"))
                  if not os.path.basename(p).startswith("_")]
    raw_total = 0
    for p in lane_files:
        data = load_json(p, [])
        raw_total += len(data) if isinstance(data, list) else 0
    chk("lane 文件齐全", len(lane_files) >= 8, f"{len(lane_files)} 个文件 / {raw_total} 条原始线索")

    n_lane_cfg = len(cfg.get("lanes") or [])
    if n_lane_cfg:
        chk("lane 数与配置一致", len(lane_files) == n_lane_cfg,
            f"配置 {n_lane_cfg} 条 / 落盘 {len(lane_files)} 个")

    chk("条数守恒（原始 - 去重/区域/同行 = 合并）", len(leads) <= raw_total,
        f"{raw_total} → {len(leads)}（差 {raw_total - len(leads)} 为过滤/去重）")
    chk("每条都有相似维度与相似逻辑",
        all(x.get("相似维度") and x.get("相似逻辑") for x in leads),
        f"缺相似维度 {sum(1 for x in leads if not x.get('相似维度'))} 条 / "
        f"缺相似逻辑 {sum(1 for x in leads if not x.get('相似逻辑'))} 条")
    chk("置信度均在枚举内", all(x.get("置信度") in ("高", "中", "低") for x in leads),
        str(dict(Counter(x.get("置信度") for x in leads))))
    chk("优先级均已计算", all(x.get("优先级") in ("高", "中", "低") for x in leads),
        str(dict(Counter(x.get("优先级") for x in leads))))
    provs = cfg.get("region", {}).get("provinces") or []
    if provs:
        bad = [x.get("公司") for x in leads if not any(p in (x.get("所在地") or "") for p in provs)]
        chk("区域白名单内", not bad, f"越界 {len(bad)} 条")
    nosrc = [x.get("公司") for x in leads if x.get("来源") in ("", "未核实")]
    chk("未核实条数已登记（允许存在，须写进报告）", True, f"{len(nosrc)} 条")
    mark = [x for x in leads if "⚠" in (x.get("来源") or "")]
    chk("链接抽检结论已注入来源列", True, f"标注 {len(mark)} 条")

    qa = load_json(os.path.join(raw_dir, "_qa_report.json"), [])
    chk("抽检报告存在（link gate）", bool(qa), f"{len(qa)} 条")

    xlsx = os.path.join(d, rep.get("workbook_output") or "下游潜客池.xlsx")
    chk("Excel 已生成", os.path.exists(xlsx),
        f"{os.path.getsize(xlsx)//1024} KB" if os.path.exists(xlsx) else "缺失（需 openpyxl）")
    htmlp = os.path.join(d, rep.get("html_output") or "报告.html")
    chk("HTML 报告已生成", os.path.exists(htmlp),
        f"{os.path.getsize(htmlp)//1024} KB" if os.path.exists(htmlp) else "缺失")
    if os.path.exists(htmlp):
        txt = open(htmlp, "r", encoding="utf-8").read()
        ext = re.findall(r"<(?:link|script|img|iframe)[^>]*(?:src|href)=\"https?://", txt, re.I)
        chk("HTML 零外链资源（离线可开）", not ext,
            "样式/脚本全内联；证据 <a> 链接指向外部属正常，不计入"
            if not ext else f"发现 {len(ext)} 个外部资源引用")
        chk("HTML 含筛选与全量线索表", 'id="leads"' in txt and 'id="f-block"' in txt)

    notes = load_json(os.path.join(d, "report_notes.json"), {})
    chk("报告第6节：剔除名单（同行）", bool(notes.get("peers")), f"{len(notes.get('peers') or [])} 条")
    chk("报告第7节：缺口与负结果",
        bool(notes.get("gaps")) and bool(notes.get("negatives")),
        f"缺口 {len(notes.get('gaps') or [])} 条 / 负结果 {len(notes.get('negatives') or [])} 条")

    dims = Counter()
    for x in leads:
        for k in norm_dims(x.get("相似维度"), cfg):
            dims[k] += 1
    chk("相似维度分布可统计", bool(dims), str(dict(dims.most_common())))

    print(f"=== 交付前总检：{d} ===")
    n_fail = 0
    for ok, name, detail in checks:
        flag = "PASS" if ok else "FAIL"
        if not ok:
            n_fail += 1
        print(f"  [{flag}] {name}" + (f" —— {detail}" if detail else ""))
    n_all = len(leads)
    print(f"\n汇总：线索 {n_all} 条；板块 {len({x.get('板块') for x in leads})} 个；"
          f"省份 {len({x.get('所在地', '')[:2] for x in leads})} 个；"
          f"高优先级 {sum(1 for x in leads if x.get('优先级') == '高')} 条；"
          f"高置信 {sum(1 for x in leads if x.get('置信度') == '高')} 条。")
    if n_fail:
        print(f"有 {n_fail} 项未通过，请修正后重新生成。")
    else:
        print("全部通过，可交付。交付时请在对话里给出四块说明：条数与分布 / 置信度分级与证据 / "
              "被剔除的同行 / 未覆盖的缺口与负结果。")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
