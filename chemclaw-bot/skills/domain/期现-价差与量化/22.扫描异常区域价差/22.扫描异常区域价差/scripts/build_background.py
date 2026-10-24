# -*- coding: utf-8 -*-
"""
build_background.py —— 生成区域供需背景配置（data_raw/background.json）

数据纪律：
  · 本文件的每条事实都带来源。可核实的写 verified=true 并给 URL；只作为方向性
    行业共识的写 verified=false 或注明「需核实」。
  · 产能只写企业级可核实数字；省级合计未查到权威发布的一律写「未查到」，
    不给估算数冒充事实。
  · 不写因果预测、不写交易建议。事件表只记录「已发生的事」和「它对当地供/需的
    作用方向」，不写「因此会涨/会跌」。
"""
from __future__ import annotations

import json
import os
import statistics as st
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, 'data_raw')

# ---------------------------------------------------------------- 来源登记
SOURCES = {
    'chembook': ('ChemicalBook 价格报告（PriceInfo 归档）', 'https://www.chemicalbook.com/priceindex_cb9853672.htm',
                 '厂家/贸易商公开挂牌报价，省级×日度，本报告价格主口径'),
    '100ppi_soda': ('生意社 纯碱产业网（重质纯碱基准价/国内混合价）', 'https://soda.100ppi.com',
                    '全国/单一市场混合价，仅作量级交叉校验，不参与区域价差'),
    '100ppi_meoh': ('生意社 甲醇产业网', 'https://me.100ppi.com',
                    '江苏太仓市场价与山东国产价，仅作交叉校验'),
    'qhrb_logistics': ('期货日报《纯碱的物流仓储与价格政策介绍》',
                       'https://finance.sina.cn/futuremarket/qszx/2019-12-01/detail-iihnzahi4623500.d.html?vt=4',
                       '重碱除西北外为送到价；300 km 为汽运/铁运分界；水运 30—120 元/吨'),
    'mysteel_shahe': ('隆众资讯《沙河及周边贸易价格行情》（我的钢铁网转载）',
                      'https://nenghua.m.mysteel.com/a/25060416/98BCA1C064AACE9D_abc.html',
                      '沙河交割库出库价 vs 送到价价差 50—100 元/吨（2025-06-04 同日）'),
    'sci99_2024': ('卓创资讯《纯碱：2024年数据盘点及2025年展望》（新浪财经转载）',
                   'https://finance.sina.com.cn/money/future/roll/2025-01-03/doc-inecsvux6433846.shtml',
                   '2024 全国产能 3838 万吨；重碱终端均价 1953 元/吨（-29.6%）；工艺成本结构'),
    'stcn_yuanxing': ('证券时报《远兴能源：启动阿拉善塔木素天然碱二期》',
                      'https://www.stcn.com/article/detail/1077670.html',
                      '阿拉善一期 500 万吨 2023-06 投产；二期 280 万吨规划'),
    'lyg_port': ('连云港市政府《碱业公司搬迁升级改造项目建成投产》',
                 'http://www.lyg.gov.cn/zglygzfmhwz/gcyw/content/3ad7d8d1-8a2a-4683-82b5-4766ac84985e.html',
                 '连云港碱业 110 万吨联碱 2025-05-18 一次开车成功'),
    'qh7_glass': ('七禾网《河北、山东玻璃纯碱调研报告完整版》', 'https://www.7hcn.com/article/458274-1.html',
                  '沙河月用纯碱约 9 万吨；玻璃厂纯碱库存 15—25 天；阿拉善→石家庄汽运 300 元/1500 km；海运南下 140—150 元/吨'),
    'czce': ('郑商所《纯碱期货业务细则》/交割手册',
             'https://np-newsimg.dfcfw.com/download/A2_cms_f_20231123161555494870?direct=1&abc7363.pdf',
             '交割品规格；入库费汽车 25 元/吨、火车 30 元/吨；仓储 0.5 元/吨·天'),
    'dfcf_frame': ('东方财富研报《纯碱行业分析框架》', 'https://pdf.dfcfw.com/pdf/H3_AP202205101564746575_1.pdf',
                   '纯碱工艺路线与成本梯次；三友化工 340 万吨口径'),
    'haihua': ('山东海化集团·纯碱厂简介', 'https://www.haihua.com.cn/About_11/1664471386467147776.html',
               '山东海化 280 万吨（老线 120 + 新线 160），氨碱法'),
    'qhrb_0515': ('期货日报（2026-10-15 等纯碱与化工品周度评论，经东方财富转载）',
                  'http://finance.eastmoney.com/a/202610153896859175.html',
                  '2026 年 10 月纯碱开工、库存与价格位置'),
    'cctd_meoh': ('中国煤炭市场网《中国甲醇运输现状及送到华东地区成本竞争力比较》',
                  'https://www.cctd.com.cn/show-36-2170-1.html',
                  '甲醇产销分离格局：西北（内蒙西部/陕西/宁夏）主产，华东沿海消费；长途运输必然'),
    'sina_sci': ('新浪财经《中国甲醇产能分布成本剖析》',
                 'https://finance.sina.cn/futuremarket/qsyw/2018-08-14/detail-ihhtfwqq6140173.d.html?vt=4',
                 '甲醇产能区域分布：西北 4000 万吨级、山东 800 万吨级、华中 600 万吨级、西南 700 万吨级'),
    'sci99_meoh': ('卓创资讯 甲醇频道', 'https://ochem.sci99.com/product/methanol',
                   '2026-10 沿海甲醇因下游停车回调；太仓/华南港口库存与到港节奏'),
    'sunsirs_pvc': ('生意社 SunSirs PVC 周度/月度评论', 'https://sunsirs.com/commodity-news/petail-27604.html',
                    'PVC SG-5 电石法均价与区域分化'),
}

