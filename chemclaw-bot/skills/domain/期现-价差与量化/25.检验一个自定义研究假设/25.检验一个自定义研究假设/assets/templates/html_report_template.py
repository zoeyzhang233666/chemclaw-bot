# -*- coding: utf-8 -*-
"""html_report_template.py — HTML 研究页模板（可直接改文案复用）。

用法：
  1. 把它复制到项目的 src/ 下；
  2. 保留 build() 的签名，替换各 sec_* 函数里的中文文案与表格字段即可；
  3. 页面必须保留以下不可删减的要素：
       - 真实 / 模拟双轨卡片（模拟必须带 SIMULATED 徽标）
       - 参数确认与数据指纹
       - 全量检验登记表（含不显著项与 BH-q）
       - 局限与风险（四类错误自查）
       - 复现说明（数据 sha256 + 重建命令）

页面自检：python scripts/check_html.py out/xxx.html
  会强制检查：无外链、tab 与 nav 对应、含「样本不足」「SIMULATED」「前视」「BH」「回源核验」、
  主要容器标签开合平衡、真实统计页未混入 SIMULATED 内容。

注意：本模板刻意不使用任何 CDN 或框架——研究页要在没有网络的分析室里也能打开。
"""
import json
from datetime import datetime

CSS = """
:root{--ink:#1b1f24;--mut:#6b7280;--line:#e5e7eb;--bg:#f7f8fa;--ok:#0f766e;--bad:#b91c1c;--sim:#6d28d9}
body{margin:0;font:15px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;color:var(--ink);background:var(--bg)}
header{background:linear-gradient(135deg,#0f172a,#134e4a);color:#fff;padding:28px 32px}
header h1{margin:0 0 6px;font-size:23px}
nav{position:sticky;top:0;background:#fff;border-bottom:1px solid var(--line);display:flex;gap:2px;
padding:0 20px;overflow-x:auto}
nav button{background:none;border:0;padding:13px 15px;font:inherit;color:var(--mut);cursor:pointer;
border-bottom:2px solid transparent}
nav button.on{color:var(--ok);border-bottom-color:var(--ok);font-weight:600}
main{max-width:1220px;margin:0 auto;padding:20px 20px 80px}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:22px 24px;margin-bottom:18px}
h2{margin:0 0 14px;font-size:19px}
.tbl{border-collapse:collapse;width:100%;font-size:13.5px}
.tbl th{background:#f3f4f6;text-align:left;padding:8px 10px}
.tbl td{padding:7px 10px;border-bottom:1px solid #f1f2f4}
.num{text-align:right;font-variant-numeric:tabular-nums}
.muted{color:var(--mut);font-size:13.5px}
.note{margin-top:14px;padding:12px 14px;background:#f9fafb;border:1px dashed var(--line);border-radius:8px;font-size:13.5px}
.badge{display:inline-block;padding:2px 8px;border-radius:99px;font-size:12px;font-weight:600}
.b-ok{background:#ccfbf1;color:#115e59}.b-bad{background:#fee2e2;color:#991b1b}
.b-sim{background:#ede9fe;color:#5b21b6}.b-none{background:#e5e7eb;color:#374151}
.tracks{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:900px){.tracks{grid-template-columns:1fr}}
.track{border-radius:10px;padding:16px;border:1px solid var(--line)}
.track.real{background:#f0fdfa;border-color:#99f6e4}
.track.sim{background:#f5f3ff;border-color:#ddd6fe}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.kpi{background:#f9fafb;border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.kpi .k{display:block;font-size:24px;font-weight:700}
.chart{width:100%;height:auto}
pre{background:#0f172a;color:#e2e8f0;padding:14px;border-radius:8px;overflow:auto;font-size:12.5px}
"""

JS = """
document.querySelectorAll('nav button').forEach(function(b){
  b.addEventListener('click',function(){
    document.querySelectorAll('nav button').forEach(function(x){x.classList.remove('on')});
    document.querySelectorAll('section.tab').forEach(function(x){x.style.display='none'});
    b.classList.add('on'); document.getElementById(b.dataset.t).style.display='block';
  });
});
document.querySelectorAll('nav button')[0].click();
"""


def badge(kind, text):
    return f'<span class="badge b-{kind}">{text}</span>'


def kpis(items):
    return '<div class="kpis">' + "".join(
        f'<div class="kpi"><span class="k">{v}</span><span class="kl">{k}</span></div>'
        for k, v in items) + "</div>"


def table(header, rows):
    th = "".join(f"<th>{h}</th>" for h in header)
    tb = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="tbl"><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>'


def dual_track(real_html, sim_html):
    return ('<div class="tracks">'
            f'<div class="track real"><h3>{badge("ok","真实数据")}</h3>{real_html}</div>'
            f'<div class="track sim"><h3>{badge("sim","模拟数据 SIMULATED")}</h3>{sim_html}</div>'
            "</div>")


def build(out_path, ctx):
    """ctx: {title, subtitle, verdict_badge, tabs:[(id,label,html)]}"""
    nav = "".join(f'<button data-t="{t[0]}">{t[1]}</button>' for t in ctx["tabs"])
    body = "".join(f'<section class="tab" id="{t[0]}">{t[2]}</section>' for t in ctx["tabs"])
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{ctx['title']}</title><style>{CSS}</style></head><body>
<header><h1>{ctx['title']}</h1><div class="sub">{ctx.get('subtitle','')}</div>
{ctx.get('verdict_badge','')}</header>
<nav>{nav}</nav><main>{body}</main>
<footer style="text-align:center;color:#6b7280;font-size:12.5px;padding:24px">
真实数据均可回溯原文；模拟数据逐行标记且不构成结论；观测数据只支持条件相关性。</footer>
<script>{JS}</script></body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


if __name__ == "__main__":
    # 最小可用示例：三个 tab，直接替换成你的章节
    ctx = {
        "title": "研究假设检验（模板）",
        "subtitle": f"生成于 {datetime.now():%Y-%m-%d %H:%M}",
        "verdict_badge": badge("bad", "样本不足，无法判断"),
        "tabs": [
            ("t1", "① 研究设计", '<section class="card"><h2>研究设计</h2>'
             + table(["项目", "取值"], [["假设", "（填原文）"], ["信号", "（填规则）"]]) + "</section>"),
            ("t2", "② 数据可用性", '<section class="card"><h2>数据可用性</h2>'
             + dual_track("<p>真实来源与覆盖度</p>", "<p>模拟机制与种子</p>") + "</section>"),
            ("t3", "③ 统计结果", '<section class="card"><h2>统计结果</h2>'
             + kpis([("信号 n", 0), ("对照 n", 0), ("检验数", 0), ("结论", "样本不足")]) + "</section>"),
        ],
    }
    build("template_demo.html", ctx)
    print("template_demo.html")
