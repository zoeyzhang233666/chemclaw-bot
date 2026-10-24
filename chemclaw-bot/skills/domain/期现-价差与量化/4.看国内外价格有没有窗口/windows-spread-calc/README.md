# windows-spread-calc · 看国内外价格有没有窗口

把海外报价（FOB / CFR / CIF，任意港口）折算成中国境内**四层可比成本**，
与国内现货价按**四个口径**对比，并给出历史价差曲线、驱动分解、敏感性矩阵与缺口清单。

产出两份可直接发给业务方的文件：

| 文件 | 形态 | 特点 |
|---|---|---|
| `output/report.html` | 单文件交互报告 | 1.1 MB，完全离线，改汇率/运费/关税/保险/术语后全页实时重算 |
| `output/model.xlsx` | 11 表 Excel | 全活公式（非静态数值），蓝格是唯一可改区，含折线图 |

两份文件从同一个 `build/data.json` 生成，因此数字永远一致（并由 `check_consistency.py` 验证）。

---

## 它解决的四个陷阱

| 陷阱 | 本 Skill 的做法 |
|---|---|
| 口径不齐（CFR 美元价直接减含税现货） | 先折四层成本再按 G1~G4 分别相减 |
| 重复计费（CFR 报价又加运费） | 按 Incoterms 自动屏蔽已含费用并报警 |
| 伪造历史（用今天的运费算去年） | 每个历史点标 实测/月度均值/假设/gap，禁止插值 |
| 把价差当利润 | 全文不出现交易指令，价差只描述口径差异 |

---

## 三分钟上手

```bash
# 1. 放置图表库（仅一次）
#    从 chem-market-brief 复制，或自行下载 echarts 5.x
copy %USERPROFILE%\.agents\skills\chem-market-brief\scripts\assets\echarts.min.js scripts\assets\

# 2. 复制模板并填写
copy research.template.json examples\02-my-product\research.json
#    填：海外报价、国内价、汇率运费税率、历史观测点、来源、缺口

# 3. 一键构建（含 30 项内核自检 + 契约校验 + 包检查）
python scripts\build_all.py examples\02-my-product
```

打开 `examples\02-my-product\output\report.html` 即可。

---

## 目录结构

```
windows-spread-calc/
├── SKILL.md                    Skill 说明（给 Agent 读）
├── README.md                   本文件（给人读）
├── research.template.json      空白母本，复制后填
├── scripts/
│   ├── core.py                 计算内核（唯一公式源）
│   ├── assets/
│   │   ├── core.js             浏览器镜像（与 core.py 逐值一致）
│   │   └── echarts.min.js      离线图表库（需自备）
│   ├── templates/report.html   HTML 模板（含 __DATA__ 占位）
│   ├── wio.py                  IO / 格式化 / 禁用词
│   ├── validate.py             数据契约校验
│   ├── assemble.py             research.json → data.json
│   ├── build_html.py           data.json + 模板 → 自包含 HTML
│   ├── build_xlsx.py           data.json → 11 表活公式 Excel
│   ├── build_all.py            一键流水线
│   ├── selftest.py             内核自检（30 项）
│   ├── check_consistency.py    Python ≡ JS 比对（需 node）
│   ├── check_package.py        交付物完整性
│   └── fetch_data.py           抓期货/汇率/中间价
├── references/                 7 篇方法论文档
└── examples/
    └── 01-meg-cfr-china-huadong/
        ├── research.json       完整案例母本（乙二醇）
        ├── raw/                原始抓取数据（可追溯）
        ├── build/data.json     中间事实源
        └── output/             report.html + model.xlsx
```

---

## 计算内核速查

```
CIF          = 货值 + 出口内陆 + 出口报关 + 运费 + 保险
保险         = (货值 + 出口端 + 运费) × 加成率 × 费率      ← 术语未含保险时才计
关税         = (CIF + 卸货) × 关税率
增值税       = (CIF + 卸货 + 关税) × 增值税率
landed_cash  = CIF + 卸货 + 关税 + 其他税 + 增值税 + 进口内陆 + 损耗
vat_credit   = 增值税 × 可抵扣比例
net_cash     = landed_cash − vat_credit                      ← 可比经济成本
```

四个价差：

| 代码 | 口径 | 公式 | 回答 |
|---|---|---|---|
| G1 | 纯价格 | 国内未税 − CIF | 国际与国内价格本身谁高 |
| G2 | 现金 | 国内含税 − landed_cash | 全部现金付出谁高 |
| G3 | 经济 | 国内含税 − net_cash | **抵扣完增值税后谁高** |
| G4 | 税制 | 国内未税 − net_cash | 抵扣权估值差异 |

正 = 国内更强；负 = 进口更便宜。**任一列都不是利润**。

---

## 验证状态

| 检查 | 结果 |
|---|---|
| `selftest.py` 内核恒等式与边界 | 30/30 通过 |
| `check_consistency.py` Python ≡ JS | 200 组随机参数 × 33 字段，容差 1e-6，全部一致 |
| `validate.py` 案例数据契约 | 0 错误 |
| Excel 公式图复算 vs 内核 | 成本 6 项 + 价差 4 项全部一致（最大偏差 9e-13） |
| HTML 无头渲染 | 4 张图、KPI、瀑布、27 行明细、矩阵、缺口、公式全部产出 |
| `check_package.py` | 见运行结果 |

---

## 已知限制

1. **目的港卸货费没有内置数据源**。示例案例按 0 计入并列入高严重度缺口；
   真实业务请向码头/货代取报价后填入。
2. **最惠国税率不等于实际执行税率**。示例案例默认 0%，并在缺口第 1 条量化了 5.5% 的影响。
3. **海外报价多为二手引用**。中文媒体的「中国到岸价」按 CIF 处理，原文未拆分 CFR 与保险。
4. **Excel 无缓存值**。用 openpyxl 生成，打开时由 Excel 计算；部分在线预览器不重算，
   请用 Excel / WPS / LibreOffice 打开。
5. **不处理 DDP 一口价**。若报价含中国关税与增值税，需把税率设为 0 并在缺口说明。

---

## 适用边界

**适合**：任一化工品/材料的进口成本折算与内外价差比较、历史窗口复盘、参数敏感性分析。

**不适合**：交易决策、价格预测、供应链优化、多品种组合、汇率对冲方案。

本 Skill 输出的每一个价差都只是「两个口径的价格之差」。它不含资金成本、通关时效、
品质折价、数量折扣、信用风险与汇率对冲成本——这些若需纳入，应作为显式参数或独立缺口列出。
