# -*- coding: utf-8 -*-
"""本 skill 的自检脚本：校验运行时依赖、核心模块与示例产物。

用法（在本 skill 根目录）：
    python scripts/verify.py            # 快速自检
    python scripts/verify.py --full     # 额外核对演示票应检出的差异数量
"""
import glob
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

OK = "[ OK ]"
FAIL = "[FAIL]"
WARN = "[WARN]"
_fail = 0


def check(name, cond, detail=""):
    global _fail
    if cond:
        print("%s %s%s" % (OK, name, (" — " + detail) if detail else ""))
    else:
        print("%s %s%s" % (FAIL, name, (" — " + detail) if detail else ""))
        _fail += 1


def main():
    full = "--full" in sys.argv

    # 1) 依赖
    try:
        import pymupdf
        check("PyMuPDF 可用", True, "版本 %s" % getattr(pymupdf, "__version__", "?"))
    except Exception as exc:
        try:
            import fitz  # 旧版入口
            check("PyMuPDF 可用", True, "旧版 fitz 入口")
        except Exception:
            check("PyMuPDF 可用", False, str(exc))
    try:
        import openpyxl
        check("openpyxl 可用", True, "版本 %s" % openpyxl.__version__)
    except Exception as exc:
        check("openpyxl 可用", False, str(exc))

    # 2) 核心模块
    for mod in ("taxonomy", "extract", "compare", "run_check", "make_html", "make_xlsx"):
        try:
            __import__(mod)
            check("模块 %s 可导入" % mod, True)
        except Exception as exc:
            check("模块 %s 可导入" % mod, False, "%s: %s" % (type(exc).__name__, exc))

    # 3) 词汇表完整性
    try:
        import taxonomy
        n_types = len(taxonomy.DOC_TYPES)
        n_fields = len(taxonomy.FIELDS)
        check("单证类型 ≥ 10 种", n_types >= 10, "%d 种" % n_types)
        check("字段词典 ≥ 30 个", n_fields >= 30, "%d 个" % n_fields)
        ids = [f["id"] for f in taxonomy.FIELDS]
        check("字段 id 无重复", len(ids) == len(set(ids)))
        missing_fmt = [f["id"] for f in taxonomy.FIELDS if not f.get("fmt")]
        check("每个字段都有格式约束", not missing_fmt, ",".join(missing_fmt))
    except Exception as exc:
        check("词汇表可读取", False, str(exc))

    # 4) 示例文件
    docs = sorted(glob.glob(os.path.join(ROOT, "examples", "demo_docs", "*.pdf")))
    check("示例单证 PDF ≥ 10 份", len(docs) >= 10, "%d 份" % len(docs))
    for name in ("check_page.html", "出口单证检查结果.xlsx"):
        p = os.path.join(ROOT, "examples", name)
        check("示例产物 %s 存在" % name, os.path.exists(p),
              ("%.1f KB" % (os.path.getsize(p) / 1024.0)) if os.path.exists(p) else "缺失")

    # 5) 模板
    for t in ("SKILL_输出模板_检查报告.md", "问题清单模板.csv"):
        p = os.path.join(ROOT, "templates", t)
        check("模板 %s 存在" % t, os.path.exists(p))

    # 6) 全量自检：对演示票跑一遍并比对预期
    if full and docs:
        try:
            import run_check
            res = run_check.run([os.path.join(ROOT, "examples", "demo_docs")])
            s = res["summary"]
            live = [d for d in res["docs"] if not d.get("excluded")]
            print("\n--- 演示票检查结果 ---")
            print("单证 %d 份（另有参考文件 %d 份被排除）" % (
                len(live), len(res["docs"]) - len(live)))
            print("差异 %d ｜ 缺失 %d ｜ 计算不符 %d ｜ 问题 %d（S1=%d）" % (
                s["cells"]["DIFF"], s["cells"]["MISS"], s["cells"]["CALC"],
                s["issues"], s["severity"].get("S1", 0)))
            check("识别出的单证类型正确（10 份本票单证）", len(live) == 10, "%d 份" % len(live))
            check("参考文件被正确排除", len(res["docs"]) - len(live) == 2)
            check("检出的差异数在合理区间（≥12）", s["cells"]["DIFF"] >= 12,
                  "%d" % s["cells"]["DIFF"])
            check("存在计算不符项", s["cells"]["CALC"] >= 3, "%d" % s["cells"]["CALC"])
            check("存在 S1 阻断级问题", s["severity"].get("S1", 0) >= 5,
                  "%d" % s["severity"].get("S1", 0))
        except Exception as exc:
            check("演示票可完整运行", False, "%s: %s" % (type(exc).__name__, exc))

    print("\n%s" % ("全部通过" if _fail == 0 else "有 %d 项未通过" % _fail))
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
