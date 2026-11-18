# 模板说明

本目录提供两份**可直接复用**的成品模板，均来自甲醇港口库存案例的真实产出。

## 1. `report_template_methanol_case.html`（约 264 KB）

单文件自包含的交互式研究报告，双击即可用浏览器打开，无需联网、无需服务器。

### 结构

10 个章节 + 附录：页首结论区（KPI 卡）→ 指标定义与发布时点 → 数据变换 → **完整 Lag 曲线** → 领先滞后矩阵 → Lag 明细查看器 → 稳定性 → 稳健性与安慰剂 → 多重检验警示 → 预测回归 → 结论 → 数据来源。

### 交互

- Lag 曲线支持 4 种视图切换（r / −log10 p / −log10 q / 样本量 n）
- 点击曲线上的点、矩阵格子、或表格行 → 明细区同步更新（对齐表、散点、滚动相关、逐年与阶段结果、判定文案）
- 6 种变换一键切换对比

### 怎么改成你的课题

1. 复制本文件，改名为你的项目报告。
2. 找到文件中的 `const DATA = {...};`，替换成你的 `build/result.json` 内容（结构照原样，字段含义见 `SKILL.md` 与 `references/05-report-spec.md`）。
3. 修改 HTML 中硬编码的章节文字（指标定义、产业解释、结论段落）。
4. 用无头浏览器跑一遍校验（脚本见 `references/05-report-spec.md` 的「质量校验」节），确认无 console error、无文字碰撞。

> 更省力的做法：直接复用案例里的 `build_html.py`，它把 `result.json` + `narrative.json` 渲染成完整 HTML。改 `narrative.json` 里的结论文字即可。

## 2. `workbook_template_methanol_case.xlsx`（约 105 KB）

13 个工作表的数据工作簿：

| 工作表 | 内容 |
|---|---|
| `00_说明` | 研究设定、结论、工作表导航 |
| `01_指标A_库存原始` | 101 期原始记录（含标题、正文摘要、原文链接） |
| `02_指标B_期货原始` | MA 主连日线（含公式计算的日涨跌） |
| `03_发布日期与可得时点` | 逐条校验统计日=发布日、发布时刻、可得性判定 |
| `04_研究样本` | 对齐样本（ΔI 与收益率为 **Excel 公式**） |
| `05_Lag+2` / `05_Lag0` / `05_Lag-2` | 三个 Lag 的逐期配对明细，表尾带 CORREL/T.DIST 公式 |
| `06_Lag扫描结果` | 25 个 Lag 的完整统计（含 FDR/Bonferroni，条件格式高亮） |
| `07_分段与逐年` | 分年度/分阶段/分半年的 r 矩阵 |
| `08_滚动相关` | 26 期滚动相关序列 |
| `09_回归与稳健性` | 变换稳健性、伪造时点、预测回归、诊断统计 |
| `10_公式与口径` | 16 条公式与出处 |

### 怎么改成你的课题

1. 复用案例的 `build_xlsx.py`（数据来自 `result.json` 与 `sample.json`）。
2. 至少修改：工作表 01/02 的原始数据源、`00_说明` 的指标名称、`10_公式与口径` 的口径描述。
3. 注意 XlsxWriter 的空单元格写法（`references/05-report-spec.md` 有踩坑说明）。

## 复用清单

| 步骤 | 动作 | 参考 |
|---|---|---|
| 1 | 拿到 A 的真实发布时间，建立双时间轴表 | `references/01-publication-time-alignment.md` |
| 2 | ADF 检验 → 决定变换；准备 6 种变换组合 | `references/02-data-transforms.md` |
| 3 | 跑 `pipeline.py` 得到完整 Lag 扫描 + FDR | `references/03-lag-scan-statistics.md` |
| 4 | 分年度/分阶段扫描 + 伪造时点安慰剂 | `references/04-stability-and-placebo.md` |
| 5 | 把 `result.json` 喂给 `build_html.py` 和 `build_xlsx.py` | `references/05-report-spec.md` |
| 6 | 按 `narrative.json` 的模板写结论（注意措辞边界） | `SKILL.md` 结论模板 |
| 7 | 对照 `references/06-pitfalls.md` 自检清单逐条打勾 | — |
