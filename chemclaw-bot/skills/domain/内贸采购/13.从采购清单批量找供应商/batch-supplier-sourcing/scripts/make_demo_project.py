#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""构建示例项目 project.json（模拟清单 + 真实公开企业信息）。

物料行来自 purchase_list_simulated.xlsx 的解析结果；本文件只补充：
  - items 的采购背景字段（hazard、packaging_risk、region、spec_detail、questions）
  - suppliers（企业身份、产地）
  - evidence（每条带等级/引文/URL/日期）
  - links（物料—企业关联 + 身份 + 覆盖度 + 置信度）
  - actions / gaps / references

所有企业信息均为 2024-2026 年公开资料，逐条附来源链接；不包含任何报价、联系人、信用代码。
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import lib_common  # noqa: E402
import lib_ingest  # noqa: E402

LIST = os.path.join(ROOT, "examples", "purchase-lists", "northeast-china-plant", "purchase_list_simulated.xlsx")
OUT = os.path.join(ROOT, "examples", "northeast-china-batch", "project.json")

# ---------------------------------------------------------------- 证据库
E = {
    # —— 三友化工
    "E-SY-01": dict(grade="a", org="唐山三友化工股份有限公司", topic="2024 年年度报告：纯碱产能与产销量",
                    quote="公司纯碱产能340 万吨/年，产品市场占有率约10%……公司采用的是氨碱法生产纯碱，包括轻质纯碱和重质纯碱两种",
                    detail="年报披露纯碱 340 万吨/年、2024 年生产纯碱 334.01 万吨、销售 326.60 万吨；工艺为氨碱法，可生产轻质/重质纯碱。",
                    url="https://static.cninfo.com.cn/finalpage/2025-04-16/1223098359.PDF", date="2025-04-16",
                    items=["P01", "P15"], family="纯碱集团"),
    "E-SY-02": dict(grade="a", org="唐山三友化工股份有限公司", topic="2024 年年度报告：氯碱公司烧碱产能、≥85% 自用",
                    quote="氯碱公司为高新技术企业，主导产品包括烧碱和聚氯乙烯（包括专用树脂），产能分别为53 万吨/年、52.5 万吨/年……生产的烧碱超过85%用于粘胶短纤维生产",
                    detail="烧碱产能 53 万吨/年，但 85% 以上自用于粘胶短纤维，外销量有限；2024 年烧碱产量 50.91 万吨。",
                    url="https://static.cninfo.com.cn/finalpage/2025-04-16/1223098359.PDF", date="2025-04-16",
                    items=["P02", "P09", "P12", "P18"], family="氯碱厂", caveat="内部自用比例高，外部可售量需在询价时明确"),
    "E-SY-03": dict(grade="a", org="唐山三友化工股份有限公司", topic="2024 年年度报告：子公司经营情况（纯碱、氯化钙、原盐）",
                    quote="唐山三友志达钙业有限公司：公司主营业务为氯化钙、氯化钠、融雪剂的生产与销售……唐山三友盐化有限公司：公司主营业务为原盐的生产与销售",
                    detail="年报“主要子公司”披露：志达钙业生产销售氯化钙，盐化公司生产销售原盐；青海五彩碱业当期生产纯碱 122.18 万吨。",
                    url="https://static.cninfo.com.cn/finalpage/2025-04-16/1223098359.PDF", date="2025-04-16",
                    items=["P03", "P06", "P08", "P21"], family="钙盐厂/盐矿"),
    "E-SY-04": dict(grade="a", org="唐山三友化工股份有限公司", topic="2024 年年度报告：产能与产品规格（32%/50%/片碱）",
                    quote="公司烧碱生产采用离子膜法生产工艺，可生产32%烧碱、50%烧碱、片状固碱、液氯、高纯盐……当前纯碱、粘胶短纤维年产能分别达到340 万吨、80 万吨",
                    detail="明确列出 32%、50% 液碱与片状固碱三种形态，可用于判断液碱形态匹配。",
                    url="https://static.cninfo.com.cn/finalpage/2025-04-16/1223098359.PDF", date="2025-04-16",
                    items=["P02", "P09", "P12", "P18"], family="氯碱厂"),
    # —— 山东海化
    "E-HH-01": dict(grade="a", org="山东海化股份有限公司", topic="2024 年年度报告：产品结构与年度产销量",
                    quote="公司立足盐化产业，继续致力于纯碱、烧碱、溴素、氯化钙、小苏打等产品的生产和销售……全年生产纯碱309.69 万吨、烧碱（折百）28.61 万吨",
                    detail="2024 年营收中纯碱占 72.64%、烧碱 10.58%、氯化钙 5.36%；纯碱产量 309.69 万吨、烧碱（折百）28.61 万吨。",
                    url="https://static.cninfo.com.cn/finalpage/2025-03-22/1222867296.PDF", date="2025-03-22",
                    items=["P01", "P02", "P03", "P06"], family="纯碱/氯碱/钙盐"),
    "E-HH-02": dict(grade="A", org="山东海化股份有限公司", topic="2025 年年度报告：安全/生产许可证载明产能与规格",
                    quote="安全生产许可证 2023.12.31-2026.12.30：氯24 万t/a、氢氧化钠30 万t/a、盐酸10 万t/a、氢6250t/a、次氯酸钠溶液13.72 万t/a、硫酸4800t/a、双氧水(折合27.5%计,含27.5%、35%、50%三种规格)20 万t/a（氯碱树脂公司）",
                    detail="许可证口径直接列出氢氧化钠 30 wt/a、双氧水 20 wt/a（含 27.5%/35%/50% 三种规格），是合规层级的直接生产证据。",
                    url="https://static.cninfo.com.cn/finalpage/2026-03-21/1225022066.PDF", date="2026-03-21",
                    items=["P02", "P07", "P09", "P11", "P12", "P13", "P14", "P18"], family="氯碱树脂公司"),
    "E-HH-03": dict(grade="a", org="山东海化股份有限公司", topic="2024 年年度报告：双氧水项目建设进展",
                    quote="项目建设加力提速，双氧水项目建成投产，球状氯化钙二期项目实现当年立项、当年达产达效目标",
                    detail="2024 年双氧水项目建成投产，与 2025 年报许可证载明 20 万吨/年装置相互印证，属“先投产、后核发许可口径”的时间差。",
                    url="https://static.cninfo.com.cn/finalpage/2025-03-22/1222867296.PDF", date="2025-03-22",
                    items=["P04", "P15"], family="氯碱厂"),
    "E-HH-04": dict(grade="F", org="山东海化股份有限公司", topic="年报披露的氯化钙相关许可（食品添加剂/饲料添加剂/质量管理体系）",
                    quote="食品添加剂氯化钙（氯化钙厂）……质量管理体系认证证书 氯化钙厂",
                    detail="年报列示氯化钙厂的食品添加剂与饲料添加剂许可，说明存在独立的氯化钙生产单元；但清单需要的工业级二水片状/32% 溶液形态无公开产能。",
                    url="https://static.cninfo.com.cn/finalpage/2025-03-22/1222867296.PDF", date="2025-03-22",
                    items=["P03", "P08", "P21"], family="钙盐厂"),
    "E-HH-05": dict(grade="B", org="郑商所/东方财富", topic="郑商所增设山东海化为指定纯碱交割厂库",
                    quote="郑商所：增设山东海化股份有限公司为指定纯碱交割厂库（2023-09）",
                    detail="交易所指定厂库意味着企业具备标准化纯碱产品的稳定交付与仓单生成能力，可与年报纯碱产销量相互印证。",
                    url="https://finance.eastmoney.com/a/202309202853074785.html", date="2023-09-20",
                    items=["P01"], family="纯碱交割"),
    # —— 博源化工（原远兴能源）
    "E-BY-01": dict(grade="a", org="内蒙古博源化工股份有限公司（原远兴能源）", topic="2025 年半年度报告：天然碱纯碱/小苏打产量",
                    quote="公司共生产各类产品515.71 万吨，其中纯碱339.46 万吨，小苏打73.97 万吨，尿素88.23 万吨",
                    detail="2025 上半年纯碱产量 339.46 万吨，说明一期 500 万吨/年天然碱装置进入稳定生产。",
                    url="https://static.cninfo.com.cn/finalpage/2025-08-08/1224424873.PDF", date="2025-08-08",
                    items=["P01", "P15"], family="天然碱"),
    "E-BY-02": dict(grade="a", org="内蒙古博源化工股份有限公司", topic="2025 年年度报告摘要：在产产能（已更名）",
                    quote="公司纯碱在产产能680 万吨/年，小苏打在产产能150 万吨/年，尿素在产产能154 万吨/年……纯碱、小苏打产能位居国内第一；另有160 万吨……处于试车阶段，产能爬坡",
                    detail="证券简称已由“远兴能源”变更为“博源化工”（000683）；在产纯碱 680 万吨/年，另有 160 万吨/年处于试车阶段（未计入在产）。",
                    url="https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=000683&id=12124597", date="2026-04-20",
                    items=["P01"], family="天然碱", caveat="名称变更后的工商主体与年报主体需以完整年报核对"),
    "E-BY-03": dict(grade="a", org="内蒙古远兴能源股份有限公司", topic="2024 年年度报告摘要：纯碱产量",
                    quote="2024 年，公司共生产各类产品907.93 万吨，其中纯碱577.79 万吨，小苏打143.25 万吨，尿素165.92 万吨",
                    detail="2024 全年纯碱产量 577.79 万吨，支撑“产能—产量—销量”链路的完整性。",
                    url="http://static.cninfo.com.cn/finalpage/2025-04-25/1223283103.PDF", date="2025-04-25",
                    items=["P01"], family="天然碱"),
    # —— 苏盐井神
    "E-JS-01": dict(grade="a", org="江苏苏盐井神股份有限公司", topic="2025 年年度报告：盐/碱/钙三类产品产销量",
                    quote="盐类产品 生产量 8,235,331.21 吨……碱类产品 746,857.83 吨……钙类产品 334,964.98 吨；主业为盐及盐化工、盐穴综合利用两大产业",
                    detail="公司产品按“盐类—碱类—钙类”三大类披露，主要产品为食盐、两碱工业盐、小工业盐、纯碱；氯化钙以分支机构口径生产。",
                    url="http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-4/2026-04-23/12149430.PDF", date="2026-04-23",
                    items=["P06", "P01", "P03", "P08"], family="盐化工"),
    "E-JS-02": dict(grade="B", org="江苏苏盐井神股份有限公司官网", topic="公司简介：产品谱系",
                    quote="拥有9 个大中型井矿盐采矿权，保有资源储量150 亿吨。主要产品有食用盐、工业盐、纯碱、元明粉、氯化钙等……年总产量突破900 万吨",
                    detail="官网明确工业盐、纯碱、氯化钙为在售产品线，可与年报三大类目相互印证。",
                    url="http://www.jssyjsgf.com/about/about.html", date="2026-09",
                    items=["P06", "P01", "P03", "P08"], family="盐化工"),
    "E-JS-03": dict(grade="B", org="郑州商品交易所 / 证券时报", topic="苏盐井神被指定为纯碱交割厂库",
                    quote="郑州商品交易所2024 年11 月11 日公告，决定增设苏盐井神公司为指定纯碱交割厂库，自2025年11月第16个交易日启用",
                    detail="交割厂库公告 + 交割免检品牌（井神牌）共同印证其纯碱为可标准化交付商品。",
                    url="https://finance.sina.com.cn/stock/relnews/cn/2024-11-12/doc-incvuxry8256559.shtml", date="2024-11-12",
                    items=["P01"], family="纯碱交割"),
    "E-JS-04": dict(grade="C", org="江苏苏盐井神股份有限公司 / 证券时报", topic="储气库卤水制盐项目（在建产能）",
                    quote="拟投资18.89 亿元建设储气库卤水制盐综合利用工程，建设规模为300 万吨/年固体盐、液体盐150 万方/年",
                    detail="此 300 万吨/年固体盐为在建产能，不得计入现有供应能力；在覆盖度计算中按“在建”处理。",
                    url="https://www.stcn.com/article/detail/1437212.html", date="2025-12-03",
                    items=["P06"], family="盐化工", caveat="在建产能，不作为当前供货能力"),
    # —— 中盐昆山
    "E-KS-01": dict(grade="B", org="中盐昆山有限公司（中国盐业集团）官网", topic="企业简介：50 万吨纯碱联碱企业",
                    quote="公司前身昆山锦港化工有限责任公司……成为年产50 万吨纯碱的大型联碱企业，曾位于全国十大碱厂之列。现为中国盐业集团所属上市公司中盐内蒙古化工股份有限公司(600328.SH)的全资子公司",
                    detail="官网明确企业性质为联碱法纯碱生产企业，年产 50 万吨，隶属中盐化工（600328）。",
                    url="http://kunshan.chinasalt.com.cn/ksgywm/ksqyjj/", date="2026-09",
                    items=["P01"], family="纯碱集团"),
    "E-KS-02": dict(grade="A", org="江苏省应急管理厅", topic="危化品项目安全审查结果公示（查询入口）",
                    quote="结果公示……“企业/项目名称”支持模糊查询……“许可证/意见书编号”必须输入精确的编号",
                    detail="该入口可按企业名称查询安全审查/许可结果。本报告只记录入口，具体许可证号须由采购员按企业全称逐一查询并留档（未代企业填列编号，避免捏造）。",
                    url="https://yjt.jszwfw.gov.cn:12200/yjgl/safe/showList.do?type=danger", date="2026-09",
                    items=["P01"], family="监管查询"),
    # —— 华泰化工
    "E-HT-01": dict(grade="C", org="每日经济新闻（访谈华泰股份）", topic="东营华泰化工 75 万吨/年离子膜烧碱",
                    quote="全资子公司东营华泰化工集团有限公司目前有2 条离子膜烧碱生产线，设计产能75 万吨/年（折百）",
                    detail="上市公司在投资者互动中披露的设计产能口径，与地方清洁生产公示一致。",
                    url="https://www.nbd.com.cn/articles/2023-10-12/3050846.html", date="2023-10-12",
                    items=["P02", "P09", "P12", "P18"], family="氯碱厂"),
    "E-HT-02": dict(grade="C", org="东营市万和节能科技有限公司（清洁生产审核公示）", topic="装置构成与产品清单",
                    quote="目前公司拥有 50万吨/年离子膜烧碱生产装置一套、 25万吨/年离子膜烧碱搬迁改造项目生产装置一套……产品为 32%离子膜烧碱、 50%离子膜烧碱、液氯、高纯盐酸、氢气",
                    detail="第三方清洁生产公示列出装置规模与 32%/50% 液碱产品，属于可公开检索的 C 级交叉证据。",
                    url="http://www.wanhesd.com/nd.jsp?id=109", date="2024-06",
                    items=["P02", "P09", "P12", "P18"], family="氯碱厂"),
    "E-HT-03": dict(grade="a", org="山东华泰纸业股份有限公司", topic="2024 年年度报告：化工业务（氯碱-盐化工）",
                    quote="公司属于造纸行业，主要业务是造纸和化工……全国领先的氯碱盐化工基地",
                    detail="上市公司年报确认化工（氯碱盐化工）为第二主业，可用于集团层面的身份判断；未单列烧碱产量。",
                    url="http://static.cninfo.com.cn/finalpage/2025-04-19/1223144229.PDF", date="2025-04-19",
                    items=["P02", "P09"], family="氯碱厂"),
    # —— 嘉化能源
    "E-JH-01": dict(grade="a", org="浙江嘉化能源化工股份有限公司", topic="2024 年年度报告：烧碱装置与产品规格",
                    quote="目前嘉化能源有两套离子膜烧碱装置，合计规模29.7 万吨……嘉化能源烧碱产品主要包括以下规格：30%烧碱、32%烧碱、48%烧碱",
                    detail="明确列出 32% 液碱规格；规模 29.7 万吨/年，属中型氯碱装置，适合区域就近供应。",
                    url="http://dataclouds.cninfo.com.cn/shgonggao/2025/2025-04-10/af49f37c153e11f0b0c3fa163e957f7a.pdf", date="2025-04-10",
                    items=["P02", "P14"], family="氯碱厂"),
    "E-JH-02": dict(grade="a", org="浙江嘉化能源化工股份有限公司", topic="2024 年年度报告：子公司浙江嘉化双氧水有限公司",
                    quote="浙江嘉化双氧水有限公司的主营业务为双氧水的生产……核准排放指标对应嘉化双氧水公司5 万吨/年双氧水系列产品技改项目",
                    detail="年报确认存在双氧水生产子公司及在产技改项目，但披露的并非完整商品量产能，需在询价中确认可售规格与量。",
                    url="http://dataclouds.cninfo.com.cn/shgonggao/2025/2025-04-10/af49f37c153e11f0b0c3fa163e957f7a.pdf", date="2025-04-10",
                    items=["P04", "P07", "P11", "P13"], family="双氧水"),
    # —— 中盐常州化工
    "E-CZ-01": dict(grade="B", org="常州市金坛区人民政府网（走访报道）", topic="中盐常化：氯碱为主业的综合性化工企业，两基地",
                    quote="中盐常州化工股份有限公司是以生产氯碱产品为主的综合性化工企业……整体占地1100余亩，拥有金坛和滨江两个生产基地",
                    detail="政府稿件认定其氯碱生产属性与两基地布局；具体烧碱产能、许可证号未在第 0 层页面披露。",
                    url="https://www.jintan.gov.cn/index.php?a=show&c=phone&catid=39491&id=264733", date="2024-10-10",
                    items=["P02", "P09"], family="氯碱厂"),
    "E-CZ-02": dict(grade="C", org="常州市生态环境局", topic="建设项目环评审批公示入口",
                    quote="常州市生态环境局 拟批准建设项目环境影响报告书公示（2025-04）",
                    detail="环评审批公示是核实装置规模最直接的公开来源之一；本次未检索到中盐常化对应烧碱扩产/技改的具体公示文本，列为待补充证据。",
                    url="https://sthjj.changzhou.gov.cn/html/hbj/2025/ALFJELKI_0421/26651.html", date="2025-04-21",
                    items=["P02"], family="监管"),
    # —— 上海氯碱化工
    "E-LJ-01": dict(grade="a", org="上海氯碱化工股份有限公司", topic="2024 年年度报告：烧碱产能与基地",
                    quote="公司主要产品行业领先，烧碱产能105 万吨/年，聚氯乙烯行业48 万吨/年……公司强化上海与广西基地协同优势",
                    detail="总产能 105 万吨/年（含广西钦州基地）；年报另披露“公司烧碱合并产能102 万吨”。两处口径并存，需按基地拆分询价。",
                    url="http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2025/2025-4/2025-04-15/10871533.PDF", date="2025-04-15",
                    items=["P02", "P09"], family="氯碱厂", conflict_with="烧碱合并产能102 万吨/年"),
    # —— 索普新材料
    "E-SP-01": dict(grade="a", org="江苏索普化工股份有限公司", topic="2024 年年度报告摘要：子公司氯碱装置",
                    quote="公司全资子公司索普新材料现拥有60 万吨/年硫酸及下游系列产品、20 万吨/年离子膜碱、12.6 万吨/年液氯、17 万吨/年高纯盐酸等装置",
                    detail="20 万吨/年离子膜碱来自上市公司摘要，可直接判断烧碱生产能力；装置规模小，多为区域内配套使用。",
                    url="https://stockn.xueqiu.com/SH600746/20250415347362.pdf", date="2025-04-15",
                    items=["P02", "P09"], family="氯碱厂"),
    "E-SP-02": dict(grade="B", org="江苏索普（集团）官网", topic="集团产品与产能清单",
                    quote="产品年产能包括69 万吨甲醇、120 万吨醋酸、25 万吨醋酸乙酯、30 万吨硫酸、4 万吨ADC 发泡剂、50 万吨液体二氧化碳等",
                    detail="官网产能清单未单列离子膜碱，与上市公司摘要存在披露颗粒度差异；以定期报告为准。",
                    url="http://www.sopo.com.cn/info/2-14-1132-1.html", date="2026-09",
                    items=["P02"], family="集团官网"),
    # —— 卫星化学
    "E-WX-01": dict(grade="a", org="卫星化学股份有限公司", topic="2024 年年度报告摘要：乙二醇产能规模",
                    quote="形成182 万吨乙二醇、50 万吨聚醚大单体与表面活性剂、20 万吨乙醇胺、15 万吨碳酸酯的产能规模",
                    detail="乙二醇 182 万吨/年为公司自述产能口径；连云港石化 EO/MEG 联产装置的检修公告可进一步印证在产（见 E-WX-03）。",
                    url="https://file.finance.qq.com/finance/hs/pdf/2025/03/25/1222880221.PDF", date="2025-03-25",
                    items=["P05", "P19"], family="乙二醇"),
    "E-WX-02": dict(grade="a", org="卫星化学股份有限公司", topic="2024 年年度报告摘要：双氧水产品与产能",
                    quote="高纯度电子级双氧水……等新产品顺利进入市场",
                    detail="年报摘要提到电子级双氧水产品，但未披露商品量产能；早期券商整理表列出平湖 25 万吨、另一基地 22 万吨双氧水（C 级），需在询价中核实。",
                    url="https://file.finance.qq.com/finance/hs/pdf/2025/03/25/1222880221.PDF", date="2025-03-25",
                    items=["P04", "P07", "P11", "P13"], family="双氧水", caveat="商品量产能未在定期报告中单独披露"),
    "E-WX-03": dict(grade="C", org="界面新闻（引自卫星化学公告）", topic="连云港石化 EO/MEG 联产装置检修与复产",
                    quote="对公司全资子公司连云港石化有限公司年产80 万吨聚乙烯装置、73 万吨环氧乙烷与91 万吨乙二醇联产装置……进行检修……已完成检修，恢复正常生产",
                    detail="检修公告中的装置口径（73 万吨 EO + 91 万吨 MEG）可用于交叉验证乙二醇在产状态。",
                    url="https://www.jiemian.com/article/11196978.html", date="2024-05-21",
                    items=["P05", "P19"], family="乙二醇"),
    # —— 古雷石化
    "E-GL-01": dict(grade="A", org="国家发展和改革委员会", topic="福建古雷炼化一体化项目投产",
                    quote="项目包括80万吨乙烯装置，以及年产10万吨/70万吨的环氧乙烷/乙二醇装置、60万吨/年苯乙烯装置、35万吨/年聚丙烯装置",
                    detail="发改委官网对装置规模的官方表述，是乙二醇生产能力的 A 级证据。",
                    url="https://www.ndrc.gov.cn/fggz/cyfz/zcyfz/202108/t20210831_1295651.html", date="2021-08-31",
                    items=["P05", "P19"], family="乙二醇"),
    "E-GL-02": dict(grade="C", org="见道网（工程报道）", topic="中沙古雷乙烯项目 EO/EG 装置开车",
                    quote="10/100万吨/年环氧乙烷/乙二醇装置正式投氧开车……第一批产品顺利送入中间罐区",
                    detail="项目中新增 10/100 万吨 EO/EG 装置（2026 年开车），可作为二期/扩产线索；投产初期以自用与合同客户为主。",
                    url="https://www.seetao.com/details/281019.html", date="2026-10-15",
                    items=["P05"], family="乙二醇", caveat="新装置投产初期供货稳定性待观察"),
    # —— 华鲁恒升
    "E-HL-01": dict(grade="a", org="山东华鲁恒升化工股份有限公司", topic="2024 年年度报告：主要产品产销量",
                    quote="新能源新材料相关产品 万吨 431.35（生产量）……有机胺 57.41……化学肥料 483.20……醋酸及衍生品 149.04",
                    detail="乙二醇、异辛醇等被归入“新能源新材料相关产品”合并披露，未单列；能说明公司确实在产该类产品，但无法据此认定乙二醇单品产能。",
                    url="http://static.cninfo.com.cn/finalpage/2025-03-29/1222940908.PDF", date="2025-03-29",
                    items=["P05", "P19"], family="煤化工", caveat="合并披露，单品产能需外部交叉验证"),
    "E-HL-02": dict(grade="a", org="山东华鲁恒升化工股份有限公司", topic="2024 年年度报告：异辛醇市场占有率",
                    quote="公司新能源新材料相关产品主要包括己内酰胺、尼龙6、己二酸、异辛醇、碳酸二甲酯、碳酸甲乙酯等产品……公司异辛醇产品市场占有率约10%",
                    detail="年报明确异辛醇为在产产品且市占率约 10%，可作为本例“同装置族”跨品种供应的判断依据。",
                    url="http://static.cninfo.com.cn/finalpage/2025-03-29/1222940908.PDF", date="2025-03-29",
                    items=["P05"], family="羰基合成"),
    "E-HL-03": dict(grade="C", org="媒体/行业报道", topic="德州基地 50 万吨/年煤制乙二醇",
                    quote="山东华鲁恒升凭借德州基地50万吨/年成熟煤制乙二醇产能充分受益",
                    detail="第三方报道口径为 50 万吨/年煤制乙二醇；公开检索已出现“煤制 MEG 装置改造转产 DMC”的券商观点，需以企业函证确认装置当前用途。",
                    url="https://www.163.com/dy/article/L3DMBSFT0514CNIT.html", date="2026-08-03",
                    items=["P05", "P19"], family="煤化工", caveat="存在“改造转产 DMC”的公开讨论，装置当前产品需确认"),
    # —— 齐翔腾达
    "E-QX-01": dict(grade="a", org="淄博齐翔腾达化工股份有限公司", topic="2024 年年度报告摘要：产品组合",
                    quote="主营：甲乙酮、顺酐、丙烯、橡胶、丁二烯、甲基丙烯酸甲酯、丁腈胶乳、叔丁醇、异辛烷、MTBE、环氧丙烷、丙烯酸、石油和化工各类催化剂",
                    detail="年报摘要的产品清单不含乙二醇/异辛醇；作为 C4/C3 综合化工企业存在跨品种可能的联想，但无任何公开生产证据 → 归为“关系待证”。",
                    url="https://static.cninfo.com.cn/finalpage/2025-04-10/1223043783.PDF", date="2025-04-10",
                    items=["P05", "P19"], family="碳四/碳三"),
    "E-QX-02": dict(grade="a", org="淄博齐翔腾达化工股份有限公司", topic="2024 年年度报告摘要：甲乙酮/顺酐规模",
                    quote="公司甲乙酮装置的设计产能为26 万吨/年……公司建有40 万吨/年产能的正丁烷氧化法制顺酐装置",
                    detail="证明其确为大型生产型化工企业（厂家身份），但对清单没有相应物料 → 不计入覆盖度。",
                    url="https://static.cninfo.com.cn/finalpage/2025-04-10/1223043783.PDF", date="2025-04-10",
                    items=[], family="碳四"),
    "E-QX-03": dict(grade="C", org="联合资信（债券评级跟踪报告）", topic="实际控制人与股权结构",
                    quote="跟踪期内，公司实际控制人未发生变化，仍为山东省国资委",
                    detail="用于判断企业性质（地方国企控股上市公司），不构成生产证据。",
                    url="https://www.lhratings.com/reports/B021592-P46179-2019-GZ2025.pdf", date="2025",
                    items=[], family="主体资质"),
    # —— 中盐昆山以外：区域稀缺物料的自述者（贸易商/待核实）
    "E-NA-01": dict(grade="D", org="【待补】本报告第二轮检索未覆盖", topic="甘油/柠檬酸/硼砂：公开渠道未核到生产厂家",
                    quote="（留位）本轮未检索到可核验的生产企业证据",
                    detail="该三条物料在本轮公开检索中未取得厂家级证据；为避免编造，保留为空并列入缺口清单，第二轮须按排污许可、环评批复、行业协会名录逐一检索。",
                    url="", date="2026-10", items=["P10", "P16", "P17"], family="缺口"),
    "E-ZZ-01": dict(grade="D", org="用户提供的供应商名片/转述（示例）", topic="辽宁某综合化工贸易公司：自述可供应氯化钙、工业盐、烧碱",
                    quote="“我们代理唐山三友、山东海化的氯化钙和工业盐，也能配 32% 液碱”",
                    detail="无链接、无经营许可证、无授权书，属于不可核验自述；只能作为“待验证线索”，不能进入厂家池，也不能计入覆盖度。",
                    url="", date="2026-09",
                    items=["P03", "P06", "P02"], family="贸易商"),
}


