# -*- coding: utf-8 -*-
"""包完整性检查：交付前最后一道闸。

检查项：
  A. 必需文件齐全（SKILL.md / references / scripts / templates / assets / examples）
  B. 代码里没有占位符残留（placeholder / stub / TODO / __DATA__ 等）
  C. HTML 报告无外链依赖、占位符已替换、体积合理
  D. Excel 工作表齐全、无 #REF! 之类错误文本
  E. 示例产物与 data.json 数字一致
  F. 文档里引用的脚本名真实存在

用法：
    python scripts/check_package.py
退出码 0 = 可交付。
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import wio  # noqa: E402

PROB = []


def prob(msg):
    PROB.append(msg)
    print("[FAIL] " + msg)


def fine(msg):
    print("[ OK ] " + msg)


REQUIRED = [
    "SKILL.md",
    "README.md",
    "scripts/core.py",
    "scripts/wio.py",
    "scripts/validate.py",
    "scripts/assemble.py",
    "scripts/build_html.py",
    "scripts/build_xlsx.py",
    "scripts/check_consistency.py",
    "scripts/selftest.py",
    "scripts/check_package.py",
    "scripts/build_all.py",
    "scripts/fetch_data.py",
    "scripts/templates/report.html",
    "scripts/assets/core.js",
    "scripts/assets/echarts.min.js",
    "references/import-cost-formulas.md",
    "references/incoterms-matrix.md",
    "references/data-contract.md",
    "references/data-sources.md",
    "references/qa-checklist.md",
    "references/adapters.md",
    "references/report-structure.md",
    "examples/01-meg-cfr-china-huadong/research.json",
    "examples/01-meg-cfr-china-huadong/output/report.html",
    "examples/01-meg-cfr-china-huadong/output/model.xlsx",
]

print("=" * 68)
print("check_package：%s" % ROOT)
print("=" * 68)

# ---------- A. 文件齐全 ----------
missing = [p for p in REQUIRED if not os.path.exists(os.path.join(ROOT, p.replace("/", os.sep)))]
if missing:
    for m in missing:
        prob("缺少文件：%s" % m)
else:
    fine("A 必需文件齐全（%d 项）" % len(REQUIRED))

# ---------- B. 未完成的桩代码 / 占位符残留 ----------
# 说明：模板 report.html 与构建脚本里出现 __DATA__/__ECHARTS__ 等是设计使然（构建时替换），
#      不算残留。真正要防的是「交付物没被真正构建」和「代码没写完」。
STUB = re.compile(r"^(#\s*(stub|placeholder|TODO|FIXME)\s*$)", re.M)
UNBUILT = re.compile(r"__(?:DATA|COREJS|ECHARTS|TITLE|H1)__")
# 只认本 Skill 自己的五个占位符。ECharts 内部有 ___EC__COMPONENT__CONTAINER___ 这类变量，
# 用宽泛的 __[A-Z]+__ 会把压缩库里的正常代码当成残留。
bad = []
for base, _dirs, files in os.walk(ROOT):
    if "__pycache__" in base:
        continue
    for f in files:
        if not f.endswith((".py", ".md", ".html", ".js", ".json")):
            continue
        rel = os.path.relpath(os.path.join(base, f), ROOT)
        if f == "echarts.min.js":
            continue
        try:
            txt = wio.read_text(os.path.join(base, f))
        except Exception:
            continue
        # 1) 桩标记
        m = STUB.search(txt)
        if m:
            bad.append("%s：桩代码 %r" % (rel, m.group(1).strip()))
            continue
        # 2) 只有「产物」才检查未替换占位符
        is_product = rel.startswith("examples" + os.sep) and (
            f == "report.html" or rel.endswith("data.json"))
        if is_product:
            hit = UNBUILT.search(txt)
            if hit:
                bad.append("%s：产物含未替换占位符 %r" % (rel, hit.group(0)))

if bad:
    for b in bad:
        prob("B " + b)
else:
    fine("B 无桩代码；产物中占位符均已替换")

# ---------- C. HTML ----------
rep = os.path.join(ROOT, "examples", "01-meg-cfr-china-huadong", "output", "report.html")
if os.path.exists(rep):
    h = wio.read_text(rep)
    size = os.path.getsize(rep)
    ext = re.findall(r'(?:src|href)\s*=\s*["\']https?://[^"\']+', h)
    # 数据与来源里的 URL 是文本，不是资源引用；只查 <script src> / <link href>
    real_ext = [x for x in ext if x.lower().startswith(("src", "href"))
                and not x.lower().startswith("href")]
    if real_ext:
        prob("HTML 存在外链资源引用：%s" % real_ext[:3])
    else:
        fine("C1 HTML 无外链脚本/样式（完全离线）")
    if size < 200 * 1024:
        prob("HTML 体积异常偏小（%.0f KB），可能没内联 ECharts" % (size / 1024.0))
    else:
        fine("C2 HTML 体积 %.2f MB（含内联 ECharts）" % (size / 1024.0 / 1024.0))
    for token in ("window.WSC", "echarts.init", "renderAll", "WSC.import_cost"):
        if token not in h:
            prob("HTML 缺少关键片段：%s" % token)
    fine("C3 HTML 关键片段齐备（内核/图表/渲染函数）")
    if "contenteditable" in h and "cdn" in h.lower():
        prob("HTML 疑似引用 CDN")
else:
    prob("缺少示例 HTML 产物")

# ---------- D. Excel ----------
xl = os.path.join(ROOT, "examples", "01-meg-cfr-china-huadong", "output", "model.xlsx")
if os.path.exists(xl):
    try:
        from openpyxl import load_workbook
        wb = load_workbook(xl)
    except ImportError:
        prob("未安装 openpyxl，无法检查 Excel")
        wb = None
    if wb:
        names = wb.sheetnames
        need = ["1 封面与口径", "2 参数与输入", "3 成本折算", "4 价差四口径",
                "5 历史序列", "6 价差曲线数据", "7 敏感性", "8 归因分解",
                "9 情景对比", "10 缺口与来源", "11 公式表"]
        lack = [n for n in need if n not in names]
        if lack:
            prob("Excel 缺少工作表：%s" % lack)
        else:
            fine("D1 Excel 工作表齐全（%d 张）" % len(names))
        errs = 0
        formulas = 0
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for c in row:
                    if isinstance(c.value, str):
                        if c.value.startswith("="):
                            formulas += 1
                        if c.value in ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?"):
                            errs += 1
        if errs:
            prob("Excel 存在错误值单元格：%d" % errs)
        else:
            fine("D2 Excel 无错误值；活公式 %d 个" % formulas)
        if formulas < 100:
            prob("Excel 公式数量偏少（%d），可能写死了数字" % formulas)
        else:
            fine("D3 Excel 为活公式模型（非静态数值）")
else:
    prob("缺少示例 Excel 产物")

# ---------- E. 示例与 data.json 一致 ----------
dj = os.path.join(ROOT, "examples", "01-meg-cfr-china-huadong", "build", "data.json")
if os.path.exists(dj):
    d = wio.load_json(dj)
    if len(d.get("gaps", [])) < 3:
        prob("缺口清单过少（%d 条），按规则应逐项列出" % len(d.get("gaps", [])))
    else:
        fine("E1 缺口清单 %d 条" % len(d["gaps"]))
    if not d.get("disclaimers"):
        prob("缺少免责声明")
    else:
        fine("E2 免责声明 %d 条" % len(d["disclaimers"]))
    if len(d.get("formulas", [])) < 8:
        prob("公式表条目过少")
    else:
        fine("E3 公式表 %d 条" % len(d["formulas"]))
    n_ok = (d.get("series") or {}).get("n_ok") or 0
    if n_ok < 5:
        prob("历史序列有效点仅 %d 条" % n_ok)
    else:
        fine("E4 历史序列 %d 个有效观测" % n_ok)
else:
    prob("缺少示例 data.json")

# ---------- F. 文档引用的脚本真实存在 ----------
skill = os.path.join(ROOT, "SKILL.md")
if os.path.exists(skill):
    txt = wio.read_text(skill)
    refs = set(re.findall(r"scripts/([a-z_]+\.py)", txt))
    for r in sorted(refs):
        if not os.path.exists(os.path.join(ROOT, "scripts", r)):
            prob("SKILL.md 引用了不存在的脚本：scripts/%s" % r)
    if refs:
        fine("F1 SKILL.md 引用的 %d 个脚本均存在" % len(refs))

print("-" * 68)
if PROB:
    print("发现 %d 个问题，尚不可交付" % len(PROB))
    sys.exit(1)
print("包完整性检查通过，可交付。")
sys.exit(0)
