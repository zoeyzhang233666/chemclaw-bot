# -*- coding: utf-8 -*-
"""合并 lane 产出：去重、peer gate、地区闸门、销售时点与优先级推导，输出 leads.json。

产品无关：板块名与用量强度来自 lanes.json，同行关键词与地区来自 config。
"""
import collections
import datetime
import glob
import json
import os
import re

from . import common as C


def load_qa(cfg, root):
    """来源 URL -> 抽检结论 的映射。

    结论单独放 `抽检结论` 字段，而不是拼进 `来源`——因为 `来源` 必须保持为
    干净、可点击的 URL，拼了后缀在 HTML 里就会变成坏链。
    """
    path = os.path.join(root, cfg['paths']['qa_report'])
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8-sig') as f:
            rep = json.load(f)
    except Exception:
        return {}
    out = {}
    for r in rep.get('results', []):
        url = r.get('url')
        if url:
            out[url] = r.get('verdict', '')
    return out


def _lane_of(cfg, root, base, lanes_by_id):
    """从文件名 `<lane_id>_<名>.json` 推 lane；必要时按名字回退匹配。"""
    lid = base[:2] if base[:2].isdigit() else None
    if lid and lid in lanes_by_id:
        ln = lanes_by_id[lid]
        return lid, ln['name'], ln.get('intensity', 3)
    stem = os.path.splitext(base)[0]
    rest = stem[3:] if (lid and len(stem) > 3) else stem
    for k, ln in lanes_by_id.items():
        if ln['name'] and (ln['name'] in rest or rest in ln['name']):
            return k, ln['name'], ln.get('intensity', 3)
    return (lid or '00'), (rest or '未分类'), 3


