# -*- coding: utf-8 -*-
"""共享基础层：配置加载、字段 schema、归一化、销售时点/优先级推导。

本模块**产品无关**：所有产品名、地区、时间窗都来自 config，不硬编码任何化工品。
只用标准库。
"""
import datetime
import json
import os
import re

# ---------------------------------------------------------------- 字段 schema

# lane 子代理必须产出的采集字段（顺序即为 Excel 列序的一部分）
COLLECT_FIELDS = [
    '公司', '细分行业', '省市', '项目名称', '建设阶段', '项目产品', '设计产能',
    '预计投产时间', '所在园区', '需求点', '产品角色', '单耗依据', '年需求量估算',
    '规模线索', '来源类型', '来源', '发布日期', '置信度',
]

CONF_WEIGHT = {'高': 3, '中': 2, '低': 1}
TIMING_ORDER = {'现在就该联系': 0, '3-6个月后再联系': 1, '仅需关注': 2}

DEFAULT_STAGES = ['拟建', '备案', '在建', '试车', '已投产']
DEFAULT_SRC_TYPES = ['备案', '环评', '招标', '公告', '新闻']
DEFAULT_ROLES = ['主原料', '辅料', '助剂']

# 建设阶段的同义说法（子代理可能用面向用户的措辞）
STAGE_ALIAS = {
    '试生产': '试车', '试运行': '试车', '联调': '试车', '投料': '试车',
    '投产': '已投产', '建成': '已投产', '正式投产': '已投产', '达产': '已投产',
    '开工': '在建', '建设': '在建', '施工': '在建', '扩建': '在建', '技改': '在建',
    '立项': '备案', '审批': '备案', '核准': '备案', '环评': '备案', '受理': '备案',
    '公示': '备案', '前期': '备案', '批复': '备案', '备案': '备案',
    '规划': '拟建', '拟开工': '拟建', '筹划': '拟建',
}


# ---------------------------------------------------------------- 配置

def load_config(path):
    """读 config.json；补默认值，返回 (cfg, project_root)。"""
    with open(path, encoding='utf-8-sig') as f:
        cfg = json.load(f)
    root = os.path.dirname(os.path.abspath(path))

    cfg.setdefault('product', {})
    cfg['product'].setdefault('name', '产品')
    cfg['product'].setdefault('formula', '')
    cfg['product'].setdefault('aliases', [])
    cfg['product'].setdefault('grades', [])
    cfg['product'].setdefault('roles_vocab', list(DEFAULT_ROLES))

    cfg.setdefault('region', {})
    cfg['region'].setdefault('name', '全国')
    cfg['region'].setdefault('provinces', [])
    cfg['region'].setdefault('cities', [])

    cfg.setdefault('window_months', 6)
    cfg.setdefault('today', datetime.date.today().isoformat())
    cfg.setdefault('peer_keywords', [])
    cfg.setdefault('stages_vocab', list(DEFAULT_STAGES))
    cfg.setdefault('source_types_vocab', list(DEFAULT_SRC_TYPES))
    cfg.setdefault('outputs', {'xlsx': True, 'html': True, 'md': True, 'csv': False})
    cfg.setdefault('qa', {'min_sample': 40, 'max_total': 70})
    cfg.setdefault('lane_fanout', {'max_concurrency': 8, 'min_records_per_lane': 8,
                                   'max_records_per_lane': 15})
    cfg.setdefault('paths', {})
    p = cfg['paths']
    p.setdefault('lanes', 'lanes.json')
    p.setdefault('raw_dir', 'leads_raw')
    p.setdefault('leads', 'leads.json')
    p.setdefault('stats', 'merge_stats.json')
    p.setdefault('qa_report', 'leads_raw/_qa_report.json')
    p.setdefault('channels', 'channels.json')
    p.setdefault('workplan', 'workplan.md')
    p.setdefault('out_stem', '{product}{region}未来{months}个月项目级潜客表')
    return cfg, root


def render_stem(cfg):
    """渲染输出文件名主干（不含扩展名）。"""
    tmpl = cfg['paths']['out_stem']
    safe = _safe_filename
    return safe(tmpl.format(product=cfg['product']['name'],
                            region=cfg['region']['name'],
                            months=cfg['window_months']))


def _safe_filename(s):
    """去掉 Windows/Unix 都不适合做文件名的字符。"""
    return re.sub(r'[\\/:*?"<>|\r\n\t]+', '_', s).strip()


def today_date(cfg):
    return _parse_date(cfg.get('today')) or datetime.date.today()


def _parse_date(s):
    m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', str(s or ''))
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def add_months(d, n):
    """按月加，日取 1 号避免月末溢出。"""
    y, m = d.year, d.month + n
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return datetime.date(y, m, d.day if d.day <= 28 else 28)


