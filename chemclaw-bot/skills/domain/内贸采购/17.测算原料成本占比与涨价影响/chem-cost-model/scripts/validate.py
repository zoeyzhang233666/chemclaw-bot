#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把工艺一致性检查升级为"按原料分组比较"，并区分主料/辅料。

规则（见 references/unit-consumption.md §4）：
- 主料之间 scope 必须一致；不一致 -> error（禁止混用不同工艺单耗）
- 辅料允许来自同工艺的另一份文件（如催化剂来自专利、NaOH 来自环评），但必须显式
  dosage.scope 且 warn 提示"辅料单耗跨工艺引用"
- 显式 meta.allowed_scope_mix 可放行，并在页面注明
"""
import re

import units
from units import Unresolvable

REQ_META = ['product', 'as_of']
PRICE_SIX = [('spec', '规格'), ('region', '地区'), ('delivery', '交货方式'),
             ('date', '数据日期'), ('source_ref', '来源')]


def _is_empty(v):
    return v is None or (isinstance(v, str) and not v.strip())


def _scope_key(s):
    """把 scope 文本归一化成可比较的键（去掉括号里的装置/规模说明）。"""
    if not s:
        return None
    t = re.sub(r'[（(][^）)]*[）)]', '', str(s))
    t = re.sub(r'[\s·、,，;/／+＋-]', '', t)
    return t


def check(data):
    E, W = [], []
    meta = data.get('meta') or {}
    for k in REQ_META:
        if _is_empty(meta.get(k)):
            E.append('meta.%s 缺少（产品名称、数据截止日必须给出）' % k)

    target_tax = (meta.get('target_tax_basis') or 'tax_included')
    if target_tax not in ('tax_included', 'tax_excluded'):
        E.append("meta.target_tax_basis 只能是 'tax_included' 或 'tax_excluded'")

    mats = [m for m in (data.get('materials') or []) if m.get('enabled', True) is not False]
    if not mats:
        E.append('materials 为空：至少需要一条原料')

    ids = set()
    main_scopes = {}
    aux_scopes = {}
    for i, m in enumerate(mats):
        tag = 'materials[%d] %s' % (i, m.get('name') or m.get('id') or '')
        if _is_empty(m.get('id')):
            E.append('%s 缺少 id' % tag)
        elif m['id'] in ids:
            E.append('%s id 重复' % tag)
        else:
            ids.add(m['id'])
        if _is_empty(m.get('name')):
            E.append('%s 缺少 name' % tag)

        d = m.get('dosage') or {}
        if isinstance(d, (int, float)) or isinstance(d, str):
            d = {'value': d, 'unit': 't/t'}
        if _is_empty(d.get('value')):
            E.append('%s 缺少 dosage.value' % tag)
        else:
            try:
                units.dosage_to_t_per_t(d['value'], d.get('unit', 't/t'))
            except (Unresolvable, ValueError) as e:
                E.append('%s 单耗单位不可解析：%s' % (tag, e))
            v = float(d['value'])
            if v <= 0:
                E.append('%s 单耗必须为正数' % tag)
        src = d.get('source', 'none')
        if src in ('none', None, ''):
            W.append('%s 单耗未注明来源，按"无来源"处理，页面会标黄' % tag)
        if src == 'simulated':
            W.append('%s 单耗为模拟参数（仅演示用，不得对外表述为企业实际单耗）' % tag)
        if _is_empty(d.get('scope')) and src not in ('simulated', 'user'):
            W.append('%s 单耗缺少 scope（适用工艺/产线），无法核对工艺一致性' % tag)
        key = _scope_key(d.get('scope')) if d.get('scope') else None
        if key:
            (aux_scopes if m.get('role') == 'aux' else main_scopes).setdefault(key, []).append(m['id'])
        if _is_empty(d.get('unit')) and src != 'simulated':
            W.append('%s 单耗未写单位，按 t/t 处理（请确认）' % tag)

        p = m.get('price') or {}
        if isinstance(p, (int, float)):
            p = {'value': p, 'unit': 'CNY/t'}
        if _is_empty(p.get('value')):
            W.append('%s 无价格：该原料不计入成本，将列为缺口（不按 0 处理）' % tag)
        else:
            try:
                units.norm_unit(p.get('unit', 'CNY/t'))
            except Unresolvable as e:
                E.append('%s 价格单位不可解析：%s' % (tag, e))
            for k, label in PRICE_SIX:
                if _is_empty(p.get(k)) and _is_empty(m.get(k)):
                    W.append('%s 价格缺"六项口径"中的%s' % (tag, label))

    # 工艺一致性（只对主料强制）
    if len(main_scopes) > 1:
        msg = ('主料之间单耗 scope 不一致（%s）：不得混用不同工艺的单耗。' %
               '；'.join('%s: %s' % (','.join(v), k) for k, v in main_scopes.items()))
        if meta.get('allowed_scope_mix'):
            W.append(msg + '已按 meta.allowed_scope_mix 显式放行：%s' % meta['allowed_scope_mix'])
        else:
            E.append(msg + '请统一工艺，或在 meta.allowed_scope_mix 中写明依据')
    if aux_scopes:
        all_main = set(main_scopes)
        if all_main and not (set(aux_scopes) & all_main):
            W.append('辅料单耗来自与主料不同的工艺/文件（辅料 scope：%s）：已在页面注明，'
                     '不得把辅料单耗当作同一产线实测值混用' % '；'.join(aux_scopes))
        elif aux_scopes.keys() - all_main:
            W.append('部分辅料的单耗 scope 与主料不同：已在页面注明')

    # ---- 历史
    H = data.get('history') or {}
    hmats = H.get('materials') or []
    if hmats:
        priced = {m.get('id') for m in mats
                  if isinstance(m.get('price'), dict) and not _is_empty((m.get('price') or {}).get('value'))}
        hier = {h.get('material_id') for h in hmats}
        for mid in sorted(x for x in (priced - hier) if x):
            W.append('历史序列缺少原料 %s：相关时段的历史理论成本将标为"不完整/缺口"' % mid)
        for h in hmats:
            if _is_empty(h.get('source')):
                E.append('历史序列 %s 缺少 source：历史价格必须可核验，不允许生成' % h.get('material_id'))
            rows = h.get('rows') or []
            if not rows:
                W.append('历史序列 %s 为空' % h.get('material_id'))
            if rows and not re.match(r'^\d{4}-\d{2}-\d{2}$', (rows[0].get('date') or '')[:10]):
                E.append('历史序列 %s 日期格式应为 YYYY-MM-DD' % h.get('material_id'))
            if any(isinstance(r.get('value'), str) and r['value'].strip() in ('', '-', 'NA', 'na')
                   for r in rows):
                W.append('历史序列 %s 含空值：已按缺口处理（不插值）' % h.get('material_id'))
            if len({(r.get('date') or '')[:10] for r in rows}) < len(rows):
                W.append('历史序列 %s 存在重复日期（按后者覆盖）' % h.get('material_id'))
        if not H.get('blend'):
            W.append('history.blend 为空：历史单耗口径未声明，将无法计算历史成本')

    sc = data.get('scenario_config') or {}
    if not sc.get('amplitude_series'):
        W.append('scenario_config.amplitude_series 未给出，默认使用 ±5%/±10%')

    if not (data.get('not_included') or []):
        W.append('not_included 为空：请显式列出未纳入的成本项（能源/人工/折旧/运费等），'
                 '否则读者会把理论原料成本误当完整成本')
    return E, W