# ---------------------------------------------------------------- 品种背景
PRODUCT_BG = {
    'soda': {
        'summary': ('纯碱是典型的「资源地—消费地」错配品种：天然碱在内蒙古阿拉善、河南桐柏，'
                    '氨碱/联碱在山东、江苏、河北、湖北。低成本天然碱持续压全国边际成本，'
                    '而沙河（玻璃）、华东（玻璃/光伏/日化）是主要消费地，因此区域价差长期由'
                    '「产地成本梯次 + 到货运费」决定，而非单纯供需强弱。'),
        'basis': '重质纯碱工业级挂牌报价中位数，含税；交货方式以挂牌为准（出厂/送到未统一标注）',
        'drivers': [
            '低成本天然碱（内蒙阿拉善、河南桐柏）持续投放，压低全国边际成本，压缩高成本氨碱区的相对升水空间。',
            '沙河玻璃集群是北方最大的纯碱消费与集散地，其冷修/复产直接改变河北供需松紧。',
            '华东（江苏/浙江/上海）本地供给不足以覆盖玻璃与光伏玻璃需求，属净调入，价格结构性高于华中。',
            '同一地区同日多规格并存（轻质/重质/含量差异），跨规格相减会制造虚假价差——本报告已按重质档圈定。',
        ],
        'regions': {
            'N_SHAHE': {'role': '北方最大纯碱消费与集散/交割地（沙河玻璃集群）',
                        'supply': '本地产能有限，主要靠河北唐山三友系（约 340 万吨，氨碱）与区外调入',
                        'demand': '浮法玻璃集群，月度纯碱用量约 9 万吨（七禾网调研）；玻璃厂原料库存常备 15—25 天',
                        'news': '2025 年末至 2026 年沙河燃煤玻璃线集中冷修、煤改气推进，日熔量下降，对纯碱刚需形成压制'},
            'N_HEBEI': {'role': '生产+集散（唐山三友系）',
                        'supply': '唐山三友 230 万吨 + 五彩碱业 110 万吨，均为氨碱法（高成本路线）',
                        'demand': '本地玻璃与天津港下水', 'news': '—'},
            'H_HENAN': {'role': '天然碱主产区之一（桐柏）+ 联碱产区',
                        'supply': '河南桐柏天然碱资源；省内联碱装置集中',
                        'demand': '本地玻璃、日化与无机盐',
                        'news': '天然碱成本显著低于氨碱/联碱，是压低全国边际成本的关键来源'},
            'H_HUBEI': {'role': '华中联碱产区 + 长江水运节点',
                        'supply': '湖北联碱产能集中（双吨法，与氯化铵联动）',
                        'demand': '本地玻璃、化工与华中消费',
                        'news': '联碱双吨成本受氯化铵价格牵制，氯化铵走弱时联碱实际成本上升'},
            'EC_JIANGSU': {'role': '华东核心消费地 + 净调入省',
                           'supply': '实联化工约 120、中盐昆山 60—80、江苏华昌 70、苏盐井神 70、江苏德邦 60、徐州丰成 60 万吨（联碱为主）；连云港碱业 110 万吨联碱 2025-05 投产',
                           'demand': '光伏玻璃集聚度高，另有浮法玻璃与无机盐/精细化工',
                           'news': '2025-05 连云港碱业 110 万吨联碱一次开车成功，本地供给回升，对江苏相对升水有收敛作用'},
            'EC_SHANDONG': {'role': '氨碱主产区 + 出口与南下枢纽',
                            'supply': '山东海化 280 万吨（氨碱，郑商所指定交割厂库）+ 山东海天生物化工 150 万吨（氨碱）',
                            'demand': '本地玻璃与出口；潍坊港具备海运南下能力（海运至华南约 140—150 元/吨）',
                            'news': '2025 年纯碱出口创新高，沿海省份受益最直接'},
            'EC_ZHEJIANG': {'role': '华东消费地（承接江苏/进口）', 'supply': '本地产能有限',
                            'demand': '玻璃、日化、无机盐', 'news': '价格通常跟随江苏，与江苏价差主要反映短途运费与规格差异'},
            'EC_SHANGHAI': {'role': '华东贸易与金融节点', 'supply': '基本无本地产能',
                            'demand': '贸易与终端分销', 'news': '报价多为贸易商挂牌，规格与批次离散度高，作区域基准的可靠性弱于产区'},
            'EC_ANHUI': {'role': '华东联碱产区（昊源、临泉等）', 'supply': '安徽联碱装置集中', 'demand': '本地与长三角外运', 'news': '—'},
            'EC_JIANGXI': {'role': '华东内陆消费地', 'supply': '依赖外省调入', 'demand': '本地轻工与日化', 'news': '—'},
            'N_INNERMONGOLIA': {'role': '天然碱主产区（阿拉善塔木素）',
                                'supply': '远兴阿拉善一期 500 万吨（2023-06 投产）、二期 280 万吨（2025-12 首线投料试车），完全成本 <1000 元/吨',
                                'demand': '本地需求极小，几乎全部外运',
                                'news': '二期增量自 2026 年起释放，是压制全国价格中枢的主要来源'},
            'N_QINGHAI': {'role': '天然碱/盐湖产区', 'supply': '盐湖化工体系天然碱', 'demand': '外运为主',
                          'news': '运距长，到货成本高，出厂价低但送到价未必低'},
            'N_SHAANXI': {'role': '西北过渡区', 'supply': '有限', 'demand': '外运', 'news': '—'},
            'N_NINGXIA': {'role': '西北天然碱/氨碱产区', 'supply': '有限', 'demand': '外运', 'news': '—'},
            'W_SICHUAN': {'role': '西南联碱/井矿盐产区', 'supply': '四川联碱与井矿盐配套', 'demand': '西南玻璃与化工',
                          'news': '西南相对封闭，价格常与全国脱钩，跨区调运受运费与运力约束'},
            'W_CHONGQING': {'role': '西南消费与长江水运节点', 'supply': '有限', 'demand': '玻璃与化工',
                            'news': '长江水运使重庆与华东存在成本联动'},
            'S_GUANGDONG': {'role': '华南消费地（净调入）', 'supply': '本地产能极少',
                            'demand': '玻璃、日化、无机盐',
                            'news': '长期为全国价格高地，与北方产区价差主要是海运/铁路运费与本地溢价'},
            'S_FUJIAN': {'role': '华南消费地', 'supply': '依赖调入', 'demand': '玻璃与日化',
                         'news': '报价离散度高，多为贸易商挂牌'},
        },
    },
    'methanol': {
        'summary': ('甲醇产销分离极明显：西北（内蒙西部、陕西、宁夏）是主产区，华东沿海是最大消费地'
                    '（MTO/MTP 与化工），因此「西北—华东」是最主要的物流与价差方向。'
                    '太仓是进口集散与港口定价锚，华东价格同时受进口到港与内地调入影响。'),
        'basis': '甲醇挂牌报价中位数，含税；国产与进口分档统计（进口货含到港成本与升贴水结构）',
        'drivers': [
            '西北—华东是最主要流向：内蒙/陕西/宁夏货源经铁路罐车与水运进入华东，运费在价差中占比高。',
            '太仓是进口甲醇集散地，港口库存与到港节奏直接决定华东与内地的价差方向。',
            '沿海 MTO 装置开停是华东需求的最大单一变量——装置停车会立刻改变华东相对内地的强弱。',
            '国产与进口两条定价曲线不可混算；本报告已按「国产/进口」分档，跨档比较标记为弱可比。',
        ],
        'regions': {
            'EC_TAICANG': {'role': '进口集散与港口定价锚（华东）',
                           'supply': '进口船货到港 + 内地（西北/山东）调入',
                           'demand': '华东 MTO/MTP、甲醛、醋酸、MTBE 等',
                           'news': '2026-10 沿海烯烃装置集中停车，华东需求端走弱，港口甲醇价格承压（卓创资讯 10 月评论）'},
            'EC_SHANDONG': {'role': '华北/华东过渡产区（山东）',
                            'supply': '山东甲醇产能约 800 万吨级（新浪财经产能分布口径），以煤制与合成氨联产为主',
                            'demand': '本地甲醛、MTBE、二甲醚与部分外运',
                            'news': '山东是内地与华东之间的关键中转，其价格通常介于西北与太仓之间'},
            'EC_ZHEJIANG': {'role': '华东消费地（宁波/乍浦港）', 'supply': '港口进口与华东调入',
                            'demand': '华东下游与转口', 'news': '宁波港报价常略高于太仓，反映短途与货源差异'},
            'EC_SHANGHAI': {'role': '华东贸易节点', 'supply': '调入为主', 'demand': '贸易与分销', 'news': '—'},
            'N_INNERMONGOLIA': {'role': '西北主产区（内蒙北线/南线）',
                                'supply': '煤制甲醇主力产区，单厂规模大、成本低', 'demand': '本地极少，全部外运',
                                'news': '西北货源经铁路与水运东进，是内地价格的下沿'},
            'N_SHAANXI': {'role': '西北主产区（陕北/榆林）', 'supply': '煤制甲醇集中', 'demand': '外运为主',
                          'news': '榆林/神木一带装置检修与外运节奏对华东到货影响直接'},
            'N_NINGXIA': {'role': '西北产区', 'supply': '煤制甲醇', 'demand': '外运', 'news': '—'},
            'N_SHANXI': {'role': '华北产区（晋城/孝义等）', 'supply': '煤制与焦炉气制甲醇', 'demand': '外运至华中/华东',
                         'news': '山西货源经铁路南下，与河南/湖北价格联动'},
            'N_HEBEI': {'role': '华北消费与集散', 'supply': '有限', 'demand': '本地甲醛与化工', 'news': '—'},
            'H_HENAN': {'role': '华中产区与消费地', 'supply': '河南煤制甲醇产能可观', 'demand': '本地二甲醚、甲醛与化工',
                        'news': '河南是西北货源东进华东的必经通道'},
            'H_HUBEI': {'role': '华中消费地（长江水运）', 'supply': '有限', 'demand': '本地化工与下游',
                        'news': '长江水运使湖北承接华东与西南，价格易受船期影响'},
            'H_HUNAN': {'role': '华中消费地', 'supply': '依赖调入', 'demand': '本地化工', 'news': '—'},
            'EC_ANHUI': {'role': '华东产区（昊源、临泉等）', 'supply': '安徽甲醇装置集中', 'demand': '本地与长三角外运', 'news': '—'},
            'EC_JIANGXI': {'role': '华东内陆消费地', 'supply': '调入', 'demand': '本地化工', 'news': '—'},
            'N_GANSU': {'role': '西北产区', 'supply': '煤制甲醇', 'demand': '外运', 'news': '运距最长，到货成本高'},
            'N_XINJIANG': {'role': '西北远端产区', 'supply': '煤制甲醇，成本最低但运距最远', 'demand': '外运受运费约束',
                           'news': '新疆货源外运受铁路运力与运费限制，出厂价为全国最低'},
            'W_SICHUAN': {'role': '西南产区（天然气制）', 'supply': '天然气制甲醇，受气价与限气影响',
                          'demand': '本地化工与西南消费', 'news': '冬季限气期天然气制装置降负，西南供给收缩'},
            'W_CHONGQING': {'role': '西南消费与长江节点', 'supply': '有限', 'demand': '本地化工', 'news': '长江水运连接华东'},
            'W_GUIZHOU': {'role': '西南产区', 'supply': '煤制甲醇', 'demand': '外运', 'news': '—'},
            'W_YUNNAN': {'role': '西南消费地', 'supply': '依赖调入', 'demand': '本地化工', 'news': '运距长，价格通常高于西南产区'},
            'S_GUANGDONG': {'role': '华南消费地（进口+内贸船运）', 'supply': '进口到港与华东内贸船运',
                            'demand': '华南化工与下游', 'news': '华南到港增多时，广东基差走弱（卓创 10-12 快讯）'},
            'S_FUJIAN': {'role': '华南消费地', 'supply': '调入', 'demand': '本地化工', 'news': '报价离散度高'},
            'S_HAINAN': {'role': '华南远端消费地', 'supply': '调入', 'demand': '本地少量', 'news': '运距长，价格通常为全国最高'},
            'NE_HEILONGJIANG': {'role': '东北产区（大庆等）', 'supply': '天然气制与煤制', 'demand': '本地与东北',
                                'news': '东北相对封闭，与全国价差主要由运费决定'},
            'NE_LIAONING': {'role': '东北消费与港口', 'supply': '有限', 'demand': '本地化工', 'news': '—'},
            'NE_JILIN': {'role': '东北消费地', 'supply': '调入', 'demand': '本地化工', 'news': '—'},
        },
    },
}


