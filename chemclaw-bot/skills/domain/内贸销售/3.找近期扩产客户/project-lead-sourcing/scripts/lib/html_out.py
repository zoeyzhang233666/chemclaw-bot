# -*- coding: utf-8 -*-
"""chem-lead-sourcing · 交互式 HTML 交付物生成模块（产品无关，纯标准库）。

入口：
    build_html(cfg: dict, leads: list[dict], out_path: str) -> str

设计要点（与 docs/INTERFACE.md §3 / §5 / §6 对齐）：
- 单文件自包含：CSS/JS 全内联，无外链 CDN、无网络依赖，离线双击即可打开。
- 模块内**不出现任何具体产品名**：产品名 / 地区 / 窗口月数 / 生成日全部来自 cfg；
  「{产品}与该项目的关系」「找客户最近的切入点」话术按 `产品角色` + `建设阶段` 通用分档。
- 派生字段（lane / lane_id / 用量强度 / 销售时点 / 时点理由 / 优先级 / 需求性质 / 抽检结论）
  一律用 `.get(k, 默认值)` 读取：新项目在 merge 之前可能还没有这些字段，缺字段不能崩。
- 安全：注入 HTML 的文本全部 `_esc()`；内嵌 <script> 的 JSON 额外转义 `</`、`<!--`、`-->`、
  U+2028/2029；来源 URL 走 http/https 白名单，`javascript:` 之类一律拦截并降级为「未核实」。
"""

import datetime
import json
import os
import re

# ---------------- 词表与默认值 ----------------
# 销售时点标准词表：由方法论（merge 阶段）固定，与具体产品无关。
# 数据里若出现词表之外的新值时，前端会自动追加到筛选条，不会崩、也不会被静默丢掉。
TIMINGS = ('现在就该联系', '3-6个月后再联系', '仅需关注')
TIMING_ORDER = {t: i for i, t in enumerate(TIMINGS)}
PRIORITY_ORDER = {'高': 3, '中': 2, '低': 1}
CONFIDENCE_ORDER = {'高': 3, '中': 2, '低': 1}
# 「在建以上」= 建设阶段已进入施工/试车/投产 的口径（按阶段名启发式判定，不依赖单一产品的阶段词）
STARTED_RE = re.compile(r'在建|施工|建设|试车|试生产|投产|达产')

DISCLOSED = '未披露'
NOT_ESTIMABLE = '无法估算'
UNVERIFIED = '未核实'
UNDECIDED = '未判定'
NO_ROLE = '未分类'
NO_LANE = '未分类'
NO_INTENSITY = '未评估'

_URL_RE = re.compile(r'^https?://[^\s]+$', re.IGNORECASE)


# ---------------- 基础小工具 ----------------
def _esc(v):
    """HTML 转义（文本与属性通用）。"""
    s = '' if v is None else str(v)
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
             .replace('"', '&quot;').replace("'", '&#39;'))


def _txt(v, default=DISCLOSED):
    """安全取文本：None / 空串 / 全空白 → default。"""
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _as_int(v, default=0):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


def _safe_url(u):
    """URL 白名单：只放行 http/https，其余（javascript:、data:、file: 等）返回空串。"""
    s = _txt(u, '')
    return s if _URL_RE.match(s) else ''


def _json_for_script(obj):
    """把 Python 对象序列化成可安全内嵌 <script> 的 JSON 字面量。"""
    s = json.dumps(obj, ensure_ascii=False)
    s = s.replace('</', '<\\/')            # 防止 </script> 提前闭合脚本
    s = s.replace('<!--', '<\\u0021--')    # 防止 HTML 注释解析开始
    s = s.replace('-->', '--\\u003e')      # 防止 HTML 注释解析结束
    s = s.replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')  # JS 行分隔符
    return s


def _days_in_month(year, month):
    if month == 12:
        nxt = datetime.date(year + 1, 1, 1)
    else:
        nxt = datetime.date(year, month + 1, 1)
    return (nxt - datetime.timedelta(days=1)).day


def _add_months(ymd, n):
    """YYYY-MM-DD 加 n 个月（用于算窗口结束日）；无法解析时返回空串。"""
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', _txt(ymd, ''))
    if not m:
        return ''
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not 1 <= mo <= 12:
        return ''
    total = y * 12 + (mo - 1) + _as_int(n, 0)
    y2, mo2 = divmod(total, 12)
    mo2 += 1
    return '%04d-%02d-%02d' % (y2, mo2, min(d, _days_in_month(y2, mo2)))


def _star_count(v):
    return str(v or '').count('★')


def _intensity_rank(r):
    """用量强度排序权重：优先用 merge 写入的数值 `_intensity`，否则数星星。"""
    raw = r.get('_intensity')
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    return _star_count(r.get('用量强度'))


# ---------------- cfg 视图（只保留交付物真正要用的字段） ----------------
def _cfg_view(cfg):
    product = cfg.get('product') or {}
    region = cfg.get('region') or {}
    months = _as_int(cfg.get('window_months'), 6)
    today = _txt(cfg.get('today'), '')
    return {
        'product': {
            'name': _txt(product.get('name'), '本产品'),
            'formula': _txt(product.get('formula'), ''),
            'aliases': [_txt(a, '') for a in (product.get('aliases') or []) if _txt(a, '')],
            'grades': [_txt(g, '') for g in (product.get('grades') or []) if _txt(g, '')],
            # 产品角色词表由 cfg 提供；前端 chip 与话术分档都以此为准，不写死
            'roles_vocab': [_txt(x, '') for x in (product.get('roles_vocab') or []) if _txt(x, '')],
        },
        'region': {
            'name': _txt(region.get('name'), '全部地区'),
            'provinces': [_txt(x, '') for x in (region.get('provinces') or []) if _txt(x, '')],
        },
        'window_months': months,
        'today': today,
        'window_end': _add_months(today, months) if today else '',
        'stages_vocab': [_txt(x, '') for x in (cfg.get('stages_vocab') or []) if _txt(x, '')],
        'source_types_vocab': [_txt(x, '') for x in (cfg.get('source_types_vocab') or []) if _txt(x, '')],
    }


