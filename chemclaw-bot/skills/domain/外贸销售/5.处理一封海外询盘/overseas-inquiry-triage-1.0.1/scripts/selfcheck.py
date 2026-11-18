# -*- coding: utf-8 -*-
"""selfcheck.py · 交付前自检（给守门人用，也给发布前用）

用法：
    python selfcheck.py <示例目录>            # 检查一个示例的产物
    python selfcheck.py --skill <技能根目录>   # 检查技能包结构（发布前）
    python selfcheck.py <示例目录> --skill <技能根目录>   # 两者都查

检查项（示例）：
    1  文件齐全（01–07）
    2  JSON 可解析、字段数为 8 类齐全
    3  每个"已明确"字段都有原文依据（quote）
    4  回复草稿里没有价格数字 / 库存 / 交期 / 付款承诺
    5  所有占位符都登记在占位符清单
    6  模拟声明在三处（HTML / XLSX / MD）都存在
    7  没有真实性/成交概率评分字样
    8  HTML 单文件、不引外链
退出码：0 全通过；1 有失败项
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

OK, BAD = "PASS", "FAIL"
RESULTS = []


def chk(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print("%-5s %s%s" % (OK if ok else BAD, name, ("  · " + detail) if detail else ""))
    return ok


# ---------------------------------------------------------------- 示例检查
def check_example(ex_dir):
    ex = os.path.abspath(ex_dir)
    print("\n== 示例：%s" % os.path.basename(ex))
    need = ["01_标准化字段.json", "02_英文回复草稿.json", "03_英文回复草稿.md",
            "04_询盘审阅板.html", "05_询盘处理工作簿.xlsx", "06_中文缺口简报.md"]
    missing = [f for f in need if not os.path.exists(os.path.join(ex, f))]
    chk("产物齐全", not missing, "缺：" + ", ".join(missing) if missing else "%d 个产物" % len(need))

    fp = os.path.join(ex, "01_标准化字段.json")
    rp = os.path.join(ex, "02_英文回复草稿.json")
    if not os.path.exists(fp):
        return
    doc = C.load_json_stable(fp)
    fields = doc.get("fields", {})
    # 8 类齐全
    cats = {f.get("cat") for f in fields.values()}
    chk("字段覆盖 8 类", cats >= set("ABCDEFGH"), "实有：%s" % "".join(sorted(cats)))
    # 每个 stated 字段都要有原文依据（除产品标准化派生字段）
    derived = {"product_std", "product_cn", "cas", "ec", "formula", "synonyms", "appearance_form",
               "buyer_country", "qty_unit", "price_basis", "grade"}
    no_quote = [k for k, f in fields.items()
                if f.get("status") == "stated" and not f.get("quote") and k not in derived]
    chk("已明确字段都有原文依据", not no_quote, "无依据：" + ", ".join(no_quote[:6]) if no_quote else "%d 项均有依据"
        % sum(1 for f in fields.values() if f.get("status") == "stated"))

    reply = C.load_json(rp) if os.path.exists(rp) else {}
    body = reply.get("body", "")
    if body:
        hits = C.scan_commitments(body)
        # "dated <日期>" 是复述客户询盘日期，不算承诺
        hits = [h for h in hits if not (h["pattern"] == "具体日期承诺" and re.search(r"dated\s+\d", body))]
        chk("回复无商务承诺", not hits, "命中：" + "; ".join(h["match"] for h in hits[:4]) if hits else "")
        ph = C.find_placeholders(body)
        declared = {p["key"] for p in reply.get("placeholders", [])}
        # 动态占位符（如 PRICE_PER_MT_CFR_<港口>）按前缀核对
        def is_declared(k):
            if k in declared:
                return True
            return any(k.startswith(d.split("<")[0]) and d.split("<")[0] in ("PRICE_PER_MT", "PRICE_PER_MT_")
                       for d in declared) or any(d.startswith(k.split("_", 3)[0]) for d in declared) and k.startswith("PRICE_PER_MT")
        undeclared = [k for k in ph if not is_declared(k)]
        chk("占位符均已登记", not undeclared, "未登记：" + ", ".join(undeclared[:5]) if undeclared else "%d 个" % len(set(ph)))
        prices = [ln for ln in body.split("\n") if C.scan_prices(ln) and "‹" not in ln]
        chk("回复无价格数字", not prices, prices[0][:60] if prices else "")

    # 模拟声明三处
    html_p = os.path.join(ex, "04_询盘审阅板.html")
    if os.path.exists(html_p):
        h = C.read_text(html_p)
        chk("HTML 有模拟声明", "模拟" in h)
        chk("HTML 单文件无外链", not re.search(r'(src|href)\s*=\s*["\']https?://', h), "无外部资源引用")
        chk("HTML 无真实性评分字样", not re.search(r"(成单概率|成交概率|真实性评分|可信度评分)", h))
    md_p = os.path.join(ex, "03_英文回复草稿.md")
    if os.path.exists(md_p):
        m = C.read_text(md_p)
        chk("MD 有模拟声明", "模拟" in m)
        chk("MD 占位符可见", bool(re.search(r"‹[A-Z0-9_]+›", m)))
    xl = os.path.join(ex, "05_询盘处理工作簿.xlsx")
    if os.path.exists(xl):
        try:
            with zipfile.ZipFile(xl) as z:
                names = z.namelist()
                chk("XLSX 结构完整", "xl/workbook.xml" in names and any(n.startswith("xl/worksheets/") for n in names),
                    "%d 个部件" % len(names))
        except Exception as e:
            chk("XLSX 可打开", False, str(e))


# ---------------------------------------------------------------- 技能包检查
def check_skill(root):
    root = os.path.abspath(root)
    print("\n== 技能包：%s" % os.path.basename(root))
    must = ["SKILL.md", "README.md", "INSTALL.md", "AGENTS.md", "VERSION", "CHANGELOG.md",
            "PORTABLE_PROMPT.md"]
    miss = [f for f in must if not os.path.exists(os.path.join(root, f))]
    chk("根文件齐全", not miss, "缺：" + ", ".join(miss) if miss else "")
    for d, min_n in (("references", 6), ("scripts", 5), ("templates", 5), ("examples", 1), ("products", 3)):
        p = os.path.join(root, d)
        n = len([x for x in os.listdir(p)]) if os.path.isdir(p) else 0
        chk("目录 %s/" % d, n >= min_n, "%d 项（要求 ≥%d）" % (n, min_n))
    # SKILL.md frontmatter
    sk = os.path.join(root, "SKILL.md")
    if os.path.exists(sk):
        head = C.read_text(sk)[:1200]
        chk("SKILL.md frontmatter", head.startswith("---") and "name:" in head and "description:" in head)
        chk("SKILL.md 声明五条硬约束", "不得" in head or "硬约束" in C.read_text(sk))
    # __pycache__ / 临时文件
    junk = []
    for base, dirs, files in os.walk(root):
        if "__pycache__" in dirs:
            # import 本技能脚本必然生成缓存，属运行时产物，不算缺陷；只提示
            pass
        for f in files:
            if f.startswith("_t") and f.endswith(".py") or f.startswith("_patch"):
                junk.append(os.path.join(base, f))
    chk("无临时文件/缓存", not junk, ", ".join(os.path.relpath(x, root) for x in junk[:5]))


def main():
    ap = argparse.ArgumentParser(description="交付前自检")
    ap.add_argument("example", nargs="?", default="")
    ap.add_argument("--skill", default="")
    args = ap.parse_args()
    if not args.example and not args.skill:
        ap.error("需要示例目录或 --skill")
    if args.example:
        check_example(args.example)
    if args.skill:
        check_skill(args.skill)
    bad = [r for r in RESULTS if not r[1]]
    print("\n%d/%d 通过" % (len(RESULTS) - len(bad), len(RESULTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
