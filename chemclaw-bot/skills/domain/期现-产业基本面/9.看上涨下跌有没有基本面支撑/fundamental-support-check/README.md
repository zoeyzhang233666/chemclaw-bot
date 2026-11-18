# fundamental-support-check

**期现与产业基本面核验：涨跌有没有基本面支撑**

给定「品种 + 时间窗口」，判断一轮价格上涨/下跌**有没有可验证的现实基本面支撑**，
并明确区分 **现实供应变化 / 现实需求变化 / 成本变化 / 主要体现预期的指标**。

- 适用：任何化工品，**有期货或没有期货**（PP、PE、PVC、甲醇、纯碱、烧碱、尿素、苯乙烯、PTA、乙二醇、丙烯、钛白粉、有机硅、碳酸锂…）
- 产出：交互式 HTML 报告 + Excel 工作簿（每项指标带日期/口径/来源，缺失项显式标注，不估算填充）
- 边界：**不给多空方向**，**不把期货上涨当作基本面改善的证据**

## 快速开始

```
1. 读 SKILL.md            → 六步流程 + 三条铁律
2. 读 references/         → 按需：窗口/基差/区块/分类/无期货/指标规则/复核清单
3. 参照 examples/pp-2026q4 → 完整可复现案例（39 条证据、20 个来源）
4. 用 templates/ + scripts/ → 生成自己的报告
```

## 目录

```
SKILL.md
references/
 01-window-and-price.md          窗口锚定与价格测量（禁止预设涨幅）
 02-basis-and-term-structure.md  基差、月差、无期货替代结构
 03-evidence-blocks.md           六区块字段规范与采集要点
 04-evidence-classification.md   证据分级 + 四轴归类 + 状态机伪代码
 05-no-futures-playbook.md       无期货品种完整适配路径
 06-metric-rules.md              指标计算规则 R01–R14 + 复合指标 M01–M05
 07-qa-checklist.md              交付前复核清单（A–G）
examples/pp-2026q4/
 README.md                       完整案例：PP 2026国庆后上涨（含 5 个教学点）
 README-no-futures.md            同一案例的"假设无期货"适配演示
 evidence-table.md               39 条证据全表 + 汇总
 sources.csv                     20 个来源
 PP-基本面支撑核验报告.html        交互式报告成品（可直接打开）
 PP-基本面支撑核验工作簿.xlsx      Excel 成品（11 表）
 dataset_data.py                 数据集模块（原始数据）
 dataset_pp_2026q4.py            组装 + 一键复现脚本
templates/
 01-evidence-board.csv           证据台账模板（含 6 行示例）
 02-window-table.csv             窗口涨幅测算模板
 03-report-outline.md            报告大纲模板（带占位符）
scripts/
 build_report.py                 数据集校验 + 指标计算 + 渲染入口
 xlsx_renderer.py                11 表 Excel 生成器
 report_template.html            自包含 HTML 模板（内联 SVG，无外部依赖）
```

## 复现示例

```bash
python examples/pp-2026q4/dataset_pp_2026q4.py out
# → out/PP-基本面支撑核验.html
# → out/PP-基本面支撑核验.xlsx
```

## 案例结论（不含方向建议）

> PP 现货在 2026-10-01 → 10-19 **真实上涨 +8.29%**（已核验原始参考价，非虚构）。
> 同期现实供需**未同步改善**：库存 +45.77%、塑编/BOPP/注塑开工 40.18%/24.37%/30.66%。
> 核心判别：PP 涨 8.29% 而丙烯涨 8.52%，**加工价差 225.66 → 222.34 几乎不动**（β=0.973）
> → **成本传导型**，而非现实供需缺口。
> 叠加同板块多品种涨停与地缘事件 → **成本传导 + 预期定价混合**。
> 证据配比：**7 支持 ｜ 18 背离 ｜ 7 数据不足 ｜ 7 中性/预期**。

## 与同类技能的区别

| 技能 | 回答的问题 |
|---|---|
| `chem-market-brief` | 现在什么价、涨跌幅、历史分位、成本传导 |
| **fundamental-support-check** | **这轮涨/跌，有没有现实基本面在支撑**（归因核验，不换方向结论） |
| `chem-procure-brief` | 采购视角：现在该不该下单 |

本技能的独特点是**证据纪律**：期货价格不能自证、单指标不能定性、缺失必须显式标注。
