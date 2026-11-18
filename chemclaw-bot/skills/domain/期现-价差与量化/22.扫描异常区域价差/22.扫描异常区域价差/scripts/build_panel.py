# -*- coding: utf-8 -*-
"""
build_panel.py —— 把原始抓取结果整理成「标准价格长表」（panel_long.csv）

这一步是整条链路里做「口径统一」的地方：
  1. 原始报价（厂家/贸易商挂牌）→ 按规格文本映射到可比规格档 spec_tier
  2. 省/市 → 统一地区节点 region_code（可交割/可采集的城市，而不是行政大区）
  3. 补齐 delivery / tax / quote_type 三个口径要素
  4. 剔除明显不在可比范围内的行（试剂级、非工业级、单位异常）
  5. 输出 catalog.json：产品元信息（定价中心、角色、规格档定义）

输入：data_raw/chembook_panel.json（scripts/fetch_chembook2.py 产出）
      data_raw/spot_snapshot.json（scripts/fetch_data.py：100ppi + 期货，用于交叉校验）
输出：data_raw/panel_long.csv
      data_raw/catalog.json
      data_raw/excluded_rows.json   （被剔除的行 + 原因，保证可审计、不隐藏）
"""
from __future__ import annotations

import json
import os
import re
import statistics as st
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, 'data_raw')

# ------------------------------------------------------------------ 地区节点
# 原始报价里的「交货地」形如「河南省」「河南省/郑州市」「上海」「上海市/宝山区」。
# 做法：先按「省份 → 节点」的规范映射剥离省/市后缀，任何「省/市」组合都能自动归并，
# 不需要逐城市枚举。价格节点取该省最具物流意义的代表点（见 fetch_distances2.NODES）。
PROVINCE_NODE = {
    '北京': 'N_BEIJING', '天津': 'N_TIANJIN', '河北': 'N_HEBEI', '山西': 'N_SHANXI',
    '内蒙古': 'N_INNERMONGOLIA', '辽宁': 'NE_LIAONING', '吉林': 'NE_JILIN',
    '黑龙江': 'NE_HEILONGJIANG', '上海': 'EC_SHANGHAI', '江苏': 'EC_JIANGSU',
    '浙江': 'EC_ZHEJIANG', '安徽': 'EC_ANHUI', '福建': 'S_FUJIAN', '江西': 'EC_JIANGXI',
    '山东': 'EC_SHANDONG', '河南': 'H_HENAN', '湖北': 'H_HUBEI', '湖南': 'H_HUNAN',
    '广东': 'S_GUANGDONG', '广西': 'S_GUANGXI', '海南': 'S_HAINAN', '重庆': 'W_CHONGQING',
    '四川': 'W_SICHUAN', '贵州': 'W_GUIZHOU', '云南': 'W_YUNNAN', '西藏': 'N_XIZANG',
    '陕西': 'N_SHAANXI', '甘肃': 'N_GANSU', '青海': 'N_QINGHAI', '宁夏': 'N_NINGXIA',
    '新疆': 'N_XINJIANG', '香港': 'S_HONGKONG',
}
NODE_NAME = {
    'N_BEIJING': '北京', 'N_TIANJIN': '天津', 'N_HEBEI': '河北沙河', 'N_SHANXI': '山西',
    'N_INNERMONGOLIA': '内蒙古', 'NE_LIAONING': '辽宁', 'NE_JILIN': '吉林',
    'NE_HEILONGJIANG': '黑龙江', 'EC_SHANGHAI': '上海', 'EC_JIANGSU': '江苏',
    'EC_ZHEJIANG': '浙江', 'EC_ANHUI': '安徽', 'S_FUJIAN': '福建', 'EC_JIANGXI': '江西',
    'EC_SHANDONG': '山东', 'H_HENAN': '河南', 'H_HUBEI': '湖北', 'H_HUNAN': '湖南',
    'S_GUANGDONG': '广东', 'S_GUANGXI': '广西', 'S_HAINAN': '海南', 'W_CHONGQING': '重庆',
    'W_SICHUAN': '四川', 'W_GUIZHOU': '贵州', 'W_YUNNAN': '云南', 'N_XIZANG': '西藏',
    'N_SHAANXI': '陕西', 'N_GANSU': '甘肃', 'N_QINGHAI': '青海', 'N_NINGXIA': '宁夏',
    'N_XINJIANG': '新疆', 'S_HONGKONG': '香港', 'EC_TAICANG': '江苏太仓',
}
# 甲醇的华东港口集散地把江苏单独拆出来：进口/港口货源归太仓，其余归江苏。
METHANOL_PORT_PROVINCES = {'江苏': 'EC_TAICANG'}