def sup(sid, name, short, identity, province, note, evidence_ids, **extra):
    d = dict(id=sid, name=name, short=short, identity=identity, province=province,
             identity_note=note, evidence_ids=evidence_ids)
    d.update(extra)
    return d


SUPPLIERS = [
    sup("SY", "唐山三友化工股份有限公司", "三友化工", "S", "河北",
        "氯碱+纯碱+钙盐一体化上市公司。纯碱 340 万吨/年见年报；烧碱 53 万吨/年但 ≥85% 自用；氯化钙经志达钙业生产。",
        ["E-SY-01", "E-SY-02", "E-SY-03", "E-SY-04"],
        roles=["纯碱厂家", "氯碱厂（液碱/片碱）", "钙盐厂（氯化钙）", "盐矿"], route="曹妃甸/唐山—大连 海运 约 260 mile",
        notes="烧碱外销比例低，询价需确认可外售量；片碱为固碱形态之一。"),
    sup("HH", "山东海化股份有限公司", "山东海化", "S", "山东",
        "盐化龙头企业（原盐—纯碱—氯碱—溴素—氯化钙）。纯碱 309.69 万吨、烧碱 28.61 万吨（2024），双氧水 20 万吨/年见 2025 年报许可证。",
        ["E-HH-01", "E-HH-02", "E-HH-03", "E-HH-04", "E-HH-05"],
        roles=["纯碱厂家", "氯碱厂", "双氧水厂", "氯化钙厂", "原盐/溴素"], route="潍坊—大连 海运 约 300 km",
        notes="本清单中覆盖物料最广的厂家（纯碱、烧碱、氯化钙、27.5%/35% 双氧水）。"),
    sup("BY", "内蒙古博源化工股份有限公司（原远兴能源）", "博源化工", "S", "内蒙古",
        "天然碱法制纯碱国内龙头，在产纯碱 680 万吨/年、小苏打 150 万吨/年（2025 年报摘要）。",
        ["E-BY-01", "E-BY-02", "E-BY-03"],
        roles=["天然碱纯碱", "小苏打"], route="鄂尔多斯—大连 铁路+港口 运距长",
        notes="成本优势明显但运距最长；适合作为价格锚/远期锁量的战略源。"),
    sup("JS", "江苏苏盐井神股份有限公司", "苏盐井神", "S", "江苏",
        "井矿盐+纯碱+氯化钙+元明粉一体化上市企业；盐类产量 823.5 万吨、碱类 74.7 万吨、钙类 33.5 万吨（2025）。",
        ["E-JS-01", "E-JS-02", "E-JS-03", "E-JS-04"],
        roles=["工业盐（井矿盐）", "纯碱厂家", "氯化钙", "元明粉"], route="淮安—大连 海运（连云港）约 600 km",
        notes="工业盐+纯碱+氯化钙三料同厂，适合做“三料同框”谈判；300 万吨/年制盐为在建产能。"),
    sup("KS", "中盐昆山有限公司", "中盐昆山", "S", "江苏",
        "中国盐业集团所属联碱法纯碱企业，年产 50 万吨纯碱，隶属中盐化工（600328）。",
        ["E-KS-01", "E-KS-02"],
        roles=["联碱法纯碱"], route="昆山—大连 海运（太仓/上海港）约 700 km",
        notes="位于长三角，运费高于山东湾内企业；适合作为备选。"),
    sup("HT", "东营华泰化工集团有限公司", "华泰化工", "S", "山东",
        "华泰股份（600308）全资子公司，75 万吨/年离子膜烧碱（折百），产品含 32%/50% 液碱、液氯、高纯盐酸。",
        ["E-HT-01", "E-HT-02", "E-HT-03"],
        roles=["氯碱（32%/50% 液碱）"], route="东营—大连 海运 约 280 km",
        notes="单纯氯碱型，跨品种能力弱；适合做液碱专项价格战/备选。"),
    sup("JH", "浙江嘉化能源化工股份有限公司", "嘉化能源", "S", "浙江",
        "嘉兴园区循环经济型上市企业，两套离子膜烧碱合计 29.7 万吨，含双氧水生产子公司。",
        ["E-JH-01", "E-JH-02"],
        roles=["氯碱（32/48% 液碱）", "双氧水子公司"], route="嘉兴—大连 海运 约 900 km",
        notes="远距离，适合不可抗力时的补充来源，不建议作为主供。"),
    sup("CZ", "中盐常州化工股份有限公司", "中盐常化", "S", "江苏",
        "中盐系统氯碱生产企业，金坛与滨江两基地；具体烧碱产能与许可证须进一步核查。",
        ["E-CZ-01", "E-CZ-02"],
        roles=["氯碱"], route="常州—大连 海运约 650 km",
        notes="身份为氯碱厂家（官媒口径），产能与产品形态未核实。"),
    sup("LJ", "上海氯碱化工股份有限公司", "上海氯碱", "S", "上海",
        "老牌氯碱上市企业，烧碱产能 105 万吨/年（含广西基地），年报另见 102 万吨合并口径。",
        ["E-LJ-01"],
        roles=["氯碱（液碱/固碱）"], route="上海—大连 海运 约 850 km",
        notes="两种产能口径并存；按基地拆分询价。"),
    sup("SP", "江苏索普新材料科技有限公司", "索普新材料（索普）", "S", "江苏",
        "上市公司索普全资子公司，20 万吨/年离子膜碱、12.6 万吨/年液氯、17 万吨/年高纯盐酸装置。",
        ["E-SP-01", "E-SP-02"],
        roles=["氯碱"], route="镇江—大连 海运约 700 km",
        notes="装置规模较小，多为区域配套，外售量有限。"),
    sup("WX", "卫星化学股份有限公司", "卫星化学", "S", "浙江",
        "轻烃一体化企业，182 万吨/年乙二醇；双氧水（含电子级）为在售产品线。",
        ["E-WX-01", "E-WX-02", "E-WX-03"],
        roles=["乙二醇（EO/MEG 联产）", "双氧水"], route="连云港/嘉兴—大连 海运 约 450–800 km",
        notes="乙二醇 + 双氧水的跨品种组合；双氧水商品量需核实。"),
    sup("GL", "福建古雷石化有限公司", "古雷石化", "S", "福建",
        "中石化与旭腾投资合资的炼化一体化企业，10/70 万吨/年 EO/EG 装置（2021 投产），另有 10/100 万吨/年新装置（2026 开车）。",
        ["E-GL-01", "E-GL-02"],
        roles=["乙二醇"], route="漳州—大连 海运 约 1,700 km",
        notes="运距远；乙二醇单品种，适合作为价格与质量对标源。"),
    sup("HL", "山东华鲁恒升化工股份有限公司", "华鲁恒升", "S", "山东",
        "煤化工平台型上市企业，产品含乙二醇（归入新能源新材料合并披露）与异辛醇（市占率约 10%）。",
        ["E-HL-01", "E-HL-02", "E-HL-03"],
        roles=["乙二醇（煤制）", "异辛醇", "尿素/醋酸/DMF"], route="德州—大连 铁路/汽运 约 1,000 km",
        notes="德州基地煤制乙二醇 50 万吨/年为第三方口径；存在装置改造转产 DMC 的公开讨论，需函证。"),
    sup("QX", "淄博齐翔腾达化工股份有限公司", "齐翔腾达", "S", "山东",
        "C4/C3 综合化工上市企业（甲乙酮、顺酐、MMA、PO 等），未见乙二醇/异辛醇产品线。",
        ["E-QX-01", "E-QX-02", "E-QX-03"],
        roles=["甲乙酮", "顺酐", "MMA", "环氧丙烷"], route="淄博—大连 铁路/汽运 约 900 km",
        notes="厂家身份成立，但与清单物料无生产证据 → 不计入覆盖度（防伪阳性样本）。"),
    sup("U-GLY-01", "【待补】甘油生产企业（未核实）", "甘油：待补厂家", "U", "",
        "本版未从公开渠道核到甘油生产厂家的直接证据；留位，禁止填猜测名称。", ["E-NA-01"], roles=["待补"]),
    sup("U-CIT-01", "【待补】柠檬酸生产企业（未核实）", "柠檬酸：待补厂家", "U", "",
        "发酵法柠檬酸生产企业名录未在本轮核实；留位，禁止填猜测名称。", ["E-NA-01"], roles=["待补"]),
    sup("U-BOR-01", "【待补】硼砂生产企业（未核实）", "硼砂：待补厂家", "U", "",
        "硼砂（十水）生产企业未在本轮核实；留位，禁止填猜测名称。", ["E-NA-01"], roles=["待补"]),
    sup("ZZ", "辽宁某综合化工贸易有限公司（示例，未核验）", "区域贸易商（示例）", "U", "辽宁",
        "用户提供的渠道线索，自述代理三友/海化的氯化钙、工业盐并配送液碱；无许可证、无授权书。",
        ["E-ZZ-01"],
        roles=["贸易商（待核验）"], route="大连本地配送",
        notes="无证据主体。列入本表是为了演示“未证实企业”应如何被隔离，而不是推荐它。"),
]


