# -*- coding: utf-8 -*-
"""生成纯碱案例的静态研究页（案例研究 + 报价效果），自包含、可打印。

    python scripts/build_case_html.py

输入：examples/example-1-soda-ash-glass/fields.json / fields_demo.json / demo/*.md
输出：examples/example-1-soda-ash-glass/案例研究_纯碱询盘报价.html
"""
from __future__ import annotations

import base64
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

EX = Path(__file__).resolve().parent.parent / "examples" / "example-1-soda-ash-glass"
OUT = EX / "案例研究_纯碱询盘报价.html"


def e(v) -> str:
    return html.escape(str(v or ""), quote=True)


def status_meta(row: dict) -> tuple[str, str]:
    st = row.get("status", "")
    if st == "extracted":
        return "已提取", "ok"
    if st == "tbc":
        return "待客户确认", "warn"
    if st == "assumed":
        return "我方假设", "assume"
    if st == "missing":
        return "缺", "miss"
    return "待你填写", "user"


def field_rows(doc: dict) -> str:
    out = []
    for key in C.FIELD_KEYS:
        r = doc["fields"][key]
        label, cls = status_meta(r)
        val = e(r.get("value")) or "—"
        src = e(r.get("source")) or (
            f"询盘未提及 → 采用我方默认假设：{e(r.get('assume_default'))}" if r["bucket"] == "assume" else "询盘未提及"
        )
        note = f'<div class="fnote">{e(r.get("note"))}</div>' if r.get("note") else ""
        bucket = "A" if r["bucket"] == "must" else "B"
        out.append(f"""
        <tr class="frow {cls}">
          <td><span class="bucket b{bucket}">{bucket}</span></td>
          <td class="flabel">{e(r['label'])}{note}</td>
          <td class="fval">{val}</td>
          <td class="fsrc">{src}</td>
          <td><span class="chip {cls}">{label}</span></td>
        </tr>""")
    return "\n".join(out)


def gap_cards(doc: dict) -> str:
    gaps = [
        ("客户全称 / 开票信息", "微信与邮件都只给到“江苏盐城华宇玻璃”，没有营业执照全称、税号、开户信息。",
         "能否发一下营业执照全称、纳税人识别号和开票信息？报价单抬头需要与发票一致。", "必须"),
        ("付款条件", "客户只要求“注明付款条件”，没有说自己的账期或预付比例。",
         "贵司常规是款到发货、预付 30%，还是月结？账期多少天？", "必须确认"),
        ("报价有效期", "客户要求写有效期，但没有给天数；纯碱随行就市。",
         "本报价按 7 天有效，是否满足贵司内部比价周期？", "可假设"),
        ("比价表 1?30", "手写/涂改数字无法辨认，不能猜成 1,130 / 1,230 / 1,630。",
         "比价表最后一行单价字迹看不清，能否补录一个清晰数字？不补也不影响本次报价。", "无法辨认"),
    ]
    out = []
    for title, why, ask, tag in gaps:
        cls = "must" if tag == "必须" else ("warn" if tag == "必须确认" else "soft")
        out.append(f"""
        <div class="gap {cls}">
          <div class="gap-top"><span class="gap-tag">{tag}</span><h4>{e(title)}</h4></div>
          <p>{e(why)}</p>
          <div class="ask"><span>建议问法</span>“{e(ask)}”</div>
        </div>""")
    return "\n".join(out)