# ---------------- 企业聚合（企业表视图用） ----------------
def _rollup_companies(leads):
    """按公司聚合；所有字段用 .get() 兜底，缺字段不崩。"""
    comp = {}
    for r in leads:
        if not isinstance(r, dict):
            continue
        name = _txt(r.get('公司'), DISCLOSED)
        c = comp.get(name)
        if c is None:
            c = comp[name] = {
                '公司': name,
                '省市': _txt(r.get('省市'), DISCLOSED),
                'lanes': [],
                '项目数': 0,
                '在建以上': 0,
                '用量强度': _txt(r.get('用量强度'), NO_INTENSITY),
                '最大优先级': '',
                '置信度': '',
                '销售时点': '',
                '_intensity': -1,
                '_prio': -1,
                '_conf': -1,
                '_timing': len(TIMINGS) + 1,
            }
        prov = _txt(r.get('省市'), '')
        if prov and c['省市'] == DISCLOSED:
            c['省市'] = prov
        lane = _txt(r.get('lane'), NO_LANE)
        if lane not in c['lanes']:
            c['lanes'].append(lane)
        c['项目数'] += 1
        if STARTED_RE.search(_txt(r.get('建设阶段'), '')):
            c['在建以上'] += 1
        rank = _intensity_rank(r)
        if rank > c['_intensity']:
            c['_intensity'] = rank
            c['用量强度'] = _txt(r.get('用量强度'), NO_INTENSITY)
        prio = PRIORITY_ORDER.get(_txt(r.get('优先级'), ''), -1)
        if prio > c['_prio']:
            c['_prio'] = prio
            c['最大优先级'] = _txt(r.get('优先级'), '')
        conf = CONFIDENCE_ORDER.get(_txt(r.get('置信度'), ''), -1)
        if conf > c['_conf']:
            c['_conf'] = conf
            c['置信度'] = _txt(r.get('置信度'), '')
        tm = TIMING_ORDER.get(_txt(r.get('销售时点'), ''), len(TIMINGS) + 1)
        if tm < c['_timing']:
            c['_timing'] = tm
            c['销售时点'] = _txt(r.get('销售时点'), '')

    out = []
    for c in comp.values():
        c['板块'] = '、'.join(sorted(c['lanes']))
        c.pop('lanes', None)
        c['最大优先级'] = c['最大优先级'] or UNDECIDED
        c['置信度'] = c['置信度'] or UNDECIDED
        c['销售时点'] = c['销售时点'] or UNDECIDED
        out.append(c)
    # 排序：先按销售时点（越早越前），再按最高优先级，最后按公司名
    out.sort(key=lambda c: (c['_timing'], -c['_prio'], c['公司']))
    return out


def _payload_lead(r):
    """深拷贝一条线索用于内嵌：不改调用方的数据，并清洗来源 URL。"""
    out = {}
    for k, v in r.items():
        out[k] = v
    out['来源'] = _safe_url(out.get('来源'))
    return out


