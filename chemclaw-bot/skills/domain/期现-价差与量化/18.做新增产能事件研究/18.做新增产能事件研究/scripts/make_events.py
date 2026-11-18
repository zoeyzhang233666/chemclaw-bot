# -*- coding: utf-8 -*-
"""
events_pp.json 生成器 — 中国聚丙烯(PP)大型新增产能「已核实正式投产」事件库

数据来源（三份已完成的核实报告，均含原文引句 + URL + 证据等级）：
  1. 中国PP新增产能_2023-2025_核实报告.md          （2023–2025 段）
  2. pp_research/中国聚丙烯2020-2022新增产能投产核实报告.md （2020–2022 段）
  3. PP项目进展核实_2026-10-20.md                  （2026 在建/新投产段）

设计原则
--------
* 事件（event）= (project, stage, date)。同一项目的不同阶段是**不同事件**。
* 只登记有公开来源的日期；来源缺失即留空，不推测、不用"计划投产日"顶替。
* evidence_grade: A=政府批复/上市公司公告/央企官网；B=权威媒体；C=行业资讯机构；D=自媒体转载
* single_source=True 表示仅一个来源，统计时应降权或单独标注。
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "events_pp.json")

# 行业产能基数（万吨/年，年末，中国PP总产能）
# 来源说明见 capacity_base.json；此处仅放可核验年份，缺年份留 None
CAPACITY_BASE = {
    "2019": None, "2020": 2554, "2021": 2944, "2022": 3320,
    "2023": 3880, "2024": 4440, "2025": 5000, "2026": None,
}

PROJECTS = [
    # ---------------- 2020 ----------------
    {
        "project_id": "PP-2020-QZ-SINOCHEM",
        "name": "中化泉州 100万吨/年乙烯项目 配套聚丙烯装置",
        "owner": "中化泉州石化有限公司（中国中化）",
        "location": "福建省 泉州市 泉港石化工业区",
        "region": "华南",
        "process": "油制乙烯 → 气相法（Unipol 类）",
        "design_capacity": 35,
        "upstream": "配套 100万吨/年乙烯裂解",
        "stages": {
            "startup": {"date": "2020-09-17", "grade": "C", "single_source": True,
                        "quote": "16时18分开车成功产出合格聚丙烯产品"},
        },
        "first_estimate": "2020年6月", "actual": "2020-09-17",
        "delay_months": 3,
    },
    {
        "project_id": "PP-2020-BAOLAI",
        "name": "宝来利安德巴赛尔 轻烃综合利用项目 聚丙烯装置",
        "owner": "宝来利安德巴赛尔石化（辽宁宝来 + LyondellBasell）",
        "location": "辽宁省 盘锦市 辽东湾新区",
        "region": "东北",
        "process": "油制（石脑油裂解）→ Spheripol",
        "design_capacity": 60,
        "upstream": "配套 100万吨/年乙烯",
        "stages": {
            "startup": {"date": "2020-09-01", "grade": "B", "single_source": False,
                        "quote": "一期10套装置全部打通流程，60万吨/年聚丙烯装置投产", "date_precision": "月"},
        },
        "first_estimate": "2020年上半年", "actual": "2020-09（月精度）",
        "delay_months": 3,
        "note": "题述“80万吨PP”有误：80万吨是PE，PP为60万吨/年",
    },
    {
        "project_id": "PP-2020-WANHUA-YT",
        "name": "万华化学 烟台百万吨乙烯 配套聚丙烯",
        "owner": "万华化学集团股份有限公司（600309）",
        "location": "山东省 烟台市 万华烟台工业园",
        "region": "华东",
        "process": "轻烃裂解 → 气相法 PP",
        "design_capacity": 30,
        "upstream": "配套 100万吨/年乙烯",
        "stages": {
            "startup": {"date": "2020-11-09", "grade": "A", "single_source": False,
                        "quote": "乙烯装置产出合格产品，PP等同日全部一次开车成功"},
        },
        "first_estimate": "2020年下半年", "actual": "2020-11-09",
        "delay_months": 0,
        "note": "PP 单套精确日均未见官方口径，按乙烯装置合格品日对齐",
    },
    # ---------------- 2021 ----------------
    {
        "project_id": "PP-2021-DONGMING",
        "name": "东明石化 恒昌化工 聚丙烯装置",
        "owner": "山东东明石化集团（东明中油/恒昌化工）",
        "location": "山东省 菏泽市 东明县",
        "region": "华东",
        "process": "油制 → 气相法",
        "design_capacity": 20,
        "upstream": "自有炼厂丙烯",
        "stages": {
            "startup": {"date": "2021-03-18", "grade": "B", "single_source": False,
                        "quote": "9时08分投三剂，18时产出合格聚丙烯产品"},
        },
        "first_estimate": "2021年一季度", "actual": "2021-03-18", "delay_months": 0,
    },
    {
        "project_id": "PP-2021-HAIGUO",
        "name": "海国龙油 550项目 聚丙烯装置",
        "owner": "海国龙油石化股份有限公司",
        "location": "山东省 东营市",
        "region": "华东",
        "process": "重油裂解 → PP",
        "design_capacity": 35,
        "upstream": "550项目配套",
        "stages": {
            "startup": {"date": "2021-03-04", "grade": "C", "single_source": True,
                        "quote": "产出合格 T30S 粒料", "note": "随即因原料不足停车待料"},
        },
        "first_estimate": "2021年初", "actual": "2021-03-04", "delay_months": 0,
        "note": "投产即停车待料，与连续商业运行不同，需单独标注",
    },
    {
        "project_id": "PP-2021-GULEI",
        "name": "古雷炼化一体化 聚丙烯装置",
        "owner": "福建古雷石化有限公司（中石化 + 福建省合资）",
        "location": "福建省 漳州市 漳浦县 古雷石化基地",
        "region": "华南",
        "process": "油制 → 气相法",
        "design_capacity": 35,
        "upstream": "配套 80万吨/年乙烯",
        "stages": {
            "startup": {"date": "2021-03-21", "grade": "C", "single_source": True,
                        "quote": "全流程产出合格聚丙烯粒料", "note": "随即停工待料"},
            "commercial": {"date": "2021-08-23", "grade": "C", "single_source": True,
                           "quote": "乙烯装置08-17投料后，PP 于08月下旬恢复连续商业生产",
                           "date_precision": "月"},
        },
        "first_estimate": "2021年一季度", "actual": "2021-03-21（出料）/ 2021-08（连续商业）",
        "delay_months": 5,
        "note": "两段式投产：先出料后停工待料，真正的连续商业供给在8月",
    },
    {
        "project_id": "PP-2021-ZHONGHAN",
        "name": "中韩石化 乙烯脱瓶颈改造 聚丙烯",
        "owner": "中韩（武汉）石油化工有限公司",
        "location": "湖北省 武汉市",
        "region": "华中",
        "process": "油制 → 环管法",
        "design_capacity": 30,
        "upstream": "乙烯脱瓶颈",
        "stages": {
            "startup": {"date": "2021-03-26", "grade": "C", "single_source": True,
                        "quote": "产出 PPH-T03 粉料", "note": "造粒机未到位，仅出粉料；04-02 即停车检修"},
        },
        "first_estimate": "2021年2—3月", "actual": "2021-03-26（粉料）",
        "delay_months": -1,
        "note": "严格说未产出合格粒料，不构成完整正式投产；作为“边角事件”单独标注",
    },
    {
        "project_id": "PP-2021-TJ-SINOPEC",
        "name": "天津石化 炼油产品结构调整 聚丙烯",
        "owner": "中国石化天津分公司",
        "location": "天津市 滨海新区",
        "region": "华北",
        "process": "油制 → 气相法",
        "design_capacity": 20,
        "upstream": "炼油结构调整配套",
        "stages": {
            "startup": {"date": "2021-04-18", "grade": "B", "single_source": False,
                        "quote": "一次开车成功并产出合格聚丙烯产品"},
        },
        "first_estimate": "2021年二季度", "actual": "2021-04-18", "delay_months": 0,
    },
    {
        "project_id": "PP-2021-DONGHUA-NB",
        "name": "东华能源 宁波三期 2×40万吨/年 聚丙烯",
        "owner": "东华能源股份有限公司（002221）",
        "location": "浙江省 宁波市 大榭开发区",
        "region": "华东",
        "process": "PDH 丙烷脱氢 → PP（Unipol 类）",
        "design_capacity": 80,
        "upstream": "自有两套 66万吨/年 PDH",
        "stages": {
            "startup": {"date": "2021-06-01", "grade": "A", "single_source": False,
                        "quote": "公告 2021-043：两套40万吨/年聚丙烯装置打通全流程并产出合格产品"},
            "construction": {"date": "2019-03-12", "grade": "B", "single_source": False,
                             "quote": "宁波三期开工"},
        },
        "first_estimate": "2021年3月", "actual": "2021-06-01", "delay_months": 3,
        "note": "本批事件中唯一有上市公司公告编号佐证的投产",
    },
    {
        "project_id": "PP-2021-LIAOYANG",
        "name": "辽阳石化 俄油加工优化增效改造 聚丙烯",
        "owner": "中国石油辽阳石化分公司",
        "location": "辽宁省 辽阳市",
        "region": "东北",
        "process": "油制 → 气相法",
        "design_capacity": 30,
        "upstream": "俄油加工改造配套",
        "stages": {
            "startup": {"date": "2021-08-18", "grade": "B", "single_source": False,
                        "quote": "16时30分一次开车投料成功并产出合格 PP 产品"},
        },
        "first_estimate": "2021年8月底", "actual": "2021-08-18", "delay_months": 0,
    },
    {
        "project_id": "PP-2021-ZPC-3",
        "name": "浙江石化 二期 3# 45万吨/年 聚丙烯",
        "owner": "浙江石油化工有限公司（荣盛石化 002493）",
        "location": "浙江省 舟山市 绿色石化基地（鱼山岛）",
        "region": "华东",
        "process": "油制 → Spherizone / Spheripol（口径有混用）",
        "design_capacity": 45,
        "upstream": "二期 2000万吨/年炼化一体化 配套 280万吨/年乙烯",
        "stages": {
            "startup": {"date": "2021-12-30", "grade": "C", "single_source": True,
                        "quote": "3#聚丙烯装置投料开车成功"},
        },
        "first_estimate": "2021年7月", "actual": "2021-12-30", "delay_months": 6,
    },
    # ---------------- 2022 ----------------
    {
        "project_id": "PP-2022-SINOCHEM-HAINAN-GAS",
        "name": "海南炼化 百万吨乙烯 20万吨/年 气相法聚丙烯",
        "owner": "中国石化海南炼油化工有限公司",
        "location": "海南省 儋州市 洋浦经济开发区",
        "region": "华南",
        "process": "Unipol 气相法",
        "design_capacity": 20,
        "upstream": "配套 100万吨/年乙烯",
        "stages": {
            "startup": {"date": "2022-12-20", "grade": "B", "single_source": True,
                        "quote": "20万吨/年气相法聚丙烯装置一次开车成功，产出合格聚丙烯产品"},
        },
        "first_estimate": "2022年底", "actual": "2022-12-20", "delay_months": 0,
    },
    {
        "project_id": "PP-2022-SINOCHEM-HAINAN-LOOP",
        "name": "海南炼化 百万吨乙烯 30万吨/年 环管法聚丙烯",
        "owner": "中国石化海南炼油化工有限公司",
        "location": "海南省 儋州市 洋浦经济开发区",
        "region": "华南",
        "process": "3G+ 环管法",
        "design_capacity": 30,
        "upstream": "配套 100万吨/年乙烯",
        "stages": {
            "startup": {"date": "2022-12-28", "grade": "B", "single_source": True,
                        "quote": "30万吨/年环管法聚丙烯装置一次开车成功，产出合格聚丙烯产品"},
        },
        "first_estimate": "2022年底", "actual": "2022-12-28", "delay_months": 0,
    },
    {
        "project_id": "PP-2022-ZHENHAI-3",
        "name": "镇海炼化 一期 3# 30万吨/年 聚丙烯（Spherizone）",
        "owner": "中国石化镇海炼化分公司",
        "location": "浙江省 宁波市 镇海",
        "region": "华东",
        "process": "LyondellBasell Spherizone",
        "design_capacity": 30,
        "upstream": "镇海基地一期 150万吨/年乙烯",
        "stages": {
            "startup": {"date": "2022-02-28", "grade": "C", "single_source": True,
                        "quote": "开工试车圆满成功",
                        "note": "措辞为“试车成功”，未写产出合格品，严格口径不构成正式投产"},
        },
        "first_estimate": "2021年", "actual": "2022-02-28（试车成功）", "delay_months": 14,
        "note": "★ 收录但降级标注：作为“试车节点”研究，不作为“正式投产”事件",
        "treat_as_stage": "commissioning",
    },
    {
        "project_id": "PP-2022-ZPC-4",
        "name": "浙江石化 二期 4# 45万吨/年 聚丙烯",
        "owner": "浙江石油化工有限公司（荣盛石化 002493）",
        "location": "浙江省 舟山市 绿色石化基地",
        "region": "华东",
        "process": "油制 → Spherizone / Spheripol",
        "design_capacity": 45,
        "upstream": "二期炼化一体化",
        "stages": {
            "startup": {"date": "2022-03-20", "grade": "B", "single_source": False,
                        "quote": "08时00分一次投料开车成功"},
        },
        "first_estimate": "2021年7月", "actual": "2022-03-20", "delay_months": 8,
    },
    {
        "project_id": "PP-2022-BOHUA",
        "name": "天津渤化化工 南港一期 30万吨/年 聚丙烯",
        "owner": "天津渤海化工集团有限责任公司",
        "location": "天津市 滨海新区 南港工业区",
        "region": "华北",
        "process": "Lummus 气相法",
        "design_capacity": 30,
        "upstream": "一期 180万吨/年甲醇制烯烃",
        "stages": {
            "startup": {"date": "2022-07-06", "grade": "A", "single_source": False,
                        "quote": "30万吨/年聚丙烯装置随一期全面投产", "date_precision": "月"},
        },
        "first_estimate": "2021年三季度末", "actual": "2022-07（月精度）", "delay_months": 10,
        "note": "题述“60万吨”有误：60万吨为二期规划（2×30），一期实际30万吨",
    },
    {
        "project_id": "PP-2022-DAXIE",
        "name": "中海石油宁波大榭 30万吨/年 聚丙烯",
        "owner": "中海石油宁波大榭石化有限公司",
        "location": "浙江省 宁波市 大榭",
        "region": "华东",
        "process": "油制 → 气相法",
        "design_capacity": 30,
        "upstream": "大榭石化馏分油改扩建",
        "stages": {
            "startup": {"date": "2022-08-30", "grade": "C", "single_source": True,
                        "quote": "30万吨/年聚丙烯装置开车成功产出合格品"},
        },
        "first_estimate": "2022年上半年", "actual": "2022-08-30", "delay_months": 5,
    },
    # ---------------- 2023 ----------------
    {
        "project_id": "PP-2023-GUANGDONG-PETRO",
        "name": "广东石化 炼化一体化（揭阳）50万吨/年 聚丙烯",
        "owner": "中国石油广东石化有限责任公司",
        "location": "广东省 揭阳市 大南海石化工业区",
        "region": "华南",
        "process": "Grace UNIPOL 气相流化床",
        "design_capacity": 50,
        "upstream": "2000万吨/年炼油 + 120万吨/年乙烯 + 260万吨/年PX",
        "stages": {
            "construction": {"date": "2021-04-15", "grade": "B", "single_source": False,
                             "quote": "聚丙烯装置建安工程开工", "date_precision": "月"},
            "mechanical": {"date": "2022-05-20", "grade": "A", "single_source": False,
                           "quote": "于5月20日中交，是炼化一体化项目第一个中交的生产装置"},
            "commissioning": {"date": "2022-10-13", "grade": "A", "single_source": False,
                              "quote": "50万吨/年聚丙烯装置挤压造粒机组正式投料并产出合格粒料……比计划节点提前36天"},
            "startup": {"date": "2023-02-08", "grade": "D", "single_source": True,
                        "quote": "15时18分反应器投入主催化剂，15时26分开始反应，15时40分开始出料"},
            "first_product": {"date": "2023-02-09", "grade": "D", "single_source": True,
                              "quote": "13时20分挤压造粒开车成功，装置打通全流程"},
            "commercial": {"date": "2023-05-30", "grade": "A", "single_source": False,
                           "quote": "中国石油宣布广东石化炼化一体化项目全面投入商业运营"},
        },
        "first_estimate": "2022年底", "actual": "2023-02-08/09", "delay_months": 3,
        "note": "★ 本批唯一具备完整“开工→中交→试车→投料→打通全流程→商运”全链条的项目",
    },
    {
        "project_id": "PP-2023-GUANGDONG-2",
        "name": "广东石化 二期新建 20万吨/年 聚丙烯",
        "owner": "中国石油广东石化有限责任公司",
        "location": "广东省 揭阳市 大南海石化工业区",
        "region": "华南",
        "process": "JPP Horizone 气相法",
        "design_capacity": 20,
        "upstream": "广东石化二期",
        "stages": {
            "startup": {"date": "2023-12-31", "grade": "B", "single_source": False,
                        "quote": "凌晨1时挤压机开车产出合格粒料，标志该装置首次投料开车一次成功"},
        },
        "first_estimate": "2023年底", "actual": "2023-12-31", "delay_months": 0,
    },
    {
        "project_id": "PP-2023-HONGYI",
        "name": "广西鸿谊新材料 30万吨/年 聚丙烯（华谊钦州配套）",
        "owner": "广西鸿谊新材料有限公司",
        "location": "广西壮族自治区 钦州市 钦州港",
        "region": "华南",
        "process": "国产 SPG 工艺",
        "design_capacity": 30,
        "upstream": "华谊钦州化工新材料一体化基地",
        "stages": {
            "mechanical": {"date": "2022-12-03", "grade": "C", "single_source": True,
                           "quote": "于2022年12月3日完成中交"},
            "startup": {"date": "2023-03-16", "grade": "C", "single_source": True,
                        "quote": "成功引入丙烯，聚合反应正式开始，合格聚丙烯产品从取料口流出"},
        },
        "first_estimate": "2023年一季度", "actual": "2023-03-16", "delay_months": 0,
        "note": "题述“华谊40万吨”有误：主体为鸿谊30万吨",
    },
    {
        "project_id": "PP-2023-JINGBO",
        "name": "山东京博石化 60万吨/年 高性能聚丙烯",
        "owner": "山东京博石油化工有限公司",
        "location": "山东省 滨州市 博兴县",
        "region": "华东",
        "process": "LyondellBasell（Spherizone 20 + Spheripol 40）",
        "design_capacity": 60,
        "upstream": "自有炼厂丙烯",
        "stages": {
            "startup": {"date": "2023-03-17", "grade": "B", "single_source": False,
                        "quote": "建成投产仪式，首车产品发运",
                        "note": "为仪式日，未见“一次开车成功/产出合格产品”原始通报"},
        },
        "first_estimate": "2022年4月", "actual": "2023-03-17", "delay_months": 11,
        "note": "★ 日期为投产仪式日而非开车通报日，证据偏弱，须单独标注",
    },
    {
        "project_id": "PP-2023-ANQING",
        "name": "安庆石化 炼油转化工结构调整 30万吨/年 聚丙烯",
        "owner": "中国石化安庆分公司",
        "location": "安徽省 安庆市",
        "region": "华东",
        "process": "RTC（重油催化裂解）→ PP",
        "design_capacity": 30,
        "upstream": "RTC 装置配套",
        "stages": {
            "startup": {"date": "2023-07-06", "grade": "B", "single_source": False,
                        "quote": "全部装置一次安全环保开车成功"},
        },
        "first_estimate": "2023年上半年", "actual": "2023-07-06", "delay_months": 3,
    },
    {
        "project_id": "PP-2023-NINGBO-KINGFA",
        "name": "宁波金发新材料 PP 装置Ⅰ 40万吨/年",
        "owner": "宁波金发新材料有限公司（金发科技 600143）",
        "location": "浙江省 宁波市 北仑区",
        "region": "华东",
        "process": "PDH → PP（工艺待核）",
        "design_capacity": 40,
        "upstream": "60万吨/年 PDH",
        "stages": {
            "startup": {"date": "2023-09-16", "grade": "C", "single_source": True,
                        "quote": "PP装置Ⅰ投料开车产出合格品"},
        },
        "first_estimate": "2023年三季度", "actual": "2023-09-16", "delay_months": 0,
    },
    {
        "project_id": "PP-2023-DONGHUA-MM",
        "name": "东华能源（茂名）一期 40万吨/年 聚丙烯",
        "owner": "东华能源（茂名）有限公司（002221）",
        "location": "广东省 茂名市 滨海新区",
        "region": "华南",
        "process": "PDH → PP（Unipol 类，待核）",
        "design_capacity": 40,
        "upstream": "一期 60万吨/年 PDH",
        "stages": {
            "startup": {"date": "2023-09-27", "grade": "A", "single_source": False,
                        "quote": "公告：已生产出合格聚丙烯产品"},
        },
        "first_estimate": "2023年三季度", "actual": "2023-09-27", "delay_months": 0,
        "note": "题述“一期60万吨PP”有误：60万吨是PDH，PP为40万吨",
    },
    {
        "project_id": "PP-2023-BAOFENG-3",
        "name": "宁夏宝丰能源 宁东三期 50万吨/年 聚丙烯",
        "owner": "宁夏宝丰能源集团股份有限公司（600989）",
        "location": "宁夏回族自治区 银川市 宁东能源化工基地",
        "region": "西北",
        "process": "煤制 MTO（DMTO）",
        "design_capacity": 50,
        "upstream": "三期 150万吨/年甲醇 + MTO + OCC",
        "stages": {
            "commissioning": {"date": "2023-11-07", "grade": "A", "single_source": False,
                              "quote": "宁东三期烯烃项目已全面进入试生产运行，主体装置已经阶段性达产"},
        },
        "first_estimate": "2022年底", "actual": "2023年（试生产运行）", "delay_months": 8,
        "note": "★ 仅有“试生产运行/阶段性达产”口径，无明确“产出合格品”日；PP 未达设计负荷",
    },
    # ---------------- 2024 ----------------
    {
        "project_id": "PP-2024-GUOHENG",
        "name": "泉州国亨化学 45万吨/年 聚丙烯",
        "owner": "泉州国亨化学有限公司（台塑集团）",
        "location": "福建省 泉州市 泉港石化工业园区",
        "region": "华南",
        "process": "LyondellBasell Spheripol",
        "design_capacity": 45,
        "upstream": "配套 PDH（2025-01-31 才出合格丙烯）",
        "stages": {
            "startup": {"date": "2024-04-27", "grade": "C", "single_source": True,
                        "quote": "产出合格聚丙烯颗粒，一次开车投产成功"},
        },
        "first_estimate": "2023年一季度", "actual": "2024-04-27", "delay_months": 13,
        "note": "★ 投产比 PDH 早 9 个月，2024-04至2025-01 丙烯只能外购，成本结构特殊",
    },
    {
        "project_id": "PP-2024-INECS-TJ",
        "name": "中沙英力士（天津南港）35万吨/年 聚丙烯",
        "owner": "中石化英力士（天津）石化有限公司",
        "location": "天津市 滨海新区 南港工业区",
        "region": "华北",
        "process": "中国石化自有聚丙烯技术",
        "design_capacity": 35,
        "upstream": "中沙石化南港配套",
        "stages": {
            "startup": {"date": "2024-11-11", "grade": "B", "single_source": False,
                        "quote": "全流程一次开车成功并产出合格产品"},
        },
        "first_estimate": "2024年三季度", "actual": "2024-11-11", "delay_months": 2,
        "note": "产能口径存冲突：中国石化 35万吨 vs 行业盘点 30万吨，本表采信 35万吨",
    },
    # ---------------- 2025 ----------------
    {
        "project_id": "PP-2025-GX-PETRO",
        "name": "中国石油广西石化 炼化一体化转型升级 40万吨/年 聚丙烯",
        "owner": "中国石油广西石化公司",
        "location": "广西壮族自治区 钦州市 钦州港经济技术开发区",
        "region": "华南",
        "process": "国产“全产品组合”聚丙烯工艺",
        "design_capacity": 40,
        "upstream": "120万吨/年乙烯",
        "stages": {
            "startup": {"date": "2025-10-16", "grade": "B", "single_source": False,
                        "quote": "40万吨/年聚丙烯装置16日在广西钦州产出首批合格产品，实现一次开工成功。这是中国首套可生产全产品组合的聚丙烯装置"},
            "first_product": {"date": "2025-10-30", "grade": "B", "single_source": False,
                              "quote": "产品合格外运，项目一次开车成功"},
            "rampup": {"date": "2025-11-15", "grade": "D", "single_source": True,
                       "quote": "装置产能利用率稳定保持90%以上", "date_precision": "月"},
        },
        "first_estimate": "2025年下半年", "actual": "2025-10-16", "delay_months": 0,
    },
    # ---------------- 2026（最新，窗口不完整） ----------------
    {
        "project_id": "PP-2026-TARIM-2",
        "name": "中国石油独山子石化 塔里木120万吨/年二期乙烯 45万吨/年 聚丙烯",
        "owner": "中国石油独山子石化公司",
        "location": "新疆维吾尔自治区 巴音郭楞州 库尔勒市 上库高新区",
        "region": "西北",
        "process": "天然气深度加工 + 绿电 → 蒸汽裂解；PP 采用中国石油自主技术",
        "design_capacity": 45,
        "upstream": "120万吨/年乙烯 + 90万吨/年全密度PE",
        "stages": {
            "construction": {"date": "2024-05-27", "grade": "A", "single_source": False,
                             "quote": "项目建设“如火如荼”，11套主要装置推进", "date_precision": "月"},
            "commissioning": {"date": "2026-04-23", "grade": "A", "single_source": False,
                              "quote": "45万吨/年聚丙烯装置挤压造粒机组实物料试车成功"},
            "mechanical": {"date": "2026-05-21", "grade": "B", "single_source": False,
                           "quote": "工程顺利中交，主体工程全面完工，转入生产准备阶段"},
            "startup": {"date": "2026-07-16", "grade": "B", "single_source": False,
                        "quote": "工程一次开车成功"},
            "first_product": {"date": "2026-07-25", "grade": "B", "single_source": False,
                              "quote": "聚丙烯等 8 套核心装置稳定产出合格产品"},
            "rampup": {"date": "2026-09-24", "grade": "B", "single_source": False,
                       "quote": "完成首次高负荷标定，多项技术经济指标优于设计值"},
            "commercial": {"date": "2026-10-15", "grade": "B", "single_source": False,
                           "quote": "中国石油宣布工程当天全面投入商业运营"},
        },
        "first_estimate": "2026年", "actual": "2026-07-16（开车）/ 2026-07-25（合格品）",
        "delay_months": 0,
        "note": "★ 事件链最完整；但投产日距数据末端仅约3个月，60/120日窗口不完备",
    },
]


def build():
    events = []
    for p in PROJECTS:
        for stage, s in (p.get("stages") or {}).items():
            stage_use = p.get("treat_as_stage") if stage == "startup" and p.get("treat_as_stage") else stage
            events.append({
                "event_id": "%s@%s" % (p["project_id"], stage),
                "project_id": p["project_id"],
                "project_name": p["name"],
                "owner": p.get("owner"),
                "location": p.get("location"),
                "region": p.get("region"),
                "process": p.get("process"),
                "design_capacity": p.get("design_capacity"),
                "upstream": p.get("upstream"),
                "stage": stage_use,
                "stage_raw": stage,
                "date": s["date"],
                "date_precision": s.get("date_precision", "day"),
                "evidence_grade": s["grade"],
                "single_source": bool(s.get("single_source")),
                "quote": s.get("quote", ""),
                "note": s.get("note") or p.get("note") or "",
                "year": s["date"][:4],
            })
    events.sort(key=lambda e: (e["date"], e["project_id"], e["stage"]))
    payload = {
        "meta": {
            "product": "聚丙烯 (PP)",
            "market": "中国",
            "as_of": "2026-10-20",
            "capacity_base_wt": CAPACITY_BASE,
            "n_projects": len(PROJECTS),
            "n_events": len(events),
            "sources": [
                "中国PP新增产能_2023-2025_核实报告.md（2023–2025 段，原文引句+URL+证据等级）",
                "pp_research/中国聚丙烯2020-2022新增产能投产核实报告.md（2020–2022 段）",
                "PP项目进展核实_2026-10-20.md（2026 在建/新投产段）",
            ],
            "rules": [
                "只有公开来源明确写出“一次开车成功/产出合格品/打通全流程”才算正式投产",
                "“计划X月投产”“预计”“试生产运行”一律不算投产日",
                "同一项目的不同阶段（开工/中交/试车/投料/合格品/达产）是不同事件，不合并统计",
                "产能为设计产能，不等于投产当天的新增实际产量",
            ],
        },
        "projects": PROJECTS,
        "events": events,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("projects", len(PROJECTS), "events", len(events), "->", OUT)
    from collections import Counter
    print("by stage", Counter(e["stage"] for e in events))
    print("by year ", Counter(e["year"] for e in events))


if __name__ == "__main__":
    build()
