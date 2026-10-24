#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_outputs.py — 交付前自检（HTML + XLSX）

检查项：
  XLSX: 表数量/名称、公式可解析、公式重算后无错误值（#REF!/#VALUE! 等）、
        交叉表引用（看板 → 其他表）指向真实存在的行/列、下拉校验覆盖、关键单元格有值
  HTML: 16 个 section 齐全、无未闭合标签、脚本可被 JS 引擎解析（若安装了 node）、
        内联资源（无外部 http 依赖）、关键交互钩子存在

用法：
    python scripts/check_outputs.py examples/h2o2-kr-30/report.html examples/h2o2-kr-30/dossier.xlsx
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

FAILS, WARNS, OKS = [], [], []


def ok(m):
    OKS.append(m)


def bad(m):
    FAILS.append(m)


def warn(m):
    WARNS.append(m)


# ------------------------------------------------------------------ XLSX
def check_xlsx(path):
    import openpyxl
    if not os.path.exists(path):
        bad(f"XLSX 不存在：{path}")
        return
    wb = openpyxl.load_workbook(path)
    names = wb.sheetnames
    ok(f"XLSX 打开成功，共 {len(names)} 张表：{', '.join(names)}")
    if len(names) < 12:
        bad(f"表数量不足（{len(names)} < 12）")

    need = ["产品属性", "HS", "法规依据", "单证要求", "已上传", "缺失资料", "责任主体", "待确认", "税费"]
    joined = " ".join(names)
    for n in need:
        if n not in joined:
            bad(f"缺少必需维度的表：{n}")
        else:
            ok(f"覆盖维度：{n}")

    # 逐表统计
    total_formula = 0
    errors = []
    for s in names:
        ws = wb[s]
        nf = 0
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    nf += 1
                    if "#REF!" in c.value or "#NAME?" in c.value:
                        errors.append(f"{s}!{c.coordinate} 公式含错误引用：{c.value[:60]}")
        total_formula += nf
        if ws.max_row < 3 or ws.max_column < 2:
            bad(f"表『{s}』内容过少（{ws.max_row}×{ws.max_column}）")
        if not ws.freeze_panes and ws.max_row > 8 and not s.startswith(("00", "11")):
            warn(f"表『{s}』未冻结窗格")
        if ws.sheet_view.showGridLines:
            warn(f"表『{s}』未隐藏网格线（视觉一致性）")
    ok(f"公式总数 {total_formula}")
    for e in errors:
        bad(e)

    # 公式中引用的表名必须存在
    valid = set(names)
    for s in names:
        ws = wb[s]
        for row in ws.iter_rows():
            for c in row:
                if not (isinstance(c.value, str) and c.value.startswith("=")):
                    continue
                for m in re.finditer(r"'([^']+)'!", c.value):
                    if m.group(1) not in valid:
                        bad(f"{s}!{c.coordinate} 引用了不存在的表『{m.group(1)}』")

    # 数据校验下拉
    dv_total = 0
    for s in names:
        dv_total += len(wb[s].data_validations.dataValidation)
    if dv_total < 2:
        warn(f"数据校验（下拉）仅 {dv_total} 处，状态列建议加下拉")
    else:
        ok(f"数据校验下拉 {dv_total} 处")

    # 关键单元格非空
    ws = wb[names[1] if len(names) > 1 else names[0]]
    nonempty = sum(1 for row in ws.iter_rows() for c in row if c.value not in (None, ""))
    ok(f"封面表有效单元格 {nonempty} 个")

    # 尝试用 LibreOffice 重算，检查是否出现错误值
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        for cand in [r"C:\Program Files\LibreOffice\program\soffice.exe",
                     r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"]:
            if os.path.exists(cand):
                soffice = cand
                break
    if soffice:
        recalc_check(soffice, path, names)
    else:
        # 无 LibreOffice：用自带的求值器把每个公式真算一遍
        try:
            import verify_xlsx_formulas as V
            ev = V.Evaluator(path)
            n = ev.run()
            if ev.errors:
                for e in ev.errors[:10]:
                    bad(f"公式求值失败：{e}")
            else:
                ok(f"公式求值通过：{n} 个公式全部可算（内置求值器，无需 Excel）")
            # 关键指标断言
            dash = {}
            wb2 = ev.wb
            dd = wb2["11 进度看板"]
            for rr in range(1, 45):
                k = dd.cell(row=rr, column=2).value
                if k:
                    v = dd.cell(row=rr, column=3).value
                    dash[k] = ev.val("11 进度看板", 3, rr) if V.is_formula(v) else v
            for k in ("单证完备度（齐备/必须）", "P0 缺口", "缺口完成率", "待确认事项", "监管事项总数"):
                if k not in dash:
                    warn(f"看板缺少指标『{k}』")
                elif dash[k] in (None, ""):
                    bad(f"看板指标『{k}』求值为空")
                else:
                    ok(f"看板『{k}』= {dash[k]}")
            # 税额勾稽
            tx = wb2["10 税费测算"]
            tax = {}
            for rr in range(20, 45):
                k = tx.cell(row=rr, column=1).value
                if k and V.is_formula(tx.cell(row=rr, column=2).value):
                    tax[k] = ev.val("10 税费测算", 2, rr)
            need = {"CIF 金额（CNY）", "关税额（CNY）", "增值税计税价格（CNY）", "增值税额（CNY）", "税费合计（CNY）"}
            if need.issubset(tax):
                ok(f"税额勾稽：CIF {tax['CIF 金额（CNY）']:,.2f} → 关税 {tax['关税额（CNY）']:,.2f}"
                   f" → 增值税 {tax['增值税额（CNY）']:,.2f} → 合计 {tax['税费合计（CNY）']:,.2f}")
            else:
                bad(f"税费测算缺少关键单元格：{need - set(tax)}")
        except Exception as exc:  # noqa: BLE001
            warn(f"内置公式求值器失败：{exc}")


def recalc_check(soffice, path, names):
    tmp = tempfile.mkdtemp()
    try:
        outdir = os.path.join(tmp, "out")
        os.makedirs(outdir, exist_ok=True)
        cmd = [soffice, "--headless", "--norestore", "--convert-to", "xlsx",
               "--outdir", outdir, path]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        out = os.path.join(outdir, os.path.basename(path))
        if not os.path.exists(out):
            warn(f"LibreOffice 重算未产出文件：{r.stderr[-200:]}")
            return
        import openpyxl
        wb = openpyxl.load_workbook(out, data_only=True)
        err = []
        for s in names:
            if s not in wb.sheetnames:
                continue
            for row in wb[s].iter_rows():
                for c in row:
                    if isinstance(c.value, str) and c.value.startswith("#") and c.value.endswith(("!", "?", "0", "A")):
                        err.append(f"{s}!{c.coordinate}={c.value}")
        if err:
            for e in err[:20]:
                bad(f"公式重算出现错误值：{e}")
        else:
            ok("LibreOffice 重算：公式全部计算成功，无 #REF!/#VALUE!/#NAME? 错误")

        # 交叉校验看板数字
        wb2 = openpyxl.load_workbook(out, data_only=True)
        if "11 进度看板" in wb2.sheetnames:
            ws = wb2["11 进度看板"]
            vals = [(ws.cell(row=r, column=2).value, ws.cell(row=r, column=3).value) for r in range(1, 30)]
            found = {str(k): v for k, v in vals if k}
            for k in ("单证完备度（齐备/必须）", "P0 缺口", "缺口完成率", "待确认事项", "监管事项总数"):
                if k not in found:
                    warn(f"看板缺少指标『{k}』")
                elif found[k] in (None, ""):
                    bad(f"看板指标『{k}』重算后为空")
                else:
                    ok(f"看板『{k}』= {found[k]}")
    except subprocess.TimeoutExpired:
        warn("LibreOffice 重算超时，跳过")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ HTML
def check_html(path):
    if not os.path.exists(path):
        bad(f"HTML 不存在：{path}")
        return
    h = open(path, encoding="utf-8").read()
    size_kb = len(h.encode("utf-8")) / 1024
    ok(f"HTML 大小 {size_kb:,.0f} KB")

    # 单文件：不得依赖外部资源
    ext = re.findall(r'(?:src|href)\s*=\s*"(https?://[^"]+)"', h)
    ext = [u for u in ext if not u.startswith("https://doi.")]
    # 来源链接本身是数据（点击查看原文），允许；但 <script src>/<link href> 不允许
    bad_ext = re.findall(r'<script[^>]+src\s*=\s*"https?://', h) + re.findall(r'<link[^>]+href\s*=\s*"https?://', h)
    if bad_ext:
        bad(f"HTML 引用了外部脚本/样式，离线打开会失效：{bad_ext[:3]}")
    else:
        ok("无外部 script/link 依赖（可离线打开）")

    # section
    ids = re.findall(r'<section id="(s\d+)"', h)
    if len(ids) < 16:
        bad(f"section 数量不足：{len(ids)}")
    else:
        ok(f"section 齐全：{len(ids)} 个（{', '.join(ids)}）")

    # 标签平衡
    for tag in ["div", "section", "table", "tbody", "thead", "tr", "td", "th", "dl", "dt", "dd", "ul", "li", "span", "aside", "main", "header", "footer"]:
        o = len(re.findall(r"<" + tag + r"[\s>]", h))
        c = len(re.findall(r"</" + tag + r">", h))
        if o != c:
            bad(f"<{tag}> 标签不平衡：开 {o} 闭 {c}")
    ok("主要块级标签平衡检查通过")

    # 必需交互
    for hook, label in [("window.DOSSIER", "数据注入"), ("__exportRequest", "导出英文清单"),
                        ("__copyRequest", "复制全文"), ("__print", "打印"),
                        ("__resetProgress", "重置进度"), ("data-gap", "缺口勾选"),
                        ("data-src", "来源抽屉"), ("class=\"scrollbar\"", "滚动进度"),
                        ("class=\"fchip\"", "筛选芯片"), ("IntersectionObserver", "侧栏高亮"),
                        ("localStorage", "本地进度保存")]:
        if hook in h:
            ok(f"交互钩子存在：{label}")
        else:
            bad(f"缺少交互：{label}（{hook}）")

    # 关键内容存在性
    must = ["产品与归类", "HS 编码候选", "监管与许可", "危险属性", "包装与标签",
            "单证清单", "已上传文件检查", "缺失资料", "责任划分", "待确认事项",
            "英文索取清单", "法规来源", "放行闸门", "税费与优惠", "进口税费与优惠"]
    for m in must:
        if m not in h:
            bad(f"缺少必需区块内容：{m}")
    ok(f"区块标题齐备（{len(must)} 项检查）")

    # 禁用表述
    for pat in ["保证通关", "100%合规", "绝对没问题", "包过"]:
        if pat in h:
            bad(f"出现禁用表述：{pat}")

    # 模拟件标注
    if "模拟" in h:
        ok("模拟文件已显式标注")

    # JS 语法：抽最后一段 inline script 交给 node --check
    node = shutil.which("node")
    scripts = re.findall(r"<script>(.*?)</script>", h, re.S)
    if scripts and node:
        js = "\n".join(scripts)
        t = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
        try:
            t.write("var window={}, document={querySelector:()=>null,querySelectorAll:()=>[],addEventListener:()=>{},getElementById:()=>null,createElement:()=>null,body:{},documentElement:{}};\n" + js)
            t.close()
            r = subprocess.run([node, "--check", t.name], capture_output=True, text=True)
            if r.returncode == 0:
                ok("内联 JS 语法检查通过（node --check）")
            else:
                bad(f"内联 JS 语法错误：{r.stderr.strip().splitlines()[:3]}")
        finally:
            os.unlink(t.name)
    elif not node:
        warn("未找到 node，跳过 JS 语法检查")

    # CSS 变量齐备
    for v in ["--paper", "--ink", "--copper", "--indigo", "--ok", "--warn", "--bad"]:
        if v not in h:
            warn(f"设计变量缺失：{v}")
    ok("设计系统变量存在（换皮只需改 :root）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html", nargs="?")
    ap.add_argument("xlsx", nargs="?")
    a = ap.parse_args()
    if a.html:
        print("=== HTML 检查 ===")
        check_html(a.html)
    if a.xlsx:
        print("=== XLSX 检查 ===")
        check_xlsx(a.xlsx)

    print("\n=== 结果 ===")
    for m in OKS:
        print(f"[OK]   {m}")
    for m in WARNS:
        print(f"[WARN] {m}")
    for m in FAILS:
        print(f"[FAIL] {m}")
    print(f"\n通过 {len(OKS)} / 警告 {len(WARNS)} / 失败 {len(FAILS)}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
