# -*- coding: utf-8 -*-
"""render_report.py — 由 report.json 生成自包含交互式 HTML 核对看板（+ 可选 Excel 台账）。

  python scripts/render_report.py --report report.json --docs <单证目录> \
      --out 核对看板.html [--manifest manifest.json] [--xlsx 台账.xlsx] [--prev-dir 缓存目录]

· HTML 自包含（图片 base64 内嵌、无外链、可离线分发）；
· DOCX→PDF、PDF→PNG 依赖 LibreOffice Kit；自动探测 DSH 内置路径，探测不到则降级为文字预览；
· Excel 台账 6 页：单证索引 / 字段核对矩阵 / 计算校验 / 问题定位 / 修正记录 / 待确认事项。
"""

_CHEMCLAW_ROOT = next(parent for parent in __import__('pathlib').Path(__file__).resolve().parents if (parent / 'runtime/deliver.mjs').is_file())
import argparse, base64, glob, json, os, subprocess, sys, tempfile

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo  # noqa: F401
    HAVE_OPENPYXL = True
except ImportError:            # 仅生成 HTML 时不需要 openpyxl
    HAVE_OPENPYXL = False

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract_fields as E

LO_STATE = {"node": "node", "cli": ""}
CONFIG = {"docs": ".", "prev": tempfile.mkdtemp(prefix="docprev_")}
REPORT = MANIFEST = None
DOCS = "."
PDFD = None


def _find_lo():
    cands_node = [os.environ.get("LO_NODE", ""),
                  __import__('sys').executable]
    cands_cli = [os.environ.get("LO_CLI", ""),
                 str(_CHEMCLAW_ROOT / 'runtime/office-cli.py')]
    LO_STATE["node"] = next((p for p in cands_node if p and os.path.exists(p)), "node")
    LO_STATE["cli"] = next((p for p in cands_cli if p and os.path.exists(p)), "")


def docx_to_pdf(docx, outdir):
    """DOCX → PDF（用于预览与真实页码）。失败返回 None（降级为文字预览）。"""
    if not LO_STATE["cli"]:
        return None
    os.makedirs(outdir, exist_ok=True)
    pdf = os.path.join(outdir, os.path.splitext(os.path.basename(docx))[0] + ".pdf")
    if os.path.exists(pdf):
        os.remove(pdf)
    subprocess.run([LO_STATE["node"], LO_STATE["cli"], "convert", "--input", docx, "--output", pdf],
                   capture_output=True)
    return pdf if os.path.exists(pdf) else None


# -*- coding: utf-8 -*-
"""生成自包含交互式 HTML 核对看板（无外部 CDN/网络依赖）。
左侧：单证清单 + 原件预览（PDF→内嵌图片、图片→原图、Excel→表格快照）
右侧：字段核对矩阵 / 问题清单 / 计算校验 / 待确认事项；点击冲突字段看各文件原值与位置；
底部：补单上传、复核、修正记录，英文要更正函一键生成。"""
import base64, glob, io, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "skill", "scripts"))
import extract_fields as E

def b64(path):
    return base64.b64encode(open(path, "rb").read()).decode()


def pdf_pages(pdf, stem):
    """渲染 PDF 每页为 PNG（缓存于 CONFIG["prev"]/<stem>/）。"""
    cachedir = os.path.join(CONFIG["prev"], stem)
    pdfs = sorted(glob.glob(os.path.join(cachedir, "*.png"))) if os.path.isdir(cachedir) else []
    if pdfs:
        return pdfs
    out = cachedir + "_out"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.isdir(out):
        import shutil
        shutil.rmtree(out)
    if LO_STATE["cli"]:
        subprocess.run([LO_STATE["node"], LO_STATE["cli"], "render", "--input", pdf,
                        "--output-dir", out, "--dpi", "110"], capture_output=True)
    if os.path.isdir(cachedir):
        for f in glob.glob(os.path.join(cachedir, "*")):
            os.remove(f)
        os.rmdir(cachedir)
    os.rename(out, cachedir)
    return sorted(glob.glob(os.path.join(cachedir, "*.png")))


def xlsx_html(path, max_rows=26):
    """把工作簿渲染为紧凑 HTML 表格（取值 + 公式）,用于预览。"""
    rows = {}
    for ln in E.read_any(path) or []:
        cells = [seg for seg in ln["text"].split("|")]
        parsed = []
        for c in cells:
            c = c.strip()
            if "=" in c and c.split("=", 1)[0].strip().isalpha():
                k, v = c.split("=", 1)
                parsed.append(("=" + v.strip()) if k.strip().endswith("#") else v.strip())
            elif c:
                parsed.append(c)
        rows[ln["line"]] = parsed
    html = ['<table class="xls">']
    for i, (n, cells) in enumerate(sorted(rows.items())):
        if i >= max_rows:
            break
        cls = ' class="tot"' if any("TOTAL" in c.upper() for c in cells) else ""
        html.append("<tr%s>%s</tr>" % (cls, "".join("<td>%s</td>" % c for c in cells)))
    html.append("</table>")
    return "".join(html)


def build_previews():
    prev = {}
    for d in REPORT["documents"]:
        f = d["file"]
        stem, ext = os.path.splitext(f)
        p = os.path.join(DOCS, f)
        if ext == ".pdf":
            pages = pdf_pages(p, stem)
            prev[f] = {"kind": "img", "pages": [b64(x) for x in pages]}
        elif ext in (".png", ".jpg", ".jpeg"):
            prev[f] = {"kind": "img", "pages": [b64(p)]}
        elif ext == ".docx":
            pdfp = os.path.join(CONFIG["prev"], stem + ".pdf")
            if not os.path.exists(pdfp):
                pdfp = docx_to_pdf(p, CONFIG["prev"])
            if pdfp and os.path.exists(pdfp):
                pages = pdf_pages(pdfp, stem)
                prev[f] = {"kind": "img", "pages": [b64(x) for x in pages]}
            else:
                txt = "\n".join(ln["text"] for ln in (E.read_any(p) or []))
                prev[f] = {"kind": "text", "pages": [txt]}
        elif ext == ".xlsx":
            prev[f] = {"kind": "table", "pages": [xlsx_html(p)]}
        else:
            prev[f] = {"kind": "text", "pages": ["(不支持预览)"]}
    return prev



TYPES_ORDER = ["CONTRACT", "PROFORMA_INVOICE", "COMMERCIAL_INVOICE", "PACKING_LIST", "BILL_OF_LADING", "COA", "SDS",
               "SPEC_SHEET", "COO", "INSURANCE"]
PREVIEWS = {}
DOCS_SORTED = []

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>进口单证核对看板 · IMPORT DOCUMENT VERIFICATION BOARD (SIMULATED)</title>
<style>__CSS__</style></head>
<body>
<header class="top">
  <div class="brand">
    <div class="logo">进口单证核对</div>
    <div class="sub">IMPORT DOCUMENT VERIFICATION · 交叉核对 / 计算校验 / 定位整改</div>
  </div>
  <div class="casebar" id="casebar"></div>
  <div class="simtag">【模拟】SIMULATED</div>
</header>

<div class="layout">
  <!-- ============ 左：单证清单 + 原件预览 ============ -->
  <aside class="left">
    <div class="pane-head">
      <span>单证清单 <b id="doccount"></b></span>
      <span class="hint">点击查看原件 · 可整批重新上传</span>
    </div>
    <ul class="doclist" id="doclist"></ul>
    <div class="pane-head"><span>原件预览</span><span class="hint" id="prevname">—</span></div>
    <div class="preview" id="preview"><div class="empty">← 选择左侧任一单证</div></div>
    <div class="pager" id="pager"></div>
  </aside>

  <!-- ============ 右：核对结果 ============ -->
  <main class="right">
    <section class="kpis" id="kpis"></section>

    <div class="tabs" id="tabs">
      <button class="tab active" data-tab="issues">问题清单 <b id="n-issues"></b></button>
      <button class="tab" data-tab="matrix">字段核对矩阵 <b id="n-matrix"></b></button>
      <button class="tab" data-tab="calc">计算校验 <b id="n-calc"></b></button>
      <button class="tab" data-tab="pending">待确认事项 <b id="n-pending"></b></button>
      <button class="tab" data-tab="letter">要更正函（英文）</button>
      <button class="tab" data-tab="records">修正记录 <b id="n-records"></b></button>
    </div>

    <div class="filters" id="filters">
      <span class="flabel">筛选：</span>
      <button class="chip on" data-f="all">全部</button>
      <button class="chip" data-f="不一致">不一致</button>
      <button class="chip" data-f="缺失">缺失</button>
      <button class="chip" data-f="计算错误">计算错误</button>
      <button class="chip" data-f="待确认">待确认</button>
      <span class="sep"></span>
      <input id="q" placeholder="搜索字段 / 单证 / 问题…">
    </div>

    <div class="panel active" id="p-issues"></div>
    <div class="panel" id="p-matrix"></div>
    <div class="panel" id="p-calc"></div>
    <div class="panel" id="p-pending"></div>
    <div class="panel" id="p-letter"></div>
    <div class="panel" id="p-records"></div>
  </main>