def link(item, sid, identity, coverage, conf, degree, current, potential, rationale, link_id=None, **extra):
    d = dict(item_code=item, supplier_id=sid, identity=identity, coverage=coverage, confidence=conf,
             degree=degree, current_relation=current, potential_relation=potential,
             rationale=rationale)
    if link_id:
        d["link_id"] = link_id
    d.update(extra)
    return d


LINKS = [
    # 纯碱 P01
    link("P01", "BY", "S", "direct", "已证实", "independent", True, True, "年报披露氨碱法/天然碱法纯碱产能与年产量；2025 年在产 680 万吨/年。"),
    link("P01", "HH", "S", "direct", "已证实", "independent", True, True, "年报+许可证：纯碱 309.69 万吨/年，郑商所指定交割厂库。"),
    link("P01", "SY", "S", "direct", "已证实", "independent", True, True, "年报：纯碱产能 340 万吨/年，重质化率行业前列，可生产重质纯碱。"),
    link("P01", "JS", "S", "direct", "已证实", "independent", True, True, "2025 年报碱类产品产量 74.69 万吨；郑商所纯碱交割厂库（井神牌）。"),
    link("P01", "KS", "S", "partial_spec", "待确认", "confirmable", False, True,
         "官网披露年产 50 万吨联碱法纯碱；未公开重质/轻质比例与铁含量，需样品与 COA。"),
    # 烧碱 P02
    link("P02", "HH", "S", "direct", "已证实", "independent", True, True, "2025 年报许可证：氢氧化钠 30 wt/a；产能含 32%/50% 液碱（本企业氯碱装置）。"),
    link("P02", "HT", "S", "direct", "已证实", "independent", True, True, "75 万吨/年离子膜烧碱，产品含 32%、50% 液碱。"),
    link("P02", "JH", "S", "direct", "已证实", "independent", True, True, "年报：两套离子膜装置合计 29.7 万吨，产品列 30%/32%/48% 烧碱。"),
    link("P02", "LJ", "S", "partial_spec", "已证实", "independent", True, True,
         "烧碱产能 105 万吨/年（含广西），年报未逐基地给出 32% 液碱外售量，形态与基地需确认。"),
    link("P02", "SY", "S", "partial_spec", "待确认", "confirmable", False, True,
         "烧碱产能 53 万吨/年，但 ≥85% 自用于粘胶短纤维；可外售量与形态（32% 液碱）需确认。"),
    link("P02", "SP", "S", "partial_spec", "待确认", "confirmable", False, True, "20 万吨/年离子膜碱；外售量与 32% 形态未披露。"),
    link("P02", "CZ", "S", "disclose", "待确认", "confirmable", False, True,
         "政府稿件认定氯碱主业的厂家；产能、许可证、产品形态均未从第 0 层公开来源取得。"),
    link("P02", "ZZ", "U", "dist_only", "待确认", "not_recommended", False, False, "自述可配送、无许可证与授权 → 不计入覆盖度。"),
    # 氯化钙 P03 二水片状
    link("P03", "HH", "S", "direct", "已证实", "independent", True, True, "年报分产品营收含氯化钙 3.23 亿元，另有氯化钙厂许可（F 级）。"),
    link("P03", "SY", "S", "direct", "已证实", "independent", True, True,
         "年报子公司志达钙业主营“氯化钙、氯化钠、融雪剂的生产与销售”（集团内生产主体）。"),
    link("P03", "JS", "S", "partial_spec", "待确认", "confirmable", False, True,
         "2025 年报钙类产品产量 33.5 万吨；二水片状 vs 无水/球状的产能分配未公开。"),
    link("P03", "ZZ", "U", "dist_only", "待确认", "not_recommended", False, False, "自述代理、无授权书。"),
    # 双氧水 27.5% P04
    link("P04", "HH", "S", "direct", "已证实", "independent", True, True, "许可证载明 20 万吨/年（含 27.5%、35%、50% 三规格）。"),
    link("P04", "WX", "S", "partial_spec", "待确认", "confirmable", False, True, "在售含电子级双氧水，但商品量产能与 27.5% 规格未在定期报告披露。"),
    link("P04", "JH", "S", "partial_spec", "待确认", "confirmable", False, True, "子公司为双氧水生产企业（5 万吨/年技改口径），可售规格需确认。"),
    # 乙二醇 P05
    link("P05", "WX", "S", "direct", "已证实", "independent", True, True, "182 万吨/年乙二醇（年报摘要），EO/MEG 联产装置在产。"),
    link("P05", "GL", "S", "direct", "已证实", "independent", True, True, "发改委：10/70 万吨/年 EO/EG 装置；另有 10/100 万吨/年新装置 2026 开车。"),
    link("P05", "HL", "S", "partial_spec", "待确认", "confirmable", False, True,
         "年报将乙二醇并入“新能源新材料相关产品”；德州 50 万吨/年为第三方口径，且公开讨论装置可能转产 DMC。"),
    link("P05", "QX", "S", "not_listed", "否", "not_recommended", False, False,
         "年报产品清单无乙二醇；C4/C3 综合化工身份不足以推断（防伪阳性）。"),
    # 工业盐 P06
    link("P06", "JS", "S", "direct", "已证实", "independent", True, True, "2025 年报盐类产品产量 823.5 万吨，主要产品含两碱工业盐。"),
    link("P06", "SY", "S", "direct", "已证实", "independent", True, True, "年报子公司三友盐化主营原盐生产销售；2025 年目标原盐 37 万吨。"),
    link("P06", "HH", "S", "partial_spec", "待确认", "confirmable", False, True, "盐化产业链含原盐，但 2025 年原盐采购占原料成本 38.65%，自供能力需确认。"),
    link("P06", "ZZ", "U", "dist_only", "待确认", "not_recommended", False, False, "自述代理、无授权。"),
    # 双氧水 35% P07
    link("P07", "HH", "S", "direct", "已证实", "independent", True, True, "许可证明确含 35% 规格。"),
    link("P07", "WX", "S", "partial_spec", "待确认", "confirmable", False, True, "双氧水在售，35% 规格待确认。"),
    link("P07", "JH", "S", "partial_spec", "待确认", "confirmable", False, True, "双氧水子公司，35% 规格待确认。"),
    # 片碱 P09
    link("P09", "SY", "S", "partial_spec", "待确认", "confirmable", False, True, "年报“可生产片状固碱”，但片碱外售量与纯度（99%）需确认。"),
    link("P09", "HH", "S", "partial_spec", "待确认", "confirmable", False, True, "氯碱装置在产，片碱生产需另行核实（未在许可证中单列）。"),
    link("P09", "HT", "S", "partial_spec", "待确认", "confirmable", False, True, "液碱产线在产，片碱为固碱形态，需确认固体烧碱装置。"),
    link("P09", "LJ", "S", "partial_spec", "待确认", "confirmable", False, True, "老牌氯碱企业，固碱/片碱供应需按基地确认。"),
    link("P09", "SP", "S", "partial_spec", "待确认", "confirmable", False, True, "20 万吨/年离子膜碱，片碱形态未披露。"),
    link("P09", "CZ", "S", "disclose", "待确认", "confirmable", False, True, "氯碱厂家，片碱能力未公开。"),
    # 氯化钙溶液 32% P08
    link("P08", "HH", "S", "partial_spec", "待确认", "confirmable", False, True, "氯化钙厂有液体产品线（废清液制钙液），32% 商品量未披露。"),
    link("P08", "JS", "S", "partial_spec", "待确认", "confirmable", False, True, "年报名列“液体氯化钙”生产能力（限分支机构）。"),
]

