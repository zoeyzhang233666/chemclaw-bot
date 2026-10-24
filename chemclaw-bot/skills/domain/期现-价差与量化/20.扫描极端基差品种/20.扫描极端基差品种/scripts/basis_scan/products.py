# -*- coding: utf-8 -*-
"""products.py — 品种池定义（扫描口径的唯一事实来源）

每个品种一条记录，字段含义见 references/product-pool-spec.md：
  code        品种代码（期货代码前缀）
  name        品种中文名
  exchange    交易所（郑商所 / 大商所）
  futures_contract_prefix  逐合约代码前缀（新浪 InnerFuturesNewService 用）
  ppid        生意社(100ppi) 商品 ID（用于取「现货基准价 / 基差」栏目）
  channel     生意社行业频道（11能源 12有色 13钢铁 14化工 15橡塑 16化纤 17建材 18农副）
  spot_name   生意社原始商品名（文章标题里出现）
  spot_spec   现货规格
  spot_region 现货基准地区口径
  spot_tax    价格口径：含税/未税
  contract_spec 交割品级
  futures_region 期货交割区域
  unit        单位
  multiplier  合约乘数（吨/手 或 元/吨×吨/手 等）
  tick        最小变动价位
  last_trade_rule 最后交易日规则（文字）
  note        口径备注
"""
from __future__ import annotations

import json
import os