def window_bounds(cfg):
    """返回 (today, now_ym, win_ym, window_end)。

    now_ym  = today + 3 个月：该月及以前投产 => 采购决策正在发生（"现在就该联系"）
    win_ym  = today + window_months：该月及以前投产 => 落在用户窗口内
    """
    t = today_date(cfg)
    n3 = add_months(t, 3)
    nw = add_months(t, int(cfg['window_months']))
    return t, (n3.year, n3.month), (nw.year, nw.month), add_months(t, int(cfg['window_months']))


# ---------------------------------------------------------------- 归一化

def norm_company(n):
    """公司名归一（用于去重键）：去掉括号注释与公司后缀。"""
    n = re.sub(r'[（(].*?[)）]', '', n or '')
    n = re.sub(r'(股份有限公司|有限责任公司|有限公司|集团有限公司|集团|控股|股份|公司)$', '', n)
    return re.sub(r'\s+', '', n)


def norm_stage(s, stages=None):
    s = (s or '').strip()
    if not s:
        return '未披露'
    for st in (stages or DEFAULT_STAGES):
        if st in s:
            return st
    for k, v in STAGE_ALIAS.items():
        if k in s:
            return v
    return '未披露'


def norm_src_type(t, src_types=None):
    t = (t or '').strip()
    for st in (src_types or DEFAULT_SRC_TYPES):
        if st in t:
            return st
    return '新闻'


