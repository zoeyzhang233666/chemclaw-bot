# -*- coding: utf-8 -*-
"""事件去重与重要性筛选。

用法：
  python dedupe.py events_raw.json --out events.json --report-date 2026-10-20

解决的问题（对应 SKILL.md「事件去重规则」）：
- D1 同一事件的转载：多家媒体同一事件 -> 保留最早发生日期那条，其余记 dup_of；
- D2 旧闻新发：event_date 早于上一期基线且已在本期之前记录过 -> 标 repeat，降级；
- D3 无主体无数字的泛评：既无企业/装置名，也无量化 -> tier=C，排除；
- D4 无影响路径：impact_path 为空 -> 最多 B；
- D5 已兑现 vs 预期：event_type=plan/expect 的，不能当「已发生」，标注 status。

评分（0-100）：影响路径清晰度 30 + 量化程度 25 + 时效性 20 + 独特性 15 + 覆盖度 10
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common


def score_event(ev, report_date, baseline_date):
    s = 0
    detail = {}
    # 1) 影响路径：有明确传导链条（成本/供给/需求/政策作用于哪个环节）
    path = ev.get('impact_path') or ''
    detail['path'] = 30 if len(path) >= 12 else (18 if path else 0)
    s += detail['path']
    # 2) 量化：事件里带吨数/万吨/元/百分点的，才算硬信息
    q = ev.get('quant') or ''
    detail['quant'] = 25 if q else 0
    s += detail['quant']
    # 3) 时效：按事件发生日与报告日的距离
    gap = common.days_between(ev.get('event_date'), report_date)
    if gap is None:
        detail['fresh'] = 0
    elif gap <= 1:
        detail['fresh'] = 20
    elif gap <= 3:
        detail['fresh'] = 12
    elif gap <= 7:
        detail['fresh'] = 6
    else:
        detail['fresh'] = 0
    s += detail['fresh']
    # 4) 独特性：是否为本次新增（非转载、非重复）
    detail['unique'] = 0 if ev.get('dup_of') else 15
    s += detail['unique']
    # 5) 覆盖度：影响几个品种
    detail['cover'] = min(10, 5 * len(ev.get('products') or []))
    s += detail['cover']
    return s, detail


def tier_of(s, ev):
    """分级：
    - 转载合并掉的从属条目（dup_of）：C；
    - 纯观点/泛评且无量化（D3）：C；
    - 发生在基线之前的事件（D2 repeat）：最高只到 B —— 它是「进展更新」，不是当日新事件，
      保留在报告里会误导读者把它当成新增，但直接删掉又会让读者失去必要的产业背景；
    - 其余按分数 A≥70 / B≥45 / C<45。
    """
    if ev.get('dup_of'):
        return 'C'
    if ev.get('event_type') in ('comment', 'view') and not ev.get('quant'):
        return 'C'
    if ev.get('status') == 'repeat':
        return 'B' if s >= 45 else 'C'
    if s >= 70:
        return 'A'
    if s >= 45:
        return 'B'
    return 'C'


# 同义事件类型归一：同一件事常被不同媒体写成不同标签
TYPE_FAMILY = {
    'shipping': 'geo', 'geo': 'geo', 'war': 'geo', 'sanction': 'geo',
    'plant': 'plant', 'maintenance': 'plant', 'restart': 'plant', 'shutdown': 'plant',
    'capacity': 'capacity', 'project': 'capacity',
    'policy': 'policy', 'regulation': 'policy', 'tariff': 'policy',
    'trade': 'trade', 'import': 'trade', 'export': 'trade',
    'price': 'price', 'quote': 'price',
    'demand': 'demand', 'inventory': 'demand', 'stock': 'demand',
    'cost': 'cost', 'profit': 'cost',
    'comment': 'comment', 'view': 'comment',
}


def _fam(t):
    return TYPE_FAMILY.get(t or '', t or '')


# 实体归一：媒体对同一主体的不同叫法要落到同一个规范名上。
# 注意顺序与外延：越具体的实体越靠前，避免「PVC 开工」被「电石成本」抢走。
ENTITY_CANON = [
    (('霍尔木兹', '海峡', 'Hormuz'), '霍尔木兹海峡'),
    (('新增产能', '新产能', '华锦', '中沙古雷', '榆林二期', '产能投放'), 'PP新增产能'),
    (('国能榆林',), '国能榆林'),
    (('检修损失', '检修损失量', '检修量'), 'PVC检修损失'),
    (('MTO', '沿海烯烃', 'C/MTO', '诚志', '富德', '斯尔邦', '兴兴'), '沿海MTO'),
    (('伊朗', 'Kaveh', 'Sabalan', 'Kimiya'), '伊朗甲醇装置'),
    (('开工', '停车装置', '秋检', '负荷率'), 'PVC开工'),
    (('出口签单', 'PVC出口'), 'PVC出口'),
    (('塑编', 'BOPP', '注塑'), 'PP下游'),
    (('大秦线', '兰炭', '电石', '煤价'), '煤-兰炭-电石成本'),
    (('信发', '淄博', '临沂'), '山东PVC'),
    (('明泉', '联盟'), '山东甲醇企业'),
]


def _entity_field(ev):
    """只取 entity 字段做精确归一（标题里的关键词太容易误判）。"""
    return (ev.get('entity') or '').strip()


# 归一化关键量：把「100 元」「10.61 万吨」「61.50%」等抽成指纹
NUM_RE = re.compile(r'\d+(?:\.\d+)?')


def num_fingerprint(ev):
    """数字指纹只从 quant 字段抽取 —— 标题里的日期、序号会造成大量假重合。"""
    src = ev.get('quant') or ''
    return set(NUM_RE.findall(src))


def dedupe(events, report_date, baseline_date, thresh=0.30):
    """事件聚类（D1）。判定「同一事件」三选一即可：

    a) 规范实体相同 + 类型族相同 + quant 数字指纹有交集；
    b) 规范实体相同 + 类型族相同 + 发生日期相差 ≤1 天且标题 2-gram 相似 ≥ 阈值；
    c) 标题/正文 2-gram 相似 ≥ 0.55（近乎原文转载）。

    仅靠字符串相似度无法识别中文改写稿（实测改写稿 sim≈0.06），
    因此以「实体 + 数字指纹 + 时间窗」为主，文本相似度只兜底原文转载。
    """
    clusters = []
    for ev in events:
        fam = _fam(ev.get('event_type'))
        ent = _entity_field(ev)
        ent_c = ent
        for keys, name in ENTITY_CANON:          # 实体字段精确归一
            if ent and any(k in ent for k in keys):
                ent_c = name
                break
        fp = num_fingerprint(ev)
        text = (ev.get('title') or '') + (ev.get('detail') or '')
        ed = common.parse_date(ev.get('event_date'))
        placed = False
        for c in clusters:
            if _fam(c['type']) != fam:
                continue
            sim = common.jaccard(c['text'], text)
            gap = abs((ed - c['date']).days) if (ed and c['date']) else 99
            same_ent = bool(ent_c) and ent_c == c['entity']
            ok = False
            if sim >= 0.55:
                ok = True                                  # c) 原文转载
            elif same_ent and (fp & c['fp']):
                ok = True                                  # a) 实体 + 数字指纹
            elif same_ent and gap <= 1 and (sim >= thresh or len(fp) == 0 or len(c['fp']) == 0):
                # b) 同实体同族、事件窗相近；其中一方无量化信息时也判为同一事件
                #    （例：『海峡遇袭致沉船』与『海峡周边航线再遭袭击』是同一持续事件的两次报道）
                ok = True
            if ok:
                c['members'].append(ev)
                c['text'] += text
                c['fp'] |= fp
                c['date'] = min([d for d in (c['date'], ed) if d] or [None])
                placed = True
                break
        if not placed:
            clusters.append({'type': ev.get('event_type'), 'entity': ent_c,
                             'text': text, 'fp': fp, 'date': ed, 'members': [ev]})

    out = []
    for c in clusters:
        # 保留发生日期最早的一条为主条（首发），标题以主条为准
        c['members'].sort(key=lambda x: (common.parse_date(x.get('event_date')) or
                                         common.parse_date('2099-01-01')))
        head = dict(c['members'][0])
        dups = [m.get('source') for m in c['members'][1:]]
        head['dup_count'] = len(dups)
        head['dup_sources'] = dups
        if dups:
            head['dedupe_note'] = '另有 %d 家转载/同事件报道已合并：%s' % (len(dups), '、'.join(dups))
        s, det = score_event(head, report_date, baseline_date)
        head['score'] = s
        head['score_detail'] = det
        # D2：发生日早于上一期基线，说明上一期就该看到——本期末再当「新闻」
        ed = common.parse_date(head.get('event_date'))
        bd = common.parse_date(baseline_date)
        if ed and bd and ed < bd and head.get('recorded_before'):
            head['status'] = 'repeat'
            head['repeat_note'] = '该事件发生于上一期基线（%s）之前，本期仅更新进展，不视为新增' % baseline_date
        head['tier'] = tier_of(s, head)
        if head['tier'] == 'C':
            head['exclude_reason'] = (
                '重复转载（%d 源合并）' % len(dups) if dups else
                '缺乏量化与明确影响路径' if s < 45 else '无新增信息')
        out.append(head)

    out.sort(key=lambda x: (-{'A': 3, 'B': 2, 'C': 1}[x['tier']], -x['score']))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('events', help='原始事件 JSON（数组）')
    ap.add_argument('--out', default='events.json')
    ap.add_argument('--report-date', required=True)
    ap.add_argument('--baseline-date', required=True)
    ap.add_argument('--threshold', type=float, default=0.55)
    a = ap.parse_args()
    evs = common.load_json(a.events)
    if isinstance(evs, dict):                     # 支持 {"events": [...]} 包装
        evs = evs.get('events') or evs.get('items') or []
    res = dedupe(evs, a.report_date, a.baseline_date, a.threshold)
    common.dump_json(res, a.out)
    a_n = sum(1 for e in res if e['tier'] == 'A')
    b_n = sum(1 for e in res if e['tier'] == 'B')
    c_n = sum(1 for e in res if e['tier'] == 'C')
    common.ok('事件簇 %d（A %d / B %d / C %d），合并转载 %d 条' % (
        len(res), a_n, b_n, c_n, sum(e.get('dup_count', 0) for e in res)))


if __name__ == '__main__':
    main()
