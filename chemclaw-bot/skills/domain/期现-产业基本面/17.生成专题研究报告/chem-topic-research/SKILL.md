---
name: chem-topic-research
description: 生成化工品专题研究报告（供应格局/产能扩张/需求变化/成本与价格/政策影响/竞争格局等任意主题，任意化工品）。按"界定问题→出可确认提纲→取证→分级结论"的流程，产出可点击下钻证据的交互式 HTML 报告 + 13 页 Excel 数据底稿 + 已确认提纲 + 执行记录。触发词：专题研究、专题报告、深度研究、行业研究、供应格局、产能扩张影响、新增产能、未来供需、格局变化、写一份研究报告、研究提纲。
whenToUse: 用户要针对某个化工品/材料研究一个"专题"（不是看今日行情、不是周报），需要成体系的研究结论、可追溯的数据与证据，并能按受众（管理层/销售/采购/研发/产业研究员）调整深浅。
---

# 化工品专题研究报告（chem-topic-research）

## 这个技能解决什么

把"帮我研究一下 X 对 Y 的影响"变成一份**能被追问**的报告：每个数字有来源、每个结论有分级、每个判断有反证条件、每处没查到的数据被显式标注为缺口，而不是用"行业普遍认为"糊过去。

产品无关：纯碱、尿素、甲醇、PVC、钛白粉、碳酸锂、磷化工、氟化工……主题无关：供应格局、产能扩张、需求结构、成本曲线、出口政策、竞争格局、区域迁移。**不要套用任何固定目录**——章节由"受众 + 本题的问题"决定。

## 交付物

| 交付物 | 说明 |
| --- | --- |
| 交互式 HTML 报告 | 单文件离线可用；首屏 KPI + 核心结论；点结论→证据/计算/反证；点图表→原始数据表；章节可拖动排序；可导出 Markdown 与 PDF |
| Excel 数据底稿 | 13 页：使用说明、证据索引、原始数据、企业产能、项目台账、价格、产业指标、计算结果、结论、关键变量、资料缺口、章节大纲、质量自检 |
| 已确认研究提纲 | Markdown，逐章写清"为什么存在/验证什么/依赖哪些数据"，用户确认后才进入研究 |
| 执行记录 | 研究流程、口径与冲突处理、每条判断的形成过程、未取得的数据、自检结果、下一步核验清单 |

## 工作流程（必须按顺序，不可跳步）

**第 1 步：界定问题。** 从标题拆出 4–7 个可回答的子问题，写清纳入/不纳入。若用户只给了模糊主题，先给问题树让用户选，不要直接开写。

**第 2 步：出提纲并等待确认。** 按受众选章节包（见 `references/audience-adaptation.md`），每章必须写：要回答的问题、为什么需要这一章、它验证或证伪什么、依赖哪些数据、用什么方法。生成提纲文件交给用户，**停下来等确认**。用户改章节就改，不要猜。

**第 3 步：取证。** 优先级：企业公告/官方统计（A）> 行业媒体引用第三方数据（B）> 研报转述或单一来源（C）。每条来源登记 ID、机构、标题、日期、口径。取不到就登记为资料缺口，**不允许估算后当事实写**。数据源与方法见 `references/data-sourcing.md`。

**第 4 步：项目核验（涉及产能/供给的题目必做）。** 每个项目给出三态之一：已投产 / 在建 / 规划（另有退出、暂停）。必须写状态依据与证据强度。**预计投产不等于新增供给**：要扣减搬迁置换、考虑爬坡与时间权重，公式与参数全部写进计算结果页。见 `references/capacity-verification.md`。

**第 5 步：测算与结论分级。** 每条结论标注类型：事实 / 计算 / 解释 / 判断，并给置信度；判断与解释必须有反证条件。见 `references/evidence-and-conclusions.md`。

**第 6 步：按受众改写并生成。** 同一份 case.json 可生成多受众版本。

**第 7 步：自检后交付。** 运行 `qa.py` 与 `qa_dom.mjs`，对照 `references/quality-gates.md` 逐项过关；未过的项明说，不要隐藏。

## 怎么跑（命令）

```bash
# 0) 新建空白 case（产品与主题自定）
python scripts/new_case.py --title "中国X行业新增产能对未来供应格局的影响" \
    --product X --shape 重质 --audience industry-researcher --out case.json

# 1) 只出提纲（用户确认阶段）
python scripts/build_md.py outline case.json --out 提纲_待确认.md

# 2) 校验（引用完整性、结论可追溯、缺口登记）
python scripts/common.py validate case.json

# 3) 一键产出全部交付物（可多受众）
python scripts/build_all.py case.json --audiences "产业研究员,管理层" --outdir 交付物

# 4) 自检
python scripts/qa.py 交付物/
node   scripts/qa_dom.mjs 交付物/xxx.html
python scripts/qa_xlsx.py 交付物/xxx_数据底稿.xlsx
```

单独生成：`build_html.py` / `build_xlsx.py` / `build_md.py {outline|record|report}`。

## 硬性规则（违反即不合格）

1. 每个数字都要能回答"哪来的、什么时候的、什么口径"；口径不同不许相减。
2. 结论必须分级；判断类结论没有反证条件 = 不合格。
3. 未取得的数据标为缺口并说明影响，不许用"行业普遍""据了解"替代。
4. 项目状态必须有依据；不把规划当在建、不把在建当已投产。
5. 不写与本题无关的行业百科；每章都要有"这一章为结论贡献了什么"。
6. 受众不同，深度与顺序不同：管理层给判断与决策含义，产业研究员给推导与可复算口径。
7. 引用未登记的来源 ID、或来源未被任何地方引用，都算不合格。

## 参考文档

- `references/workflow.md` — 七步流程详解与每步产出物
- `references/audience-adaptation.md` — 五类受众的框架、篇幅、措辞差异
- `references/research-design.md` — 问题树、范围界定、提纲写法
- `references/data-sourcing.md` — 数据源分层、检索路径、口径冲突处理
- `references/capacity-verification.md` — 项目三态核验与有效供给折算
- `references/evidence-and-conclusions.md` — 结论分级、置信度、反证条件
- `references/interactive-report-spec.md` — HTML 交互规范
- `references/quality-gates.md` — 验收清单（交付前逐项打勾）
- `references/data-gaps.md` — 缺口分级与表述模板
- `references/anti-patterns.md` — 反例：不合格报告长什么样
- `references/portability.md` — 跨 agent、跨环境移植说明
- `references/case-schema.md` — case.json 完整字段说明
- `examples/` — 纯碱完整案例（两受众）、提纲样例、执行记录样例

## 边界

本技能产出研究结论与决策参考，不产出投资建议、价格承诺、生产计划保证。涉及交易策略、套利头寸时应明确说明不在范围内。