# ---------------- 页面模板 ----------------
# 说明：模板用 __TOKEN__ 占位，最后一次性 re.sub 替换（用函数式替换，避免回填被二次解析）。
_TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{
  --now:#0f7b3f; --nowbg:#e7f6ec; --soon:#a9680a; --soonbg:#fdf3dd; --watch:#5b6572; --watchbg:#eef1f4;
  --ink:#16202b; --muted:#68727e; --line:#e2e7ec; --brand:#1f4e79; --bg:#f6f8fa;
}
*{box-sizing:border-box}
body{margin:0;font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;color:var(--ink);background:var(--bg)}
a{color:var(--brand);text-decoration:none}
a:hover{text-decoration:underline}
header{background:linear-gradient(135deg,#1f4e79,#2d6fa8);color:#fff;padding:20px 26px 18px}
h1{margin:0 0 4px;font-size:20px;font-weight:650;letter-spacing:.3px}
.sub{opacity:.85;font-size:12.5px}
.askbar{margin-top:14px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;background:rgba(255,255,255,.13);
  border:1px solid rgba(255,255,255,.25);border-radius:10px;padding:9px 11px;max-width:1180px}
.askbar label{font-size:12px;opacity:.9}
.askbar input,.askbar select{font:inherit;font-size:12.5px;padding:5px 9px;border-radius:6px;border:1px solid rgba(255,255,255,.35);
  background:rgba(255,255,255,.95);color:var(--ink)}
.askbar input#q-product{width:110px}.askbar input#q-region{width:96px}.askbar input#q-horizon{width:78px}
.askbar input#q-today{width:104px}
.btn{cursor:pointer;border:0;border-radius:6px;padding:6px 14px;font:inherit;font-size:12.5px;font-weight:600;
  background:#fff;color:var(--brand)}
.btn:hover{background:#eaf2fa}
.btn.ghost{background:rgba(255,255,255,.16);color:#fff;border:1px solid rgba(255,255,255,.4)}
.wrap{padding:18px 26px 60px;max-width:1500px}
.kpis{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}
.kpi{background:#fff;border:1px solid var(--line);border-radius:10px;padding:11px 16px;min-width:132px;flex:1}
.kpi .n{font-size:24px;font-weight:700;line-height:1.2}
.kpi .l{font-size:12px;color:var(--muted)}
.kpi.now .n{color:var(--now)}.kpi.soon .n{color:var(--soon)}.kpi.watch .n{color:var(--watch)}
.filters{background:#fff;border:1px solid var(--line);border-radius:10px;padding:11px 14px;margin-bottom:14px;
  display:flex;flex-wrap:wrap;gap:16px;align-items:center}
.fgroup{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.fgroup>.fl{font-size:12px;color:var(--muted);margin-right:2px}
.chip{cursor:pointer;user-select:none;border:1px solid var(--line);background:#fff;border-radius:999px;
  padding:3px 12px;font-size:12.5px;color:var(--ink)}
.chip:hover{border-color:#b9c6d4}
.chip.on{background:var(--brand);border-color:var(--brand);color:#fff}
.chip.now.on{background:var(--now);border-color:var(--now)}
.chip.soon.on{background:var(--soon);border-color:var(--soon)}
.chip.watch.on{background:var(--watch);border-color:var(--watch)}
.toolbar{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:4px 0 12px;flex-wrap:wrap}
.views{display:flex;gap:0;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#fff}
.views button{cursor:pointer;border:0;background:#fff;font:inherit;font-size:13px;padding:7px 18px;color:var(--muted)}
.views button.on{background:var(--brand);color:#fff;font-weight:600}
.qbox{font:inherit;font-size:12.5px;padding:6px 10px;border-radius:7px;border:1px solid var(--line);background:#fff;
  color:var(--ink);min-width:250px}
.count{font-size:12.5px;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px}
.month{grid-column:1/-1;display:flex;align-items:center;gap:10px;margin:14px 0 2px}
.month .mt{font-size:15px;font-weight:700;color:var(--brand)}
.month .mn{font-size:12px;color:var(--muted)}
.month:after{content:"";flex:1;height:1px;background:var(--line)}
.card{background:#fff;border:1px solid var(--line);border-left:4px solid var(--watch);border-radius:10px;
  padding:12px 14px;cursor:pointer;transition:.12s;box-shadow:0 1px 2px rgba(16,32,48,.03)}
.card:hover{box-shadow:0 4px 14px rgba(16,32,48,.10);transform:translateY(-1px)}
.card.now{border-left-color:var(--now)}.card.soon{border-left-color:var(--soon)}
.card .co{font-weight:650;font-size:14px;margin-bottom:2px}
.card .prj{font-size:12.5px;color:#33404d;margin-bottom:7px}
.card .tags{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:7px}
.tag{font-size:11px;border-radius:5px;padding:1px 7px;background:#f0f3f6;color:#4b5563;border:1px solid #e6eaee}
.tag.stage{background:#eef4fb;color:var(--brand);border-color:#d8e6f5}
.tag.role{background:#f4eefb;color:#6b3fa0;border-color:#e6dcf5}
.tag.t-now{background:var(--nowbg);color:var(--now);border-color:#bfe4cd}
.tag.t-soon{background:var(--soonbg);color:var(--soon);border-color:#f0dca8}
.card .row{font-size:12px;color:var(--muted);display:flex;gap:6px;margin-top:3px}
.card .row b{color:#3a4552;font-weight:600}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{padding:8px 10px;text-align:left;font-size:12.5px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#f2f6fa;color:var(--brand);font-weight:650;font-size:12px;white-space:nowrap;position:sticky;top:0;z-index:2}
tbody tr{cursor:pointer}
tbody tr:hover{background:#f7fafd}
td.c{text-align:center;white-space:nowrap}
.pill{display:inline-block;font-size:11px;border-radius:999px;padding:1px 9px;font-weight:600}
.pill.now{background:var(--nowbg);color:var(--now)}
.pill.soon{background:var(--soonbg);color:var(--soon)}
.pill.watch{background:var(--watchbg);color:var(--watch)}
.pill.hi{background:#e7f6ec;color:#0f7b3f}.pill.mid{background:#fdf3dd;color:#a9680a}.pill.lo{background:#fdecec;color:#b3261e}
.drawer{position:fixed;top:0;right:0;height:100%;width:min(720px,94vw);background:#fff;border-left:1px solid var(--line);
  box-shadow:-10px 0 34px rgba(16,32,48,.16);transform:translateX(102%);transition:.22s;overflow-y:auto;z-index:60}
.drawer.open{transform:none}
.dh{position:sticky;top:0;background:linear-gradient(135deg,#1f4e79,#2d6fa8);color:#fff;padding:15px 18px;z-index:2}
.dh h2{margin:0 0 3px;font-size:16px;padding-right:26px}
.dh .x{position:absolute;top:12px;right:14px;cursor:pointer;font-size:20px;line-height:1;opacity:.85}
.db{padding:16px 18px 48px}
.sec{margin-bottom:18px}
.sec h3{font-size:12.5px;color:var(--brand);margin:0 0 8px;padding-bottom:5px;border-bottom:1px solid var(--line);
  text-transform:uppercase;letter-spacing:.6px}
.kv{display:grid;grid-template-columns:96px 1fr;gap:5px 10px;font-size:13px}
.kv .k{color:var(--muted);font-size:12.5px}
.kv .v{color:#26313c}
.note{background:#fbfcfd;border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:12.5px;color:#33404d}
.play{background:#f4f9ff;border:1px solid #d3e4f7;border-radius:10px;padding:13px 15px}
.play h4{margin:0 0 8px;font-size:13.5px;color:var(--brand)}
.play ol{margin:0;padding-left:19px;font-size:13px}
.play li{margin-bottom:6px}
.warn{background:#fff8f8;border:1px solid #f6d9d7;color:#8f2c24;border-radius:8px;padding:9px 12px;font-size:12.5px}
.overlay{position:fixed;inset:0;background:rgba(12,22,32,.34);opacity:0;pointer-events:none;transition:.2s;z-index:50}
.overlay.on{opacity:1;pointer-events:auto}
.src{font-size:12px;word-break:break-all}
.empty{background:#fff;border:1px dashed var(--line);border-radius:10px;padding:34px;text-align:center;color:var(--muted)}
footer{margin-top:26px;font-size:12px;color:var(--muted);line-height:1.8}
@media(max-width:640px){.wrap{padding:14px}.kpi{min-width:104px}.qbox{min-width:150px}}
</style>
</head>
<body>
<header>
  <h1>__H1__</h1>
  <div class="sub" id="subline">__SUB__</div>
  <div class="askbar">
    <label>产品</label><input id="q-product" value="__PRODUCT_ATTR__">
    <label>地区</label><input id="q-region" value="__REGION_ATTR__">
    <label>未来</label><input id="q-horizon" value="__HORIZON_ATTR__">
    <label>生成日</label><input id="q-today" value="__TODAY_ATTR__" readonly>
    <button class="btn" id="btn-run">重新检索</button>
    <button class="btn ghost" id="btn-reset">清空筛选</button>
  </div>
</header>

<noscript><div class="wrap"><div class="warn">本页的筛选、双视图与详情抽屉需要启用 JavaScript 才能使用。</div></div></noscript>

<div class="wrap">
  <div class="kpis" id="kpis"></div>

  <div class="filters">
    <div class="fgroup" id="f-timing"><span class="fl">销售时点</span></div>
    <div class="fgroup" id="f-stage"><span class="fl">建设阶段</span></div>
    <div class="fgroup" id="f-prov"><span class="fl">省份</span></div>
    <div class="fgroup" id="f-lane"><span class="fl">板块</span></div>
    <div class="fgroup" id="f-role"><span class="fl">产品角色</span></div>
  </div>

  <div class="toolbar">
    <div class="views">
      <button id="v-timeline" class="on">项目时间线</button>
      <button id="v-company">企业表</button>
    </div>
    <div class="fgroup"><span class="fl">全文搜索</span>
      <input id="q" class="qbox" placeholder="公司 / 项目 / 园区 / 细分行业 / 产品别名" autocomplete="off">
    </div>
    <div class="count" id="count"></div>
  </div>

  <div id="view-timeline"></div>
  <div id="view-company" style="display:none"></div>

  <footer id="foot">__FOOT__</footer>
</div>

<div class="overlay" id="overlay"></div>
<aside class="drawer" id="drawer"><div id="dinner"></div></aside>

<script>
const DATA = __DATA__;
const CFG = DATA.cfg || {};
const LEADS = (DATA.leads || []).map(function(r, i){ r._idx = i; return r; });
const COMPANIES = DATA.companies || [];
const PROD = ((CFG.product || {}).name) || '本产品';
const GRADES = ((CFG.product || {}).grades) || [];
const ROLES_VOCAB = ((CFG.product || {}).roles_vocab) || [];
const ALIASES = [PROD].concat(((CFG.product || {}).aliases) || []).concat([((CFG.product || {}).formula) || '']);

// 销售时点标准词表（方法论常量，与产品无关）。数据里出现的新值会自动追加到筛选条。
const TIMINGS = ['现在就该联系', '3-6个月后再联系', '仅需关注'];
const T_CLASS = {'现在就该联系':'now', '3-6个月后再联系':'soon', '仅需关注':'watch'};
const T_ORDER = {'现在就该联系':0, '3-6个月后再联系':1, '仅需关注':2};
const TIMING_NOTE = {
  '现在就该联系':'窗口内最先出手：试车 / 近期投产 / 在建且临近投料',
  '3-6个月后再联系':'留资送样，等临近投料再谈商务',
  '仅需关注':'拟建或投产超出窗口，作商机储备'
};
const PRIO_CLASS = {'高':'hi', '中':'mid', '低':'lo'};
const CONF_CLASS = {'高':'hi', '中':'mid', '低':'lo'};

const state = {timing:new Set(), stage:new Set(), prov:new Set(), lane:new Set(), role:new Set(),
               q:'', view:'timeline'};

function esc(s){
  return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
    return {'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c];
  });
}
// 派生字段安全读取：缺字段一律回落默认值，不抛错
function g(r, k, d){ if(!r) return d; const v = r[k]; return (v === undefined || v === null || v === '') ? d : v; }
function txt(v, d){ return (v === undefined || v === null || String(v).trim() === '') ? d : v; }
function cv(comp, k, d){ return comp ? txt(comp[k], d) : d; }
function tclass(t){ return T_CLASS[t] || 'watch'; }
function torder(t){ return (t in T_ORDER) ? T_ORDER[t] : 9; }
// URL 白名单（前端二次防线；Python 侧已清洗过一次）
function safeUrl(u){ u = String(u == null ? '' : u).trim(); return /^https?:\/\//i.test(u) ? u : ''; }
function provOf(r){ return String(g(r, '省市', '未披露')).split('/')[0] || '未披露'; }
function laneOf(r){ return String(g(r, 'lane', '未分类')); }
function stageOf(r){ return String(g(r, '建设阶段', '未披露')); }
function roleOf(r){ return String(g(r, '产品角色', '未分类')); }
function timingOf(r){ return String(g(r, '销售时点', '未判定')); }
function pill(text, cls){ return '<span class="pill ' + esc(cls || 'watch') + '">' + esc(text) + '</span>'; }
function pillTiming(t){ return '<span class="pill ' + tclass(t) + '">' + esc(t) + '</span>'; }
function pillConf(c){ return pill(c, CONF_CLASS[String(c)] || 'lo'); }
function pillPrio(p){ return pill(p, PRIO_CLASS[String(p)] || 'lo'); }
function uniq(arr){ const s = new Set(); arr.forEach(function(v){ if(v) s.add(v); }); return Array.from(s); }
function cmpText(a, b){ return String(a).localeCompare(String(b), 'zh'); }
// 词表内优先、按词表顺序；词表外的值排在后面（不丢数据）
function orderByVocab(vals, vocab){
  const inside = [], rest = [];
  vals.forEach(function(v){ (vocab.indexOf(v) >= 0 ? inside : rest).push(v); });
  inside.sort(function(a, b){ return vocab.indexOf(a) - vocab.indexOf(b); });
  rest.sort(cmpText);
  return inside.concat(rest);
}

// ---------------- 筛选维度（全部由数据 / cfg 派生） ----------------
function timingFacet(){
  const s = new Set();
  TIMINGS.forEach(function(t){ s.add(t); });
  LEADS.forEach(function(r){ const t = timingOf(r); if(t && t !== '未判定') s.add(t); });
  return orderByVocab(Array.from(s), TIMINGS.slice());
}
function stageFacet(){
  const vocab = (CFG.stages_vocab || []).slice();
  const s = new Set();
  LEADS.forEach(function(r){ const t = stageOf(r); if(t && t !== '未披露') s.add(t); });
  return orderByVocab(Array.from(s), vocab);
}
function roleFacet(){
  const vocab = ROLES_VOCAB.slice();
  let vals = uniq(LEADS.map(function(r){ const t = roleOf(r); return t === '未分类' ? '' : t; }));
  if(!vals.length) vals = vocab.slice();
  return orderByVocab(vals, vocab);
}
function provFacet(){ return uniq(LEADS.map(provOf)).sort(cmpText); }
function laneFacet(){ return uniq(LEADS.map(laneOf)).sort(cmpText); }

function chipGroup(el, label, values, key, cls){
  const box = document.getElementById(el);
  box.innerHTML = '<span class="fl">' + esc(label) + '</span>';
  values.forEach(function(v){
    const b = document.createElement('span');
    b.className = 'chip ' + (cls || '');
    b.textContent = v;
    b.setAttribute('data-chip', v);
    b.onclick = function(){
      const s = state[key];
      if(s.has(v)){ s.delete(v); } else { s.add(v); }
      render();
    };
    box.appendChild(b);
  });
}
function syncChips(){
  [['f-timing','timing'], ['f-stage','stage'], ['f-prov','prov'], ['f-lane','lane'], ['f-role','role']].forEach(function(x){
    const box = document.getElementById(x[0]);
    const s = state[x[1]];
    Array.prototype.forEach.call(box.querySelectorAll('.chip'), function(c){
      c.classList.toggle('on', s.has(c.getAttribute('data-chip')));
    });
  });
  Array.prototype.forEach.call(document.querySelectorAll('#f-timing .chip'), function(c){
    c.classList.add(tclass(c.getAttribute('data-chip')));
  });
}

// ---------------- 过滤 + 检索 ----------------
// 检索索引：公司 / 项目 / 园区 / 细分行业 / 项目产品 + 产品名与别名（cfg 驱动）
function hay(r){
  if(r.__hay === undefined){
    const parts = [g(r, '公司', ''), g(r, '项目名称', ''), g(r, '所在园区', ''),
                   g(r, '细分行业', ''), g(r, '项目产品', '')].concat(ALIASES);
    r.__hay = parts.join(' ').toLowerCase();
  }
  return r.__hay;
}
function filtered(){
  const q = state.q.trim().toLowerCase();
  return LEADS.filter(function(r){
    if(state.timing.size && !state.timing.has(timingOf(r))) return false;
    if(state.stage.size && !state.stage.has(stageOf(r))) return false;
    if(state.prov.size && !state.prov.has(provOf(r))) return false;
    if(state.lane.size && !state.lane.has(laneOf(r))) return false;
    if(state.role.size && !state.role.has(roleOf(r))) return false;
    if(q && hay(r).indexOf(q) < 0) return false;
    return true;
  }).sort(function(a, b){
    return torder(timingOf(a)) - torder(timingOf(b)) || cmpText(laneOf(a), laneOf(b));
  });
}

// ---------------- 投产时间的月份归组 ----------------
function monthKey(s){
  s = String(s || '');
  let m = s.match(/(20\d{2})\s*[-/年\.]\s*(\d{1,2})/);
  if(m) return m[1] + '-' + String(+m[2]).padStart(2, '0');
  m = s.match(/(20\d{2})\s*[Qq]\s*([1-4])/);
  if(m) return m[1] + '-Q' + m[2];
  m = s.match(/(20\d{2})/);
  if(m) return m[1] + '-年内未明确';
  return '未披露';
}
function monthSort(k){
  if(k === '未披露') return [9, 0, 0];
  let m = k.match(/^(\d{4})-(\d{2})$/); if(m) return [0, +m[1], +m[2]];
  m = k.match(/^(\d{4})-Q(\d)$/); if(m) return [1, +m[1], +m[2]];
  m = k.match(/^(\d{4})/); return [2, +m[1], 0];
}

// ---------------- KPI（由当前命中数据实时算出） ----------------
function renderKpis(rows){
  const by = {};
  let unverified = 0;
  rows.forEach(function(r){
    const t = timingOf(r);
    by[t] = (by[t] || 0) + 1;
    const src = String(g(r, '来源', '')).trim();
    if(!safeUrl(src) || src === '未核实') unverified++;
  });
  const order = orderByVocab(Object.keys(by), TIMINGS.slice());
  let html = '<div class="kpi"><div class="n">' + rows.length + '</div><div class="l">命中的项目级线索'
    + '<br><span style="opacity:.75">全表共 ' + LEADS.length + ' 条（去重后）</span></div></div>';
  html += '<div class="kpi"><div class="n">' + uniq(rows.map(function(r){ return g(r, '公司', '未披露'); })).length
    + '</div><div class="l">覆盖企业（业主）数</div></div>';
  order.forEach(function(t){
    const note = TIMING_NOTE[t] ? '<br><span style="opacity:.75">' + esc(TIMING_NOTE[t]) + '</span>' : '';
    html += '<div class="kpi ' + tclass(t) + '"><div class="n">' + (by[t] || 0) + '</div><div class="l">'
      + esc(t) + note + '</div></div>';
  });
  html += '<div class="kpi watch"><div class="n">' + unverified
    + '</div><div class="l">来源未核实<br><span style="opacity:.75">需电话确认，不得当证据用</span></div></div>';
  document.getElementById('kpis').innerHTML = html;
}

// ---------------- 时间线卡片 ----------------
function card(r){
  return '<div class="card ' + tclass(timingOf(r)) + '" data-i="' + r._idx + '">'
    + '<div class="co">' + esc(g(r, '公司', '未披露')) + '</div>'
    + '<div class="prj">' + esc(g(r, '项目名称', '未披露')) + '</div>'
    + '<div class="tags">'
      + '<span class="tag t-' + tclass(timingOf(r)) + '">' + esc(timingOf(r)) + '</span>'
      + '<span class="tag stage">' + esc(stageOf(r)) + '</span>'
      + '<span class="tag role">' + esc(roleOf(r)) + '</span>'
      + '<span class="tag">' + esc(g(r, '来源类型', '未披露')) + '</span>'
      + '<span class="tag">' + esc(g(r, '用量强度', '未评估')) + '</span>'
    + '</div>'
    + '<div class="row"><b>项目产品</b><span>' + esc(g(r, '项目产品', '未披露')) + '</span></div>'
    + '<div class="row"><b>设计产能</b><span>' + esc(g(r, '设计产能', '未披露')) + '</span></div>'
    + '<div class="row"><b>预计投产</b><span>' + esc(g(r, '预计投产时间', '未披露'))
      + '　<b>园区</b>' + esc(g(r, '所在园区', '未披露')) + '</span></div>'
    + '<div class="row"><b>地区</b><span>' + esc(provOf(r)) + '　<b>板块</b>' + esc(laneOf(r)) + '</span></div>'
  + '</div>';
}
function renderTimeline(rows){
  const box = document.getElementById('view-timeline');
  if(!rows.length){ box.innerHTML = '<div class="empty">当前筛选条件下没有项目。请放宽筛选或清空搜索。</div>'; return; }
  const byM = {};
  rows.forEach(function(r){ const k = monthKey(g(r, '预计投产时间', '')); (byM[k] = byM[k] || []).push(r); });
  let html = '<div class="grid">';
  Object.keys(byM).sort(function(a, b){
    const x = monthSort(a), y = monthSort(b);
    return x[0] - y[0] || x[1] - y[1] || x[2] - y[2];
  }).forEach(function(k){
    html += '<div class="month"><span class="mt">' + esc(k === '未披露' ? '投产时间未披露' : k)
      + '</span><span class="mn">' + byM[k].length + ' 个项目</span></div>';
    byM[k].forEach(function(r){ html += card(r); });
  });
  box.innerHTML = html + '</div>';
}

// ---------------- 企业表 ----------------
function renderCompany(rows){
  const box = document.getElementById('view-company');
  const names = {};
  rows.forEach(function(r){ names[g(r, '公司', '未披露')] = 1; });
  const cos = COMPANIES.filter(function(c){ return names[txt(c['公司'], '未披露')]; });
  if(!cos.length){ box.innerHTML = '<div class="empty">当前筛选条件下没有企业。</div>'; return; }
  let h = '<table><thead><tr><th>销售时点</th><th>企业（业主）</th><th>省市</th><th>板块</th>'
    + '<th class="c">项目数</th><th class="c">在建以上</th><th class="c">用量强度</th>'
    + '<th class="c">优先级</th><th class="c">置信度</th></tr></thead><tbody>';
  cos.forEach(function(c){
    h += '<tr data-co="' + esc(cv(c, '公司', '未披露')) + '">'
      + '<td class="c">' + pillTiming(cv(c, '销售时点', '未判定')) + '</td>'
      + '<td><b>' + esc(cv(c, '公司', '未披露')) + '</b></td>'
      + '<td>' + esc(cv(c, '省市', '未披露')) + '</td>'
      + '<td>' + esc(cv(c, '板块', '未分类')) + '</td>'
      + '<td class="c">' + cv(c, '项目数', 0) + '</td>'
      + '<td class="c">' + cv(c, '在建以上', 0) + '</td>'
      + '<td class="c">' + esc(cv(c, '用量强度', '未评估')) + '</td>'
      + '<td class="c">' + pillPrio(cv(c, '最大优先级', '未判定')) + '</td>'
      + '<td class="c">' + pillConf(cv(c, '置信度', '未判定')) + '</td></tr>';
  });
  box.innerHTML = h + '</tbody></table>';
}

// ---------------- 主渲染 ----------------
function render(){
  chipGroup('f-timing', '销售时点', timingFacet(), 'timing');
  chipGroup('f-stage', '建设阶段', stageFacet(), 'stage');
  chipGroup('f-prov', '省份', provFacet(), 'prov');
  chipGroup('f-lane', '板块', laneFacet(), 'lane');
  chipGroup('f-role', '产品角色', roleFacet(), 'role');
  syncChips();

  const rows = filtered();
  document.getElementById('count').textContent = '命中 ' + rows.length + ' 个项目 / '
    + uniq(rows.map(function(r){ return g(r, '公司', '未披露'); })).length + ' 家企业（全表 ' + LEADS.length + ' 条）';
  renderKpis(rows);

  document.getElementById('view-timeline').style.display = state.view === 'timeline' ? '' : 'none';
  document.getElementById('view-company').style.display = state.view === 'company' ? '' : 'none';
  if(state.view === 'timeline'){ renderTimeline(rows); } else { renderCompany(rows); }
}
function setView(v){
  state.view = v;
  document.getElementById('v-timeline').classList.toggle('on', v === 'timeline');
  document.getElementById('v-company').classList.toggle('on', v === 'company');
  render();
}

// ---------------- 详情抽屉 ----------------
function kv(k, v){ return '<div class="k">' + esc(k) + '</div><div class="v">' + esc(txt(v, '未披露')) + '</div>'; }
function companyOf(name){
  for(let i = 0; i < COMPANIES.length; i++){ if(txt(COMPANIES[i]['公司'], '') === name) return COMPANIES[i]; }
  return null;
}
// 切入点话术：按「产品角色」与「建设阶段」通用分档，不含任何单一产品专用词
function roleTip(role){
  const n = esc(PROD), r = String(role || '');
  if(/主原料|主料|主要原料|原料/.test(r)){
    return n + '进入产品主体或作为主要成分来源，不可替代、单耗高：谈法重点是<b>量价绑定与长协</b>'
      + '（月度/季度框架量 + 区域统一价锁量），并把规格与质检指标写进合同附件。';
  }
  if(/辅料|辅助/.test(r)){
    return n + '作中和 / 缓冲 / 吸收 / 洗涤等辅助用途，用量相对小但连续：谈法重点是'
      + '<b>小批量多频次配送与账期</b>，用稳定到货率换取份额。';
  }
  if(/助剂|添加|催化|熔剂|调节/.test(r)){
    return n + '在配合料或反应体系中起助熔 / 降粘 / 调节等作用，属大宗不可中断原料：谈法重点是'
      + '<b>稳定供应与规格一致性</b>（含量、粒度、水分、包装），一次指标波动就可能影响对方产品良率。';
  }
  return n + '在本项目中的角色是「' + esc(r || '未披露') + '」：先电话核实工序位置与作用机理，'
    + '再按用量规模与可替代性决定投入节奏。';
}
function stageTip(stage){
  const s = String(stage || '');
  if(/试车|试生产/.test(s)){
    return '项目已进入试车 / 试生产 —— 装置正在消耗物料，供应商名单仍可切入。立即行动：确认月用量与规格、'
      + '争取试车期临时供应，这是最快进入合格供应商名单的窗口。';
  }
  if(/在建|施工|建设/.test(s)){
    return '项目在建、产量尚未释放。按「装置投料前 1~3 个月锁定原料并完成供应商入库」的规律，'
      + '现在要把技术对接 + 送样检测 + 合格供应商入库三步走完。';
  }
  if(/投产|达产/.test(s)){
    return '项目已投产、处于达产爬坡期，供应商结构仍可能调整。切入点是用<b>补量、换源、区域就近配送降本</b>'
      + '说服对方给一次试单。';
  }
  if(/备案|核准|环评|审批/.test(s)){
    return '项目已完成备案 / 审批但尚未开工，采购未启动。现在只做<b>关系建立与技术交流</b>，待开工后再推进商务。';
  }
  if(/拟建|规划|设计/.test(s)){
    return '项目仅处拟建 / 规划阶段，落地存在不确定性。保持<b>低频跟进</b>、作为商机储备，避免投入过多资源。';
  }
  return '先电话核实建设阶段与预计投产时间，再决定投入节奏。';
}
function playbook(r){
  const role = roleOf(r), stage = stageOf(r);
  const t = txt(g(r, '预计投产时间', ''), '未披露');
  const spec = String(g(r, '需求点', ''));
  const specText = spec ? esc(spec.slice(0, 180)) + (spec.length > 180 ? '…' : '') : '未披露（先问清工序与作用）';
  const specQ = GRADES.length ? '（规格：含量 / 粒度 / 水分 / 包装；本产品常见牌号 ' + esc(GRADES.join('、')) + '）' : '（规格：含量 / 粒度 / 水分 / 包装）';
  return '<h4>找客户最近的切入点</h4><ol>'
    + '<li><b>角色定位：' + esc(role) + '</b> —— ' + roleTip(role) + '</li>'
    + '<li><b>阶段动作：</b>' + stageTip(stage) + '</li>'
    + '<li><b>首通电话该问的三件事：</b>①项目预计 ' + esc(t) + ' 投产是否仍按计划？'
      + '②' + esc(PROD) + '的月需求量与规格要求' + specQ + '？'
      + '③采购由总部集中还是本项目自主？合格供应商入库要走哪些流程、需要什么资料？</li>'
    + '<li><b>可用的技术话术：</b>把该项目的需求点原文转述给技术口 —— ' + specText + '</li>'
    + '<li><b>量级依据：</b>' + esc(txt(g(r, '单耗依据', ''), '无法估算')) + '</li>'
  + '</ol>';
}
function openDetail(i){
  const r = LEADS[i];
  if(!r) return;
  const co = g(r, '公司', '未披露'), prj = g(r, '项目名称', '未披露');
  const comp = companyOf(co);
  const sibs = LEADS.filter(function(x){ return g(x, '公司', '') === co && g(x, '项目名称', '') !== prj; });
  const url = safeUrl(g(r, '来源', ''));
  document.getElementById('dinner').innerHTML =
    '<div class="dh"><span class="x" data-act="close">&times;</span>'
    + '<h2>' + esc(co) + '</h2>'
    + '<div>' + pillTiming(timingOf(r)) + ' <span class="tag stage">' + esc(stageOf(r))
    + '</span> <span class="tag role">' + esc(roleOf(r)) + '</span></div></div>'
    + '<div class="db">'
    + '<div class="sec"><h3>项目档案</h3><div class="kv">'
      + kv('项目名称', prj) + kv('项目产品', g(r, '项目产品', '未披露')) + kv('细分行业', g(r, '细分行业', '未披露'))
      + kv('设计产能', g(r, '设计产能', '未披露')) + kv('建设阶段', stageOf(r))
      + kv('预计投产', g(r, '预计投产时间', '未披露')) + kv('所在园区', g(r, '所在园区', '未披露'))
      + kv('所在地区', g(r, '省市', '未披露')) + kv('所属板块', laneOf(r))
      + kv('用量强度', g(r, '用量强度', '未评估'))
    + '</div></div>'
    + '<div class="sec"><h3>' + esc(PROD) + '与该项目的关系</h3><div class="kv">'
      + kv('产品角色', roleOf(r)) + kv('需求性质', g(r, '需求性质', '未披露'))
      + kv('需求点', g(r, '需求点', '未披露')) + kv('单耗依据', g(r, '单耗依据', '无法估算'))
      + kv('年需求量估算', g(r, '年需求量估算', '无法估算'))
    + '</div></div>'
    + '<div class="sec"><div class="play">' + playbook(r) + '</div></div>'
    + '<div class="sec"><h3>销售时点判定</h3><div class="note"><b>' + esc(timingOf(r)) + '</b> —— '
      + esc(g(r, '时点理由', '未给出判定理由（派生字段缺失，请以电话核实为准）')) + '</div></div>'
    + '<div class="sec"><h3>企业背景</h3><div class="kv">'
      + kv('企业名称', co) + kv('所在地区', g(r, '省市', '未披露'))
      + kv('涉及板块', comp ? cv(comp, '板块', laneOf(r)) : laneOf(r))
      + kv('本表项目数', comp ? cv(comp, '项目数', 1) : 1)
      + kv('其中在建以上', comp ? cv(comp, '在建以上', 0) : 0)
      + kv('用量强度', comp ? cv(comp, '用量强度', g(r, '用量强度', '未评估')) : g(r, '用量强度', '未评估'))
    + '</div>' + (sibs.length
      ? '<div class="note" style="margin-top:8px">该企业在本表中另有 ' + sibs.length + ' 个项目：'
        + sibs.map(function(x){ return esc(g(x, '项目名称', '未披露')) + '（' + esc(stageOf(x)) + '）'; }).join('、') + '</div>'
      : '') + '</div>'
    + '<div class="sec"><h3>规模线索</h3><div class="note">' + esc(g(r, '规模线索', '未披露')) + '</div></div>'
    + '<div class="sec"><h3>证据与来源</h3><div class="kv">'
      + kv('来源类型', g(r, '来源类型', '未披露')) + kv('发布日期', g(r, '发布日期', '未披露'))
      + kv('置信度', g(r, '置信度', '未披露')) + kv('来源抽检', g(r, '抽检结论', '未抽检'))
    + '</div>'
    + '<div class="src" style="margin-top:6px">' + (url
      ? '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + esc(url) + '</a>'
      : '<span class="warn">未核实（未取得可点击的可信来源，需电话确认；非 http/https 链接已被安全拦截）</span>')
    + '</div></div>'
    + '<div class="sec"><button class="btn" style="background:#1f4e79;color:#fff" data-act="close">关闭</button></div>'
    + '</div>';
  document.getElementById('drawer').classList.add('open');
  document.getElementById('overlay').classList.add('on');
}
function openCompany(name){
  const ps = LEADS.filter(function(r){ return g(r, '公司', '') === name; });
  if(!ps.length) return;
  const comp = companyOf(name);
  document.getElementById('dinner').innerHTML =
    '<div class="dh"><span class="x" data-act="close">&times;</span><h2>' + esc(name) + '</h2>'
    + '<div>' + pillTiming(cv(comp, '销售时点', '未判定')) + ' <span class="tag">' + esc(cv(comp, '省市', '未披露'))
    + '</span> <span class="tag">' + esc(cv(comp, '板块', '未分类')) + '</span></div></div>'
    + '<div class="db"><div class="sec"><h3>企业概览</h3><div class="kv">'
      + kv('企业名称', name) + kv('所在地区', cv(comp, '省市', '未披露')) + kv('涉及板块', cv(comp, '板块', '未分类'))
      + kv('本表项目数', cv(comp, '项目数', ps.length)) + kv('其中在建以上', cv(comp, '在建以上', 0))
      + kv('用量强度', cv(comp, '用量强度', '未评估')) + kv('最高优先级', cv(comp, '最大优先级', '未判定'))
      + kv('置信度', cv(comp, '置信度', '未判定'))
    + '</div></div><div class="sec"><h3>该企业的项目（点击查看切入点）</h3>'
    + ps.map(function(r){
        return '<div class="card ' + tclass(timingOf(r)) + '" style="margin-bottom:9px" data-i="' + r._idx + '">'
          + '<div class="prj">' + esc(g(r, '项目名称', '未披露')) + '</div><div class="tags">'
          + '<span class="tag t-' + tclass(timingOf(r)) + '">' + esc(timingOf(r)) + '</span>'
          + '<span class="tag stage">' + esc(stageOf(r)) + '</span>'
          + '<span class="tag role">' + esc(roleOf(r)) + '</span>'
          + '<span class="tag">投产 ' + esc(g(r, '预计投产时间', '未披露')) + '</span></div></div>';
      }).join('')
    + '</div></div>';
  document.getElementById('drawer').classList.add('open');
  document.getElementById('overlay').classList.add('on');
}
function closeDrawer(){
  document.getElementById('drawer').classList.remove('open');
  document.getElementById('overlay').classList.remove('on');
}

// ---------------- 事件（用事件委托，不拼内联 onclick，避免引号/转义破口） ----------------
function onCardClick(e){
  const t = e.target.closest ? e.target.closest('[data-i],[data-co],[data-act]') : null;
  if(!t) return;
  if(t.getAttribute('data-act') === 'close'){ closeDrawer(); return; }
  const i = t.getAttribute('data-i');
  if(i !== null && i !== undefined){ openDetail(+i); return; }
  const co = t.getAttribute('data-co');
  if(co !== null){ openCompany(co); return; }
}
['view-timeline', 'view-company', 'dinner'].forEach(function(id){
  document.getElementById(id).addEventListener('click', onCardClick);
});
document.getElementById('overlay').onclick = closeDrawer;
document.addEventListener('keydown', function(e){ if(e.key === 'Escape') closeDrawer(); });
document.getElementById('v-timeline').onclick = function(){ setView('timeline'); };
document.getElementById('v-company').onclick = function(){ setView('company'); };
document.getElementById('btn-reset').onclick = function(){
  state.timing.clear(); state.stage.clear(); state.prov.clear(); state.lane.clear(); state.role.clear();
  state.q = '';
  const q = document.getElementById('q');
  if(q) q.value = '';
  render();
};
document.getElementById('q').oninput = function(){ state.q = this.value; render(); };

function sublineHtml(p, r, h){
  return '检索条件：<b>' + esc(p) + '</b> · <b>' + esc(r) + '</b> · 未来 <b>' + esc(h) + '</b>'
    + (CFG.window_end ? '（' + esc(CFG.today) + ' ~ ' + esc(CFG.window_end) + '）' : '')
    + ' ｜ 共 ' + LEADS.length + ' 个项目级线索 ｜ 数据生成日 ' + esc(CFG.today || '未记录')
    + ' ｜ 点击任意项目查看企业背景与「找客户最近的切入点」';
}
document.getElementById('btn-run').onclick = function(){
  const p = document.getElementById('q-product').value;
  const r = document.getElementById('q-region').value;
  const h = document.getElementById('q-horizon').value;
  document.getElementById('subline').innerHTML = sublineHtml(p, r, h)
    + ' ｜ 提示：本页数据在生成时已固定，要换条件请在 agent 侧重跑取数与合并流程。';
  window.scrollTo({top:0, behavior:'smooth'});
};

render();
</script>
</body>
</html>
'''

_TOKEN_RE = re.compile(r'__[A-Z][A-Z_]*__')


def build_html(cfg: dict, leads: list[dict], out_path: str) -> str:
    """生成单文件自包含的交互式 HTML 交付物，返回实际写入的路径。

    cfg:  config.json 的内容（产品 / 地区 / 窗口 / 生成日 / 词表）
    leads: leads.json 的内容（合并去重后的线索数组）
    out_path: 由调用方用 cfg['paths']['out_stem'] 渲染好的文件名，本模块不拼文件名
    """
    cfg = cfg or {}
    leads = leads or []
    if not out_path:
        raise ValueError('build_html: out_path 不能为空')

    view = _cfg_view(cfg)
    product = view['product']['name']
    region = view['region']['name']
    months = view['window_months']
    today = view['today']
    window_end = view['window_end']

    clean = [_payload_lead(r) for r in leads if isinstance(r, dict)]
    companies = _rollup_companies(leads)

    payload = {'cfg': view, 'leads': clean, 'companies': companies}

    # 统计口径全部从数据现算，不写死
    unverified = sum(1 for r in clean if not _safe_url(r.get('来源')))
    n_companies = len({_txt(r.get('公司'), DISCLOSED) for r in clean})

    peers = [_txt(x, '') for x in (cfg.get('peer_keywords') or []) if _txt(x, '')]
    window_txt = '%s ~ %s' % (today, window_end) if (today and window_end) else (today or '未记录')

    title = '%s · %s · 未来 %d 个月 项目级潜客清单' % (product, region, months)
    h1 = '%s · %s · 未来 %d 个月 —— 项目级潜在客户清单' % (product, region, months)
    sub = ('检索条件：<b>%s</b> · <b>%s</b> · 未来 <b>%d个月</b>%s ｜ 共 <b>%d</b> 个项目级线索 ｜ 数据生成日 <b>%s</b>'
           ' ｜ 点击任意项目查看企业背景与「找客户最近的切入点」') % (
        _esc(product), _esc(region), months,
        ('（%s ~ %s）' % (_esc(today), _esc(window_end))) if (today and window_end) else '',
        len(clean), _esc(today or '未记录'))

    foot = ('<b>方法与边界：</b>证据来自公开来源（官方公告 / 环评公示 / 招标公告 / 公开新闻），'
            '每条线索都附可点击来源；未取得可信来源的记为「未核实」<b>%d</b> 条，'
            '单耗无依据的写「无法估算」，不给假精度。<br>'
            '<b>同行闸门：</b>配置的同行关键词（自产 %s 的同行，不列为客户）共 <b>%d</b> 个，已在采集阶段剔除。<br>'
            '本表共 <b>%d</b> 条线索 / <b>%d</b> 家企业 ｜ 取数窗口 <b>%s</b> ｜ 数据生成日 <b>%s</b>。'
            ) % (unverified, _esc(product), len(peers), len(clean), n_companies, _esc(window_txt), _esc(today or '未记录'))

    tokens = {
        '__TITLE__': _esc(title),
        '__H1__': _esc(h1),
        '__SUB__': sub,
        '__PRODUCT_ATTR__': _esc(product),
        '__REGION_ATTR__': _esc(region),
        '__HORIZON_ATTR__': _esc('%d个月' % months),
        '__TODAY_ATTR__': _esc(today),
        '__FOOT__': foot,
        '__DATA__': _json_for_script(payload),
    }
    html = _TOKEN_RE.sub(lambda m: tokens.get(m.group(0), m.group(0)), _TEMPLATE)

    abs_out = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(abs_out), exist_ok=True)
    with open(abs_out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(html)
    return abs_out