def resolve_region(raw: str, product_key: str = 'soda'):
    """把原始「交货地」归并到物流节点；无法识别返回 (None, 原因)。"""
    if not raw:
        return None, 'REGION_EMPTY'
    s = raw.strip().replace('／', '/').replace(' ', '')
    prov = re.split(r'[/、\-]', s)[0]
    for suf in ('维吾尔自治区', '壮族自治区', '回族自治区', '特别行政区', '自治区', '省', '市'):
        if prov.endswith(suf):
            prov = prov[:-len(suf)]
            break
    code = None
    if product_key == 'methanol' and prov in METHANOL_PORT_PROVINCES:
        code = METHANOL_PORT_PROVINCES[prov]
    if not code:
        code = PROVINCE_NODE.get(prov)
    if not code:
        return None, 'REGION_NOT_MAPPED'
    return code, NODE_NAME.get(code, prov)

# ------------------------------------------------------------------ 规格档
# 规格文本 → 可比档。只有落进同一档的省内报价才允许互相做价差。
def spec_tier(product_key: str, spec: str, maker: str, price: float):
    s = (spec or '') + ' ' + (maker or '')
    s_l = s.lower()
    if product_key == 'soda':
        # 排除试剂级 / 食品级高价小包装
        if re.search(r'阿拉丁|分析纯|试剂|GR|AR|食品级', s):
            return None, 'NON_INDUSTRIAL_GRADE'
        if price > 3000:
            return None, 'PRICE_OUT_OF_INDUSTRIAL_RANGE'
        if re.search(r'70%|90%|60%|50%|含量\s*[:：]?\s*(?:7|8|9)0', s) and not re.search(r'9[5-9]', s):
            return None, 'LOW_PURITY_SPEC'
        if re.search(r'轻质|轻灰', s):
            return 'light', ''
        if re.search(r'重质|重灰|99\.2|99\.0|优等品|国标|含量\s*99|双环', s):
            return 'heavy', ''
        return 'unspecified', ''
    if product_key == 'methanol':
        if price > 6000 or price < 800:
            return None, 'PRICE_OUT_OF_INDUSTRIAL_RANGE'
        if re.search(r'进口', s_l):
            return 'import', ''
        if re.search(r'优等品|99\.9|99\.99|国标|合格品|精醇|工业级', s):
            return 'domestic', ''
        return 'unspecified', ''
    return 'unspecified', ''


DEFAULT_CATALOG = {
    'products': {
        'soda': {
            'name': '纯碱', 'unit': '元/吨',
            'spec_tiers': {'heavy': '重质纯碱 工业级', 'light': '轻质纯碱 工业级'},
            'pricing_center': '',
            'orientation': {
                'base_role': '基准地区（按价格水平最低的产区/交割地固定方向）',
                'roles': {},
            },
            'price_basis': '厂家/贸易商公开挂牌报价中位数，含税出厂/送到混合口径（见 delivery 字段）',
        },
        'methanol': {
            'name': '甲醇', 'unit': '元/吨',
            'spec_tiers': {'domestic': '国产甲醇 优等品/国标', 'import': '进口甲醇 合格品'},
            'pricing_center': 'EC_TAICANG',
            'orientation': {
                'base_role': '基准地区：太仓（进口集散与港口定价锚）',
                'roles': {},
            },
            'price_basis': '厂家/贸易商公开挂牌报价中位数，含税',
        },
    },
    'region_nodes': dict(NODE_NAME),
    'region_role': {
        'N_SHAHE': '北方消费集散/交割地', 'N_HEBEI': '生产+集散', 'N_TIANJIN': '港口下水',
        'H_HENAN': '中部产区', 'H_HUBEI': '华中联碱产区', 'H_HUNAN': '华中消费地',
        'EC_SHANDONG': '华东产区', 'EC_JIANGSU': '华东净调入', 'EC_ZHEJIANG': '华东消费地',
        'EC_SHANGHAI': '华东贸易节点', 'EC_ANHUI': '华东产区', 'EC_JIANGXI': '华东内陆消费地',
        'EC_TAICANG': '港口集散/定价锚', 'N_INNERMONGOLIA': '西北主产区', 'N_NINGXIA': '西北产区',
        'N_SHAANXI': '西北过渡区', 'N_QINGHAI': '西北远端产区', 'N_GANSU': '西北产区',
        'N_XINJIANG': '西北远端产区', 'N_SHANXI': '华北产区', 'N_BEIJING': '华北消费/贸易',
        'W_SICHUAN': '西南产区', 'W_CHONGQING': '西南消费/长江节点', 'W_GUIZHOU': '西南产区',
        'W_YUNNAN': '西南消费地', 'S_GUANGDONG': '华南净调入', 'S_FUJIAN': '华南消费地',
        'S_GUANGXI': '华南消费地', 'S_HAINAN': '华南远端', 'S_HONGKONG': '华南贸易节点',
        'NE_LIAONING': '东北消费/港口', 'NE_JILIN': '东北消费地', 'NE_HEILONGJIANG': '东北产区',
        'N_XIZANG': '西南远端',
    },
}


