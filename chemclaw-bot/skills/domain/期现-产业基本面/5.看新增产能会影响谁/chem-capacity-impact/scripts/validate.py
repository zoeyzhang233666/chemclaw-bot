#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chem-capacity-impact · 数据校验（error / warn / info 三级）

用法：
    python scripts/validate.py project.json

退出码：0 = 无 error；1 = 存在 error（流水线应停止）。
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compute import (  # noqa: E402
    BANNED_WORDS, EVIDENCE_ORDER, STAGE_VOCAB, _f, normalize_uc,
)

URL_RE = re.compile(r'^https?://[^\s]+$', re.IGNORECASE)


class Report:
    def __init__(self) -> None:
        self.items: List[Dict[str, str]] = []

    def add(self, level: str, code: str, msg: str, path: str = '') -> None:
        self.items.append({'level': level, 'code': code, 'msg': msg, 'path': path})

    def err(self, code, msg, path=''):
        self.add('error', code, msg, path)

    def warn(self, code, msg, path=''):
        self.add('warn', code, msg, path)

    def info(self, code, msg, path=''):
        self.add('info', code, msg, path)

    def count(self, level):
        return sum(1 for i in self.items if i['level'] == level)

    def dump(self) -> None:
        for lv in ('error', 'warn', 'info'):
            rows = [i for i in self.items if i['level'] == lv]
            if not rows:
                continue
            print(f'--- {lv.upper()} ({len(rows)}) ---')
            for r in rows:
                p = f' [{r["path"]}]' if r['path'] else ''
                print(f'  {r["code"]:<26}{p} {r["msg"]}')