</div>

<!-- 字段详情抽屉 -->
<div class="drawer-mask" id="mask"></div>
<div class="drawer" id="drawer">
  <div class="dw-head">
    <div><b id="dw-title"></b><span class="dw-sub" id="dw-sub"></span></div>
    <button class="x" id="dw-close">×</button>
  </div>
  <div class="dw-body" id="dw-body"></div>
  <div class="dw-foot" id="dw-foot"></div>
</div>

<div class="toast" id="toast"></div>
<footer class="foot">__FOOTER__</footer>

<script id="payload" type="application/json">__PAYLOAD__</script>
<script>__JS__</script>
</body></html>
"""

CSS = r"""
:root{
  --ink:#12161d; --ink2:#39424f; --mut:#69737f; --line:#dde3ea; --line2:#eef2f6;
  --bg:#f4f6f9; --card:#fff; --navy:#123456; --navy2:#1e4d7b;
  --ok:#14794a; --okbg:#e6f4ec; --bad:#b3261e; --badbg:#fdeceb;
  --warn:#9a6700; --warnbg:#fff6e0; --info:#20536e; --infobg:#e7f1f7;
  --grey:#6b7280; --greybg:#f1f3f6;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:13px/1.55 "Microsoft YaHei","Segoe UI",system-ui,-apple-system,sans-serif}
b{font-weight:700}
header.top{display:flex;align-items:center;gap:18px;padding:12px 20px;background:#0f2942;color:#fff;
  position:sticky;top:0;z-index:30;box-shadow:0 2px 10px rgba(9,25,42,.25)}
.logo{font-size:17px;font-weight:800;letter-spacing:.5px}
.sub{font-size:11px;color:#9fc0dd;letter-spacing:.6px}
.casebar{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:#d7e6f3;margin-left:auto}
.casebar span b{color:#fff;font-weight:700}
.simtag{background:#a8201a;padding:3px 9px;border-radius:3px;font-size:11px;font-weight:700;letter-spacing:.5px}
.layout{display:grid;grid-template-columns:430px minmax(0,1fr);gap:14px;padding:14px;align-items:start}
@media (max-width:1180px){.layout{grid-template-columns:1fr}}
aside.left,.right{background:var(--card);border:1px solid var(--line);border-radius:8px;
  box-shadow:0 1px 3px rgba(16,32,50,.06)}
aside.left{position:sticky;top:66px;max-height:calc(100vh - 82px);display:flex;flex-direction:column;overflow:hidden}
.pane-head{display:flex;justify-content:space-between;align-items:center;padding:9px 12px;background:#fafbfd;
  border-bottom:1px solid var(--line);font-size:12px;font-weight:700;color:var(--ink2);flex:none}
.pane-head .hint{font-weight:400;color:var(--mut);font-size:11px}
.doclist{list-style:none;margin:0;padding:6px;overflow:auto;max-height:242px;flex:none}
.doclist li{display:grid;grid-template-columns:22px 1fr auto;gap:8px;align-items:center;padding:6px 8px;
  border-radius:6px;cursor:pointer;border:1px solid transparent}
.doclist li:hover{background:#f5f8fb}
.doclist li.on{background:#eaf2fa;border-color:#b9d3ea}
.doclist .no{font:11px/1 ui-monospace,Consolas,monospace;color:var(--mut)}
.doclist .nm{font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.doclist .tp{font-size:10.5px;padding:1px 6px;border-radius:9px;background:#eef2f7;color:#48546a;white-space:nowrap}
.doclist .badge{font-size:10px;padding:0 5px;border-radius:8px;margin-left:4px}
.preview{flex:1;overflow:auto;padding:10px;background:#f7f9fb;min-height:220px}
.preview img{width:100%;display:block;border:1px solid #d5dce4;box-shadow:0 1px 5px rgba(20,40,70,.10);
  margin-bottom:8px;background:#fff}
.preview .empty{color:var(--mut);text-align:center;padding:44px 0;font-size:12px}
.preview pre{margin:0;font:11px/1.5 ui-monospace,Consolas,monospace;white-space:pre-wrap;background:#fff;
  border:1px solid #d5dce4;padding:8px;max-height:none}
.pager{display:flex;gap:6px;padding:6px 10px;border-top:1px solid var(--line);flex:none;flex-wrap:wrap}
.pager button{font-size:11px;padding:2px 8px;border:1px solid var(--line);background:#fff;border-radius:4px;cursor:pointer}
.pager button.on{background:var(--navy);color:#fff;border-color:var(--navy)}
table.xls{border-collapse:collapse;width:100%;background:#fff;font-size:10.5px}
table.xls td{border:1px solid #e2e7ee;padding:2px 4px;vertical-align:top;word-break:break-word}
table.xls tr.tot td{background:#eef6ee;font-weight:700}

.right{overflow:hidden}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:0;border-bottom:1px solid var(--line)}
@media (max-width:900px){.kpis{grid-template-columns:repeat(3,1fr)}}
.kpi{padding:11px 12px;border-right:1px solid var(--line2)}
.kpi:last-child{border-right:none}
.kpi .v{font-size:21px;font-weight:800;line-height:1.15}
.kpi .l{font-size:11px;color:var(--mut)}
.kpi.bad .v{color:var(--bad)} .kpi.ok .v{color:var(--ok)} .kpi.warn .v{color:var(--warn)}
.kpi.info .v{color:var(--info)} .kpi.grey .v{color:var(--grey)}
.tabs{display:flex;gap:2px;padding:8px 10px 0;border-bottom:1px solid var(--line);flex-wrap:wrap;background:#fafbfd}
.tab{border:1px solid transparent;border-bottom:none;background:transparent;padding:7px 12px;font-size:12.5px;
  cursor:pointer;border-radius:6px 6px 0 0;color:var(--ink2);font-family:inherit}
.tab b{font-size:10.5px;color:var(--mut);margin-left:3px}
.tab.active{background:#fff;border-color:var(--line);color:var(--navy);font-weight:700}
.tab.active b{color:var(--bad)}
.filters{display:flex;gap:6px;align-items:center;padding:8px 12px;border-bottom:1px solid var(--line2);flex-wrap:wrap}
.flabel{font-size:11.5px;color:var(--mut)}
.chip{font-size:11.5px;padding:3px 10px;border-radius:12px;border:1px solid var(--line);background:#fff;
  cursor:pointer;font-family:inherit;color:var(--ink2)}
.chip.on{background:var(--navy);border-color:var(--navy);color:#fff;font-weight:700}
.sep{width:1px;height:16px;background:var(--line);margin:0 4px}
#q{flex:1;min-width:150px;border:1px solid var(--line);border-radius:5px;padding:4px 9px;font-size:12px;
  font-family:inherit;outline:none}
#q:focus{border-color:var(--navy2)}
.panel{display:none;padding:12px}
.panel.active{display:block}

.card{border:1px solid var(--line);border-radius:7px;margin-bottom:10px;overflow:hidden;background:#fff}
.card:hover{border-color:#c3d3e2}
.ch{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:start;padding:10px 12px;cursor:pointer}
.ch .id{font:11px/1.7 ui-monospace,Consolas,monospace;color:var(--mut)}
.ch .ti{font-size:13px;font-weight:700}
.ch .de{font-size:11.5px;color:var(--mut);margin-top:2px}
.st{font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:10px;white-space:nowrap;height:fit-content}
.st-不一致,.st-计算错误{background:var(--badbg);color:var(--bad)}
.st-缺失{background:var(--warnbg);color:var(--warn)}
.st-待确认{background:var(--infobg);color:var(--info)}
.st-一致{background:var(--okbg);color:var(--ok)}
.st-无法判断,.st-无法直接比较{background:var(--greybg);color:var(--grey)}
.cb{padding:0 12px 11px;display:none;border-top:1px dashed var(--line2);margin-top:2px}
.card.open .cb{display:block}
.lbl{font-size:11px;color:var(--mut);margin:9px 0 4px;font-weight:700;letter-spacing:.3px}
table.loc{width:100%;border-collapse:collapse;font-size:11.5px}
table.loc th{text-align:left;font-weight:700;color:var(--ink2);background:#f7f9fc;padding:4px 6px;
  border-bottom:1px solid var(--line);font-size:11px}
table.loc td{padding:4px 6px;border-bottom:1px solid var(--line2);vertical-align:top}
table.loc td.v{font-family:ui-monospace,Consolas,monospace;font-size:11px}
table.loc tr.diff td.v{background:#fff4f3;font-weight:700;color:var(--bad)}
.diffmark{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--bad);margin-right:5px}
.imps{display:flex;gap:5px;flex-wrap:wrap}
.imp{font-size:11px;background:#eef2f7;border:1px solid #dde5ee;border-radius:4px;padding:1px 7px;color:#3d4a5c}
.act{font-size:12px;background:#f6faf7;border-left:3px solid var(--ok);padding:7px 10px;border-radius:0 5px 5px 0}
.sev{font-size:10.5px;font-weight:700;padding:1px 6px;border-radius:3px;margin-right:6px}
.sev-高{background:#b3261e;color:#fff} .sev-中{background:#9a6700;color:#fff} .sev-提示{background:#6b7280;color:#fff}

table.mx{width:100%;border-collapse:collapse;font-size:11px}
table.mx th,table.mx td{border:1px solid var(--line2);padding:3px 5px;vertical-align:top}
table.mx th{background:#f4f7fb;position:sticky;top:0;font-size:10.5px;z-index:2}
table.mx th.f{min-width:96px;text-align:left}
table.mx td.fc{font-weight:700;white-space:nowrap;background:#fbfcfe}
table.mx td{max-width:118px;overflow:hidden;text-overflow:ellipsis}
table.mx tr:hover td{background:#f8fbff}
table.mx td.has{cursor:pointer}
table.mx td.miss{color:#b3b9c2;text-align:center}
table.mx td.nc{background:#f6f7f9;color:#8b93a1;text-align:center;font-size:10.5px}
.mxwrap{overflow:auto;max-height:62vh;border:1px solid var(--line);border-radius:7px}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:11px;color:var(--mut);margin:0 0 8px}
.legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:4px}
tr.datarow.sh{background:#fff8e6}

table.calc{width:100%;border-collapse:collapse;font-size:11.5px}
table.calc th{background:#f4f7fb;text-align:left;padding:5px 7px;border-bottom:1px solid var(--line);font-size:11px}
table.calc td{padding:5px 7px;border-bottom:1px solid var(--line2)}
table.calc tr.fail td{background:#fff4f3}
.okb{color:var(--ok);font-weight:700} .nob{color:var(--bad);font-weight:700}

.drawer-mask{position:fixed;inset:0;background:rgba(10,20,32,.35);opacity:0;pointer-events:none;
  transition:.16s;z-index:40}
.drawer-mask.on{opacity:1;pointer-events:auto}
.drawer{position:fixed;top:0;right:-540px;width:540px;max-width:96vw;height:100%;
  background:#fff;z-index:41;display:flex;flex-direction:column;transition:right .2s;
  box-shadow:-6px 0 24px rgba(10,25,42,.2)}
.drawer.on{right:0}
.dw-head{display:flex;justify-content:space-between;align-items:flex-start;padding:12px 14px;
  border-bottom:1px solid var(--line);background:#fafbfd}
.dw-head b{font-size:14px}
.dw-sub{display:block;font-size:11px;color:var(--mut);margin-top:2px}
.x{border:none;background:transparent;font-size:22px;line-height:1;cursor:pointer;color:var(--mut)}
.dw-body{flex:1;overflow:auto;padding:12px 14px}
.dw-foot{padding:10px 14px;border-top:1px solid var(--line);background:#fafbfd;display:flex;gap:8px;
  align-items:center;flex-wrap:wrap;font-size:11.5px}
.btn{border:1px solid var(--navy);background:var(--navy);color:#fff;border-radius:5px;padding:6px 12px;
  font-size:12px;cursor:pointer;font-family:inherit;font-weight:600}
.btn.ghost{background:#fff;color:var(--navy)}
.btn.ghost:hover{background:#eef4fa}
.btn:disabled{opacity:.45;cursor:not-allowed}
.verdict{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0 2px}
.verdict button{font-size:11.5px;padding:4px 10px;border:1px solid var(--line);background:#fff;
  border-radius:14px;cursor:pointer;font-family:inherit}
.verdict button.on{background:var(--okbg);border-color:#9ecfb4;color:var(--ok);font-weight:700}
.verdict button.rej.on{background:var(--badbg);border-color:#e8b4b0;color:var(--bad)}
.upload{border:1.5px dashed #c3d3e2;border-radius:7px;background:#fbfdff;padding:14px;text-align:center;
  font-size:12px;color:var(--mut);cursor:pointer}
.upload:hover{border-color:var(--navy2);background:#f4f9fd}
.upload b{color:var(--navy2)}
.filechip{display:inline-flex;gap:6px;align-items:center;background:#eaf2fa;border:1px solid #b9d3ea;
  border-radius:5px;padding:3px 8px;font-size:11.5px;margin:4px 5px 0 0}
.mono{font-family:ui-monospace,Consolas,monospace}
textarea{width:100%;min-height:330px;border:1px solid var(--line);border-radius:6px;padding:10px;
  font:11.5px/1.6 ui-monospace,Consolas,monospace;resize:vertical;outline:none;background:#fcfdfe}
.toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(20px);background:#12263a;
  color:#fff;padding:9px 18px;border-radius:6px;font-size:12.5px;opacity:0;pointer-events:none;transition:.2s;z-index:60}
.toast.on{opacity:1;transform:translateX(-50%)}
.tblwrap{border:1px solid var(--line);border-radius:7px;overflow:hidden}
.rec{border:1px solid var(--line);border-radius:7px;padding:9px 11px;margin-bottom:8px;background:#fff;
  display:grid;grid-template-columns:1fr auto;gap:8px}
.rec .rr{font-size:11px;color:var(--mut)}
.foot{padding:10px 20px 26px;color:var(--mut);font-size:11px;text-align:center;line-height:1.7}
.hl{background:#fff2a8;padding:0 2px}
"""

JS = r"""
const P = JSON.parse(document.getElementById('payload').textContent);
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const state = { doc:null, filter:'all', q:'', tab:'issues', open:{}, records:[], override:{} };

/* ---------- 顶部批次信息 ---------- */
(function(){
  const b = P.batch;
  $('#casebar').innerHTML = [
    ['批次', b.case_no], ['货物', b.product_cn + ' / MEG'], ['路线', b.port_load.split('(')[0].trim() + ' → ' + b.port_disch.split(',')[0]],
    ['金额', 'USD ' + b.amount_usd.toLocaleString('en-US')], ['ETD/ETA', b.etd + ' / ' + b.eta]
  ].map(([k,v]) => `<span>${k} <b>${esc(v)}</b></span>`).join('');
})();

/* ---------- KPI ---------- */
(function(){
  const s = P.summary, cs = P.calsum;
  const bad = P.findings.filter(f => f.status==='不一致').length;
  const miss = P.findings.filter(f => f.status==='缺失').length;
  const calc = P.findings.filter(f => f.status==='计算错误').length;
  const pend = P.pending.length;
  const nc = s.not_comparable_rows, uv = s.unverifiable_rows;
  $('#kpis').innerHTML = `
    <div class="kpi bad"><div class="v">${bad}</div><div class="l">不一致事项</div></div>
    <div class="kpi warn"><div class="v">${miss}</div><div class="l">缺失单证</div></div>
    <div class="kpi bad"><div class="v">${calc}</div><div class="l">计算错误</div></div>
    <div class="kpi info"><div class="v">${pend}</div><div class="l">待确认</div></div>
    <div class="kpi ok"><div class="v">${s.consistent_rows}</div><div class="l">字段一致行 / ${s.matrix_rows}</div></div>
    <div class="kpi grey"><div class="v">${nc+uv}</div><div class="l">不可比/无法判断</div></div>`;
  $('#doccount').textContent = P.docs.length + ' 份';
  $('#n-issues').textContent = P.findings.length;
  $('#n-matrix').textContent = s.matrix_rows;
  $('#n-calc').textContent = cs.total;
  $('#n-pending').textContent = pend;
  $('#n-records').textContent = state.records.length;
})();

/* ---------- 单证清单 ---------- */
function renderDocs(){
  $('#doclist').innerHTML = P.docs.map((d,i) => {
    const issues = P.findings.filter(f => f.locations.some(l => l.file === d.file)).length;
    const dot = issues ? `<span class="badge" style="background:#fdeceb;color:#b3261e">${issues}</span>` : '';
    return `<li data-f="${esc(d.file)}" class="${state.doc===d.file?'on':''}">
      <span class="no">${String(i+1).padStart(2,'0')}</span>
      <span class="nm" title="${esc(d.file)}">${esc(d.file.replace(/^\d+_/,'').replace(/\.[a-z]+$/,''))}${dot}</span>
      <span class="tp">${esc(d.type_cn)}</span></li>`;
  }).join('');
  document.querySelectorAll('#doclist li').forEach(li => li.onclick = () => showDoc(li.dataset.f));
}
function showDoc(f){
  state.doc = f;
  renderDocs();
  const d = P.docs.find(x => x.file === f), pv = P.previews[f];
  $('#prevname').textContent = f;
  let html = '';
  if (pv.kind === 'img'){
    html = pv.pages.map((b,i) => `<img src="data:image/png;base64,${b}" alt="page ${i+1}">`).join('');
  } else if (pv.kind === 'table'){
    html = pv.pages[0];
  } else {
    html = `<pre>${esc(pv.pages[0]).slice(0,6000)}</pre>`;
  }
  $('#preview').innerHTML = html;
  $('#pager').innerHTML = pv.pages.length > 1
    ? pv.pages.map((_,i) => `<button data-i="${i}" class="${i===0?'on':''}">第 ${i+1} 页</button>`).join('')
        + `<span style="font-size:11px;color:#69737f;margin-left:6px">共 ${pv.pages.length} 页</span>`
    : `<span style="font-size:11px;color:#69737f">${pv.kind==='table'?'工作表快照（含公式）':''}</span>`;
  document.querySelectorAll('#pager button').forEach(b => b.onclick = () => {
    const imgs = document.querySelectorAll('#preview img');
    const t = imgs[+b.dataset.i];
    if (t) t.scrollIntoView({behavior:'smooth', block:'start'});
    document.querySelectorAll('#pager button').forEach(x => x.classList.remove('on'));
    b.classList.add('on');
  });
}

/* ---------- Tab ---------- */
document.querySelectorAll('.tab').forEach(t => t.onclick = () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  state.tab = t.dataset.tab;
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  $('#p-' + state.tab).classList.add('active');
  $('#filters').style.display = (state.tab === 'issues') ? 'flex' : 'none';
});
document.querySelectorAll('.chip').forEach(c => c.onclick = () => {
  document.querySelectorAll('.chip').forEach(x => x.classList.remove('on'));
  c.classList.add('on'); state.filter = c.dataset.f; renderIssues();
});
$('#q').oninput = e => { state.q = e.target.value.trim().toLowerCase(); renderIssues(); };

/* ---------- 问题清单 ---------- */
function allIssues(){
  return [...P.findings, ...P.pending];
}
function renderIssues(){
  const q = state.q;
  const list = allIssues().filter(f =>
    (state.filter === 'all' || f.status === state.filter) &&
    (!q || (f.title + f.detail + f.locations.map(l => l.file + l.value).join()).toLowerCase().includes(q)));
  if (!list.length){
    $('#p-issues').innerHTML = `<div class="empty" style="padding:40px;text-align:center;color:#69737f">
      当前筛选下没有问题项 —— 但"没有问题"仅指已上传单证之间，未上传的单证仍需确认。</div>`;
    return;
  }
  $('#p-issues').innerHTML = list.map(f => {
    const open = state.open[f.id];
    const locs = f.locations.map(l => {
      const files = new Set(f.locations.map(x => x.value));
      const diff = files.size > 1 ? 'diff' : '';
      return `<tr class="${diff}"><td>${esc(l.file)}</td><td>${esc(l.kind)}</td>
        <td>${l.page ? '第 '+l.page+' 页' : '—'}</td><td class="v">${diff?'<span class="diffmark"></span>':''}${esc(l.value)}</td>
        <td style="color:#69737f;font-size:11px">${esc(l.snippet || '')}</td></tr>`;
    }).join('');
    return `<div class="card ${open?'open':''}" data-id="${f.id}">
      <div class="ch">
        <span class="id">${esc(f.id)}</span>
        <div>
          <div class="ti"><span class="sev sev-${f.severity||'中'}">${esc(f.severity||'中')}</span>${esc(f.title)}</div>
          <div class="de">${esc(f.detail)}</div>
        </div>
        <span class="st st-${f.status}">${esc(f.status)}</span>
      </div>
      <div class="cb">
        <div class="lbl">各单证原值与位置</div>
        <table class="loc"><thead><tr><th style="width:34%">单证</th><th style="width:12%">类型</th>
          <th style="width:12%">位置</th><th style="width:20%">原值</th><th>原文片段</th></tr></thead>
          <tbody>${locs}</tbody></table>
        <div class="lbl">影响的业务环节</div>
        <div class="imps">${f.impacts.map(i => `<span class="imp">${esc(i)}</span>`).join('')}</div>
        ${f.question ? `<div class="lbl">需要确认的问题</div><div class="act">${esc(f.question)}</div>` : ''}
        <div class="lbl">建议处理</div><div class="act">${esc(f.action)}</div>
        <div class="lbl">处理</div>
        <div class="verdict" data-id="${f.id}">
          <button data-v="已更正">标记已更正</button>
          <button data-v="已接受">确认可接受</button>
          <button class="rej" data-v="已驳回">驳回（不成立）</button>
        </div>
      </div></div>`;
  }).join('');
  document.querySelectorAll('#p-issues .card').forEach(c => {
    c.querySelector('.ch').onclick = () => { state.open[c.dataset.id] = !c.classList.contains('open'); renderIssues(); };
    c.querySelectorAll('.verdict button').forEach(b => b.onclick = ev => {
      ev.stopPropagation();
      addRecord(c.dataset.id, b.dataset.v);
    });
  });
}

/* ---------- 字段矩阵 ---------- */
function renderMatrix(){
  const docs = P.docs;
  const head = `<tr><th class="f">核对字段</th><th style="min-width:88px">判定</th>
    ${docs.map(d => `<th title="${esc(d.file)}">${esc(d.type_cn)}</th>`).join('')}</tr>`;
  const rows = P.matrix.map(r => {
    const nc = r.status === '无法直接比较';
    const cells = docs.map(d => {
      const c = r.cells[d.file];
      if (!c || c.value === null || c.value === undefined) return `<td class="miss">—</td>`;
      const cls = nc ? 'nc' : 'has';
      const loc = c.loc ? `第 ${c.loc.page} 页${c.loc.line ? ' · 行 '+c.loc.line : ''}` : '';
      return `<td class="${cls}" data-field="${esc(r.field)}" data-doc="${esc(d.file)}"
        title="${esc(c.value)}\n${esc(loc)}">${esc(String(c.fvalue).slice(0,26))}</td>`;
    }).join('');
    return `<tr class="${r.status==='不一致'?'datarow sh':''}">
      <td class="fc">${esc(r.field_cn)}</td>
      <td><span class="st st-${r.status}">${esc(r.status)}</span></td>${cells}</tr>`;
  }).join('');
  $('#p-matrix').innerHTML = `
    <div class="legend">
      <span><i style="background:#fff;border:1px solid #dde3ea"></i>有值（点击看各单证原值）</span>
      <span><i style="background:#fdeceb"></i>不一致</span>
      <span><i style="background:#f6f7f9"></i>该类单证本不要求此字段 / 不可比</span>
      <span><i style="background:#eef2f6"></i>— 未载明</span>
    </div>
    <div class="mxwrap"><table class="mx"><thead>${head}</thead><tbody>${rows}</tbody></table></div>
    <div style="font-size:11px;color:#69737f;margin-top:8px">
      说明：空白「—」表示该单证未载明该字段，并不必然构成缺失（仅当它是该类单证的必备字段时才计为【缺失】）。
      「无法直接比较」的行已在下方给出不可比原因。</div>`;
  document.querySelectorAll('#p-matrix td.has, #p-matrix td.nc').forEach(td => {
    td.onclick = () => openField(td.dataset.field);
  });
}

/* ---------- 字段详情抽屉 ---------- */
function fmtAction(has, match, file, field){
  if (!has) return '';
  if (match) return '<span style="color:#14794a;font-weight:700">✓ 相符</span>';
  return '<button class="btn ghost" style="padding:2px 8px;font-size:11px" '
    + 'onclick="acceptValue(\'' + file.replace(/'/g, '') + '\',\'' + field + '\')">采用此值</button>';
}
function openField(field){
  const r = P.matrix.find(x => x.field === field);
  if (!r) return;
  $('#dw-title').textContent = r.field_cn;
  $('#dw-sub').textContent = '判定：' + r.status + ' — ' + r.explain;
  const rows = P.docs.map(d => {
    const c = r.cells[d.file];
    if (!c) return '';
    const has = c.value !== null && c.value !== undefined;
    const match = has && r.expected !== null && r.expected !== undefined && String(c.norm) === String(r.expected);
    const files = new Set(Object.values(r.cells).filter(x=>x.value!=null).map(x=>String(x.norm ?? x.value)));
    const diff = has && files.size > 1;
    return `<tr class="${diff?'diff':''}"><td>${esc(d.type_cn)}<div style="font-size:10.5px;color:#69737f">${esc(d.file)}</div></td>
      <td class="v">${has ? (diff?'<span class="diffmark"></span>':'') + esc(c.value) : '<span style="color:#b3b9c2">未载明</span>'}</td>
      <td style="white-space:nowrap">${c.loc && c.loc.page ? '第 '+c.loc.page+' 页' + (c.loc.line?' · 行 '+c.loc.line:'') : '—'}</td>
      <td style="font-size:11px;color:#69737f">${esc(c.loc && c.loc.snippet || '')}</td>
      <td style="white-space:nowrap">${fmtAction(has, match, d.file, r.field)}</td></tr>`;
  }).join('');
  const ex = (r.expected !== null && r.expected !== undefined && r.kind !== 'code' && r.kind !== 'party')
    ? '<div class="act" style="margin-top:8px"><b>建议采用值：</b>' + esc(r.expected) + '　<span style="color:#69737f">'
      + esc(r.basis || '') + '</span></div>' : '';
  $('#dw-body').innerHTML = `
    ${ex}
    <div class="lbl">各单证原值 / 位置</div>
    <table class="loc"><thead><tr><th style="width:30%">单证</th><th style="width:26%">原值</th>
      <th style="width:16%">位置</th><th>原文片段</th><th style="width:11%">处理</th></tr></thead>
      <tbody>${rows}</tbody></table>
    <div class="lbl">判定依据</div><div class="act">${esc(r.explain)}</div>`;
  $('#dw-foot').innerHTML = `<span style="color:#69737f">跳转到问题清单只显示与本字段相关的条目</span>
    <button class="btn ghost" id="dw-goto">查看相关问题</button>
    <button class="btn ghost" id="dw-locate">在原件中定位</button>`;
  $('#drawer').classList.add('on'); $('#mask').classList.add('on');
  $('#dw-close').onclick = closeDrawer; $('#mask').onclick = closeDrawer;
  $('#dw-goto').onclick = () => {
    closeDrawer();
    const rel = allIssues().filter(f => f.field === field);
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    document.querySelector('[data-tab=issues]').classList.add('active');
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    $('#p-issues').classList.add('active'); $('#filters').style.display='flex';
    state.filter='all'; state.q = r.field_cn;
    document.querySelectorAll('.chip').forEach(x => x.classList.toggle('on', x.dataset.f==='all'));
    $('#q').value = r.field_cn; renderIssues();
  };
  $('#dw-locate').onclick = () => {
    const first = P.docs.find(d => { const c = r.cells[d.file]; return c && c.value != null; });
    if (!first) return;
    closeDrawer(); showDoc(first.file);
    setTimeout(()=>{
      const loc = r.cells[first.file].loc;
      const pb = document.querySelectorAll('#pager button')[Math.max(0,(loc.page||1)-1)];
      if (pb) pb.click();
    }, 60);
  };
}
function acceptValue(file, field){
  const r = P.matrix.find(x => x.field === field);
  const c = r.cells[file];
  state.records.unshift({id:'ADOPT', verdict:'已采用该值',
    title: r.field_cn + ' → ' + c.value + '（' + file + '）',
    at: new Date().toLocaleString('zh-CN'), note:'依据：' + (r.basis || '')});
  $('#n-records').textContent = state.records.length;
  renderRecords(); toast('已采纳「' + c.value + '」，其余单证需按此更正');
  openField(field);
}
function closeDrawer(){ $('#drawer').classList.remove('on'); $('#mask').classList.remove('on'); }

/* ---------- 计算校验 ---------- */
function renderCalc(){
  const rows = P.calcs.map(c => `<tr class="${c.ok?'':'fail'}">
    <td>${esc(c.kind)}<div style="font-size:10.5px;color:#69737f">${esc(c.doc)}</div></td>
    <td>${esc(c.check)}</td><td class="mono">${esc(c.formula)}</td>
    <td class="mono">${typeof c.expected==='number'?c.expected.toLocaleString('en-US'):esc(c.expected)}</td>
    <td class="mono">${typeof c.actual==='number'?c.actual.toLocaleString('en-US'):esc(c.actual)}</td>
    <td>${c.ok?'<span class="okb">通过</span>':'<span class="nob">不通过</span>'}</td>
    <td style="white-space:nowrap">${c.loc && c.loc.page ? '第 '+c.loc.page+' 页'+(c.loc.line?' · 行 '+c.loc.line:'') : '—'}</td></tr>`).join('');
  $('#p-calc').innerHTML = `
    <div class="tblwrap"><table class="calc"><thead><tr><th style="width:24%">单证</th><th style="width:26%">校验项</th>
      <th>算式</th><th>应得</th><th>单证所载</th><th style="width:8%">结论</th><th style="width:14%">位置</th></tr></thead>
      <tbody>${rows}</tbody></table></div>
    <div style="font-size:11px;color:#69737f;margin-top:8px">
      共 ${P.calsum.total} 项，未通过 ${P.calsum.failed} 项。仅对"单证内部可自证"的算术做判定；
      跨单证的重量/件数差异在字段矩阵中处理，避免同一问题重复计数。</div>`;
}

/* ---------- 待确认 ---------- */
function renderPending(){
  if (!P.pending.length){ $('#p-pending').innerHTML = '<div class="empty">无待确认事项</div>'; return; }
  $('#p-pending').innerHTML = P.pending.map(p => {
    const rows = p.locations.map(l => `<tr><td>${esc(l.file)}</td><td>${l.page?'第 '+l.page+' 页':'—'}</td>
      <td class="v">${esc(l.value)}</td><td style="font-size:11px;color:#69737f">${esc(l.snippet||'')}</td></tr>`).join('');
    return `<div class="card open"><div class="ch">
      <span class="id">${esc(p.id)}</span>
      <div><div class="ti"><span class="st st-待确认">待确认</span> ${esc(p.title)}</div>
      <div class="de">${esc(p.detail)}</div></div>
      <span class="sev sev-${p.severity}">${esc(p.severity)}</span></div>
      <div class="cb">
        <div class="lbl">各单证表述</div>
        <table class="loc"><thead><tr><th style="width:34%">单证</th><th style="width:14%">位置</th>
          <th style="width:26%">原值</th><th>原文片段</th></tr></thead><tbody>${rows}</tbody></table>
        <div class="lbl">需要确认的问题</div><div class="act">${esc(p.question)}</div>
        <div class="lbl">影响的业务环节</div>
        <div class="imps">${p.impacts.map(i=>`<span class="imp">${esc(i)}</span>`).join('')}</div>
      </div></div>`;
  }).join('');
}

/* ---------- 修正记录 ---------- */
function addRecord(id, verdict, note){
  const it = allIssues().find(x => x.id === id) || {title:id};
  state.records.unshift({id, verdict, note: note||'', at: new Date().toLocaleString('zh-CN'), title: it.title});
  $('#n-records').textContent = state.records.length;
  renderRecords(); toast(`已记录：${id} → ${verdict}`);
  if (state.tab === 'records') return;
}
function renderRecords(){
  if (!state.records.length){
    $('#p-records').innerHTML = `<div class="empty" style="padding:30px;text-align:center;color:#69737f">
      暂无记录。在问题卡片中点击「标记已更正 / 确认可接受 / 驳回」即可留下处理痕迹。</div>`;
    return;
  }
  $('#p-records').innerHTML = state.records.map(r => `<div class="rec">
    <div><b>${esc(r.id)}</b> · ${esc(r.title)}</div>
    <div><span class="st st-${r.verdict.replace('已','')||'待确认'}">${esc(r.verdict)}</span></div>
    <div class="rr">${esc(r.at)}${r.note?' · '+esc(r.note):''}</div><div></div></div>`).join('')
    + `<div style="margin-top:10px"><button class="btn ghost" onclick="exportRecords()">导出处理记录 CSV</button></div>`;
}
function exportRecords(){
  const csv = '\ufeff问题编号,问题,处理结论,时间\n' + state.records.map(r =>
    [r.id, '"'+r.title.replace(/"/g,'""')+'"', r.verdict, r.at].join(',')).join('\n');
  const a = document.createElement('a');
  a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
  a.download = '修正记录.csv'; a.click();
}

/* ---------- 英文要更正函 ---------- */
function renderLetter(){
  $('#p-letter').innerHTML = `
    <div class="lbl">上传更正后的单证（模拟）</div>
    <div class="upload" id="drop"><b>点击选择或拖入文件</b> — 支持 PDF / DOCX / XLSX / JPG / PNG；
      更正件会与原件并存，重新核对后写入修正记录</div>
    <div id="filelist"></div>
    <div style="display:flex;gap:8px;margin:12px 0 6px;align-items:center;flex-wrap:wrap">
      <button class="btn" id="recheck">重新核对</button>
      <span style="font-size:11.5px;color:#69737f">演示环境仅记录文件与状态，不执行云端识别</span>
    </div>
    <div class="lbl">英文要更正函（可直接发送给海外供应商）</div>
    <textarea id="letter" spellcheck="false">${esc(letterText())}</textarea>
    <div style="display:flex;gap:8px;margin-top:8px">
      <button class="btn" onclick="copyLetter()">复制全文</button>
      <button class="btn ghost" onclick="downloadLetter()">下载 .txt</button>
      <span style="font-size:11.5px;color:#69737f;align-self:center">
        函件按当前问题清单自动生成，仅涵盖已确证的不一致/缺失/计算错误</span>
    </div>`;
  const drop = $('#drop');
  drop.onclick = () => {
    const i = document.createElement('input'); i.type='file'; i.multiple = true;
    i.onchange = () => addFiles([...i.files]); i.click();
  };
  ['dragover','dragenter'].forEach(e => drop.addEventListener(e, ev => {ev.preventDefault(); drop.style.background='#eef6fc';}));
  ['dragleave','drop'].forEach(e => drop.addEventListener(e, ev => {ev.preventDefault(); drop.style.background='';}));
  drop.addEventListener('drop', ev => addFiles([...ev.dataTransfer.files]));
  $('#recheck').onclick = () => {
    if (!state.files || !state.files.length) return toast('请先选择更正后的单证');
    state.files.forEach(f => state.records.unshift({id:'UPLOAD', verdict:'已提交更正件',
      title: f, at: new Date().toLocaleString('zh-CN'), note:'待复核'}));
    $('#n-records').textContent = state.records.length;
    renderRecords(); toast('已提交 ' + state.files.length + ' 份更正件，状态：待复核');
  };
}
function addFiles(fs){
  state.files = (state.files || []).concat(fs.map(f => f.name));
  $('#filelist').innerHTML = state.files.map(n => `<span class="filechip">📄 ${esc(n)}</span>`).join('');
}
function letterText(){
  const b = P.batch;
  const date = new Date().toISOString().slice(0,10);
  const L = [];
  L.push(`Subject: Request for Correction of Import Documents — Case ${b.case_no}`);
  L.push(`Our Ref.: ${b.case_no}   Date: ${date}`);
  L.push('');
  L.push('Dear Sir or Madam,');
  L.push('');
  L.push(`Reference is made to our purchase of ${b.product_en} (CAS ${b.cas}), HS Code ${b.hs},`);
  L.push(`quantity ${b.quantity_mt.toFixed(3)} MT at USD ${b.unit_price_usd.toFixed(2)}/MT ${b.incoterm},`);
  L.push(`${b.vessel_voyage}, ETD ${b.etd}, ETA ${b.eta}.`);
  L.push('');
  L.push('Upon cross-checking the full set of shipping documents, we have identified the following');
  L.push('points that require your correction or confirmation before we can proceed with payment,');
  L.push('customs declaration and vessel arrival arrangements. Please treat this as urgent.');
  L.push('');
  let n = 0;
  P.findings.filter(f => ['不一致','计算错误'].includes(f.status)).forEach(f => {
    n++;
    L.push(`${n}. [${f.status.toUpperCase()}] ${enTitle(f)}`);
    L.push('   Documents affected: ' + [...new Set(f.locations.map(l => l.file.replace(/^\d+_/,'')))]
      .join('; '));
    f.locations.forEach(l => L.push(`     - ${l.file.replace(/^\d+_/,'')}${l.page?', page '+l.page:''}: "${l.value}"`));
    L.push('   Action requested: ' + (f.status === '计算错误'
      ? 'Please re-issue the Commercial Invoice so that Amount equals Unit Price x Quantity, and confirm the correct total payable.'
      : 'Please issue a corrected document (or a signed amendment) making this item identical across all documents.'));
    L.push('');
  });
  P.findings.filter(f => f.status === '缺失').forEach(f => {
    n++;
    L.push(`${n}. [MISSING] ${f.field_cn === '单证齐全性' ? 'Document not received' : 'Missing field'}: ${enTitle(f)}`);
    L.push('   Action requested: Please send the missing document/field by e-mail so that we can complete');
    L.push('   the customs declaration and document presentation.');
    L.push('');
  });
  P.pending.forEach(p => {
    n++;
    L.push(`${n}. [TO BE CONFIRMED] ${enTitle(p)}`);
    L.push('   Action requested: Please confirm in writing which route applies to this shipment, so that we');
    L.push('   may align the payment instruction and advise our bank accordingly.');
    L.push('');
  });
  L.push('For your convenience, no items that are legitimately different by the nature of the documents');
  L.push('(e.g. Proforma Invoice vs Commercial Invoice amounts, SDS Section 14 standard-shipment data) have');
  L.push('been raised in this letter.');
  L.push('');
  L.push('Please return the corrected documents within three (3) working days. Kindly reply to this e-mail');
  L.push('with the amended files attached, quoting our reference number above.');
  L.push('');
  L.push('Yours faithfully,');
  L.push('______________________');
  L.push(`${b.buyer}`);
  L.push(`USCC: ${b.uscc}`);
  L.push('');
  L.push('(SIMULATED DOCUMENTS — this letter is generated for import-document workflow testing only.)');
  return L.join('\n');
}
function enTitle(f){
  const m = {
    '批号':'Batch No. differs between documents',
    '付款方式':'Payment terms on the Contract / Proforma Invoice / Commercial Invoice do not match',
    '规格/含量':'Specification (purity) differs between documents',
    '数量(MT)':'Quantity differs between documents',
    '金额':'Invoice amount does not equal Unit Price x Quantity',
    '收货人':'Consignee name differs between documents',
  };
  if (m[f.field_cn]) return m[f.field_cn];
  if (f.field_cn === '单证齐全性' || /缺少/.test(f.title)) {
    const t = f.title.replace(/^【[^】]*】缺少/,'').trim();
    return `Document not received: ${t}`;
  }
  return f.field_cn;
}
function copyLetter(){
  navigator.clipboard.writeText($('#letter').value).then(()=>toast('已复制到剪贴板'));
}
function downloadLetter(){
  const a = document.createElement('a');
  a.href = 'data:text/plain;charset=utf-8,' + encodeURIComponent('\ufeff' + $('#letter').value);
  a.download = 'Correction_Request_' + P.batch.case_no + '.txt'; a.click();
}
function toast(m){ const t = $('#toast'); t.textContent = m; t.classList.add('on');
  clearTimeout(window.__t); window.__t = setTimeout(()=>t.classList.remove('on'), 1900); }

/* ---------- 启动 ---------- */
renderDocs(); showDoc(P.docs[0].file); renderIssues(); renderMatrix(); renderCalc();
renderPending(); renderLetter(); renderRecords();
$('#filters').style.display = 'flex';
"""

FOOTER = ("【模拟】本看板全部数据来自虚构的模拟单证（SIM-MEG-2026-0518），仅用于演示进口单证交叉核对流程；"
          "不构成任何法律、报关或付款建议。所有判定均为「基于已上传单证之间的一致性」结论，"
          "未上传单证不得推定为一致。")



# ---------------------------------------------------------------- Excel 台账
# ---------------------------------------------------------------- 台账样式常量
NAVY = "123456"
HEAD = PatternFill("solid", fgColor="1F3864")
SUB = PatternFill("solid", fgColor="EAF0F7")
TOT = PatternFill("solid", fgColor="EEF6EE")
BAD = PatternFill("solid", fgColor="FDECEB")
WARN = PatternFill("solid", fgColor="FFF6E0")
INFO = PatternFill("solid", fgColor="E7F1F7")
GREY = PatternFill("solid", fgColor="F1F3F6")
OKF = PatternFill("solid", fgColor="E6F4EC")
THIN = Side(style="thin", color="D5DCE4")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
F_BODY = Font(name="微软雅黑", size=9)
F_HEAD = Font(name="微软雅黑", size=9, bold=True, color="FFFFFF")
F_TITLE = Font(name="微软雅黑", size=14, bold=True, color="FFFFFF")
F_SUB = Font(name="微软雅黑", size=9, color="4A5568")
MONO = Font(name="Consolas", size=9)
STATUS_FILL = {"不一致": BAD, "计算错误": BAD, "缺失": WARN, "待确认": INFO,
               "一致": OKF, "无法判断": GREY, "无法直接比较": GREY}


def title_block(ws, title, sub, ncols):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(row=1, column=1, value=title)
    c.font = F_TITLE
    c.fill = PatternFill("solid", fgColor=NAVY)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[1].height = 30
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    c2 = ws.cell(row=2, column=1, value=sub)
    c2.font = F_SUB
    c2.fill = SUB
    c2.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[2].height = 22


def header_row(ws, row, cols):
    for i, (name, w) in enumerate(cols, 1):
        c = ws.cell(row=row, column=i, value=name)
        c.font = F_HEAD
        c.fill = HEAD
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[row].height = 30


def put(ws, r, values, wrap_cols=(), mono_cols=(), fill=None):
    for i, v in enumerate(values, 1):
        c = ws.cell(row=r, column=i, value=v)
        c.font = MONO if i in mono_cols else F_BODY
        c.border = BOX
        c.alignment = Alignment(vertical="top", wrap_text=(i in wrap_cols))
        if fill:
            c.fill = fill


def build_workbook():
    wb = Workbook()

    # ---------------------------------------------------------------- 1 单证索引
    ws = wb.active
    ws.title = "1 单证索引"
    b = MANIFEST.get("batch", {})
    title_block(ws, "进口单证核对台账 · 单证索引",
                "批次 %s ｜ %s（%s） ｜ CAS %s ｜ HS %s ｜ %s MT × USD %s/MT = USD %s ｜ %s → %s ｜ 【模拟】仅供流程测试"
                % (b["case_no"], b["product_cn"], b["product_en"], b["cas"], b["hs"],
                   "{:,.3f}".format(b["quantity_mt"]), "{:,.2f}".format(b["unit_price_usd"]),
                   "{:,.2f}".format(b["amount_usd"]), b["port_load"].split("(")[0].strip(),
                   b["port_disch"].split(",")[0]), 8)
    cols = [("序号", 6), ("单证文件", 42), ("单证类型", 14), ("文件类型", 9), ("大小 (KB)", 10),
            ("关联问题数", 10), ("原件路径", 52), ("核对状态", 12)]
    header_row(ws, 4, cols)
    r = 5
    for i, d in enumerate(REPORT["documents"], 1):
        rel = "documents/" + d["file"]
        p = os.path.join(DOCS, d["file"])
        size = round(os.path.getsize(p) / 1024, 1) if os.path.exists(p) else ""
        n = sum(1 for f in REPORT["findings"] if any(l["file"] == d["file"] for l in f["locations"]))
        st = "需处理" if n else "已核对"
        put(ws, r, [i, d["file"], d["type_cn"], os.path.splitext(d["file"])[1].upper().strip("."), size, n, rel, st],
            wrap_cols=(2, 7), fill=None)
        ws.cell(row=r, column=8).fill = BAD if n else OKF
        r += 1
    put(ws, r, ["", "合计 %d 份单证" % len(REPORT["documents"]), "", "", "", sum(
        1 for f in REPORT["findings"]), "", ""], fill=TOT)
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = "A4:H%d" % (r - 1)

    # 应上传而未上传
    r += 2
    ws.cell(row=r, column=1, value="按合同/信用证/报关要求应随附、但本批次未收到的单证").font = Font(
        name="微软雅黑", size=10, bold=True, color="9A6700")
    r += 1
    header_row(ws, r, [("单证类型", 16), ("单证名称", 30), ("重要性", 10), ("未收到的影响", 40), ("处理建议", 46)])
    ws.column_dimensions["F"].width = 10
    r += 1
    for e in MANIFEST["expected_documents"]:
        if e["type"] in {d["type"] for d in REPORT["documents"]}:
            continue
        put(ws, r, [e["type"], e["name"], e["severity"], "；".join(e["impacts"]), e["action"]],
            wrap_cols=(2, 4, 5), fill=WARN)
        r += 1

    # ---------------------------------------------------------------- 2 字段核对矩阵
    ws = wb.create_sheet("2 字段核对矩阵")
    docs = REPORT["documents"]
    title_block(ws, "字段核对矩阵（跨单证逐字段比对）",
                "判定口径：一致 / 不一致 / 缺失 / 无法判断 / 无法直接比较（不同单证性质本不相同者，不计为错误）", 3 + len(docs))
    cols = [("字段", 14), ("判定", 11), ("判定说明 / 不可比原因", 46)]
    for d in docs:
        cols.append((d["type_cn"], 20))
    header_row(ws, 4, cols)
    r = 5
    for row in REPORT["matrix"]:
        vals = [row["field_cn"], row["status"], row["explain"]]
        for d in docs:
            c = row["cells"][d["file"]]
            vals.append("" if c["value"] is None else c["fvalue"])
        put(ws, r, vals, wrap_cols=(3,), mono_cols=tuple(range(4, 4 + len(docs))))
        ws.cell(row=r, column=2).fill = STATUS_FILL.get(row["status"], GREY)
        ws.cell(row=r, column=2).alignment = Alignment(horizontal="center", vertical="center")
        if row["status"] == "不一致":
            for i in range(4, 4 + len(docs)):
                ws.cell(row=r, column=i).fill = BAD
            ws.cell(row=r, column=1).fill = BAD
        r += 1
    ws.freeze_panes = "D5"
    ws.auto_filter.ref = "A4:%s%d" % (get_column_letter(3 + len(docs)), r - 1)

    # ---------------------------------------------------------------- 3 计算校验
    ws = wb.create_sheet("3 计算校验")
    title_block(ws, "计算校验（单证内部自证的算术关系）",
                "共 %d 项，未通过 %d 项。仅校验可由单证自身数据推出的等式，跨单证差异在矩阵页处理。" % (
                    REPORT["calculations_summary"]["total"], REPORT["calculations_summary"]["failed"]), 9)
    header_row(ws, 4, [("单证", 30), ("校验项", 30), ("算式", 26), ("应得", 14), ("单证所载", 14),
                       ("差额", 12), ("结论", 10), ("位置", 16), ("说明", 30)])
    r = 5
    for c in REPORT["calculations"]:
        loc = "第 %s 页%s" % (c["loc"].get("page"), (" · 行 " + str(c["loc"].get("line"))) if c["loc"] and c["loc"].get("line") else "") if c["loc"] else ""
        put(ws, r, [c["doc"], c["check"], c["formula"], c["expected"], c["actual"], c["gap"],
                    "通过" if c["ok"] else "不通过", loc, ""], mono_cols=(3, 4, 5, 6))
        if not c["ok"]:
            for i in range(1, 10):
                ws.cell(row=r, column=i).fill = BAD
            ws.cell(row=r, column=7).font = Font(name="微软雅黑", size=9, bold=True, color="B3261E")
        r += 1
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = "A4:I%d" % (r - 1)

    # ---------------------------------------------------------------- 4 问题定位
    ws = wb.create_sheet("4 问题定位")
    title_block(ws, "问题定位（逐条列出涉及的单证、页码、原值、影响与处理建议）",
                "共 %d 项：不一致 %d ｜ 缺失 %d ｜ 计算错误 %d" % (
                    len(REPORT["findings"]),
                    len([f for f in REPORT["findings"] if f["status"] == "不一致"]),
                    len([f for f in REPORT["findings"] if f["status"] == "缺失"]),
                    len([f for f in REPORT["findings"] if f["status"] == "计算错误"])), 10)
    header_row(ws, 4, [("编号", 11), ("状态", 10), ("重要性", 8), ("核对字段", 14), ("问题", 40),
                       ("涉及单证", 34), ("位置(页/行)", 14), ("原值", 22), ("影响的业务环节", 30),
                       ("建议处理", 44)])
    r = 5
    for f in REPORT["findings"]:
        first = True
        for l in f["locations"]:
            loc = ("第 %s 页" % l["page"] if l.get("page") else "—") + (
                " · 行 %s" % l["line"] if l.get("line") else "")
            put(ws, r, [f["id"] if first else "", f["status"] if first else "", f["severity"] if first else "",
                        f["field_cn"] if first else "", f["title"] if first else "",
                        l["file"], loc, l["value"], "；".join(f["impacts"]) if first else "",
                        f["action"] if first else ""], wrap_cols=(5, 6, 9, 10), mono_cols=(8,))
            ws.cell(row=r, column=2).fill = STATUS_FILL.get(f["status"], GREY)
            if first and len(f["locations"]) > 1:
                ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=5)
            first = False
            r += 1
        if len(f["locations"]) > 1:
            # 合并首列到最后一行的部分单元格，保证可读
            top = r - len(f["locations"])
            for col in (1, 3, 9, 10):
                ws.merge_cells(start_row=top, start_column=col, end_row=r - 1, end_column=col)
            ws.merge_cells(start_row=top, start_column=5, end_row=r - 1, end_column=5)
            ws.merge_cells(start_row=top, start_column=2, end_row=r - 1, end_column=2)
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = "A4:J%d" % (r - 1)

    # ---------------------------------------------------------------- 5 修正记录
    ws = wb.create_sheet("5 修正记录")
    title_block(ws, "修正记录（补单 / 改单 / 复核留痕）",
                "每行一条处理痕迹：谁在何时、对哪一项、做了什么决定、证据是什么。复核后追加，不覆盖原记录。", 9)
    header_row(ws, 4, [("序号", 6), ("时间", 18), ("相关编号", 12), ("事项", 44), ("处理结论", 14),
                       ("提交/上传文件", 30), ("复核人", 12), ("复核结论", 14), ("备注", 30)])
    r = 5
    rows = [
        ["待填", "", "ISSUE-01", "批号：装箱单/COA 为 MEG2605-B12，提单为 MEG2605-B11",
         "待更正", "", "", "", "已向卖方发出更正函，等提单改单或 COA 重出"],
        ["待填", "", "ISSUE-04", "发票金额 117,000.00 ≠ 单价 612 × 数量 160 = 97,920.00",
         "待更正", "", "", "", "要求重开发票，金额须等于单价×数量"],
        ["待填", "", "ISSUE-02", "缺少原产地证", "待索取", "", "", "", "合同第 5.2 条约定的随附单证"],
        ["待填", "", "PENDING-01", "付款方式：合同 T/T 30+70 vs 发票即期信用证",
         "待确认", "", "", "", "需买方书面确认适用路径"],
    ]
    for i, row in enumerate(rows, 1):
        put(ws, r, [i] + row, wrap_cols=(4, 9))
        r += 1
    for _ in range(6):
        put(ws, r, [r - 4], wrap_cols=(4, 9))
        r += 1
    ws.freeze_panes = "A5"

    # ---------------------------------------------------------------- 6 待确认事项
    ws = wb.create_sheet("6 待确认事项")
    title_block(ws, "待确认事项（不得推定为错误，须向对方书面确认）",
                "这些差异源于单证性质或交易路径不同，不能直接判为单证不符；须由买卖双方/银行确认后再定处理。", 8)
    header_row(ws, 4, [("编号", 11), ("事项", 26), ("重要性", 8), ("各单证表述", 60), ("需要确认的问题", 52),
                       ("影响的业务环节", 26), ("结论（确认后填写）", 30), ("确认人/日期", 20)])
    r = 5
    for p in REPORT["pending"]:
        put(ws, r, [p["id"], p["title"].replace("【待确认】", ""), p["severity"], p["detail"], p["question"],
                    "；".join(p["impacts"]), "", ""], wrap_cols=(2, 4, 5, 6), fill=INFO)
        r += 1
    # 追加"结构性差异（本不构成不符）"清单，供答辩/复核用
    r += 1
    ws.cell(row=r, column=1, value="以下差异属单证性质不同，已判定【无法直接比较】，不计为问题").font = Font(
        name="微软雅黑", size=10, bold=True, color="20536E")
    r += 1
    header_row(ws, r, [("核对字段", 14), ("涉及的不可比单证对/文件", 40), ("原因（为什么不构成不符）", 80)])
    r += 1
    for row in REPORT["matrix"]:
        if row["status"] != "无法直接比较":
            continue
        files = [k for k, v in row["cells"].items() if v["value"] is not None]
        put(ws, r, [row["field_cn"], "、".join(files), row["explain"]], wrap_cols=(2, 3), fill=GREY)
        r += 1

    # 打印设置
    for s in wb.worksheets:
        s.sheet_view.showGridLines = False
        s.page_setup.orientation = "landscape"
        s.page_setup.fitToWidth = 1
        s.sheet_properties.pageSetUpPr.fitToPage = True

    return wb


# ---------------------------------------------------------------- main
def _payload():
    return {
        "batch": MANIFEST.get("batch", {}),
        "docs": [{"file": d["file"], "type": d["type"], "type_cn": d["type_cn"],
                  "size": os.path.getsize(os.path.join(DOCS, d["file"]))
                  if os.path.exists(os.path.join(DOCS, d["file"])) else 0} for d in DOCS_SORTED],
        "previews": PREVIEWS,
        "matrix": REPORT["matrix"], "findings": REPORT["findings"],
        "pending": REPORT.get("pending", []), "calcs": REPORT["calculations"],
        "summary": REPORT["summary"], "calsum": REPORT["calculations_summary"],
        "expect": MANIFEST.get("expected_documents", []),
    }


def main():
    global REPORT, MANIFEST, DOCS
    ap = argparse.ArgumentParser(description="生成进口单证核对看板（HTML）与台账（XLSX）")
    ap.add_argument("--report", required=True)
    ap.add_argument("--docs", required=True)
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--out", default="核对看板.html")
    ap.add_argument("--xlsx", default=None)
    ap.add_argument("--prev-dir", default=None)
    a = ap.parse_args()

    _find_lo()
    CONFIG["docs"] = DOCS = a.docs
    if a.prev_dir:
        CONFIG["prev"] = a.prev_dir
    os.makedirs(CONFIG["prev"], exist_ok=True)
    REPORT = json.load(open(a.report, encoding="utf-8"))
    MANIFEST = json.load(open(a.manifest, encoding="utf-8")) if a.manifest else {
        "batch": REPORT.get("batch", {}), "expected_documents": []}

    globals()["PREVIEWS"] = build_previews()
    globals()["DOCS_SORTED"] = sorted(REPORT["documents"],
                         key=lambda d: TYPES_ORDER.index(d["type"]) if d["type"] in TYPES_ORDER else 99)
    html = (HTML.replace("__CSS__", CSS)
            .replace("__PAYLOAD__", json.dumps(_payload(), ensure_ascii=False).replace("</", "<\\/"))
            .replace("__JS__", JS).replace("__FOOTER__", FOOTER))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(html)
    print("HTML:", a.out, round(os.path.getsize(a.out) / 1024, 1), "KB")

    if a.xlsx:
        if not HAVE_OPENPYXL:
            print("跳过 Excel：未安装 openpyxl（HTML 已生成）")
            return
        try:
            wb = build_workbook()
            os.makedirs(os.path.dirname(os.path.abspath(a.xlsx)), exist_ok=True)
            wb.save(a.xlsx)
            print("XLSX:", a.xlsx, round(os.path.getsize(a.xlsx) / 1024, 1), "KB")
        except ImportError:
            print("跳过 Excel：未安装 openpyxl")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
