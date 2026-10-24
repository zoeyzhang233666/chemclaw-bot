# -*- coding: utf-8 -*-
"""全部来源清单（品种数据 + 产业关系 + 事件）。每条都被 chain_graph / fundamentals 引用。"""

SOURCES = {
    # ---------------- 数据源 ----------------
    'S14': dict(group='数据', title='新浪财经期货 K 线接口 InnerFuturesNewService.getDailyKLine（主力连续日线）',
                url='https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_{SYM}=/InnerFuturesNewService.getDailyKLine?symbol={SYM}',
                date='2026-10-20 抓取', reliability='高',
                usage='全部 15 个品种的 open/high/low/close/volume/open_interest/settle，元/吨，主力连续'),
    'S16': dict(group='数据', title='新浪财经 InnerFuturesNewService 数据字段说明（d/o/h/l/c/v/p/s = 日期/开/高/低/收/量/持仓/结算）',
                url='https://stock2.finance.sina.com.cn/futures/api/jsonp.php',
                date='2026-10-20', reliability='中', usage='字段解析口径'),
    'S17': dict(group='数据', title='郑商所 PX 期货上市公告（2023-09-15 上市，合约单位 5 吨/手）',
                url='http://www.czce.com.cn/', date='2023-09', reliability='高',
                usage='PX 历史仅约 2.9 年的原因说明；与其他品种重叠期最短板'),
    'S18': dict(group='数据', title='大连商品交易所 塑料/聚丙烯/聚氯乙烯合约规则（5 吨/手，元/吨报价）',
                url='http://www.dce.com.cn/', date='—', reliability='高', usage='报价单位与合约乘数核对'),
    'S19': dict(group='数据', title='上海期货交易所 沥青/燃料油/螺纹钢合约规则', url='https://www.shfe.com.cn/',
                date='—', reliability='高', usage='报价单位核对'),

    # ---------------- 产业关系 ----------------
    'S1': dict(group='产业关系', title='国贸期货 丙烯上市前瞻专题系列（二）：生产工艺路线（蒸汽裂解/催化裂化/PDH/MTO 丙烯来源）',
               url='https://m.hibor.com.cn/wap_detail.aspx?id=9d11130d65cd87005abf0a5647bb321d',
               date='2025-05-22', reliability='中',
               usage='PP 的丙烯来源多元（石脑油裂解、催化裂化、PDH、MTO），直接决定 PP 与原油/丙烷/甲醇的多条成本路径'),
    'S2': dict(group='产业关系', title='新湖期货《聚烯烃专题——2023 年 L-PP 套利回顾》（中国期货业协会投教网）',
               url='https://www.cfachina.org/servicesupport/analygarden/nyhgl/fxszh3/202311/P020231113560919881791.pdf',
               date='2023-11-13', reliability='高',
               usage='PE 与 PP 产业链相关性强、价格多数时间趋同；PP 原料来源更分散（含外采丙烷/甲醇/丙烯），'
                     '派生 L-PP 价差的分化机制'),
    'S3': dict(group='产业关系', title='《甲醇期货十问》产业链套利密码：MTO 利润修复中的交易机会',
               url='https://www.sohu.com/a/1053868539_121118710', date='2026-07-23', reliability='中',
               usage='MTO 装置同时生产乙烯/丙烯并进一步生产 PE/PP；MTO 环节利润与综合利润的区别'),
    'S4': dict(group='产业关系', title='CCFGroup《2025 China PP industry annual report》（含油制/MTO/PDH 三条 PP 成本章节）',
               url='https://ccfgroup.com/newscenter/newsview.php?Class_ID=400000&Info_ID=2026020430010',
               date='2026-02-04', reliability='高', usage='PP 三条工艺路线并存的成本核算口径'),
    'S5': dict(group='产业关系', title='长城证券《PTA 工艺路线均为 PX 氧化催化工艺》',
               url='http://www.cgws.com/cczq/ggdt/ccyj/202404/P020240410301157597544.pdf',
               date='2024-04', reliability='高', usage='PX → CTA → PTA 的唯一主流工艺路径'),
    'S6': dict(group='产业关系', title='中国期货业协会《行业概况及利润分析》（PTA 配方约 65.5% PX、醋酸与 PX 成本结构）',
               url='https://www.cfachina.org/servicesupport/analygarden/nyhgl/pta_5763/202302/P020230216316919105054.pdf',
               date='2023-02', reliability='高', usage='0.655 单耗系数与醋酸 0.036/0.029 口径'),
    'S7': dict(group='产业关系', title='信达期货《PTA：在检修的间隙，等待旺季的风》',
               url='https://www.7hcn.com/article/473292-1.html', date='2025-08-15', reliability='中',
               usage='PX 单耗由 0.665 降至 0.648、醋酸单耗降至 0.029 的技术迭代'),
    'S8': dict(group='产业关系', title='前瞻产业研究院《2021 年中国聚丙烯(PP)市场供需现状》（拉丝 33%、共聚注塑 22%、均聚注塑 14%、纤维 11%）',
               url='https://bg.qianzhan.com/report/detail/300/220402-93687da0.html', date='2022-04', reliability='中',
               usage='PP 下游结构，用于替代关系的业务意义说明'),
    'S9': dict(group='产业关系', title='qianniucaixin《干货/作PTA：成本的底线在哪里》（0.655 与加工费区间）',
               url='https://www.qianniucaixin.com/m/view.php?aid=31849', date='未标注', reliability='低',
               usage='仅作 0.655 口径的旁证（主力来源为 S6）'),
    'S10': dict(group='产业关系', title='信易科技《甲醇制烯烃(MTO)产业链套利策略》（1 吨烯烃约耗 3 吨甲醇）',
                url='https://www.shinnytech.com/articles/trading-strategy/arbitrage/mto-spread', date='2026-09-03',
                reliability='中', usage='MTO 利润价差的计算思路；说明 PP-MA 不是单一物料关系'),
    'S11': dict(group='产业关系', title='隆众资讯 乙二醇 9 月月度报告（产能基数 3257.2 万吨，乙烯制/合成气制产量结构）',
                url='https://finance.sina.com.cn/money/future/fmnews/2026-10-10/doc-iniutcvm2150191.shtml',
                date='2026-10-10', reliability='中', usage='EG 与 PTA 同为聚酯原料（共同下游），EG 自有乙烯/煤两条工艺'),
    'S12': dict(group='产业关系', title='期货日报（中国期货业协会转载）《黑色产业链利润与企业行为的相互影响》（焦化利润=焦炭-1.33×焦煤-160）',
                url='https://www.cfachina.org/industrydynamics/mediaviewoffuturesmarket/202404/t20240416_72636.html',
                date='2024-04-16', reliability='高', usage='JM-J 上下游关系与 1.33 系数、160 元/吨经验值'),
    'S13': dict(group='产业关系', title='中国钢铁新闻网《炼焦煤缘何成为钢铁产业链难以承受之重》（1 吨焦炭约耗 1.3 吨炼焦煤、1 吨钢约耗 0.5 吨焦炭）',
                url='http://www.csteelnews.com/xwzx/jrrd/202207/t20220720_65413.html', date='2022-07-20',
                reliability='高', usage='焦煤-焦炭-螺纹 的物料系数与成本占比（焦炭约占吨钢成本 38%）'),
    'S15': dict(group='产业关系', title='东方财富期货知识库《焦炭基础知识》（1 吨焦炭约耗 1.33 吨炼焦煤）',
                url='https://qhweb.eastmoney.com/help/739841.html', date='2026-10-08', reliability='中',
                usage='焦煤-焦炭 系数旁证'),
    'S30': dict(group='产业关系', title='行业通识：聚氯乙烯（电石法/乙烯法）与 PP、PE 在管材/型材/板材/包装中部分互相替代；PVC 需求与地产强绑定',
                url='（行业通识，无单一原文）', date='—', reliability='中',
                usage='PP-PVC、L-PVC 替代关系标注为 medium，且因稳定机制弱而列为"弱稳定"'),
    'S31': dict(group='产业关系', title='行业通识：氯化铵（联碱副产）可替代尿素用于氮肥；纯碱、尿素同属煤化工与合成氨下游',
                url='（行业通识，无单一原文）', date='—', reliability='中',
                usage='SA-UR 共用原料（合成氨/煤）关系的业务意义与局限'),

    # ---------------- 事件 ----------------
    'S20': dict(group='事件', title='《甲醇：供需结构改善》（9 艘承运伊朗甲醇的船舶列入 SDN 清单，运力超 400 万吨、约占伊朗对华出口 40%）',
                url='https://www.7hcn.com/article/475095-1.html', date='2026-10-13', reliability='中', usage='E01'),
    'S21': dict(group='事件', title='《甲醇主力合约日内暴涨10%报3925元/吨 港口库存30万吨刷历史新低》',
                url='https://feng.ifeng.com/c/8x5AgdbN2d1', date='2026-10-09', reliability='低',
                usage='E02（媒体口径，未经机构数据交叉验证）'),
    'S22': dict(group='事件', title='盛达期货研报《甲醇：国产供应增加 下游需求对高价接受度低》',
                url='https://emwap.eastmoney.com/a/202610123892877254.html', date='2026-10-12', reliability='中', usage='E03'),
    'S23': dict(group='事件', title='《PX：检修增加，成品油持续偏强，对二甲苯节后大涨》（新浪财经期货频道）',
                url='https://finance.sina.cn/futuremarket/qsyw/2026-10-08/detail-iniupafi7731780.d.html',
                date='2026-10-08', reliability='中', usage='E04、E12'),
    'S24': dict(group='事件', title='首创期货《成本和低库存提振，PTA 期价盘中一度涨停》（国际金融报）',
                url='https://ifnews.com/news.html?aid=874679&cid=48', date='2026-10-08', reliability='中', usage='E05'),
    'S25': dict(group='事件', title='建信期货《PTA供需走弱约束反弹空间 短期价格受成本主导》（中国金融信息网）',
                url='https://www.cnfin.com/dz-lb/detail/20261015/4481016_1.html', date='2026-10-15', reliability='中', usage='E06'),
    'S26': dict(group='事件', title='隆众资讯《聚丙烯 | 强成本低库存与弱需求博弈》（10-14 商业库存 62.08 万吨、产能利用率约 65%）',
                url='https://finance.sina.com.cn/money/future/roll/2026-10-17/doc-inivnvku1480435.shtml',
                date='2026-10-17', reliability='中', usage='E07、E08'),
    'S27': dict(group='事件', title='卓创资讯《PE：供应偏紧叠加刚性需求 10月预计LLDPE价格重心继续上移》（9 月产量/开工/检修损失）',
                url='https://www.sohu.com/a/1088204796_639898', date='2026-10-15', reliability='中', usage='E09'),
    'S28': dict(group='事件', title='百川盈孚 聚乙烯日评（2026-10-20 报价）',
                url='http://www.baiinfo.com.cn/suliaochanye/juyixi', date='2026-10-20', reliability='中', usage='E10'),
    'S29': dict(group='事件', title='隆众资讯《乙二醇：9月港口库存继续下探 现货流动性紧张加剧》',
                url='https://finance.sina.com.cn/money/future/fmnews/2026-10-10/doc-iniutcvm2150191.shtml',
                date='2026-10-10', reliability='中', usage='E11'),
    'S32': dict(group='事件', title='华联期货《聚丙烯：供应近紧远松，产能集中投放叠加旺季需求修复有限》',
                url='https://www.sohu.com/a/1088388385_121123911', date='2026-10-16', reliability='中', usage='E08 补充'),
}


def get(sid):
    return SOURCES.get(sid)


def cite(sid_list):
    """返回 [(id, title, url, date)] 便于生成表格。"""
    out = []
    for s in sid_list:
        v = SOURCES.get(s)
        if v:
            out.append((s, v['title'], v['url'], v['date']))
    return out
