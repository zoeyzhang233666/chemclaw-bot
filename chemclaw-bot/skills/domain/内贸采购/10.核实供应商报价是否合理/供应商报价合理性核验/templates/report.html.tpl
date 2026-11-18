<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{
  --ink:#0f172a; --ink2:#334155; --ink3:#64748b; --line:#e2e8f0; --bg:#f6f8fb; --card:#ffffff;
  --brand:#1d4ed8; --brand2:#3b82f6; --ok:#0f9d76; --warn:#d97706; --bad:#dc2626; --neutral:#6366f1;
  --shadow:0 1px 2px rgba(15,23,42,.06),0 8px 24px rgba(15,23,42,.06);
}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:var(--ink);background:var(--bg);font-size:14px;line-height:1.6}
a{color:var(--brand);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1280px;margin:0 auto;padding:0 20px}
header.topbar{background:linear-gradient(120deg,#0b1f4d 0%,#1d4ed8 60%,#3b82f6 100%);color:#fff;padding:22px 0 18px}
header.topbar .wrap{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end;justify-content:space-between}
header h1{margin:0 0 4px;font-size:22px;letter-spacing:.3px}
header .sub{opacity:.86;font-size:13px}
.badges{display:flex;gap:8px;flex-wrap:wrap}
.badge{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.3);border-radius:999px;padding:3px 11px;font-size:12px}
.badge.test{background:#fbbf24;border-color:#fbbf24;color:#422006;font-weight:700}
nav.tabs{position:sticky;top:0;z-index:30;background:rgba(255,255,255,.96);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
nav.tabs .wrap{display:flex;gap:4px;overflow-x:auto}
nav.tabs button{border:0;background:none;padding:13px 14px;font-size:14px;color:var(--ink3);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap}
nav.tabs button.on{color:var(--brand);border-bottom-color:var(--brand);font-weight:700}
main{padding:22px 0 60px}
section{display:none}
section.on{display:block}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);padding:18px 20px;margin-bottom:16px}
.card h2{margin:0 0 4px;font-size:16px}
.card h3{margin:14px 0 8px;font-size:14px;color:var(--ink2)}
.card .hint{color:var(--ink3);font-size:12.5px;margin:0 0 12px}
.grid{display:grid;gap:16px}
.g2{grid-template-columns:1fr 1fr}
.g3{grid-template-columns:repeat(3,1fr)}
.g4{grid-template-columns:repeat(4,1fr)}
@media(max-width:960px){.g2,.g3,.g4{grid-template-columns:1fr}}
.kpi{background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px 16px;box-shadow:var(--shadow)}
.kpi .lab{font-size:12px;color:var(--ink3)}
.kpi .val{font-size:26px;font-weight:800;letter-spacing:.5px;margin:4px 0 2px}
.kpi .meta{font-size:12px;color:var(--ink3)}
.kpi.bad .val{color:var(--bad)}
.kpi.ok .val{color:var(--ok)}
.kpi.brand .val{color:var(--brand)}
.kpi.warn .val{color:var(--warn)}
table{width:100%;border-collapse:collapse;font-size:13px;table-layout:fixed}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;word-break:break-word;overflow-wrap:anywhere}
th{background:#f8fafc;color:var(--ink2);font-weight:700;font-size:12.5px;position:sticky;top:0}
tbody tr:hover{background:#f8fbff}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.tag{display:inline-block;border-radius:6px;padding:1px 8px;font-size:12px;font-weight:700;white-space:nowrap}
.t-ok{background:#e7f7f1;color:#0b7a5b}
.t-warn{background:#fef3e2;color:#a45a06}
.t-bad{background:#fdeaea;color:#b91c1c}
.t-neutral{background:#eef0ff;color:#4338ca}
.t-muted{background:#f1f5f9;color:#475569}
.alert{border-radius:12px;padding:12px 14px;margin:10px 0;font-size:13px;border:1px solid}
.alert.mismatch{background:#fff7ed;border-color:#fdba74;color:#7c2d12}
.alert.mismatch b{color:#b45309}
.alert.gap{background:#f1f5f9;border-color:#cbd5e1;color:#334155}
.alert.test{background:#fffbeb;border-color:#fcd34d;color:#713f12}
.alert.info{background:#eff6ff;border-color:#bfdbfe;color:#1e3a8a}
.rangebar{position:relative;height:58px;margin:26px 6px 40px}
.rangebar .track{position:absolute;left:0;right:0;top:18px;height:14px;border-radius:8px;background:linear-gradient(90deg,#dbeafe,#93c5fd,#60a5fa);}
.rangebar .mid{position:absolute;top:12px;width:2px;height:26px;background:#1e40af;}
.rangebar .mk{position:absolute;top:-4px;width:0;height:0;transform:translateX(-50%)}
.rangebar .mk i{position:absolute;left:-1px;top:26px;width:2px;height:16px;background:#dc2626}
.rangebar .mk b{position:absolute;left:-52px;top:-14px;width:104px;text-align:center;font-size:11.5px;color:#b91c1c;white-space:nowrap}
.rangebar .tick{position:absolute;top:36px;font-size:11.5px;color:var(--ink3);transform:translateX(-50%);white-space:nowrap}
.rangebar .cap{position:absolute;top:-16px;left:0;font-size:12px;color:var(--ink3)}
.pctbar{position:relative;height:22px;background:#eef2f7;border-radius:999px;overflow:hidden}
.pctbar .fill{position:absolute;left:0;top:0;bottom:0;background:linear-gradient(90deg,#93c5fd,#2563eb)}
.pctbar .qq{position:absolute;left:0;right:0;top:0;bottom:0;display:flex;align-items:center;justify-content:center;font-size:11.5px;font-weight:700;color:#0f172a}
.chart{width:100%;height:360px}
.chart.sm{height:280px}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 10px}
.chip{border:1px solid var(--line);background:#fff;border-radius:999px;padding:5px 12px;cursor:pointer;font-size:12.5px;color:var(--ink2)}
.chip.on{background:var(--brand);color:#fff;border-color:var(--brand);font-weight:700}
.timeline{position:relative;margin:6px 0 0;padding-left:18px;border-left:2px solid #dbeafe}
.tl-item{position:relative;padding:0 0 14px 8px;cursor:pointer}
.tl-item::before{content:"";position:absolute;left:-27px;top:6px;width:12px;height:12px;border-radius:50%;background:#fff;border:3px solid #3b82f6}
.tl-item.hot::before{border-color:#dc2626}
.tl-item .d{font-size:12px;color:var(--ink3);font-variant-numeric:tabular-nums}
.tl-item .t{font-weight:700;margin:1px 0 2px}
.tl-item .f{font-size:12.5px;color:var(--ink2)}
.tl-item .pe{font-size:12px;color:#b45309;margin-top:2px}
.srcs{font-size:12px;color:var(--ink3);word-break:break-all}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:820px){.two{grid-template-columns:1fr}}
code,pre{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}
pre{background:#0b1220;color:#e2e8f0;border-radius:10px;padding:12px 14px;overflow:auto;font-size:12.5px;line-height:1.55}
.mono{font-variant-numeric:tabular-nums}
footer{color:var(--ink3);font-size:12px;text-align:center;padding:18px 0 34px}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--ink3);margin:4px 0 0}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;vertical-align:middle}
tbody td.wrapcell{max-width:420px}
.small{font-size:12px;color:var(--ink3)}
.sec-title{font-size:13px;font-weight:800;color:var(--ink2);letter-spacing:.4px;margin:2px 0 8px;text-transform:none}
</style>
</head>
<body>
<header class="topbar">
  <div class="wrap">
    <div>
      <h1>__H1__</h1>
      <div class="sub">__SUBTITLE__</div>
    </div>
    <div class="badges">__BADGES__</div>
  </div>
</header>
<nav class="tabs"><div class="wrap" id="tabs"></div></nav>
<main class="wrap" id="main">__SECTIONS__</main>
<footer>__FOOTER__</footer>
<script>__ECHARTS__</script>
<script>__DATA__</script>
<script>__APP__</script>
</body>
</html>