# ---------------------------------------------------------------- 待补物料：公开渠道未核到厂家（留位，不作为候选）
LINKS += [
    link("P10", "U-GLY-01", "S", "disclose", "待确认", "not_recommended", False, False,
         "待第二阶段检索（排污许可/环评/协会名录）后补入；本版不作为候选。"),
    link("P16", "U-CIT-01", "S", "disclose", "待确认", "not_recommended", False, False,
         "待第二阶段检索（发酵法柠檬酸生产企业名录）后补入；本版不作为候选。"),
    link("P17", "U-BOR-01", "S", "disclose", "待确认", "not_recommended", False, False,
         "待第二阶段检索（硼化工企业名录）后补入；本版不作为候选。"),
]

# ---------------------------------------------------------------- 异常行物料
# P13=双氧水50% | P14=烧碱(片碱?) | P15=纯碱轻质(单位缺失) | P16=硫磺 | P17=硫酸
# P18=柠檬酸 | P19=硼砂 | P20=烧碱(重复行) | P21=乙二醇(CAS错写) | P22=重酸 | P23=氯化钙(数量0)
LINKS += [
    link("P13", "HH", "S", "direct", "已证实", "independent", True, True, "许可证明确含 50% 规格。"),
    link("P13", "WX", "S", "partial_spec", "待确认", "confirmable", False, True, "双氧水在售（含电子级），50% 商品量与包装需确认。"),
    link("P13", "JH", "S", "partial_spec", "待确认", "confirmable", False, True, "双氧水子公司，50% 规格待确认。"),
    link("P15", "HH", "S", "partial_spec", "待确认", "confirmable", False, True, "氨碱法可产轻质纯碱（年报工艺说明），但轻质线产能未披露。"),
    link("P15", "SY", "S", "direct", "已证实", "independent", True, True, "年报：“可生产轻质纯碱和重质纯碱两种”。"),
    link("P15", "BY", "S", "partial_spec", "待确认", "confirmable", False, True, "天然碱法以重质纯碱为主，轻质品级需确认。"),
    link("P14", "HH", "S", "disclose", "待确认", "confirmable", False, True, "2025 年报许可证载明硫酸 4,800 t/a 装置与“液体硫磺在焚硫炉内燃烧”工艺；硫磺为本企业原料而非产物，是否外售需确认。"),
    link("P18", "SY", "S", "partial_spec", "待确认", "confirmable", False, True, "同 P09/P12：片状固碱能力见年报，第 21 行与第 15 行疑似重复物料。"),
    link("P14", "JH", "S", "partial_spec", "待确认", "confirmable", False, True, "年报披露 98% 工业硫酸/发烟硫酸在产，硫磺为其原料；硫磺外售需确认。"),
    link("P16", "WX", "S", "not_listed", "否", "not_recommended", False, False, "无柠檬酸产品线（企业强但物料无关，不应被匹配）。"),
    link("P17", "HH", "S", "not_listed", "否", "not_recommended", False, False, "无硼酸/硼砂产品线。"),
    link("P12", "SY", "S", "partial_spec", "待确认", "confirmable", False, True, "年报“可生产片状固碱”，与 P09 为同一物料的不同行，一并询价。"),
    link("P12", "HH", "S", "partial_spec", "待确认", "confirmable", False, True, "同 P09，需确认固体烧碱。"),
    link("P18", "SY", "S", "partial_spec", "待确认", "confirmable", False, True, "与第 15 行烧碱疑似同一物料，复用 P09/P12 候选。"),
    link("P18", "HH", "S", "partial_spec", "待确认", "confirmable", False, True, "同 P09。"),
    link("P19", "WX", "S", "direct", "已证实", "independent", True, True, "CAS 错写校正为 107-21-1 后与 P05 同一物质；工厂有乙二醇产能。"),
    link("P19", "HL", "S", "partial_spec", "待确认", "confirmable", False, True, "同 P05（CAS 校正后为同一物料）。"),
    link("P20", "QX", "S", "not_listed", "否", "not_recommended", False, False, "“重酸”未识别，无匹配依据。"),
    link("P21", "SY", "S", "direct", "已证实", "independent", True, True, "志达钙业氯化钙；本行待清单补齐数量后启用。"),
    link("P21", "HH", "S", "direct", "已证实", "independent", True, True, "氯化钙产品线；本行待清单补齐数量后启用。"),
]