def main() -> int:
    doc = C.load_doc(EX / "fields.json")
    demo = C.load_doc(EX / "fields_demo.json")
    ctx = C.build_context(demo)
    t = ctx["totals"]
    price = demo["price"]
    md_path = next((EX / "demo").glob("*报价草稿.md"))
    quote_md = md_path.read_text(encoding="utf-8")

    shot = EX / "input" / "微信截图_华宇玻璃.png"
    b64 = base64.b64encode(shot.read_bytes()).decode("ascii") if shot.exists() else ""

    blockers = C.blockers(doc)
    blocker_lis = "".join(f"<li>{e(x)}</li>" for x in blockers)

    rows = field_rows(doc)
    gaps = gap_cards(doc)

    # 报价单条款
    pending = "".join(f"<li>{e(x)}</li>" for x in ctx["pending"]) or "<li>无</li>"
    terms = [
        ("价格与口径", [
            f"税费口径：{ctx['tax_mode']}（税率 {t['rate']*100:.0f}%）。",
            f"运费口径：{ctx['freight_mode']}。",
            f"价税构成：不含税金额 {C.money(t['net'])} 元 + 税额 {C.money(t['tax'])} 元 = 价税合计 {C.money(t['amount'])} 元。",
        ]),
        ("数量与执行", [
            f"询盘口径：{ctx['quantity']}。",
            f"本次报价按 {C.money(t['qty'])} 吨计价；正式合同以双方书面确认数量为准。",
        ]),
        ("交付条件", [
            f"交货地点：{ctx['place']}。",
            f"运输方式：{ctx['incoterm']}；交期：{ctx['delivery_date']}。",
            f"包装：{ctx['packaging']}。",
        ]),
        ("付款条件", [ctx["payment"]]),
        ("质量与验收", [
            f"质量指标：按 {ctx['grade']} 执行，随货提供批批 COA。",
            "验收：到货后按双方确认指标验收；异议应在收货后 7 个工作日内书面提出。",
        ]),
        ("报价有效期", [
            f"自 {ctx['quote_date']} 起 {ctx['valid_days']} 天有效（至 {ctx['valid_until']}）。",
            "逾期未确认需重新确认价格与交期；原材料大幅波动时我方有权提前书面通知调整。",
        ]),
    ]
    terms_html = ""
    for title, items in terms:
        lis = "".join(f"<li>{e(x)}</li>" for x in items)
        terms_html += f'<div class="term"><h4>{e(title)}</h4><ul>{lis}</ul></div>'

    # 引用与边界
    refs = [
        ("GB/T 210-2022《工业碳酸钠》", "产品标准与验收指标的产品背景；客户给的是内控验收值，最终以双方确认的 COA 为准。",
         "https://openstd.samr.gov.cn/bzgk/std/"),
        ("HS 2836.20.00.00（碳酸钠）", "内贸报价不直接使用 HS 编码；出口/报关场景再核对申报要素与监管条件。",
         "https://hsguilei.com/hs/2836200000"),
        ("增值税 13%（一般纳税人专票）", "客户邮件明确需要 13% 增值税专用发票；税率与开票主体仍需财务复核。",
         "https://www.chinatax.gov.cn/"),
        ("华东重碱公开行情（2026-10-14）", "仅用于说明纯碱价格波动快、报价有效期宜短；不进入报价单，不作为定价依据。",
         "https://www.mysteel.com/oilchem/a/26101415/8E759DEF0FABB7A3.html"),
    ]
    refs_html = "".join(
        f'<div class="ref"><div class="ref-t">{e(a)}</div><p>{e(b)}</p><a href="{e(u)}" target="_blank" rel="noreferrer">查看来源 →</a></div>'
        for a, b, u in refs
    )

    # JSON 片段
    profile = {
        "product": "纯碱（重质）",
        "aliases": ["碳酸钠", "Soda Ash", "Na2CO3"],
        "standard": "GB/T 210-2022 工业碳酸钠",
        "customer_specs": ["Na2CO3 ≥ 99.2%", "Fe2O3 ≤ 0.003%", "烧失量 ≤ 0.5%", "180 目筛余 ≤ 5%"],
        "packaging": ["1000kg 吨包 + 栈板 + 缠膜", "50kg 编织袋", "散装/槽车（按工厂）"],
        "documents": ["COA（批批）", "MSDS", "营业执照/生产资质（按客户安环要求）"],
        "tax": "13% 增值税专用发票（一般纳税人）",
        "hs_code": "2836.20.00.00",
        "price_policy": "系统不生成价格；单价由销售确认后填入",
    }
    profile_json = json.dumps(profile, ensure_ascii=False, indent=2)

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>纯碱询盘 → 报价草稿｜华宇玻璃案例研究</title>
<style>
  :root{{
    --navy:#081b3a; --navy2:#0d2b5c; --blue:#1e56c8; --blue2:#3b78e7;
    --gold:#c8963c; --gold2:#e6c27a; --teal:#0f766e;
    --ink:#101a2c; --sub:#53627a; --muted:#8793a8; --line:#dfe6f1;
    --bg:#eef2f8; --paper:#fffdf8; --soft:#f6f9ff;
    --ok:#0f7b3f; --okbg:#e4f6eb; --warn:#9a5b00; --warnbg:#fff3d6;
    --miss:#b42318; --missbg:#fde8e5; --assume:#7a5a00; --assumebg:#fffaeb;
    --shadow:0 10px 30px rgba(10,30,70,.08); --shadow2:0 24px 70px rgba(10,30,70,.16);
  }}
  *{{box-sizing:border-box}}
  html{{-webkit-text-size-adjust:100%;scroll-behavior:smooth}}
  body{{margin:0;color:var(--ink);background:var(--bg);font:14px/1.7 "Microsoft YaHei","PingFang SC","Hiragino Sans GB",system-ui,-apple-system,"Segoe UI",sans-serif}}
  a{{color:var(--blue);text-decoration:none}} a:hover{{text-decoration:underline}}
  .num{{font-variant-numeric:tabular-nums}}
  .wrap{{max-width:1240px;margin:0 auto;padding:0 26px}}
  .mono{{font-family:ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace}}

  /* top */
  .top{{position:sticky;top:0;z-index:50;background:rgba(8,27,58,.92);backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,.12)}}
  .top-in{{max-width:1240px;margin:0 auto;padding:10px 26px;display:flex;align-items:center;gap:14px;color:#fff}}
  .brand{{display:flex;align-items:center;gap:10px;font-weight:800;letter-spacing:.02em}}
  .brand-mark{{width:26px;height:26px;border:2px solid var(--gold2);border-radius:7px;position:relative;transform:rotate(45deg)}}
  .brand-mark::after{{content:"";position:absolute;inset:6px;border:1.5px solid rgba(255,255,255,.7);border-radius:3px}}
  .top nav{{margin-left:auto;display:flex;gap:18px;font-size:12.5px;color:#c9d8f5}}
  .top nav a{{color:#c9d8f5}} .top nav a:hover{{color:#fff;text-decoration:none}}
  .top .badge{{margin-left:8px;background:rgba(200,150,60,.18);border:1px solid rgba(230,194,122,.5);color:#ffe6ad;border-radius:999px;padding:3px 10px;font-size:11px}}

  /* hero */
  .hero{{position:relative;overflow:hidden;background:
      radial-gradient(900px 420px at 12% -10%,#173b78 0%,transparent 62%),
      radial-gradient(700px 380px at 95% 8%,#1b4a8f 0%,transparent 58%),
      linear-gradient(118deg,#06162f 0%,#0a2450 48%,#123a7a 100%);
    color:#fff;padding:54px 0 44px}}
  .hero::before{{content:"";position:absolute;inset:0;opacity:.16;
    background-image:linear-gradient(rgba(255,255,255,.12) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.12) 1px,transparent 1px);
    background-size:46px 46px;mask-image:linear-gradient(90deg,#000,transparent 78%)}}
  .hero::after{{content:"Na₂CO₃";position:absolute;right:-30px;bottom:-40px;font-size:190px;font-weight:900;letter-spacing:-.06em;color:rgba(255,255,255,.045);white-space:nowrap}}
  .hero-in{{position:relative;z-index:1;display:grid;grid-template-columns:1.25fr .75fr;gap:36px;align-items:end}}
  .eyebrow{{font-size:11px;letter-spacing:.3em;color:#a9c2ef;font-weight:800}}
  .hero h1{{margin:12px 0 12px;font-size:40px;line-height:1.18;letter-spacing:.01em;font-weight:900}}
  .hero h1 em{{font-style:normal;color:#ffe0a3}}
  .hero .lede{{max-width:760px;color:#cfdcf6;font-size:15px;margin:0 0 18px}}
  .hero-chips{{display:flex;flex-wrap:wrap;gap:8px}}
  .hero-chips span{{background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.2);border-radius:999px;padding:5px 12px;font-size:12px;color:#eaf1ff}}
  .hero-chips b{{color:#fff}}
  .hero-card{{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.2);border-radius:18px;padding:18px 20px;backdrop-filter:blur(8px)}}
  .hero-card .k{{font-size:11px;letter-spacing:.18em;color:#a9c2ef;font-weight:800}}
  .hero-card .v{{font-size:21px;font-weight:900;margin:4px 0 10px}}
  .hero-card .row{{display:flex;justify-content:space-between;gap:12px;border-top:1px solid rgba(255,255,255,.16);padding:7px 0;font-size:12.5px;color:#dbe6fb}}
  .hero-card .row b{{color:#fff}}
  .hero-card .demo{{margin-top:10px;background:rgba(200,150,60,.2);border:1px solid rgba(230,194,122,.55);color:#ffe6ad;border-radius:9px;padding:7px 10px;font-size:11.5px;line-height:1.5}}

  /* sections */
  main{{padding:30px 0 70px}}
  section{{margin:30px 0}}
  .sec-head{{display:flex;align-items:flex-end;gap:16px;margin-bottom:14px;flex-wrap:wrap}}
  .sec-no{{font:800 12px/1 ui-monospace,Consolas,monospace;color:var(--gold);letter-spacing:.16em;padding-bottom:6px}}
  .sec-head h2{{margin:0;font-size:24px;line-height:1.25;color:var(--navy);font-weight:900}}
  .sec-head .desc{{margin-left:auto;color:var(--muted);font-size:12.5px;max-width:560px;text-align:right}}
  .card{{background:#fff;border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow)}}
  .pad{{padding:22px 24px}}

  /* source */
  .source-grid{{display:grid;grid-template-columns:1fr 380px;gap:18px;align-items:start}}
  .mail{{background:#fff;border:1px solid var(--line);border-radius:18px;overflow:hidden;box-shadow:var(--shadow)}}
  .mail-h{{background:linear-gradient(180deg,#f7faff,#f1f6ff);border-bottom:1px solid var(--line);padding:16px 20px}}
  .mail-h .subj{{font-size:16px;font-weight:900;color:var(--navy)}}
  .mail-h .meta{{margin-top:6px;color:var(--muted);font-size:12px;display:flex;flex-wrap:wrap;gap:14px}}
  .mail-b{{padding:18px 22px;font-size:13.5px;color:#24344d}}
  .mail-b p{{margin:0 0 10px}}
  .mail-b ol{{margin:8px 0 10px 20px;padding:0}} .mail-b li{{margin:4px 0}}
  .mail-b .sig{{margin-top:14px;padding-top:12px;border-top:1px dashed var(--line);color:var(--sub);font-size:12.5px}}
  .wechat{{background:#fff;border:1px solid var(--line);border-radius:22px;box-shadow:var(--shadow);padding:12px}}
  .wechat img{{width:100%;display:block;border-radius:16px}}
  .wechat .cap{{font-size:11.5px;color:var(--muted);text-align:center;padding:8px 4px 3px}}
  .src-note{{margin-top:12px;background:var(--soft);border:1px solid #dbe6fa;border-radius:12px;padding:11px 14px;color:var(--sub);font-size:12px}}

  /* field table */
  .legend{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}}
  .chip{{display:inline-flex;align-items:center;gap:5px;border-radius:999px;padding:2px 9px;font-size:11px;font-weight:800;border:1px solid transparent;white-space:nowrap}}
  .chip.ok{{background:var(--okbg);color:var(--ok);border-color:#b7e3c8}}
  .chip.warn{{background:var(--warnbg);color:var(--warn);border-color:#eccb8c}}
  .chip.miss{{background:var(--missbg);color:var(--miss);border-color:#f3c9c3}}
  .chip.assume{{background:var(--assumebg);color:var(--assume);border-color:#e7d9a8}}
  .chip.user{{background:#edf3ff;color:var(--blue);border-color:#c9d6ee}}
  .table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:14px}}
  table{{width:100%;border-collapse:collapse;background:#fff}}
  th,td{{text-align:left;padding:11px 12px;border-bottom:1px solid #eef2f8;vertical-align:top}}
  thead th{{background:#f4f7fd;color:#3b4a63;font-size:11.5px;font-weight:900;letter-spacing:.03em;white-space:nowrap}}
  tbody tr:last-child td{{border-bottom:none}}
  .frow.miss{{background:#fffaf0}} .frow.miss td:first-child{{box-shadow:inset 4px 0 0 #d99a00}}
  .frow.warn{{background:#fffdf5}} .frow.warn td:first-child{{box-shadow:inset 4px 0 0 #e0a92e}}
  .frow.assume{{background:#fcfdff}}
  .bucket{{display:inline-flex;width:24px;height:24px;border-radius:7px;align-items:center;justify-content:center;font:900 11px/1 ui-monospace,Consolas,monospace}}
  .bA{{background:#e8f0ff;color:var(--blue)}} .bB{{background:#f3f6fb;color:var(--sub)}}
  .flabel{{font-weight:800;color:var(--navy);min-width:110px}}
  .fnote{{font-weight:400;color:var(--muted);font-size:11px;margin-top:3px;line-height:1.5}}
  .fval{{color:var(--ink);font-weight:700;min-width:200px}}
  .fsrc{{color:var(--sub);font-size:11.5px;line-height:1.55;max-width:420px}}
  .frow.miss .fval,.frow.warn .fval{{color:#7a4a00}}

  /* gaps */
  .gaps{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}
  .gap{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:16px 18px;box-shadow:var(--shadow)}}
  .gap.must{{border-left:4px solid #d99a00}} .gap.warn{{border-left:4px solid #e0a92e}} .gap.soft{{border-left:4px solid #9db9ec}}
  .gap-top{{display:flex;align-items:center;gap:9px}}
  .gap-tag{{font:800 10px/1 ui-monospace,Consolas,monospace;color:#fff;background:var(--navy);border-radius:5px;padding:5px 7px;letter-spacing:.04em}}
  .gap h4{{margin:0;font-size:14px;color:var(--navy)}}
  .gap p{{margin:8px 0 10px;color:var(--sub);font-size:12.5px}}
  .ask{{background:var(--soft);border:1px dashed #c9d6ee;border-radius:10px;padding:9px 11px;font-size:12px;color:#24344d}}
  .ask span{{display:block;font:800 10px/1 ui-monospace,Consolas,monospace;color:var(--blue);letter-spacing:.1em;margin-bottom:4px}}

  /* gate */
  .gate-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
  .lock{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px;box-shadow:var(--shadow)}}
  .lock .n{{font:900 11px/1 ui-monospace,Consolas,monospace;color:var(--muted);letter-spacing:.1em}}
  .lock h4{{margin:6px 0 4px;font-size:13px;color:var(--navy)}}
  .lock p{{margin:0;color:var(--sub);font-size:11.5px;line-height:1.55}}
  .lock .state{{margin-top:9px;font-weight:900;font-size:11px;color:var(--miss)}}
  .lock.on .state{{color:var(--ok)}} .lock.on{{border-color:#b7e3c8;background:#fbfffd}}
  .lock.demo .state{{color:var(--gold)}}
  .gate-bar{{margin-top:12px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;background:linear-gradient(180deg,#f8fbff,#eef4ff);border:1px solid #c9d9f5;border-radius:14px;padding:12px 14px}}
  .gate-bar .bl{{font-size:12.5px;color:var(--sub)}} .gate-bar .bl b{{color:var(--miss)}}
  .btn{{display:inline-flex;align-items:center;gap:7px;border-radius:10px;border:1px solid var(--line);background:#fff;color:var(--ink);padding:9px 14px;font:800 12.5px/1 inherit;cursor:pointer;transition:.15s}}
  .btn:hover{{transform:translateY(-1px);box-shadow:var(--shadow)}}
  .btn.primary{{background:linear-gradient(180deg,#2a66d8,#1e56c8);border-color:#1e56c8;color:#fff}}
  .btn.ghost{{background:#f7faff;border-color:#c9d9f5;color:var(--blue)}}
  .btn[disabled]{{background:#e9eef7;border-color:#dbe3ef;color:#98a4b8;cursor:not-allowed;transform:none;box-shadow:none}}
  .gate-bar .btn{{margin-left:auto}}

  /* quote */
  .quote-wrap{{position:relative}}
  .quote{{position:relative;background:var(--paper);border:1px solid #e8e2d4;border-radius:6px;box-shadow:var(--shadow2);padding:40px 44px 34px;overflow:hidden}}
  .quote::before{{content:"";position:absolute;left:0;right:0;top:0;height:7px;background:linear-gradient(90deg,var(--navy),var(--blue),var(--gold))}}
  .quote::after{{content:"DEMO";position:absolute;right:-30px;top:120px;font:900 170px/1 "Arial Black",Impact,sans-serif;color:rgba(200,150,60,.07);transform:rotate(-18deg);letter-spacing:.05em;pointer-events:none}}
  .q-top{{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;border-bottom:2px solid var(--navy);padding-bottom:18px}}
  .q-brand{{display:flex;gap:13px;align-items:center}}
  .q-logo{{width:46px;height:46px;border:2px solid var(--gold);border-radius:12px;position:relative;transform:rotate(45deg);flex:0 0 auto}}
  .q-logo::after{{content:"";position:absolute;inset:10px;border:2px solid var(--navy);border-radius:4px}}
  .q-brand .co{{font-size:19px;font-weight:900;color:var(--navy);letter-spacing:.02em}}
  .q-brand .en{{font-size:9.5px;letter-spacing:.22em;color:var(--muted);font-weight:700;margin-top:2px}}
  .q-title{{text-align:right}}
  .q-title .cn{{font-size:30px;font-weight:900;letter-spacing:.22em;color:var(--navy)}}
  .q-title .en{{font-size:10px;letter-spacing:.26em;color:var(--muted);font-weight:800;margin-top:2px}}
  .q-title .tag{{display:inline-block;margin-top:8px;background:var(--warnbg);border:1px solid #eccb8c;color:var(--warn);border-radius:4px;padding:3px 9px;font-size:10px;font-weight:900;letter-spacing:.08em}}
  .q-meta{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#e8e2d4;border:1px solid #e8e2d4;margin:16px 0 18px}}
  .q-meta div{{background:#fffdf8;padding:9px 11px}}
  .q-meta .k{{font-size:9.5px;color:var(--muted);letter-spacing:.08em;font-weight:800}}
  .q-meta .v{{font-size:12px;color:var(--ink);font-weight:800;margin-top:2px}}
  .q-cust{{display:flex;justify-content:space-between;gap:16px;background:#f4f7fd;border-left:4px solid var(--blue);padding:10px 14px;margin-bottom:16px;font-size:12.5px;color:#24344d}}
  .q-cust b{{color:var(--navy)}}
  .qt-wrap{{overflow-x:auto;margin:4px 0 0;-webkit-overflow-scrolling:touch}}
  .qt{{width:100%;border-collapse:collapse;min-width:680px}}
  .qt th{{background:var(--navy);color:#fff;font-size:10.5px;letter-spacing:.04em;text-align:center;padding:9px 8px;border:1px solid #1b3b6b}}
  .qt td{{border:1px solid #dfd8c8;padding:10px 9px;font-size:12px;vertical-align:top;background:#fffdf8}}
  .qt td.c{{text-align:center}} .qt td.r{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
  .qt tr.total td{{background:#eef3fb;font-weight:900;color:var(--navy);border-top:2px solid var(--navy)}}
  .q-terms{{display:grid;grid-template-columns:1fr 1fr;gap:14px 26px;margin-top:18px}}
  .term h4{{margin:0 0 4px;font-size:11.5px;color:var(--blue);letter-spacing:.03em}}
  .term ul{{margin:0;padding-left:16px;color:#2c3a51;font-size:11.5px;line-height:1.65}}
  .pending{{margin-top:16px;background:#fff8e8;border:1px solid #ecd39a;border-radius:8px;padding:11px 14px}}
  .pending h4{{margin:0 0 5px;font-size:11.5px;color:var(--warn);letter-spacing:.04em}}
  .pending ul{{margin:0;padding-left:16px;font-size:11.5px;color:#6b4a00;line-height:1.6}}
  .q-foot{{margin-top:18px;padding-top:12px;border-top:1px dashed #d9d1c0;display:flex;justify-content:space-between;gap:16px;align-items:flex-end}}
  .q-foot .note{{font-size:10.5px;color:var(--muted);line-height:1.6;max-width:720px}}
  .stamp{{flex:0 0 auto;border:2px solid rgba(180,35,24,.55);color:rgba(180,35,24,.7);border-radius:8px;padding:7px 12px;font-size:10.5px;font-weight:900;letter-spacing:.12em;transform:rotate(-5deg)}}
  .demo-banner{{display:flex;gap:12px;align-items:center;background:linear-gradient(90deg,#fff7e2,#fffdf8);border:1px solid #ecd39a;border-left:5px solid var(--gold);border-radius:10px;padding:11px 15px;margin-bottom:14px;color:#6b4a00;font-size:12.5px}}
  .demo-banner b{{color:#8a5a00}}

  /* workflow */
  .flow{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}}
  .step{{position:relative;background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px 14px 13px;box-shadow:var(--shadow)}}
  .step .no{{font:900 10px/1 ui-monospace,Consolas,monospace;color:var(--gold);letter-spacing:.12em}}
  .step h4{{margin:6px 0 4px;font-size:13px;color:var(--navy)}}
  .step p{{margin:0;color:var(--sub);font-size:11.5px;line-height:1.55}}
  .step:not(:last-child)::after{{content:"→";position:absolute;right:-12px;top:50%;transform:translateY(-50%);color:#b8c6dd;font-weight:900}}
  .split{{display:grid;grid-template-columns:1.05fr .95fr;gap:16px}}
  .code{{background:#0b1f40;color:#d8e6ff;border-radius:14px;padding:16px 18px;font:11.5px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace;overflow:auto;box-shadow:var(--shadow)}}
  .code .k{{color:#8fb6ff}} .code .s{{color:#ffe0a3}} .code .n{{color:#9be3c0}}
  .port{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
  .port .card{{padding:15px 16px}}
  .port h4{{margin:0 0 5px;font-size:13px;color:var(--navy)}}
  .port p{{margin:0;color:var(--sub);font-size:11.5px;line-height:1.6}}

  /* refs */
  .refs{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}
  .ref{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:13px 15px;box-shadow:var(--shadow)}}
  .ref-t{{font-weight:900;color:var(--navy);font-size:12.5px}}
  .ref p{{margin:4px 0 6px;color:var(--sub);font-size:11.5px;line-height:1.55}}
  .ref a{{font-size:11px;font-weight:800}}

  .actions{{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}}
  .footer{{border-top:1px solid var(--line);background:#fff;padding:26px 0;color:var(--muted);font-size:11.5px}}
  .footer .wrap{{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}}

  @media(max-width:1000px){{
    .hero-in,.source-grid,.split{{grid-template-columns:1fr}}
    .gate-grid,.flow,.port{{grid-template-columns:repeat(2,1fr)}}
    .step:not(:last-child)::after{{display:none}}
    .hero h1{{font-size:32px}}
    .quote{{padding:28px 24px}}
    .q-meta{{grid-template-columns:repeat(2,1fr)}}
    .q-terms{{grid-template-columns:1fr}}
  }}
  @media(max-width:640px){{
    .wrap{{padding:0 16px}} .top nav{{display:none}}
    .hero h1{{font-size:27px}} .hero {{padding:34px 0 30px}}
    .gate-grid,.flow,.port,.gaps,.refs{{grid-template-columns:1fr}}
    .sec-head .desc{{margin-left:0;text-align:left}}
    .q-top{{flex-direction:column}} .q-title{{text-align:left}}
    .q-cust{{flex-direction:column;gap:4px}}
    .quote{{padding:22px 16px}}
    .qt{{min-width:640px}} .table-wrap{{overflow:auto}}
  }}
  @media print{{
    @page{{size:A4;margin:12mm}}
    body{{background:#fff}}
    .top,.hero,.actions,.demo-banner,.footer{{display:none!important}}
    main{{padding:0}}
    section{{margin:0 0 10mm}}
    .card,.quote,.gap,.ref,.step,.lock{{box-shadow:none}}
    .quote{{border:1px solid #ccc;page-break-inside:avoid}}
    .source-grid{{grid-template-columns:1fr 300px}}
    .wechat img{{max-height:520px;object-fit:contain}}
    .print-hide{{display:none!important}}
    .print-break{{page-break-before:always}}
  }}
</style>
</head>
<body>

<div class="top">
  <div class="top-in">
    <div class="brand"><span class="brand-mark"></span><span>询盘 → 报价草稿</span></div>
    <span class="badge">CASE STUDY · 纯碱</span>
    <nav>
      <a href="#source">客户原声</a>
      <a href="#fields">字段提取</a>
      <a href="#gaps">缺口</a>
      <a href="#quote">报价效果</a>
      <a href="#skill">复用方法</a>
    </nav>
  </div>
</div>

<header class="hero">
  <div class="wrap hero-in">
    <div>
      <div class="eyebrow">DOMESTIC CHEMICAL SALES · INQUIRY TO QUOTATION</div>
      <h1>把一条散装询盘，变成<br><em>可逐项确认</em>的报价草稿</h1>
      <p class="lede">纯碱 · 浮法玻璃客户案例。先提取字段、标出缺口、分清“必须补充”与“可按假设”，
      等销售自己确认单价与税费/运费口径后，系统才排版报价。价格不是系统给的，是你签的字。</p>
      <div class="hero-chips">
        <span><b>产品</b> 重质纯碱</span>
        <span><b>客户</b> 江苏盐城华宇玻璃（简称）</span>
        <span><b>试单</b> 200 吨</span>
        <span><b>月用量</b> 约 800 吨</span>
        <span><b>案例日期</b> 2026-10-19</span>
      </div>
    </div>
    <aside class="hero-card">
      <div class="k">当前状态</div>
      <div class="v">待补 3 项 · 不可生成</div>
      <div class="row"><span>客户全称 / 税号</span><b>待确认</b></div>
      <div class="row"><span>税费 / 运费口径</span><b>待你选择</b></div>
      <div class="row"><span>确认单价</span><b>待你填写</b></div>
      <div class="row"><span>报价数量</span><b>200 吨</b></div>
      <div class="demo">本页报价区使用 <b>1,180 元/吨</b> 的演示输入，仅展示版式；系统没有生成、推荐或推导这个价格。</div>
    </aside>
  </div>
</header>

<main class="wrap">

  <section id="source">
    <div class="sec-head">
      <div class="sec-no">01</div>
      <h2>客户原声：一封邮件 + 一张微信截图</h2>
      <div class="desc">同一客户、两个渠道。微信给数量与指标，邮件补地点、发票、包装与交期；冲突处不合并，保留原话。</div>
    </div>
    <div class="source-grid">
      <article class="mail">
        <div class="mail-h">
          <div class="subj">重质纯碱询价（华宇玻璃）——补充几点</div>
          <div class="meta"><span>发件人：王经理 &lt;wangjian@huayuglass.com&gt;</span><span>2026-10-19 14:32</span><span>收件人：销售部</span></div>
        </div>
        <div class="mail-b">
          <p>您好：补充几点，方便您报价：</p>
          <ol>
            <li>交货地点：江苏省盐城市亭湖区 华宇玻璃一期厂区（需提前一天预约卸车，厂区有地磅）。</li>
            <li>我们是增值税一般纳税人，需要 13% 增值税专用发票。</li>
            <li>试单希望 10 月底前到货；后续按月度计划滚动下单。</li>
            <li>包装请用 1000kg 吨包，栈板 + 缠膜，方便叉车卸货。</li>
            <li>请注明报价有效期与付款条件，走内部比价时这两项要一起报。</li>
          </ol>
          <p>进厂需先提供 COA、MSDS 与相关资质文件（纯碱非危化品，但厂区安环要备案）。如价格合适，可先安排小批量试供，再签年度框架。</p>
          <p>开票抬头我让财务整理好发您，先按我们厂名报即可。</p>
          <div class="sig">江苏盐城华宇玻璃　采购部　王经理<br>手机 138****（微信同号）</div>
        </div>
      </article>
      <div>
        <div class="wechat">
          <img src="data:image/png;base64,{b64}" alt="华宇玻璃王经理微信询盘截图（案例演示）">
          <div class="cap">微信截图 · 6 条消息 + 1 张比价表 · 案例演示</div>
        </div>
        <div class="src-note"><b>OCR 脏数据：</b>比价表最后一行写作“1?30”，字迹被涂改/遮挡，无法确认是 1,130、1,230 还是 1,630。系统只把它列入“无法辨认”，不猜、不锚定。</div>
      </div>
    </div>
  </section>

  <section id="fields">
    <div class="sec-head">
      <div class="sec-no">02</div>
      <h2>标准字段：逐项确认，缺失黄色高亮</h2>
      <div class="desc">A 类缺一项就不能报价；B 类可带“我方假设 · 待客户确认”先准备。每条都保留出处原句，方便回头核对。</div>
    </div>
    <div class="legend">
      <span class="chip ok">已提取</span>
      <span class="chip warn">待客户确认 / 缺失</span>
      <span class="chip assume">我方假设</span>
      <span class="chip user">待你填写 / 选择</span>
      <span class="chip" style="background:#eef3fb;color:#1e56c8;border-color:#c9d6ee">A = 必须补充</span>
      <span class="chip" style="background:#f3f6fb;color:#53627a;border-color:#dfe6f1">B = 可按假设</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th style="width:46px">桶</th><th style="width:140px">字段</th><th style="width:250px">提取值</th><th>出处 / 判定说明</th><th style="width:110px">状态</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <div class="src-note" style="margin-top:12px"><b>数量口径：</b>试单 200 吨，月用量约 800 吨。报价按 <b>试单 200 吨</b> 计算；月用量只做执行口径说明，不能拿来摊薄首单价格。</div>
  </section>

  <section id="gaps">
    <div class="sec-head">
      <div class="sec-no">03</div>
      <h2>缺口不是一句“请补充资料”</h2>
      <div class="desc">每个 A 类缺口，给一句能直接发给客户的话；B 类缺口写清假设值与影响。</div>
    </div>
    <div class="gaps">{gaps}</div>
  </section>

  <section id="gate">
    <div class="sec-head">
      <div class="sec-no">04</div>
      <h2>四道锁：价格与口径必须由销售确认</h2>
      <div class="desc">系统只做算术：数量 × 单价、价税拆分、金额大写与版式。改价会让已生成草稿标“已过期”。</div>
    </div>
    <div class="gate-grid">
      <div class="lock">
        <div class="n">LOCK 01</div><h4>A 类字段齐全</h4>
        <p>产品、规格、数量、交货地点、客户全称。当前客户全称/税号仍待确认。</p>
        <div class="state">✕ 还差 1 项</div>
      </div>
      <div class="lock">
        <div class="n">LOCK 02</div><h4>税费口径</h4>
        <p>含税 13% 专票 / 不含税 / 普票。客户邮件提到 13% 专票，但仍需我方点选。</p>
        <div class="state">✕ 待你选择</div>
      </div>
      <div class="lock">
        <div class="n">LOCK 03</div><h4>运费口径</h4>
        <p>到厂价含运费 / 出厂价不含 / 送到站。客户说送到厂区，但不能从询盘单向推断。</p>
        <div class="state">✕ 待你选择</div>
      </div>
      <div class="lock demo">
        <div class="n">LOCK 04</div><h4>单价 + 确认勾选</h4>
        <p>单价空着就是空着；填入后必须勾选“我确认该单价为我方销售价格”。</p>
        <div class="state">◐ 演示区已由销售填入</div>
      </div>
    </div>
    <div class="gate-bar">
      <div class="bl">按钮状态：<b>生成报价草稿（还差 3 项）</b> · 灰</div>
      <button class="btn" disabled>生成报价草稿（还差 3 项）</button>
    </div>
    <div class="src-note" style="margin-top:10px">演示区展示的是“销售已补全客户全称 + 选择含税 13% 专票 + 到厂价 + 填入 1,180 元/吨”之后的版式效果。真实流程里，这四步都必须由人完成。</div>
  </section>

  <section id="quote" class="print-break">
    <div class="sec-head">
      <div class="sec-no">05</div>
      <h2>报价草稿效果：一页纸，七个要素</h2>
      <div class="desc">商品明细、价格与口径、数量与执行、交付、付款、有效期、待确认事项。以下为演示价版式。</div>
    </div>
    <div class="demo-banner"><b>演示说明</b><span>本区单价 <b>1,180 元/吨</b> 由演示者手动填入，仅用于展示报价版式；不是系统建议价，也不是成交价。正式使用时请清空后填入你自己的确认价。</span></div>
    <div class="quote-wrap">
      <article class="quote" id="quotePaper">
        <div class="q-top">
          <div class="q-brand">
            <div class="q-logo"></div>
            <div><div class="co">鲁盐化工（山东）有限公司</div><div class="en">LUYAN CHEMICAL · SODA ASH DIVISION</div></div>
          </div>
          <div class="q-title"><div class="cn">报 价 单</div><div class="en">QUOTATION</div><div class="tag">草稿 · 待我方审阅</div></div>
        </div>
        <div class="q-meta">
          <div><div class="k">报价单号</div><div class="v">QT-20261019-01</div></div>
          <div><div class="k">报价日期</div><div class="v">2026-10-19</div></div>
          <div><div class="k">有效期至</div><div class="v">2026-10-26（7 天）</div></div>
          <div><div class="k">币种 / 单位</div><div class="v">CNY · 元/吨</div></div>
        </div>
        <div class="q-cust"><div><b>致：</b>江苏盐城华宇玻璃有限公司（王经理）</div><div><b>我方联系人：</b>内贸部 李经理　138****0000</div></div>
        <div class="qt-wrap"><table class="qt">
          <thead><tr><th style="width:40px">序号</th><th>产品名称</th><th>规格 / 牌号</th><th style="width:64px">数量</th><th style="width:52px">单位</th><th style="width:96px">单价（元）</th><th style="width:112px">金额（元）</th></tr></thead>
          <tbody>
            <tr><td class="c">1</td><td><b>重质纯碱</b></td><td>Na2CO3 ≥ 99.2%；Fe2O3 ≤ 0.003%；烧失量 ≤ 0.5%；180 目筛余 ≤ 5%</td><td class="c">200</td><td class="c">吨</td><td class="r">1,180.00<br><small>含税</small></td><td class="r">236,000.00<br><small>含税</small></td></tr>
            <tr class="total"><td colspan="6" style="text-align:right">价税合计（含 13% 增值税）</td><td class="r">¥ 236,000.00</td></tr>
          </tbody>
        </table></div>
        <div class="q-terms">{terms_html}</div>
        <div class="pending"><h4>七、待客户确认事项（不藏假设）</h4><ul>{pending}</ul></div>
        <div class="q-foot">
          <div class="note">本报价为草稿，未经我方销售负责人确认不得对外发送。单价、税率、运费口径均由业务人员填写并确认；系统未生成、未推荐、未调整任何商业价格。<br>含税金额 236,000.00 元 = 不含税 208,849.56 元 + 税额 27,150.44 元。</div>
          <div class="stamp">草稿 · 非最终报价</div>
        </div>
      </article>
    </div>
    <div class="actions print-hide">
      <button class="btn primary" onclick="window.print()">打印 / 存 PDF</button>
      <button class="btn ghost" onclick="copyQuote()">复制报价全文</button>
      <button class="btn ghost" onclick="downloadQuote()">下载报价 .md</button>
      <a class="btn ghost" href="询盘工作台_华宇玻璃纯碱.html">打开交互工作台 →</a>
    </div>
  </section>

  <section id="skill">
    <div class="sec-head">
      <div class="sec-no">06</div>
      <h2>这套方法怎么复用到别的化工品</h2>
      <div class="desc">换产品只换“产品画像 + 提取词表 + 报价条款”；字段结构、A/B 分桶、价格闸门、输出格式不变。</div>
    </div>
    <div class="flow">
      <div class="step"><div class="no">STEP 01</div><h4>收料</h4><p>微信截图、邮件、PDF/Excel 需求表；先编号，保留原话，不替客户合并冲突。</p></div>
      <div class="step"><div class="no">STEP 02</div><h4>抽字段</h4><p>10 个标准字段 + 税费/运费口径线索；每条带出处、置信度、状态。</p></div>
      <div class="step"><div class="no">STEP 03</div><h4>分两桶</h4><p>A 类必须补齐；B 类可按假设，但每条都写“我方假设 · 待客户确认”。</p></div>
      <div class="step"><div class="no">STEP 04</div><h4>过闸门</h4><p>A 类齐、口径选、单价填、确认勾选；缺一项按钮就是灰的。</p></div>
      <div class="step"><div class="no">STEP 05</div><h4>出草稿</h4><p>七要素报价 + 复制/导出/打印 + 转合同审阅；改任何值标“已过期”。</p></div>
    </div>
    <div class="split" style="margin-top:16px">
      <div class="card pad">
        <h3 style="margin:0 0 8px;color:var(--navy);font-size:16px">产品画像：把“行话”固化成配置</h3>
        <p style="margin:0 0 10px;color:var(--sub);font-size:12.5px">纯碱的别名、标准、验收指标、包装、单证、税率、HS 编码写进一个 JSON；换钛白粉、SBS、甲醇时复制一份改字段即可。价格字段永远不写进去。</p>
        <pre class="code" style="margin:0">{e(profile_json)}</pre>
      </div>
      <div class="card pad">
        <h3 style="margin:0 0 8px;color:var(--navy);font-size:16px">跨 Agent 的可移植性</h3>
        <div class="port">
          <div class="card"><h4>Claude / Codex</h4><p>把整个目录放进 skills 目录，SKILL.md 的 frontmatter 提供 name / description；脚本用 python 直接跑。</p></div>
          <div class="card"><h4>ChemClaw / WorkBuddy</h4><p>若不支持技能目录，把 SKILL.md 作为系统提示词，附上 examples 的输入输出；脚本仍可独立运行。</p></div>
          <div class="card"><h4>纯人工 / Excel</h4><p>不跑脚本也能用：照 02 表逐项填，03 表看缺口，05 表按七要素写；价格列永远手填。</p></div>
        </div>
        <div class="src-note" style="margin-top:12px"><b>硬边界：</b>没有默认价、参考价、区间价、建议价、历史价回填。任何“先填一个看看效果”的占位价都不允许进入正式报价。</div>
      </div>
    </div>
  </section>

  <section id="refs">
    <div class="sec-head">
      <div class="sec-no">07</div>
      <h2>研究依据与边界</h2>
      <div class="desc">产品标准、税号、包装与物流常识用于“把话说专业”；公开行情只解释有效期，不进入报价。</div>
    </div>
    <div class="refs">{refs_html}</div>
    <div class="src-note" style="margin-top:12px"><b>案例声明：</b>本页客户、联系人、公司、价格与交易均为教学演示虚构；公开行情引用只作背景，不构成报价建议。实际报价前请核对最新标准、企业资质、税率与合同条款。</div>
  </section>

</main>

<footer class="footer">
  <div class="wrap">
    <div>询盘 → 报价草稿 · 化工品内贸销售技能 · v1.1</div>
    <div>核心原则：价格是销售的决定，不是系统的输出。</div>
  </div>
</footer>

<script>
const QUOTE_MD = {json.dumps(quote_md, ensure_ascii=False)};
async function copyQuote(){{
  try{{ await navigator.clipboard.writeText(QUOTE_MD); alert('报价全文已复制'); }}
  catch(e){{ const ta=document.createElement('textarea'); ta.value=QUOTE_MD; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); alert('报价全文已复制'); }}
}}
function downloadQuote(){{
  const blob = new Blob([QUOTE_MD], {{type:'text/markdown;charset=utf-8'}});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = '报价草稿_华宇玻璃纯碱_演示价1180.md'; a.click(); URL.revokeObjectURL(a.href);
}}
</script>
</body>
</html>
"""
    OUT.write_text(html_doc, encoding="utf-8")
    print(f"  ← {OUT}（{OUT.stat().st_size/1024:.1f} KB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
