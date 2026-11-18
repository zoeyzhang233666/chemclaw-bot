#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-file integrity validator for a news-event-localization case.

Usage:
    python validate.py <src_dir>

Checks id uniqueness, referential integrity, dedupe coverage (every news item is
either linked to an event or explicitly unassigned), enum legality, and the hard
constraint that capacity figures always carry a source.

Exit code 0 = pass, 1 = errors found.
"""
import json
import os
import sys
import collections

REQUIRED = ('sources.json', 'news.json', 'events.json', 'entities.json',
            'chain.json', 'dedupe.json', 'toverify.json')
TYPES = ('项目投产', '装置检修', '停车复产', '产能扩建', '贸易政策', '环保安全',
         '下游需求', '其他产业事件')
LEVELS = ('full', 'partial', 'summary_only', 'title_only')
CONFS = ('C1', 'C2', 'C3', 'C4')
RELATIONS = ('primary', 'republish', 'followup', 'index_entry', 'selfmedia', 'conflict')
TIERS = ('T0', 'T1', 'T2')

errors, warns = [], []


def err(m):
    errors.append(m)


def warn(m):
    warns.append(m)


def main(srcdir):
    files = {}
    for name in REQUIRED:
        p = os.path.join(srcdir, name)
        if not os.path.exists(p):
            err(f'缺少文件 {name}')
            continue
        try:
            with open(p, encoding='utf-8') as f:
                files[name] = json.load(f)
        except Exception as e:
            err(f'{name} 不是合法 JSON: {e}')

    if errors:
        report()
        return 1

    sources = files['sources.json'].get('sources', [])
    news = files['news.json'].get('items', [])
    events = files['events.json'].get('events', [])
    ents = files['entities.json']
    chain = files['chain.json']
    ded = files['dedupe.json']
    tv = files['toverify.json'].get('questions', [])

    src_ids = {s.get('src_id') for s in sources}
    news_ids = {n.get('news_id') for n in news}
    evt_ids = {e.get('event_id') for e in events}
    ent_ids = {c.get('ent_id') for c in ents.get('companies', [])}
    plant_ids = {p.get('plant_id') for p in ents.get('plants', [])}
    node_ids = {n.get('node_id') for n in chain.get('nodes', [])}
    q_ids = {q.get('q_id') for q in tv}

    # ---- uniqueness
    for label, ids in (('source', [s.get('src_id') for s in sources]),
                       ('news', [n.get('news_id') for n in news]),
                       ('event', [e.get('event_id') for e in events]),
                       ('company', [c.get('ent_id') for c in ents.get('companies', [])]),
                       ('plant', [p.get('plant_id') for p in ents.get('plants', [])]),
                       ('node', [n.get('node_id') for n in chain.get('nodes', [])]),
                       ('question', [q.get('q_id') for q in tv])):
        dup = [k for k, v in collections.Counter(ids).items() if v > 1]
        if dup:
            err(f'{label} 存在重复 id: {dup}')
        if None in ids:
            err(f'{label} 存在缺失 id')

    # ---- sources
    for s in sources:
        if s.get('tier') not in TIERS:
            err(f"{s.get('src_id')}: tier 非法 {s.get('tier')}")
        if not s.get('access_note') and s.get('access') != '可读':
            err(f"{s.get('src_id')}: 非“可读”源必须写 access_note")

    # ---- news
    for n in news:
        nid = n.get('news_id')
        if n.get('src_id') not in src_ids:
            err(f'{nid}: 未知 src_id {n.get("src_id")}')
        if not str(n.get('url', '')).startswith('http'):
            err(f'{nid}: 缺少合法 url')
        if not n.get('first_pub') and not n.get('first_pub_note'):
            err(f'{nid}: first_pub 与 first_pub_note 均为空')
        if n.get('content_level') not in LEVELS:
            err(f'{nid}: content_level 非法 {n.get("content_level")}')
        if n.get('dup_of') and n['dup_of'] not in news_ids:
            err(f'{nid}: dup_of 指向未知 {n["dup_of"]}')

    # ---- events
    for e in events:
        eid = e.get('event_id')
        if e.get('type') not in TYPES:
            err(f'{eid}: type 非法 {e.get("type")}')
        if e.get('verify_status') not in CONFS:
            err(f'{eid}: verify_status 非法')
        if not e.get('verify_basis'):
            err(f'{eid}: 缺少 verify_basis')
        refs = e.get('news_refs') or []
        if not refs:
            err(f'{eid}: news_refs 为空')
        for r in refs:
            if r not in news_ids:
                err(f'{eid}: news_refs 含未知 {r}')
        for c in e.get('companies') or []:
            if c not in ent_ids:
                err(f'{eid}: 未知企业 {c}')
        for p in e.get('plants') or []:
            if p not in plant_ids:
                err(f'{eid}: 未知装置 {p}')
        cn = e.get('chain_node')
        if cn and cn not in node_ids:
            err(f'{eid}: 未知 chain_node {cn}')
        for q in e.get('open_questions') or []:
            if q not in q_ids:
                err(f'{eid}: 未知问题 {q}')
        d = e.get('dedupe') or {}
        prim = d.get('primary_news') or []
        if not prim:
            err(f'{eid}: dedupe.primary_news 为空')
        for x in prim:
            if x not in refs:
                err(f'{eid}: primary_news {x} 不在 news_refs 中')
        for key in ('republish', 'followups', 'index_entries', 'selfmedia'):
            for x in d.get(key) or []:
                if x not in refs:
                    warn(f'{eid}: dedupe.{key} 的 {x} 不在 news_refs 中')
        if not e.get('title'):
            err(f'{eid}: 缺少 title')
        if not e.get('occur_date'):
            err(f'{eid}: 缺少 occur_date')

    # ---- entities
    for p in ents.get('plants', []):
        if p.get('ent_id') not in ent_ids:
            err(f"{p.get('plant_id')}: 未知 ent_id {p.get('ent_id')}")
        cap = p.get('capacity')
        if cap is not None:
            if not isinstance(cap, (int, float)):
                err(f"{p.get('plant_id')}: capacity 不是数字")
            if not p.get('capacity_source'):
                err(f"{p.get('plant_id')}: 有 capacity 但缺 capacity_source")

    # ---- chain
    for ed in chain.get('edges', []):
        for k in ('from', 'to'):
            if ed.get(k) not in node_ids:
                err(f"edge {ed.get('from')}->{ed.get('to')}: 未知节点 {ed.get(k)}")
    for ind in chain.get('indicators', []):
        if ind.get('node_id') not in node_ids:
            err(f"indicator {ind.get('name')}: 未知节点 {ind.get('node_id')}")

    # ---- dedupe
    seen = set()
    for l in ded.get('links', []):
        ev, nw = l.get('event_id'), l.get('news_id')
        if ev not in evt_ids:
            err(f'dedupe: 未知事件 {ev}')
        if nw not in news_ids:
            err(f'dedupe: 未知资讯 {nw}')
        if l.get('relation') not in RELATIONS:
            err(f'dedupe: relation 非法 {l.get("relation")} ({ev},{nw})')
        if not l.get('basis'):
            err(f'dedupe: ({ev},{nw}) 缺少 basis 判定依据')
        key = (ev, nw)
        if key in seen:
            err(f'dedupe: 重复关系 {key}')
        seen.add(key)
        if ev in evt_ids:
            ev_obj = next(x for x in events if x.get('event_id') == ev)
            if nw not in (ev_obj.get('news_refs') or []):
                warn(f'({ev},{nw}) 在 dedupe 中但不在该事件 news_refs 中')

    for u in ded.get('unassigned', []):
        nw = u.get('news_id')
        if nw not in news_ids:
            err(f'unassigned: 未知资讯 {nw}')
        if not u.get('reason'):
            err(f'unassigned: {nw} 缺少 reason（为什么不立事件）')
        ev = u.get('event_id')
        if ev and ev not in evt_ids:
            err(f'unassigned: 未知事件 {ev}')

    # ---- coverage: every news accounted for exactly once
    linked = {l.get('news_id') for l in ded.get('links', [])}
    unas = {u.get('news_id') for u in ded.get('unassigned', [])}
    for n in news:
        nid = n.get('news_id')
        if nid not in linked and nid not in unas:
            err(f'{nid}: 既未挂到事件，也未列入 unassigned（不允许静默丢失）')
        if nid in linked and nid in unas:
            err(f'{nid}: 同时在 links 与 unassigned')

    # ---- questions
    for q in tv:
        ev = q.get('event_id')
        if ev and ev != '*' and ev not in evt_ids:
            err(f"{q.get('q_id')}: 未知事件 {ev}")
        if q.get('priority') not in ('高', '中', '低'):
            warn(f"{q.get('q_id')}: priority 非 高/中/低")
        if not q.get('where_to_get'):
            warn(f"{q.get('q_id')}: 缺少 where_to_get（不可执行的待验证项）")

    # ---- stats
    print('=' * 66)
    print(f'源 {len(sources)} | 资讯 {len(news)} | 事件 {len(events)} | '
          f'企业 {len(ents.get("companies", []))} | 装置 {len(ents.get("plants", []))}')
    print(f'产业链节点 {len(node_ids)} | 连接 {len(chain.get("edges", []))} | '
          f'指标 {len(chain.get("indicators", []))} | 待验证 {len(q_ids)}')
    print(f'去重关系 {len(ded.get("links", []))} | 未归入 {len(ded.get("unassigned", []))}')
    print('内容深度:', dict(collections.Counter(n.get('content_level') for n in news)))
    print('确认度:', dict(sorted(collections.Counter(e.get('verify_status') for e in events).items())))
    print('事件类型:', dict(collections.Counter(e.get('type') for e in events)))
    return report()


def report():
    print('-' * 66)
    for w in warns:
        print('WARN ', w)
    for e in errors:
        print('ERROR', e)
    print('=' * 66)
    ok = not errors
    print('RESULT:', 'PASS' if ok else f'FAIL ({len(errors)} errors, {len(warns)} warnings)')
    return 0 if ok else 1


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))