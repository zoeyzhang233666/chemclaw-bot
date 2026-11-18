# -*- coding: utf-8 -*-
"""检查出口单证 —— 主入口。

用法：
    python scripts/check_docs.py <单证目录或若干PDF>
    python scripts/check_docs.py ./本票单证 --out ./结果
    python scripts/check_docs.py ./本票单证 --out ./结果 --no-filename-hint

产出（--out 目录下）：
    check_result.json     结构化检查结果（机器可读，供二次处理）
    check_page.html       交互式检查页（单文件，双击打开）
    出口单证检查结果.xlsx   6 页核对工作簿
    issue_list.md         问题清单（Markdown，可直接贴进邮件）

退出码：0 = 无 S1 阻断问题；1 = 存在 S1（必须修改后才能交单）；2 = 运行错误。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run_check      # noqa: E402
import make_html      # noqa: E402
import make_xlsx      # noqa: E402


def _write_markdown(result, path):
    a = result.get("anchor") or {}
    s = result.get("summary") or {}
    sev = s.get("severity") or {}
    L = []
    L.append("# 出口单证检查报告（模拟演示票）")
    L.append("")
    if a.get("contract_no") or a.get("ci_no"):
        L.append("| 项目 | 内容 |")
        L.append("| --- | --- |")
        for k, cn in (("contract_no", "合同号"), ("ci_no", "商业发票号"),
                      ("bl_no", "提单号"), ("seller", "出口商"), ("buyer", "进口商"),
                      ("product", "品名"), ("pol", "起运港"), ("pod", "目的港"),
                      ("quantity", "数量"), ("amount", "总金额"), ("incoterm", "贸易术语")):
            if a.get(k):
                L.append("| %s | %s |" % (cn, a[k]))
        L.append("")
    L.append("## 结论")
    L.append("")
    L.append("- 受检单证：**%d** 份（另有参考文件 %d 份不参与核对）" % (
        len([d for d in result["docs"] if not d.get("excluded")]),
        len([d for d in result["docs"] if d.get("excluded")])))
    L.append("- 字段一致 **%d** ｜ 不一致 **%d** ｜ 缺失 **%d** ｜ 计算不符 **%d** ｜ 不适用 %d" % (
        s["cells"]["OK"], s["cells"]["DIFF"], s["cells"]["MISS"],
        s["cells"]["CALC"], s["cells"]["NA"]))
    L.append("- 问题合计 **%d** 项：S1 阻断交单 **%d**、S2 需修正 **%d**、S3 建议核对 **%d**" % (
        s["issues"], sev.get("S1", 0), sev.get("S2", 0), sev.get("S3", 0)))
    L.append("")
    L.append("### 计算关系核验")
    L.append("")
    L.append("| 编号 | 核验项 | 结论 | 说明 |")
    L.append("| --- | --- | --- | --- |")
    for c in result["checks"]:
        L.append("| %s | %s | %s | %s |" % (
            c["id"], c["name"], "通过" if c["ok"] else "**不符**", c["detail"]))
    L.append("")

    issues = result["issues"]
    for level, title in (("S1", "阻断交单（必须修改）"), ("S2", "需修正"),
                         ("S3", "建议核对 / 补录")):
        grp = [i for i in issues if i.get("severity") == level]
        if not grp:
            continue
        L.append("## %s — %s（%d 项）" % (level, title, len(grp)))
        L.append("")
        L.append("| 编号 | 字段 | 单证 | 当前值 | 定位 | 处理建议 |")
        L.append("| --- | --- | --- | --- | --- | --- |")
        for it in grp:
            loc = ("第 %s 页" % it["page"]) if it.get("page") else "—"
            val = str(it.get("value") or "").replace("|", "／")
            adv = str(it.get("advice") or it.get("note") or "").replace("|", "／")
            doc = it.get("doc", "")
            for d in result["docs"]:
                if d["id"] == doc:
                    doc = d.get("type_cn") or doc
            L.append("| %s | %s | %s | %s | %s | %s |" % (
                it.get("id", ""), it.get("field_cn", it.get("field", "")), doc,
                val or "（空）", loc, adv))
        L.append("")
    L.append("---")
    L.append("")
    L.append("> 本报告基于 PDF 文本层的版面位置进行标签→取值，**不对任何无法确认的数值、"
             "单位或公司名进行推测**；无法判断的项一律标为需人工确认。"
             "模拟单证中的企业、编号、航次均为虚构，仅用于演示检查流程。")
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:]]
    out_dir = None
    if "--out" in args:
        i = args.index("--out")
        out_dir = args[i + 1]
        del args[i:i + 2]
    hint = True
    if "--no-filename-hint" in args:
        args.remove("--no-filename-hint")
        hint = False
    inputs = [a for a in args if not a.startswith("--")]
    if not inputs:
        print(__doc__)
        return 2

    try:
        result = run_check.run(inputs, use_filename_hint=hint)
    except Exception as exc:
        print("运行错误：%s: %s" % (type(exc).__name__, exc))
        return 2

    out_dir = out_dir or os.path.join(os.getcwd(), "出口单证检查结果")
    os.makedirs(out_dir, exist_ok=True)
    p_json = os.path.join(out_dir, "check_result.json")
    p_html = os.path.join(out_dir, "check_page.html")
    p_xlsx = os.path.join(out_dir, "出口单证检查结果.xlsx")
    p_md = os.path.join(out_dir, "issue_list.md")

    with io.open(p_json, "w", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False, indent=1))
    make_html.build(result, p_html)
    try:
        make_xlsx.build(result, p_xlsx)
    except ImportError:
        p_xlsx = None
        print("提示：未安装 openpyxl，已跳过 Excel 输出")
    _write_markdown(result, p_md)

    s = result["summary"]
    print("受检单证 %d 份（参考文件 %d 份已排除）" % (
        len([d for d in result["docs"] if not d.get("excluded")]),
        len([d for d in result["docs"] if d.get("excluded")])))
    print("差异 %d ｜ 缺失 %d ｜ 计算不符 %d ｜ 问题 %d（S1=%d）" % (
        s["cells"]["DIFF"], s["cells"]["MISS"], s["cells"]["CALC"],
        s["issues"], s["severity"].get("S1", 0)))
    print("\n已输出：")
    for p in (p_html, p_xlsx, p_xlsx and os.path.join(out_dir, "issue_list.md"), p_json):
        if p:
            print("  ", p)
    return 1 if s["severity"].get("S1", 0) else 0


if __name__ == "__main__":
    sys.exit(main())