def parse_month(s):
    """把各种写法解析为 (year, month)；解析不出返回 None。

    支持 2027-03 / 2027/3 / 2027.3 / 2027年3月 / 2027Q1 / 2027年上半年 / 2027。
    """
    if not s:
        return None
    s = str(s).strip()
    m = re.search(r'(20\d{2})\s*[-/年\.]\s*(\d{1,2})', s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return (y, mo)
    m = re.search(r'(20\d{2})\s*[Qq]\s*([1-4])', s)
    if m:
        return (int(m.group(1)), (int(m.group(2)) - 1) * 3 + 1)
    m = re.search(r'(20\d{2})\s*年?\s*(上|下)?半年', s)
    if m:
        return (int(m.group(1)), 1 if m.group(2) != '下' else 7)
    m = re.search(r'(20\d{2})', s)
    if m:
        return (int(m.group(1)), 6)  # 只给年份 → 取年中，粗糙
    return None


def in_region(cfg, prov_city):
    """地区闸门：省市是否落在 cfg.region.provinces 内。provinces 为空表示不限。"""
    provs = cfg.get('region', {}).get('provinces') or []
    if not provs:
        return True
    prov = re.split(r'[/／、,，\s]', str(prov_city or ''))[0]
    prov = re.sub(r'(省|市|自治区|特别行政区)$', '', prov)
    for p in provs:
        pp = re.sub(r'(省|市|自治区|特别行政区)$', '', p)
        if prov == pp or prov.startswith(pp) or pp.startswith(prov):
            return True
    return False


def is_peer(cfg, name):
    """peer gate：返回命中的同行关键词，未命中返回 None。"""
    n = name or ''
    for p in cfg.get('peer_keywords', []):
        if p and p in n:
            return p
    return None


# ---------------------------------------------------------------- 推导

def derive_timing(cfg, stage, ramp):
    """销售时点推导。返回 (时点, 理由)。按月粒度对齐用户窗口。"""
    _, now_ym, win_ym, _ = window_bounds(cfg)
    months = int(cfg['window_months'])
    now_lbl = '%d-%02d' % now_ym
    win_lbl = '%d-%02d' % win_ym
    ym = parse_month(ramp)

    if stage == '试车':
        return ('现在就该联系',
                '项目已进入试车/试生产，装置正在消化原料，供应商名单尚可切入，是最佳窗口')
    if stage == '已投产':
        # "近半年内投产" = 今天往前 6 个月
        d = _month_date(ym)
        cutoff = add_months(today_date(cfg), -6)
        if d and d >= cutoff:
            return ('现在就该联系',
                    '项目近半年内投产，仍处达产爬坡与供应商调整期，补量/换源机会大')
        return ('仅需关注', '项目已投产较久，供应商格局稳定，仅作长期替换储备，非当期机会')
    if stage == '在建':
        if ym is None:
            # 在建但未披露投产月份：不能当作"什么都不用做"——合格供应商入库/送样检测本身
            # 就要 1~3 个月，等到点火/试车再切入就晚了。故归入"提前布局"。
            return ('3-6个月后再联系',
                    '项目已在建但未披露投产月份；按合格供应商入库与送样检测 1~3 个月的前置期，'
                    '应在未来 3~6 个月完成技术对接与入库，待投产时间明确后立即推进商务')
        if ym <= now_ym:
            return ('现在就该联系',
                    '在建且 %s 前投产，按装置提前 1~3 个月锁定原料并完成合格供应商入库的规律，'
                    '采购决策正在发生' % now_lbl)
        if ym <= win_ym:
            return ('3-6个月后再联系',
                    '预计 %s~%s 投产，采购启动点落在 3~6 个月后；现在留资、送样、建立技术对接正当其时'
                    % (_next_month_label(now_ym), win_lbl))
        return ('仅需关注',
                '预计投产时间超出未来 %d 个月窗口，暂不投入销售资源' % months)
    if stage == '备案':
        if ym is not None and ym <= win_ym:
            return ('3-6个月后再联系',
                    '项目已备案、落地确定性较高，但仍在审批/设计阶段，采购尚未启动；先建联，待开工后再推进')
        return ('仅需关注', '仅完成备案，投产时间远或未披露，尚未形成当期原料需求')
    if stage == '拟建':
        return ('仅需关注', '拟建阶段，尚未核准/备案落地，存在取消或延期风险，仅作商机储备')
    return ('仅需关注', '建设阶段未披露，需电话核实')


def _month_date(ym):
    if not ym:
        return None
    y, mo = ym
    return datetime.date(y, mo, 15)


def _next_month_label(ym):
    y, m = ym
    m += 1
    if m > 12:
        y, m = y + 1, 1
    return '%d-%02d' % (y, m)


def demand_nature(rec):
    """直接 = 本产品进入产品分子/配合料主体系；间接 = 仅上游转化或尾气/废水中和等衍生需求。"""
    txt = (rec.get('需求点', '') or '') + (rec.get('单耗依据', '') or '')
    if '间接' in txt and rec.get('产品角色') != '主原料':
        return '间接'
    return '直接'


def derive_priority(intensity, conf, indirect=False):
    """优先级 = 用量强度 × 置信度权重；间接需求降权。返回 (等级, 分数)。"""
    score = int(intensity or 0) * CONF_WEIGHT.get(conf, 1)
    if indirect:
        score -= 4
    if score >= 12:
        return ('高', score)
    if score >= 8:
        return ('中', score)
    return ('低', score)


def normalize_record(cfg, raw, lane_id, lane_name, intensity):
    """把一条原始记录补全为规范记录；返回 (rec, drop_reason)。

    drop_reason 非空表示该条被剔除（peer / 地区 / 缺关键字段）。
    """
    rec = {}
    for k in COLLECT_FIELDS:
        v = raw.get(k, '')
        rec[k] = '' if v is None else v
    for k in ('置信度', '产品角色', '需求点', '来源', '公司', '项目名称', '省市'):
        rec[k] = str(rec[k]).strip()

    if not rec['公司'] or not rec['项目名称']:
        return None, 'missing_company_or_project'

    hit = is_peer(cfg, rec['公司'])
    if hit:
        return None, 'peer:%s' % hit

    if not in_region(cfg, rec['省市']):
        return None, 'out_of_region'

    rec['lane'] = '%s %s' % (lane_id, lane_name)
    rec['lane_id'] = lane_id
    rec['用量强度'] = '★' * int(intensity or 0)
    rec['_intensity'] = int(intensity or 0)
    rec['建设阶段'] = norm_stage(rec['建设阶段'], cfg.get('stages_vocab'))
    rec['来源类型'] = norm_src_type(rec['来源类型'], cfg.get('source_types_vocab'))
    if rec['置信度'] not in CONF_WEIGHT:
        rec['置信度'] = '低'

    st, why = derive_timing(cfg, rec['建设阶段'], rec['预计投产时间'])
    rec['销售时点'] = st
    rec['时点理由'] = why
    rec['需求性质'] = demand_nature(rec)

    if not rec['来源'] or rec['来源'] in ('未核实', '无', '-', 'N/A', 'n/a'):
        rec['来源'] = '未核实'
        rec['置信度'] = '低'

    pr, score = derive_priority(intensity, rec['置信度'], rec['需求性质'] == '间接')
    rec['优先级'] = pr
    rec['_score'] = score
    return rec, ''


def load_lanes(cfg, root):
    """读 lanes.json；返回 (lanes_by_id, lanes_list)。缺文件返回空。"""
    path = os.path.join(root, cfg['paths']['lanes'])
    if not os.path.exists(path):
        return {}, []
    try:
        with open(path, encoding='utf-8-sig') as f:
            data = json.load(f)
    except Exception:
        return {}, []
    lanes = data.get('lanes', data if isinstance(data, list) else [])
    by_id = {}
    for i, ln in enumerate(lanes):
        lid = str(ln.get('id') or '%02d' % (i + 1)).zfill(2)
        ln['id'] = lid
        ln.setdefault('name', '未命名板块')
        ln.setdefault('intensity', 3)
        by_id[lid] = ln
    return by_id, lanes