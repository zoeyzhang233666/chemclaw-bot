# -*- coding: utf-8 -*-
"""
config.py —— 「看上下游价格联动」研究配置

设计原则：研究口径（品种、单耗、频率、窗口）全部集中在配置里，
脚本只负责执行；换一组上下游品种时，改这里 + 换数据文件即可。

字段说明
  upstream / downstream      : 品种标识与显示名
  coef                       : 主口径理论单耗（吨上游/吨下游）。必须来自 references/02，
                               不得由模型自行猜测；无可靠单耗时置 None，加工价差一律不出数。
  coef_alt                   : 敏感性区间（用于 Excel 的敏感性表与 HTML 滑块默认范围）
  other_cost                 : 其他辅料/动力成本（元/吨）。可为 0（只算收入型加工费），
                               非 0 时必须在报告注明来源。
  spread_mode                : 'process' = 下游价格 − coef×上游价格 − 其他成本
                               'raw'     = 下游价格 − 上游价格（两者同标尺时使用）
  anchor_check               : True 时自动做 log-log 斜率检验并给出建议 spread_mode
  freq                       : 'D' 日频 / 'W' 周频
  date_basis                 : 价格口径日期（发布日 vs 报道日）—— 见 references/01
  segments                   : 阶段划分（按产业逻辑断点，不得按结果反复切）
  windows                    : 滚动窗口（观测数）
  maxlag                     : 领先滞后最大滞后阶数（与 freq 匹配）
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

CONFIG = {
    'case': 'px-pta',
    'title': 'PX × PTA 上下游价格联动研究',
    'upstream': {'code': 'PX', 'name': '对二甲苯 PX', 'unit': '元/吨'},
    'downstream': {'code': 'PTA', 'name': '精对苯二甲酸 PTA', 'unit': '元/吨'},

    'coef': 0.655,
    'coef_alt': [0.60, 0.70],
    'other_cost': 0.0,
    'spread_mode': 'process',
    'anchor_check': True,

    'freq': 'D',
    'date_basis': 'report_date_deflated_by_one_day',  # SunSirs 英文站滞后一天，已在 align 阶段校正
    'tax': 'both_vat_inclusive',
    'freight_included': False,

    'segments': [
        {'start': '2023-10-07', 'end': '2024-12-31', 'code': 'S1',
         'name': 'PX扩能兑现+PTA过剩，加工费中枢下移'},
        {'start': '2025-01-01', 'end': '2025-12-31', 'code': 'S2',
         'name': 'PX供给趋紧、PTA加工费走阔'},
        {'start': '2026-01-01', 'end': '2026-10-20', 'code': 'S3',
         'name': 'PTA集中检修+地缘油价扰动'},
    ],
    'windows': [20, 60, 120],
    'maxlag': 20,
    'min_obs_ratio': 0.8,
    'data_file': os.path.join(HERE, 'processed', 'px_pta_daily.csv'),
    'events_file': os.path.join(HERE, 'events.json'),
}

# 单耗依据台账（每条都必须能在 references/02 中找到）
COEF_SOURCES = [
    {'value': 0.655, 'type': '行业通用值', 'source': '长江期货《PTA 上下游产能与加工利润分析》(2023-12-18)',
     'quote': '每生产 1 吨 PTA 平均消耗 0.655 吨左右 PX；原料成本=PX 国内现货价格*0.655（单耗系数）'},
    {'value': 0.653, 'type': '调研值', 'source': 'SCI99《PX Upstream-Downstream Linkages Strengthen》(2026-08-20)',
     'quote': 'Producing one ton of PTA requires approximately 0.653 tons of PX (slightly lower in new facilities)'},
    {'value': 0.647, 'type': '单套装置实测', 'source': '天风证券《石油化工·PTA 技术代际升级》(2019-12-14) 表 4',
     'quote': '恒力 PTA-4/5# 0.649 吨；新凤鸣独山 0.647 吨；汉邦石化一期 0.657 吨'},
    {'value': 0.032, 'type': '辅料单耗', 'source': '天风证券表 4 / SCI99 2026-08-20',
     'quote': '醋酸 0.029~0.040 吨/吨 PTA（SCI99：0.030~0.039 吨）'},
]