# 默认：大商所/郑商所「化工期货品种池」中现货口径可比、且国内期货有对应合约的 12 个品种。
DEFAULT_POOL = [
    dict(code='MA', name='甲醇', exchange='郑商所', futures_contract_prefix='MA',
         ppid=397, channel=14, spot_name='甲醇',
         spot_spec='优等品，≥99.9%', spot_region='全国/华东综合基准', spot_tax='含税',
         contract_spec='国标优等品，甲醇含量≥99.9%', futures_region='仓库交割(华东/华南/华中)+厂库',
         unit='元/吨', multiplier=10, tick=1,
         last_trade_rule='合约交割月份第 10 个交易日（郑商所）',
         note='基准价含税；期货为不含税净价，基差天然含 13% 增值税项，故只看自身历史分位'),
    dict(code='SA', name='纯碱', exchange='郑商所', futures_contract_prefix='SA',
         ppid=533, channel=14, spot_name='纯碱',
         spot_spec='重质纯碱 ≥99.2% 优等品', spot_region='全国/华东综合基准', spot_tax='含税',
         contract_spec='重质纯碱(GB/T 210-2022 Ⅱ类优等品)', futures_region='仓库交割(华北/华东/华中/西北)',
         unit='元/吨', multiplier=20, tick=1,
         last_trade_rule='合约交割月份第 10 个交易日（郑商所）',
         note='生意社纯碱栏目以重质纯碱为主口径；轻质纯碱价格另计'),
    dict(code='V', name='PVC', exchange='大商所', futures_contract_prefix='V',
         ppid=421, channel=15, spot_name='PVC',
         spot_spec='电石法 SG-5 型(聚氯乙烯)', spot_region='华东(常州/江浙沪)主流', spot_tax='含税',
         contract_spec='电石法 SG-5 型(GB/T 5761-2018 优等品)', futures_region='华东/华南仓库交割',
         unit='元/吨', multiplier=5, tick=1,
         last_trade_rule='合约交割月份第 10 个交易日（大商所）',
         note='基准价含税；V 合约为 5 吨/手'),
    dict(code='PP', name='聚丙烯', exchange='大商所', futures_contract_prefix='PP',
         ppid=414, channel=15, spot_name='PP',
         spot_spec='拉丝级(均聚)', spot_region='华东主流(拉丝)', spot_tax='含税',
         contract_spec='拉丝级均聚聚丙烯(GB/T 12670)', futures_region='华东/华南/华北仓库交割',
         unit='元/吨', multiplier=5, tick=1,
         last_trade_rule='合约交割月份第 10 个交易日（大商所）',
         note='PP 标品为拉丝，注塑/纤维料与之存在牌号价差，不混用'),
    dict(code='L', name='LLDPE', exchange='大商所', futures_contract_prefix='L',
         ppid=409, channel=15, spot_name='LLDPE',
         spot_spec='7042(薄膜级)', spot_region='华东主流', spot_tax='含税',
         contract_spec='线型低密度聚乙烯(7042 等薄膜级)', futures_region='华东/华南/华北仓库交割',
         unit='元/吨', multiplier=5, tick=1,
         last_trade_rule='合约交割月份第 10 个交易日（大商所）',
         note='L 合约为 7042 标品，与注塑级价差显著'),
    dict(code='TA', name='PTA', exchange='郑商所', futures_contract_prefix='TA',
         ppid=442, channel=16, spot_name='PTA',
         spot_spec='精对苯二甲酸(纤维级)', spot_region='华东(主港/江浙)', spot_tax='含税',
         contract_spec='PTA 优等品(GB/T 32685)', futures_region='仓库交割(华东主港)',
         unit='元/吨', multiplier=5, tick=2,
         last_trade_rule='合约交割月份第 10 个交易日（郑商所）',
         note='郑商所 PTA 合约 5 吨/手'),
    dict(code='EG', name='乙二醇', exchange='大商所', futures_contract_prefix='EG',
         ppid=448, channel=14, spot_name='乙二醇',
         spot_spec='涤纶级(聚酯级)', spot_region='华东主流', spot_tax='含税',
         contract_spec='聚酯级乙二醇(GB/T 4649)', futures_region='华东/华南仓库交割',
         unit='元/吨', multiplier=10, tick=1,
         last_trade_rule='合约交割月份第 10 个交易日（大商所）',
         note='EG 合约 10 吨/手'),
    dict(code='UR', name='尿素', exchange='郑商所', futures_contract_prefix='UR',
         ppid=519, channel=14, spot_name='尿素',
         spot_spec='小颗粒/中颗粒(≥46.4%)', spot_region='全国综合基准', spot_tax='含税',
         contract_spec='尿素(GB/T 2440 优等品)', futures_region='仓库交割(河南/山东/河北等)',
         unit='元/吨', multiplier=20, tick=1,
         last_trade_rule='合约交割月份第 10 个交易日（郑商所）',
         note='氮肥，出口法检影响内外价差'),
    dict(code='SH', name='烧碱', exchange='郑商所', futures_contract_prefix='SH',
         ppid=520, channel=14, spot_name='烧碱',
         spot_spec='32% 液碱(折百口径需换算)', spot_region='华东主流', spot_tax='含税',
         contract_spec='32% 液碱(GB/T 11199)', futures_region='仓库/厂库交割',
         unit='元/吨', multiplier=30, tick=1,
         last_trade_rule='合约交割月份第 10 个交易日（郑商所）',
         note='★口径风险：现货若按 32% 液碱实物吨报价，而期货按折百(100%)计价，基差需×折算系数才可比'),
    dict(code='EB', name='苯乙烯', exchange='大商所', futures_contract_prefix='EB',
         ppid=358, channel=14, spot_name='苯乙烯',
         spot_spec='工业级 ≥99.8%', spot_region='华东(江阴/张家港)', spot_tax='含税',
         contract_spec='苯乙烯(GB/T 3915 优等品)', futures_region='华东/华南仓库交割',
         unit='元/吨', multiplier=5, tick=1,
         last_trade_rule='合约交割月份第 10 个交易日（大商所）',
         note='EB 合约 5 吨/手'),
    dict(code='FG', name='玻璃', exchange='郑商所', futures_contract_prefix='FG',
         ppid=473, channel=17, spot_name='玻璃',
         spot_spec='5mm 浮法白玻（生意社现货稿原始计数单位：元/平方米）',
         spot_region='沙河/华中/华东', spot_tax='含税',
         spot_unit='元/平方米', spot_to_fut_factor=20,
         spot_unit_note='现货 元/平方米 × 20 = 元/吨（5mm 浮法玻璃 20 m² ≙ 1 吨）；'
                        '换算在基差计算前统一施加，公式仍为 现货(元/吨) − 期货(元/吨)',
         contract_spec='5mm 浮法玻璃(GB/T 11614)', futures_region='仓库交割(沙河/华中/华东)',
         unit='元/吨', multiplier=20, tick=1,
         last_trade_rule='合约交割月份第 10 个交易日（郑商所）',
         note='玻璃为建材类但属郑商所化工板块常设品种，可按需纳入/剔除'),
    dict(code='PX', name='PX', exchange='郑商所', futures_contract_prefix='PX',
         ppid=388, channel=14, spot_name='PX',
         spot_spec='对二甲苯(CFR/国内出厂)', spot_region='国内出厂/进口 CFR', spot_tax='含税/未税混杂',
         contract_spec='对二甲苯(GB/T 34054)', futures_region='仓库交割',
         unit='元/吨', multiplier=5, tick=2,
         last_trade_rule='合约交割月份第 10 个交易日（郑商所）',
         note='★口径风险：现货常为 CFR 美元价，需汇率与关税换算后才可比'),
]

# 池内但按设计不予扫描的品种（写明原因，避免"只扫有结果的"）。
EXCLUDED = [
    dict(code='PF', name='涤纶短纤', reason='生意社该商品无逐日「基准价/基差」文章，仅零星行情稿，无法构成同口径日序列'),
    dict(code='PG', name='液化石油气', reason='现货为进口 CFR 丙烷/丁烷美元价，与国内期货价需海运费+汇率+关税折算，口径不可直接相减'),
    dict(code='RU', name='天然橡胶', reason='原料(胶水/杯胶)与全乳胶、20 号胶价差体系独立，需专业换算，本次不纳入'),
    dict(code='SP', name='纸浆', reason='进口针叶浆 CFR 美元价，口径不可直接相减'),
    dict(code='LU', name='低硫燃料油', reason='国际化合约、以美元/吨计价，需汇率折算'),
]


def load_pool(path: str | None = None) -> list[dict]:
    if path and os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            obj = json.load(f)
        if isinstance(obj, list):
            return obj
        return obj.get('products', [])
    return [dict(p) for p in DEFAULT_POOL]


def by_code(pool: list[dict]) -> dict[str, dict]:
    return {p['code']: p for p in pool}