ACTIONS = []  # 由 build_all 依据覆盖矩阵生成


def main():
    assets = lib_common.load_assets()
    proj = {"list": {"path": LIST}}
    res = lib_ingest.normalize_list(proj, lib_common.MaterialsDict(assets["materials"]), assets["field_map"], assets["rules"])

    items = []
    for idx, it in enumerate(res["items"]):
        rec = {k: it.get(k) for k in (
            "code", "raw_name", "name", "en", "aliases", "cas", "form", "spec", "purity", "unit", "unit_raw",
            "qty", "qty_annual", "packing", "delivery", "application", "supplier", "hazard", "hazard_ref",
            "status", "issues", "notes")}
        rec["source_row"] = it.get("source_row")
        rec["hazard_raw"] = it.get("hazard")
        rec["dup_of"] = it.get("dup_of")
        items.append(rec)

    project = {
        "_comment": "本文件由 make_demo_project.py 生成。模拟清单 + 真实公开企业资料。数字均可回溯到 evidence.url。",
        "meta": {
            "title": "某化工工厂 2027 年度大宗原料批量寻源",
            "subtitle": "模拟采购清单 × 真实公开企业信息 · 批量寻源与物料—供应商匹配矩阵",
            "buyer": "【模拟】东北某化工工厂采购部",
            "buyer_region": "辽宁·大连",
            "as_of": "2026-10-19",
            "sources_scope": [
                "上市公司定期报告/摘要（巨潮资讯、上交所、深交所）",
                "政府监管文件（发改委、应急管理厅、生态环境局、地方政府）",
                "亚洲企业交易所公告（郑商所交割厂库/免检品牌）",
                "企业官网与官方媒体报道",
                "行业媒体（标为 C 级，仅作交叉参考）"
            ],
            "exclusions": [
                "不含任何报价、账期、运费与关税",
                "不含联系人、银行账户、统一社会信用代码",
                "不保证覆盖全市场，样本为公开可核验的上市/央企/知名企业",
                "贸易商仅作为线索提示，不作推荐"
            ],
            "version": "v1.0",
            "accept_trader": False,
            "headline": [
                "21 行清单中 9 行可直接进入比价（P01 纯碱重质、P02 32% 液碱、P03 二水氯化钙、P05 乙二醇、P06 工业盐各有 ≥2 家厂家级候选）；"
                "另外 12 行存在歧义或厂家覆盖不足，需先澄清再谈价。",
                "跨品种能力集中在山东海化（7 个物料行已证实可为厂家）与唐山三友（5 个），两家合计可覆盖纯碱/烧碱/氯化钙/双氧水/工业盐五条主线；"
                "这两家应作为“打包谈判”的第一梯队。",
                "双氧水系（27.5%/35%/50%）证据链最强的一条是山东海化 2025 年报披露的安全生产许可证：氢氧化钠 30 万 t/a、双氧水折 27.5% 计 20 万 t/a（含 27.5%、35%、50% 三规格）——"
                "是极少数把产品规格写进许可证的公开材料。",
                "烧碱不适合只押一家：三友化工烧碱 53 万吨/年但 ≥85% 自用于粘胶短纤维，实际可外售量必须书面确认；液碱更现实的选择是华泰化工（75 万吨/年，32%/50%）、"
                "上海氯碱（105 万吨/年）与嘉化能源（29.7 万吨/年，30%/32%/48%）。",
                "乙二醇可核验厂家为卫星化学（182 万吨/年）与古雷石化（10/70 万吨/年 EO/EG）；华鲁恒升只能到“部分规格待确认”（年报将乙二醇并入新能源新材料合并披露）；"
                "齐翔腾达被明确判为“产品清单无乙二醇”，作为防伪阳性样本保留在表中。",
                "8 条缺口需在第二轮补检索：片碱 99%、32% 氯化钙溶液、50%/35% 双氧水部分规格、硫磺、硫酸、柠檬酸、硼砂、甘油和无法识别的“重酸”。"
                "这些“无厂家覆盖”只代表本轮未查出可核验厂家，不等于市场上没有。",
            ],
            "code_remap": {
                "P11": "P13", "P12": "P14", "P13": "P15", "P14": "P16", "P15": "P17",
                "P16": "P18", "P17": "P19", "P18": "P20", "P19": "P21", "P20": "P22", "P21": "P23",
            },
            "delivery_point": "辽宁·大连（工厂门到门）",
            "annual_scale_note": "清单数量为单次采购量，年用量用于判断规模与供货保障能力",
        },
        "list": {
            "source_file": "purchase_list_simulated.xlsx",
            "sheet": res["sheet"],
            "header_row": res["header_row"],
            "simulated": True,
            "note": "【模拟数据】仅用于演示方法；企业名、数量、用途为虚构。",
        },
        "items": items,
        "ambiguities": res["ambiguities"],
        "suppliers": SUPPLIERS,
        "evidence": [dict(id=k, **v) for k, v in E.items()],
        "links": LINKS,
        "actions": ACTIONS,
        "gaps": [],
        "references": [],
    }
    # 去掉证据里非 schema 字段
    clean = []
    for e in project["evidence"]:
        d = {k: e[k] for k in ("id", "org", "topic", "quote", "detail", "url", "date", "grade")}
        d["items"] = e.get("items", [])
        d["family"] = e.get("family", "")
        if e.get("caveat"):
            d["caveat"] = e["caveat"]
        if e.get("conflict_with"):
            d["conflict_with"] = e["conflict_with"]
        clean.append(d)
    project["evidence"] = clean
    project["evidence_map"] = {e["id"]: e for e in clean}

    lib_common.write_json(OUT, project)
    print("OK", OUT, "items=", len(items), "suppliers=", len(SUPPLIERS), "evidence=", len(clean), "links=", len(LINKS))


if __name__ == "__main__":
    main()