CB_PRODUCTS = {'soda': ('CB9853672', '纯碱'), 'methanol': ('CB7854099', '甲醇')}


def load_raw_panel():
    """读取原始报价。

    优先读抓取脚本逐条追加的 cb_rows_<key>.jsonl（可断点续采、行数最全）；
    若不存在则回退到聚合后的 chembook_panel.json。
    两种来源都做同一条「日期+交货地+厂家+规格+价格」去重，因为相邻报告日期范围
    有重叠，同一条报价会在多份报告里重复出现。
    """
    products = {}
    for pk in CB_PRODUCTS:
        jl = os.path.join(RAW, 'cb_rows_%s.jsonl' % pk)
        rows, seen = [], set()
        if os.path.exists(jl):
            with open(jl, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    k = (r.get('date'), r.get('location'), r.get('maker'),
                         r.get('spec'), r.get('price'))
                    if k in seen:
                        continue
                    seen.add(k)
                    rows.append(r)
        if rows:
            products[pk] = {'name': CB_PRODUCTS[pk][1], 'rows': rows}
            print('  %-9s 原始行 %d（已去重，来源 cb_rows_%s.jsonl）' % (pk, len(rows), pk))
    if products:
        return {'products': products}
    return json.load(open(os.path.join(RAW, 'chembook_panel.json'), encoding='utf-8'))


def main():
    panel = load_raw_panel()
    out_rows, excluded = [], []
    stat = Counter()

    for pk, prod in panel['products'].items():
        for r in prod['rows']:
            loc = r.get('location', '')
            node = resolve_region(loc, pk)
            if not node[0]:
                excluded.append({**r, 'reason': 'REGION_NOT_MAPPED'})
                stat['REGION_NOT_MAPPED'] += 1
                continue
            tier, why = spec_tier(pk, r.get('spec', ''), r.get('maker', ''), r.get('price') or 0)
            if tier is None:
                excluded.append({**r, 'reason': why})
                stat[why] += 1
                continue
            unit = r.get('unit', '')
            if '吨' not in unit:
                excluded.append({**r, 'reason': 'UNIT_MISMATCH'})
                stat['UNIT_MISMATCH'] += 1
                continue
            out_rows.append({
                'product_key': pk,
                'product': r.get('product') or DEFAULT_CATALOG['products'][pk]['name'],
                'region_code': node[0],
                'region': node[1],
                'spec': r.get('spec', ''),
                'spec_tier': tier,
                'delivery': '挂牌报价（含税，出厂/送到未标注）',
                'tax': '含税（增值税，按厂家挂牌惯例）',
                'quote_type': 'dealer_listing',
                'date': r['date'],
                'price': round(float(r['price']), 2),
                'unit': '元/吨',
                'maker': r.get('maker', ''),
                'source': 'ChemicalBook 价格报告',
                'source_url': 'https://www.chemicalbook.com/PriceInfo_%s.htm' % r.get('report_id', ''),
                'report_id': r.get('report_id', ''),
            })
            stat['kept'] += 1

    out_rows.sort(key=lambda x: (x['product_key'], x['spec_tier'], x['region_code'], x['date']))

    # 主规格档判定：样本最多的工业级档
    catalog = json.loads(json.dumps(DEFAULT_CATALOG))
    for pk in panel['products']:
        pr = [r for r in out_rows if r['product_key'] == pk]
        if not pr:
            continue
        cnt = Counter(r['spec_tier'] for r in pr)
        main_tier = max(cnt, key=cnt.get)
        regions = sorted({r['region_code'] for r in pr if r['spec_tier'] == main_tier})
        # 基准地区选取：低价的「产区端」作基准，方向从产区指向消费区。
        # 但不能只按价格低来选 —— 报价稀疏的地区会让绝大多数组合无法配对。
        # 折中：在报价覆盖度达标的地区里选价格最低者（覆盖率 = 该地区有报价的天数 / 最长天数）。
        med = {}
        for rc in regions:
            vals = [r['price'] for r in pr if r['spec_tier'] == main_tier and r['region_code'] == rc]
            med[rc] = st.median(vals)
        cover = {}
        for rc in regions:
            days = {r['date'] for r in pr if r['spec_tier'] == main_tier and r['region_code'] == rc}
            cover[rc] = len(days)
        maxd = max(cover.values()) if cover else 1
        eligible = [rc for rc in regions if cover[rc] >= maxd * 0.5] or regions
        base = min(eligible, key=lambda rc: med.get(rc, 1e9))
        if pk == 'methanol':
            # 甲醇以太仓（进口集散与港口定价锚）为基准，缺失时才退回低价产区
            base = 'EC_TAICANG' if 'EC_TAICANG' in regions else base
        catalog['products'][pk]['primary_tier'] = main_tier
        catalog['products'][pk]['pricing_center'] = base
        catalog['products'][pk]['orientation']['base_role'] = (
            '基准地区：%s（同档报价覆盖度达标且中位价最低的产区，固定为基准端，窗口内方向不翻转）' % base)
        catalog['products'][pk]['tier_counts'] = dict(cnt)
        catalog['products'][pk]['tier_medians'] = {k: round(v, 2) for k, v in sorted(med.items())}
        catalog['products'][pk]['tier_regions'] = regions

    # 100ppi / 期货交叉校验信息
    snap_path = os.path.join(RAW, 'spot_snapshot.json')
    if os.path.exists(snap_path):
        snap = json.load(open(snap_path, encoding='utf-8'))
        spot = {}
        for ppid, v in (snap.get('products') or {}).items():
            ser = v.get('series') or []
            hl = v.get('headline') or {}
            spot[v.get('product') or ppid] = {
                'ppid': ppid,
                'headline': hl.get('raw') if isinstance(hl, dict) else hl,
                'scope': (v.get('series_meta') or {}).get('subtext', ''),
                'n_days': len(ser),
                'first_date': ser[0]['date'] if ser else None,
                'last_date': ser[-1]['date'] if ser else None,
                'markets': sorted({r.get('market') for r in (v.get('snapshot_rows') or []) if r.get('market')}),
                'source_url': v.get('source_url'),
            }
        fut = {}
        for sym, kl in (snap.get('futures') or {}).items():
            if isinstance(kl, list) and kl:
                fut[sym] = {'last_close': kl[-1].get('close'), 'last_date': kl[-1].get('date'),
                            'first_date': kl[0].get('date'), 'n': len(kl)}
        catalog['cross_check'] = {
            'note': ('生意社100ppi 为单市场/全国口径序列，仅用于量级交叉校验与历史走势参照，'
                     '不含区域维度，不参与区域价差计算'),
            'spot': spot,
            'futures': fut,
        }

    cols = ['product_key', 'product', 'region_code', 'region', 'spec', 'spec_tier', 'delivery',
            'tax', 'quote_type', 'date', 'price', 'unit', 'maker', 'source', 'source_url', 'report_id']
    import csv
    with open(os.path.join(RAW, 'panel_long.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in out_rows:
            w.writerow({k: r.get(k, '') for k in cols})
    json.dump(catalog, open(os.path.join(RAW, 'catalog.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    json.dump({'count': len(excluded), 'by_reason': dict(stat),
               'rows': excluded[:2000]},
              open(os.path.join(RAW, 'excluded_rows.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    print('保留 %d 行，剔除 %d 行' % (len(out_rows), len(excluded)))
    print('剔除原因：', dict(stat))
    for pk in panel['products']:
        pr = [r for r in out_rows if r['product_key'] == pk]
        ds = sorted({r['date'] for r in pr})
        tiers = Counter(r['spec_tier'] for r in pr)
        regs = sorted({r['region_code'] for r in pr})
        print('%-9s 行=%4d 日=%3d %s..%s 规格档=%s 地区=%d %s'
              % (pk, len(pr), len(ds), ds[0] if ds else '-', ds[-1] if ds else '-',
                 dict(tiers), len(regs), regs))


if __name__ == '__main__':
    main()
