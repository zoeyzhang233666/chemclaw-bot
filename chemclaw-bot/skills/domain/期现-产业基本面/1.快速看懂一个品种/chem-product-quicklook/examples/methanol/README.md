# 甲醇案例（完整研究工作流）

这是一份**完整的真实案例**，演示本技能从 0 到交付的全过程。
它同时是回归测试基线：`scripts/` 的任何改动都应当能重新生成并 QA 通过本案例。

## 目录

```
methanol/
├── README.md               ← 本文件
├── methanol_a.py           meta / product / frame 三个基础板块
├── methanol_chain.py       产业链 5 列 21 节点
├── methanol_panels1.py     面板 01–03：产品百科 / 工艺 / 下游
├── methanol_panels2.py     面板 04–06：企业产能 / 贸易期现 / 指标逻辑
├── methanol_sources.py     17 条来源（S01–S13、S21–S24）
├── assemble_methanol.py    组装 → data/research.json
├── merge_anchors.py        把真实价格锚点合并进 research.json
├── data/
│   └── research.json       最终数据（可被 build_html / build_xlsx 直接消费）
└── raw/
    ├── MA0_daily.json      MA 主连日线 2862 个交易日（2014-12-24 → 2026-10-19）
    └── anchors_MA0.json    build_anchors.py 算出的分位与区间
```

## 复现步骤

```bash
cd examples/methanol

# 1) 重新组装数据（含口径与缺口声明）
python assemble_methanol.py

# 2) 合并价格锚点（从原始日线计算，不手写任何数字）
python merge_anchors.py

# 3) 校验事实纪律
python ../../scripts/validate.py data/research.json

# 4) 生成交付物
python ../../scripts/build_html.py data/research.json --out out/
python ../../scripts/build_xlsx.py data/research.json --out out/

# 5) 交互 QA + Excel 自检
python ../../scripts/qa_render.py "out/甲醇-品种研究入口.html" --shots out/shots
python ../../scripts/check_xlsx.py "out/甲醇-品种研究入口.xlsx" --research data/research.json
```

> `assemble_methanol.py` 与 `merge_anchors.py` 里写的是相对路径 `_build_output/`，
> 在 `examples/methanol/` 下运行会写到本目录；如需按原路径，请先改脚本内路径。
> 若只想快速出页面，直接用 `data/research.json` 跑第 4、5 步即可。

## 这份案例证明了什么

**1. 每个关键数字都有出处与日期**
例如"2025 年末总产能 1.15 亿吨/年、产量 9993 万吨"标注为
中国氮肥工业协会顾宗勤在 2026 年甲醇产业发展大会（2026-05-20/21，榆林）的工作报告，
经中国化工报/中化新网 2026-05-25 报道（S01），并由新浪财经转载版交叉核对（S02）。

**2. 口径冲突被显式处理，而不是被抹平**
- 产能：1.15 亿吨（协会名义口径）vs 10,804.5 万吨（隆众产能基数）→ 双列并注明"是否剔除长期停车装置"
- 宝丰：2000（集团含规划）/ 1400（单厂）/ 440（存量）→ 三口径并列，注明不可混用
- 下游：MTO 48.9%（2025 协会）vs 44%（2024 观研）→ 分年分机构列，标注"禁止相加"
- MTO 单耗：2.66（DMTO-Ⅲ 中试）/ 2.87（宝丰二期盘库）/ ≈3.0（一代技术）→ 给区间与代际说明

**3. 价格不是编的**
页面上的 3143 元/吨、97% 分位、2004–3553 区间、日均 102 万手成交，
全部由 `build_anchors.py` 从 2862 个交易日的原始日线算出，可用 `raw/` 复算。

**4. 拿不到的就是缺口**
8 条缺口各自写明"缺什么/为什么缺/怎么补/影响什么分析"，包括：
现货逐日序列、港口与厂库库存、郑商所规则原文（站点反爬拦截）、
分国别进口、分省产能、企业级单套产能、2025 年下游分项、MTO 利润序列。

## 已知局限

- **郑商所原文未取得**：`czce.com.cn` 反爬（HTTP 412），合约要素转自东财转录页，
  已在 S21 与页面显著位置标注"需以交易所原文复核"。最小变动价位、最低保证金、
  交割单位、交割品级均标为缺口。
- **现货价格缺失**：因此基差、区域价差无法量化，只能用方向性描述。
- **部分企业产能为二手来源**：已在 `note` 与 `confidence` 中降级。