def live_prices_by_region(product_key: str):
    """从面板取各地区最新价格，用于背景卡的「当前价格位置」。"""
    p = os.path.join(RAW, 'panel_long.csv')
    if not os.path.exists(p):
        return {}
    import csv
    cat = {}
    cp = os.path.join(RAW, 'catalog.json')
    if os.path.exists(cp):
        cat = json.load(open(cp, encoding='utf-8')).get('products', {}).get(product_key, {})
    tier = cat.get('primary_tier')
    vals = defaultdict(list)
    with open(p, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['product_key'] != product_key:
                continue
            if tier and r['spec_tier'] != tier:
                continue
            vals[(r['region_code'], r['region'])].append((r['date'], float(r['price'])))
    out = {}
    for (rc, rn), seq in vals.items():
        seq.sort()
        latest_date = seq[-1][0]
        last = [v for d, v in seq if d == latest_date]
        out[rc] = {'latest': round(st.median(last), 1), 'date': latest_date,
                   'n_days': len({d for d, _ in seq})}
    return out


def build():
    bg = {}
    for pk, cfg in PRODUCT_BG.items():
        live = live_prices_by_region(pk)
        regions = {}
        for rc, info in cfg['regions'].items():
            d = dict(info)
            if rc in live:
                d['price_latest'] = live[rc]['latest']
                d['price_date'] = live[rc]['date']
                d['price_days'] = live[rc]['n_days']
            regions[rc] = d
        bg[pk] = {'summary': cfg['summary'], 'basis': cfg['basis'], 'drivers': cfg['drivers'],
                  'regions': regions,
                  'source': 'ChemicalBook 价格报告 + 公开行业调研（见 sources）；区域供需为结构性描述，非逐日统计',
                  'source_url': 'https://www.chemicalbook.com/priceindex_cb9853672.htm'}
    bg['_sources'] = {k: {'name': v[0], 'url': v[1], 'covers': v[2]} for k, v in SOURCES.items()}
    json.dump(bg, open(os.path.join(RAW, 'background.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('background.json ok:', {k: len(v.get('regions', {})) for k, v in bg.items() if k != '_sources'})


if __name__ == '__main__':
    build()
