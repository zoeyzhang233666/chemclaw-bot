# -*- coding: utf-8 -*-
"""research.json 契约校验（采购版）。

用法：
  python validate.py research.json
  python validate.py research.json --strict    # warning 也当错误

规则分三级：
  ERROR  结构错误 / 会产出误导性数字 —— 必须修
  WARN   缺字段但可降级 —— 会以“缺口”呈现，建议补
  INFO   提示

采购版相比销售版新增的硬约束：
  * 每条报价必须带 point（采购点）、spec、tax、basis、date、src —— 六项口径；
  * 事件必须标 evidence（公开报道/机构观点/传闻/待确认），传闻不会进时间线；
  * 产业链必须带 chain_proof（工艺路线自证），否则报“链未自证”缺口。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

WHY = {
    'meta.product': '没有品种名，报告无法命名',
    'meta.asof': '没有基准日，读者无法判断数据新旧',
    'spot': '没有现货报价，就无法回答“当前价是多少”',
    'spot.point': '缺采购点，不同库/不同区域的价不能混用',
    'spot.spec': '缺规格（品位/执行标准），报价不可比',
    'spot.tax': '未标含税与否，报价不可比',
    'spot.basis': '缺提货方式（出厂/送到/库提），报价不可比',
    'spot.date': '缺日期，报价不可用',
    'spot.src': '缺来源，报价不可引用',
    'quote_series': '没有报价序列，涨跌幅与分位都做不了',
    'futures.series': '没有期货序列，只能少一块参考',
    'gaps': '没有缺口登记，等于宣称数据完整',
    'sources': '没有来源清单，数字不可回溯',
    'chain_proof': '没有工艺路线自证，产业链可能把无关品种算进来',
}

EVIDENCE_OK = ('公开报道', '机构观点', '传闻', '待确认')


def check(R, base_dir='.'):
    E, W, I = [], [], []

    def err(m, key=None):
        E.append(m + ('　（%s）' % WHY[key] if key and key in WHY else ''))

    def warn(m, key=None):
        W.append(m + ('　（%s）' % WHY[key] if key and key in WHY else ''))

    # ---------- meta
    meta = R.get('meta') or {}
    for k in ('product', 'asof'):
        if not meta.get(k):
            err('meta.%s 缺失' % k, 'meta.' + k)
    if meta.get('asof') and not common.parse_date(meta['asof']):
        err('meta.asof 不是可解析日期：%r' % meta['asof'])
    if not meta.get('region'):
        warn('meta.region 缺失，报告将标注为“全国”')
    if not meta.get('spec'):
        warn('meta.spec 缺失（如“≥99.9%”“GB/T 210-2022 II 类”）；规格不明会导致报价不可比')
    if not meta.get('unit'):
        warn('meta.unit 缺失，默认“元/吨”')

    # ---------- 期货（可选）
    fut = R.get('futures') or {}
    if fut.get('series'):
        p = fut['series'] if os.path.isabs(fut['series']) else os.path.join(base_dir, fut['series'])
        if not os.path.exists(p):
            if '_说明' in R or (R.get('meta') or {}).get('product', '').startswith('目标'):
                I.append('模板占位：futures.series 未指向真实文件（%s），实盘请删掉 futures 或生成序列' % fut['series'])
            else:
                err('futures.series 指向的文件不存在：%s' % p, 'futures.series')
        else:
            try:
                rows = common.load_series(p)
                if len(rows) < 30:
                    warn('期货序列只有 %d 行，不足以算区间分位' % len(rows))
                if meta.get('asof') and rows[-1]['d'] > meta['asof']:
                    warn('期货序列中有晚于 asof(%s) 的行，assemble 会自动截断' % meta['asof'])
            except Exception as e:
                err('期货序列解析失败：%s' % e)
    else:
        I.append('未配置 futures.series：本页只做现货口径（采购场景通常不需要期货）')

    # ---------- 现货报价
    spots = R.get('spot') or []
    if not spots:
        err('spot 数组为空', 'spot')
    names = set()
    for i, s in enumerate(spots):
        tag = 'spot[%d]（%s/%s）' % (i, s.get('point') or s.get('region') or '?', s.get('spec') or '?')
        if common.num(s.get('lo')) is None and common.num(s.get('hi')) is None and common.num(s.get('value')) is None:
            err('%s 没有价格数字（lo/hi/value 都为空）' % tag)
        for k in ('point', 'spec', 'tax', 'basis', 'date', 'src'):
            if not s.get(k):
                warn('%s 缺 %s' % (tag, k), 'spot.' + k)
        if s.get('point'):
            names.add(s['point'])
        d = s.get('date')
        if d and common.parse_date(d) and meta.get('asof'):
            age = common.days_between(d, meta['asof'])
            if age is not None and age > 30:
                warn('%s 的报价日期 %s 距 asof %s 已 %d 天' % (tag, d, meta['asof'], age))
        if s.get('tax') and '含税' not in str(s['tax']) and '不含' not in str(s['tax']):
            warn('%s 的 tax 未明确含税/不含税：%r' % (tag, s['tax']))
        if s.get('unit') and s['unit'] != (meta.get('unit') or '元/吨'):
            I.append('%s 使用 %s 口径（与主单位 %s 不同，价格差需换算后再比）'
                     % (tag, s['unit'], meta.get('unit') or '元/吨'))

    # ---------- 采购点序列
    qs = R.get('quote_series') or []
    if not qs:
        if len(spots) >= 2:
            warn('未提供 quote_series；将用 spot 里同一点位的多条报价兜底（点位可能只有 1 条）', 'quote_series')
        else:
            err('既没有 quote_series，spot 也不足 2 条：涨跌幅与分位无法计算', 'quote_series')
    else:
        pts = {}
        for i, q in enumerate(qs):
            if not (q.get('point') and q.get('date')):
                err('quote_series[%d] 缺 point 或 date' % i)
                continue
            if common.num(q.get('lo')) is None and common.num(q.get('hi')) is None:
                err('quote_series[%d] 没有价格数字' % i)
            pts.setdefault(q['point'], []).append(q['date'])
        for p, ds in pts.items():
            if len(ds) < 3:
                I.append('采购点「%s」只有 %d 条报价，无法做区间统计' % (p, len(ds)))
        prim = R.get('primary_point')
        if prim and prim not in pts:
            err('primary_point「%s」不在 quote_series 里' % prim)
        elif prim and len(pts.get(prim, [])) < 3:
            warn('primary_point「%s」报价条数 < 3，首屏分位会留空' % prim)

    # ---------- 锚
    a = R.get('anchor')
    if not a:
        warn('anchor 缺失：首屏“当前价”将取主采购点最后一条报价')
    else:
        if common.num(a.get('value')) is None:
            err('anchor.value 不是数字')
        if a.get('date') and common.parse_date(a['date']) and meta.get('asof'):
            age = common.days_between(a['date'], meta['asof'])
            if age is not None and age > 3:
                I.append('锚价取 %s，距 asof 已 %d 天（现货逐日报价，采购下单前须当日询价）' % (a['date'], age))

    # ---------- 事件
    for i, e in enumerate(R.get('events') or []):
        tag = 'events[%d]（%s）' % (i, e.get('date', '?'))
        if not e.get('date'):
            err('%s 缺 date' % tag)
        if not e.get('title'):
            err('%s 缺 title' % tag)
        if meta.get('asof') and e.get('date') and e['date'] > meta['asof']:
            err('%s 的日期晚于 asof，属未来事件' % tag)
        if not e.get('src'):
            warn('%s 缺 src，事件不可回溯' % tag)
        if not e.get('detail'):
            warn('%s 缺 detail（“当时发生了什么”会显示为空）' % tag)
        ev = e.get('evidence')
        if ev not in EVIDENCE_OK:
            warn('%s 的 evidence=%r，建议用 公开报道/机构观点/传闻/待确认' % (tag, ev))
        if ev == '传闻':
            I.append('%s 为传闻，只会出现在“未采纳消息”，不进入时间线' % tag)

    # ---------- 产业链自证
    proof = R.get('chain_proof') or []
    if not proof:
        warn('chain_proof 为空：产业链上下游无法自证，可能混入无关品种', 'chain_proof')
    for i, p in enumerate(proof):
        if not (p.get('from') and p.get('to')):
            err('chain_proof[%d] 缺 from/to' % i)
        if not p.get('evidence'):
            warn('chain_proof[%d]（%s→%s）缺 evidence：凭什么说这两者是上下游' % (i, p.get('from'), p.get('to')))
        if p.get('checked') is False:
            I.append('chain_proof[%d]（%s→%s）标记为未通过，报告会标红' % (i, p.get('from'), p.get('to')))

    # ---------- 缺口 / 来源
    if not R.get('gaps'):
        warn('gaps 为空：如果确实全部字段有来源，请保留一条说明；否则逐条登记缺口', 'gaps')
    for i, g in enumerate(R.get('gaps') or []):
        if not g.get('item') or not g.get('detail'):
            err('gaps[%d] 缺 item 或 detail' % i)
        if g.get('status') not in ('缺口', '口径冲突', '待更新'):
            warn('gaps[%d].status=%r，建议用 缺口 / 口径冲突 / 待更新' % (i, g.get('status')))
    if not R.get('sources'):
        warn('sources 为空，数字不可回溯', 'sources')
    for i, s in enumerate(R.get('sources') or []):
        if not s.get('name'):
            err('sources[%d] 缺 name' % i)
        u = s.get('url') or ''
        if u and not u.startswith('http'):
            warn('sources[%d].url 不是 http 链接：%s' % (i, u))

    # ---------- 方向性表述
    def scan(obj, path):
        if isinstance(obj, dict):
            for k, v in obj.items():
                scan(v, path + '.' + k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                scan(v, path + '[%d]' % i)
        elif isinstance(obj, str):
            if path.endswith('.q'):
                return
            for b in common.banned_hits(obj):
                err('出现方向性表述「%s」于 %s' % (b, path))
    scan(R, 'root')

    # ---------- 采购侧补充建议
    pr = R.get('procurement') or {}
    if common.num(pr.get('inventory_days')) is None:
        warn('procurement.inventory_days 未填：无法计算“现有库存可支撑到哪一天”')
    if not (R.get('balance') or []):
        warn('balance 为空：缺少库存/开工，无法解释“为什么贵/为什么跌”的供给端事实')
    if not (R.get('cost_lines') or R.get('routes')):
        warn('cost_lines 与 routes 都为空：无法回答“这个价在成本之上还是之下”')
    if not (R.get('upstream') or R.get('downstream')):
        warn('upstream/downstream 都为空：产业链模块会整体留空')
    if not (R.get('facts') or []):
        warn('facts 为空：可用事实卡会留空')
    if not (R.get('talk') or []):
        warn('talk 为空：供应商问答会留空')
    return E, W, I


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('research')
    ap.add_argument('--strict', action='store_true')
    a = ap.parse_args()
    try:
        R = common.load_json(a.research)
    except Exception as e:
        print('[FATAL] research.json 解析失败：%s' % e)
        sys.exit(2)
    E, W, I = check(R, os.path.dirname(os.path.abspath(a.research)))
    for m in E:
        print('[ERROR] ' + m)
    for m in W:
        print('[WARN ] ' + m)
    for m in I:
        print('[INFO ] ' + m)
    print('== %d error ｜ %d warn ｜ %d info' % (len(E), len(W), len(I)))
    if E or (a.strict and W):
        sys.exit(1)


if __name__ == '__main__':
    main()