def walk_strings(obj: Any, path: str = ''):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(v, f'{path}.{k}' if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_strings(v, f'{path}[{i}]')
    elif isinstance(obj, str):
        yield path, obj


def validate(project: Dict[str, Any]) -> Report:
    r = Report()
    meta = project.get('meta') or {}
    proj = project.get('project') or {}
    chain = project.get('chain') or {}
    bases = project.get('capacity_bases') or []
    ucs = project.get('unit_consumption') or []
    assumptions = project.get('assumptions') or {}
    scenarios = project.get('scenarios') or []
    regional = project.get('regional') or {}

    # ---------- meta ----------
    if not meta.get('asof'):
        r.err('META_ASOF', 'meta.asof 缺失：必须写明数据截止日（YYYY-MM-DD），不是写作日')
    elif not re.match(r'^\d{4}-\d{2}-\d{2}$', str(meta['asof'])):
        r.warn('META_ASOF_FMT', f'meta.asof={meta.get("asof")} 不是 YYYY-MM-DD')
    if not meta.get('product'):
        r.err('META_PRODUCT', 'meta.product 缺失')
    if meta.get('simulated') and not meta.get('simulated_note'):
        r.info('META_SIM', 'meta.simulated=true 但缺少模拟说明，HTML 会自动加默认横幅')

    # ---------- project ----------
    cap = _f(proj.get('design_capacity_t'))
    if cap <= 0:
        r.err('PROJ_CAP', 'project.design_capacity_t 必须 > 0（单位：吨/年）', 'project.design_capacity_t')
    elif cap > 50_000_000:
        r.warn('PROJ_CAP_UNIT', f'design_capacity_t={cap:,.0f} 超过 5000 万吨，请确认单位是否为"吨/年"而非其他')
    stage = proj.get('stage')
    if stage not in STAGE_VOCAB:
        r.err('PROJ_STAGE', f'project.stage="{stage}" 不在标准词表 {STAGE_VOCAB} 内', 'project.stage')
    sp = proj.get('startup_plan') or {}
    m = sp.get('month')
    if m is None:
        r.err('PROJ_START_MONTH', 'startup_plan.month 缺失（1–12）', 'project.startup_plan.month')
    elif not (1 <= int(_f(m)) <= 12):
        r.err('PROJ_START_MONTH', f'startup_plan.month={m} 不在 1–12', 'project.startup_plan.month')
    if not _f(sp.get('year')):
        r.err('PROJ_START_YEAR', 'startup_plan.year 缺失', 'project.startup_plan.year')
    if not sp.get('text'):
        r.warn('PROJ_START_TEXT', 'startup_plan.text 缺失：应抄录公告原文（"建成"≠"投产"）')
    if not sp.get('announce_date'):
        r.warn('PROJ_START_ANN', 'startup_plan.announce_date 缺失：投产计划必须挂公告日期')
    for k in ('owner', 'location', 'product_spec', 'capacity_scope'):
        if not proj.get(k):
            r.warn('PROJ_FIELD', f'project.{k} 缺失（事实核验卡七必核字段之一）', f'project.{k}')
    conf = proj.get('phase_confidence') or {}
    for k in ('design_capacity', 'process', 'stage', 'startup'):
        lv = conf.get(k)
        if lv is None:
            r.warn('PROJ_CONF', f'phase_confidence.{k} 缺失', f'project.phase_confidence.{k}')
        elif lv not in EVIDENCE_ORDER:
            r.err('PROJ_CONF', f'phase_confidence.{k}="{lv}" 不是 E1–E5', f'project.phase_confidence.{k}')
        elif lv in ('E4', 'E5') and k in ('design_capacity', 'process', 'stage'):
            r.warn('PROJ_CONF_LOW', f'关键字段 {k} 证据等级仅 {lv}：报告结论应降级为情景测算',
                   f'project.phase_confidence.{k}')

    # ---------- chain 与单耗 ----------
    ucs_map = normalize_uc(ucs)
    if not ucs:
        r.err('UC_EMPTY', 'unit_consumption 为空，无法测算上游原料需求')
    for e in (chain.get('edges') or []):
        uk = e.get('unit_key')
        if uk and uk not in ucs_map:
            r.err('CHAIN_UC_MISS', f'chain.edges 引用了不存在的 unit_key="{uk}"', 'chain.edges')
    node_ids = {n.get('id') for n in (chain.get('nodes') or [])}
    for e in (chain.get('edges') or []):
        for side in ('from', 'to'):
            if e.get(side) not in node_ids:
                r.err('CHAIN_NODE_MISS', f'chain.edges.{side}="{e.get(side)}" 不在 chain.nodes 中', 'chain.edges')

    for i, u in enumerate(ucs):
        p = f'unit_consumption[{i}]'
        v = _f(u.get('value'))
        if v <= 0:
            r.err('UC_VALUE', f'{u.get("key")} value 必须 > 0', p)
        base = (u.get('basis') or '').split()[0] if u.get('basis') else ''
        if base not in ('C1', 'C2', 'C3', 'C4'):
            r.warn('UC_BASIS', f'{u.get("key")} basis 未标 C1–C4 等级', p)
        ev = u.get('evidence') or {}
        lv = ev.get('level') or u.get('evidence_level')
        if lv not in EVIDENCE_ORDER:
            r.warn('UC_EVID', f'{u.get("key")} evidence.level 缺失或非法（可写在 evidence.level 或顶层 evidence_level）', p)
        elif lv in ('E4', 'E5'):
            r.warn('UC_EVID_LOW', f'{u.get("key")} 单耗证据仅 {lv}：报告中必须标为"情景参数（假设）"并允许调整', p)
        if not ev.get('url') and lv in ('E1', 'E2'):
            r.warn('UC_URL', f'{u.get("key")} 标为 {lv} 但未给 URL，无法复核；将降级展示', p)
        if ev.get('level') and u.get('evidence_level') and ev.get('level') != u.get('evidence_level'):
            r.warn('UC_EVID_CONFLICT',
                   f'{u.get("key")} 两处证据等级不一致（evidence.level={ev.get("level")} / evidence_level={u.get("evidence_level")}），将以后者为准',
                   p)
        rng = u.get('range')
        if rng:
            if not (isinstance(rng, list) and len(rng) == 2):
                r.warn('UC_RANGE', f'{u.get("key")} range 应为 [下限, 上限]', p)
            elif not (_f(rng[0]) <= v <= _f(rng[1])):
                r.warn('UC_RANGE_OUT', f'{u.get("key")} value={v} 不在 range {rng} 内', p)
        pur = u.get('purity')
        if pur is not None and not (0.5 <= _f(pur) <= 1.0):
            r.warn('UC_PURITY', f'{u.get("key")} purity={pur} 应在 0.5–1.0', p)
        if base == 'C3' and 'on_site' not in u:
            r.info('UC_C3', f'{u.get("key")} 为化学计量下限，仅可作"最低不可能低于"的校验')

    # ---------- capacity bases ----------
    keys = [b.get('key') for b in bases]
    for k in ('national', 'regional'):
        if k not in keys:
            r.err('BASE_MISSING', f'capacity_bases 缺少必需分母 "{k}"')
    if 'radius' not in keys and not regional.get('neighbors'):
        r.warn('BASE_RADIUS', '缺少竞争半径分母，且无 neighbors：radius 占比将无法计算')
    for i, b in enumerate(bases):
        p = f'capacity_bases[{i}]'
        # grade 及其它"可选分母"允许留空——留空即缺口，由脚本在报告中标注，不报 error
        optional_keys = ('grade', 'radius', 'pipeline', 'imports', 'exports')
        if _f(b.get('value_t')) <= 0 and not (b.get('key') == 'radius' and regional.get('neighbors')):
            if b.get('key') in optional_keys:
                r.info('BASE_EMPTY', f'{b.get("key")} 分母为空，将作为缺口在报告中标注（不参与占比计算）', p)
            else:
                r.err('BASE_VALUE', f'{b.get("key")} value_t 必须 > 0', p)
        if not b.get('year'):
            r.warn('BASE_YEAR', f'{b.get("key")} 缺少年份：占比必须绑定年份', p)
        if not b.get('scope'):
            r.warn('BASE_SCOPE', f'{b.get("key")} 缺少口径说明（含不含在建/粉料等）', p)
        if b.get('level') in ('E4', 'E5'):
            r.info('BASE_LEVEL', f'{b.get("key")} 分母证据 E4/E5：建议同时提供替代口径做敏感性', p)

    # ---------- assumptions ----------
    lf = _f(assumptions.get('steady_lf'), -1)
    if lf < 0:
        r.err('ASM_LF', 'assumptions.steady_lf 缺失')
    elif not (0.4 <= lf <= 1.0):
        r.warn('ASM_LF_RANGE', f'steady_lf={lf} 超出常见 0.40–1.00')
    elif not assumptions.get('steady_lf_basis'):
        r.warn('ASM_LF_BASIS', 'steady_lf 缺少 *_basis 说明（属假设，必须在报告中标注）')
    model = (assumptions.get('ramp_model') or '').lower()
    if model not in ('none', 'linear', 'exponential', 's_curve', 'step', 'custom'):
        r.err('ASM_RAMP', f'ramp_model="{model}" 非法')
    if model not in ('none', 'step', 'custom') and not _f(assumptions.get('ramp_months')):
        r.err('ASM_RAMP_M', 'ramp_months 缺失')
    elif model not in ('none', 'step', 'custom') and not assumptions.get('ramp_basis'):
        r.warn('ASM_RAMP_BASIS', 'ramp_months 缺少 *_basis 说明')
    if model not in ('none', 'step', 'custom') and _f(assumptions.get('ramp_months')) > 30:
        r.warn('ASM_RAMP_LONG', 'ramp_months > 30：检查是否把"建设期"误当"爬坡期"')

    # ---------- scenarios ----------
    if not scenarios:
        r.warn('SCN_EMPTY', 'scenarios 为空：将只用默认情景')
    has_upper = any((s.get('ramp_model') == 'none' and _f(s.get('steady_lf')) >= 1.0) for s in scenarios)
    if not has_upper:
        r.warn('SCN_UPPER', '缺少"满负荷上限"情景（ramp_model=none 且 steady_lf=1.0）：报告中需据此说明"设计产能≠首年产量"')
    for i, s in enumerate(scenarios):
        sm = s.get('start_month')
        if sm is not None and not (1 <= int(_f(sm)) <= 12):
            r.err('SCN_MONTH', f'scenarios[{i}].start_month={sm} 不在 1–12')
        if s.get('ramp_model') not in (None, 'none', 'linear', 'exponential', 's_curve', 'step', 'custom'):
            r.err('SCN_RAMP', f'scenarios[{i}].ramp_model 非法')

    # ---------- regional ----------
    if not regional.get('name'):
        r.warn('REG_NAME', 'regional.name 缺失')
    if not regional.get('provinces'):
        r.warn('REG_PROV', 'regional.provinces 缺失：区域边界必须写明省份清单')
    if not _f(regional.get('demand_t')):
        r.info('REG_DEM', 'regional.demand_t 缺失：无法计算区域自给率变化')

    # ---------- 前瞻性词 ----------
    for path, s in walk_strings({k: v for k, v in project.items()
                                 if k not in ('meta',)}):
        if path.startswith('meta.disclaimer'):
            continue
        for w in BANNED_WORDS:
            if w in s:
                r.err('BANNED_WORD', f'出现方向性/预测性表述"{w}"：请改写为机制与量级描述', path)

    # ---------- sources ----------
    for i, s in enumerate(project.get('sources') or []):
        u = s.get('url') or ''
        if u and not URL_RE.match(u):
            r.warn('SRC_URL', f'sources[{i}].url 非 http(s)：将被降级为"未核实"', f'sources[{i}]')

    # ---------- gaps ----------
    gaps = project.get('gaps') or []
    must_cover = ('投产', '开工', '产能')
    text_all = ' '.join(str(g.get('item', '')) + str(g.get('impact', '')) for g in gaps)
    for kw in must_cover:
        if kw not in text_all:
            r.warn('GAP_COVER', f'gaps 未覆盖"{kw}"相关的待核实事项（八项必查：投产进度/实际产能/开工条件…）')

    return r


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(__doc__)
        return 2
    path = args[0]
    with open(path, 'r', encoding='utf-8-sig') as fh:
        project = json.load(fh)
    rep = validate(project)
    rep.dump()
    e, w = rep.count('error'), rep.count('warn')
    print(f'\n== {e} error / {w} warn / {rep.count("info")} info ==')
    return 0 if e == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
