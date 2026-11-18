#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一键编排：合并 → 同主体合并 → 链接抽检 → 出 Excel → 出 HTML。

用「同进程导入并调用各脚本 main()」而不是起子进程 —— 某些受限沙箱里
子进程的管道 stdio 会被拒绝（EPERM），同进程最稳。

用法:
    python run_all.py --config <product.json> [--dir <任务目录>] [--skip-qa]
"""
from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import radarlib as R  # noqa: E402


def banner(t):
    print("\n" + "=" * 74)
    print("  " + t)
    print("=" * 74)


def run(module_name, cfg_path, base):
    import importlib
    mod = importlib.import_module(module_name)
    argv_bak = sys.argv[:]
    sys.argv = [module_name, "--config", cfg_path, "--dir", base]
    t0 = time.time()
    try:
        mod.main()
        print("   ↳ %s 完成（%.1fs）" % (module_name, time.time() - t0))
        return True
    except SystemExit as e:
        if e.code:
            print("   ↳ %s 中止: %s" % (module_name, e.code))
            return False
        return True
    except Exception as e:
        print("   ↳ %s 失败: %s: %s" % (module_name, type(e).__name__, e))
        return False
    finally:
        sys.argv = argv_bak


def main():
    cfg, base, cfg_path = R.resolve_config()
    skip_qa = "--skip-qa" in sys.argv
    t = cfg["task"]
    print("化工品采购商机雷达 · 一键出表")
    print("产品: %s  区域: %s  窗口: %s ~ %s  基准日: %s"
          % (t["product_name"], t["region_name"], t["window_start"], t["window_end"], t["baseline_date"]))
    print("任务目录: %s" % base)

    steps = [("merge_leads", "套用六道闸门 + 去重"),
             ("consolidate", "同主体合并成一张卡"),
             ("qa_links", "链接抽检（网络较慢，可 --skip-qa 跳过）"),
             ("build_workbook", "产出 Excel"),
             ("build_html", "产出 HTML")]
    failed = []
    for name, desc in steps:
        if name == "qa_links" and skip_qa:
            print("\n[跳过] %s —— %s" % (name, desc))
            continue
        banner("%s —— %s" % (name, desc))
        if not run(name, cfg_path, base):
            failed.append(name)

    banner("完成")
    od = R.outdir(cfg, base)
    for f in sorted(os.listdir(od)):
        print("   %-46s %8.1f KB" % (f, os.path.getsize(os.path.join(od, f)) / 1024.0))
    if failed:
        print("\n!! 以下步骤失败，请检查: %s" % ", ".join(failed))
        sys.exit(1)
    print("\n产出目录: %s" % od)
    print("提醒：负结果 / 覆盖缺口 / 通道清单 / 置信度依据 这四块叙事内容要写进 "
          "<任务目录>/report_notes.json，再重跑 build_html.py。")


if __name__ == "__main__":
    main()