def merge(cfg, root):
    """合并 leads_raw/*.json。返回 (leads, stats)，并写出 leads.json / merge_stats.json。"""
    raw_dir = os.path.join(root, cfg['paths']['raw_dir'])
    lanes_by_id, _lanes = C.load_lanes(cfg, root)
    qa_map = load_qa(cfg, root)

    files = sorted(glob.glob(os.path.join(raw_dir, '*.json')))
    files = [f for f in files if not os.path.basename(f).startswith('_')]

    records, problems, per_file = [], [], {}
    dropped = collections.Counter()
    peers_hit, out_of_region = [], []

    for f in files:
        base = os.path.basename(f)
        lid, lane_name, intensity = _lane_of(cfg, root, base, lanes_by_id)
        try:
            with open(f, encoding='utf-8-sig') as fh:
                data = json.load(fh)
        except Exception as e:
            problems.append('%s: JSON 解析失败 %s' % (base, e))
            per_file[base] = 0
            continue
        if not isinstance(data, list):
            problems.append('%s: 顶层不是 JSON 数组' % base)
            per_file[base] = 0
            continue

        n = 0
        for r in data:
            if not isinstance(r, dict):
                continue
            rec, why = C.normalize_record(cfg, r, lid, lane_name, intensity)
            if rec is None:
                dropped[why.split(':')[0]] += 1
                if why.startswith('peer:'):
                    peers_hit.append((r.get('公司', ''), why.split(':', 1)[1], base))
                elif why == 'out_of_region':
                    out_of_region.append((r.get('公司', ''), r.get('省市', ''), base))
                continue
            rec['抽检结论'] = qa_map.get(rec['来源'], '未抽检')
            records.append(rec)
            n += 1
        per_file[base] = n

    # 去重：同公司 + 同项目（归一化后前 24 字），保留置信度更高的一条
    seen, deduped, dups = {}, [], 0
    for r in records:
        key = (C.norm_company(r['公司']),
               re.sub(r'[\s（）()、,，]+', '', r['项目名称'])[:24])
        if key in seen:
            dups += 1
            old = seen[key]
            if C.CONF_WEIGHT.get(r['置信度'], 1) > C.CONF_WEIGHT.get(old['置信度'], 1):
                deduped[deduped.index(old)] = r
                seen[key] = r
            continue
        seen[key] = r
        deduped.append(r)

    deduped.sort(key=lambda r: (C.TIMING_ORDER.get(r['销售时点'], 9),
                                -r['_score'], r['lane_id'], r['公司']))

    with open(os.path.join(root, cfg['paths']['leads']), 'w', encoding='utf-8') as f:
        json.dump(deduped, f, ensure_ascii=False, indent=1)

    t, now_ym, win_ym, win_end = C.window_bounds(cfg)
    by_timing = collections.Counter(r['销售时点'] for r in deduped)
    by_stage = collections.Counter(r['建设阶段'] for r in deduped)
    by_prov = collections.Counter((r['省市'] or '/').split('/')[0] for r in deduped)
    by_conf = collections.Counter(r['置信度'] for r in deduped)
    by_lane = collections.Counter(r['lane'] for r in deduped)
    by_src = collections.Counter(r['来源类型'] for r in deduped)
    by_role = collections.Counter(r['产品角色'] for r in deduped)
    by_nature = collections.Counter(r['需求性质'] for r in deduped)
    by_prio = collections.Counter(r['优先级'] for r in deduped)
    unverified = sum(1 for r in deduped if r['来源'] == '未核实')
    estimated = sum(1 for r in deduped
                    if (r.get('年需求量估算') or '').strip() not in ('', '无法估算', '未披露'))

    stats = {
        'generated_at': str(datetime.datetime.now()),
        'product': cfg['product']['name'],
        'region': cfg['region']['name'],
        'today': str(t), 'window_end': str(win_end),
        'now_cutoff': '%d-%02d' % now_ym, 'win_cutoff': '%d-%02d' % win_ym,
        'raw_records': len(records), 'dups_removed': dups, 'final': len(deduped),
        'unverified_source': unverified, 'estimated_demand': estimated,
        'peers_removed': sorted(set(p[0] for p in peers_hit)),
        'peer_details': [{'company': a, 'keyword': b, 'file': c} for a, b, c in peers_hit],
        'out_of_region': sorted(set('%s(%s)' % (a, b) for a, b, b2 in
                                    [(x[0], x[1], x[2]) for x in out_of_region])),
        'out_of_region_details': [{'company': a, 'prov_city': b, 'file': c}
                                  for a, b, c in out_of_region],
        'dropped': dict(dropped),
        'per_file': per_file,
        'by_timing': dict(by_timing), 'by_stage': dict(by_stage),
        'by_province': dict(by_prov), 'by_confidence': dict(by_conf),
        'by_lane': dict(by_lane), 'by_source_type': dict(by_src),
        'by_role': dict(by_role), 'by_nature': dict(by_nature), 'by_priority': dict(by_prio),
        'unique_sources': len(set(r['来源'] for r in deduped if r.get('来源'))),
        'problems': problems,
    }
    with open(os.path.join(root, cfg['paths']['stats']), 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)

    return deduped, stats


def print_summary(stats):
    print('== 每个 lane 文件产出 ==')
    for k in sorted(stats['per_file']):
        print('  %-42s %d' % (k, stats['per_file'][k]))
    print('\n原始 %d 条 → 去重剔除 %d 条 → 最终 %d 条'
          % (stats['raw_records'], stats['dups_removed'], stats['final']))
    print('peer 剔除 %d 条：%s' % (len(stats['peers_removed']), stats['peers_removed']))
    if stats['out_of_region']:
        print('地区闸门剔除 %d 条：%s' % (len(stats['out_of_region']), stats['out_of_region'][:12]))
    print('无来源(未核实) %d 条 | 年需求量可估算 %d 条'
          % (stats['unverified_source'], stats['estimated_demand']))
    if stats['problems']:
        print('问题：%s' % stats['problems'])
    print('\n销售时点: %s' % stats['by_timing'])
    print('建设阶段: %s' % stats['by_stage'])
    print('置信度:   %s' % stats['by_confidence'])
    print('产品角色: %s' % stats['by_role'])
    print('来源类型: %s' % stats['by_source_type'])
    print('省份:     %s' % stats['by_province'])
    print('\n板块分布:')
    for k, v in sorted(stats['by_lane'].items()):
        print('  %3d  %s' % (v, k))


# --- 契约别名 -----------------------------------------------------------------
# docs/INTERFACE.md §5 把 load_config / render_stem 列在 merge 下，实际实现在 common。
# 这里 re-export，保证按契约 import 的调用方不会踩空。
load_config = C.load_config
render_stem = C.render_stem
window_bounds = C.window_bounds