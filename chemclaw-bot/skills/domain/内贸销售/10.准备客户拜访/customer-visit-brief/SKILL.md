---
name: customer-visit-brief
description: Use when a B2B chemical sales rep is about to visit a customer and needs a 5-minute pre-visit background brief — research what the customer actually makes (plants, capacity, value-chain position), why our product fits (use-point, specs, selling points), its major events of the last 6–12 months (startups, cold repairs, tenders, results), market prices of our product and its key raw materials with dated sources, confirmed/unresolved items from past communications (only from provided records — never fabricated), and 5–8 questions per audience (purchasing / technical / boss). Triggers 准备客户拜访 / 拜访背景卡 / 拜访准备 / 首次接触 / 技术对接 / 送样 / 报价 / 客户拜访 / visit brief / pre-visit research / sales visit prep. Product-agnostic across chemicals (纯碱、烧碱、钛白粉、树脂、助剂、中间体……). Always delivers an Excel workbook (8 sheets, fillable on-site) plus a self-contained HTML one-pager (3 audience tabs, print-to-PDF ready); every fact carries a dated, clickable source.
---

# 准备客户拜访 · 一页式拜访背景卡（化工品通用版）

在任何一次 B2B 化工品客户拜访前，生成一张**5分钟能看完、现场能用、事后可归档**的拜访背景卡。
整个 skill 围绕三个词：**sourced（每个事实带日期+可点开的来源）**、**honest（无记录就留空，绝不替客户编需求）**、**actionable（问题清单直接可在现场打勾）**。

产品可以是任何化工品（纯碱、烧碱、钛白粉、柠檬酸、DMC、环氧树脂、水处理剂……）。
研究思路与结果结构固定，**只有配置是产品的**：产品名、规格级别、用点与单耗、行情品种、客户行业术语。

## 0. 适用与不适用

- 适用：内贸/外贸 B2B 化工原料销售的拜访准备（首次接触 / 技术对接 / 送样 / 报价 / 高层拜访）。
- 不适用：终端消费者调研、没有明确目标企业的泛客户开发（找客户请用 lead-sourcing 类 skill）。

## 1. 五件输入（缺一不可，历史记录可选）

| 输入 | 说明 | 示例 |
|---|---|---|
| 企业名称 | 一家真实目标客户 | 福莱特玻璃集团股份有限公司 |
| 拜访对象 | 角色（采购/技术/老板）与姓名（若有） | 基地采购经理 |
| 本次目标 | 首次接触 / 技术对接 / 送样 / 报价 / 高层汇报 | 首次接触→进名录+小样试单 |
| 我方产品 | 化工品名 + 规格/级别 | 纯碱（重质碱为主，国标优等品） |
| 历史沟通记录（可选） | 微信/邮件/纪要/报价单 | 无 → 第⑤节留空并明示 |

用户没给全就一次性问全（带推荐项）；**企业名称缺失时必须询问，绝不允许 agent 自己挑一家演示**，除非用户明确说"找XX的例子"。

## 2. 六步工作流

```bash
# ① 落盘契约：先把五件输入写成 visit_data.json（唯一事实来源，随研究增量填充）
cp templates/visit_data.template.json work/<项目>/visit_data.json

# ② 取证研究：四个研究面（见 references/research-playbook.md）
#    A 客户是什么  B 为什么适配  C 近6-12个月大事  D 行情
#    每条事实 = 内容 + 日期 + 来源URL；先查用户上传记录，再查公开信息

# ③ 内容组装：按六节结构填 visit_data.json（推断/公开/用户提供 三级标注）

# ④ 出 Excel：8 个工作表，现场可填写
python scripts/build_visit_workbook.py --data work/<项目>/visit_data.json \
       --out work/<项目>/拜访背景卡_<客户>_<产品>_<日期>.xlsx

# ⑤ 出 HTML：以 examples/soda-ash-flat-glass/*.html 为母版改造
#    （保留设计体系与三版本标签页，替换内容；无浏览器环境时按 output-spec.md 直接手写）

# ⑥ 交付前体检（见 references/workflow.md 检查单）
#    - 每个价格有日期+来源？每个链接能点开且主体一致？
#    - 无上传记录时第⑤节是空态？推断项标了"待验证"？
#    - 三个版本各 5–8 问？Excel 能打开、下拉与冻结窗格在？
```

每步的完成判据、降级方案见 [`references/workflow.md`](references/workflow.md)；数据字段定义见 [`references/data-contract.md`](references/data-contract.md)；HTML/Excel 逐节规范见 [`references/output-spec.md`](references/output-spec.md)。

## 3. 结果结构（固定六节，正文一页 5 分钟）

1. **客户实际做什么**：主营、行业地位、生产基地、公开产能、产业链位置、规模。
2. **我们为什么适合它**：用点与单耗（标"经验值"）、可讲卖点、切入时机；风险与机会。
3. **近 6–12 个月重要事情**：点火/冷修/投产/中标/业绩/评级/行业事件 → 每条写"对本次拜访的意义"。
4. **相关行情**：我方产品及主要原料价格 + 客户产品景气，**全部注明日期与来源**，末尾给"谈判含义"。
5. **历史沟通中已确认 / 未解决**：**仅依据用户上传的记录**；无记录 → 空态明示，并给"首访基线采集清单"。
6. **本次最值得问清的 5–8 个问题**：按拜访对象分 采购版/技术版/老板版，每问附"为什么问"。

三版本共用同一底稿，只换②⑥与开场目标——对应 HTML 的三个标签页。

## 4. 四条不可谈判的纪律

1. **不许编造客户说过的话**：第⑤节只来自用户上传记录；没有就空态明示。编一条客户需求，整张卡就废了。
2. **每个价格必带日期+来源**：行情写"低位"必须有价格数与日期；链接 302 到无关主体的一律弃用。
3. **三级标注**：公开信息（带来源）/ 推断（标"推断·待验证"）/ 用户提供（标"客户确认"）。现场追问推断项，而不是当事实讲。
4. **先落盘、再汇报**：visit_data.json 与交付物先写文件，回复只给摘要；上下文是易耗品。

## 5. 环境适配

- 宿主有联网搜索/抓取 → 取证主力；`research-playbook.md` 给了逐节的检索模板。
- 出 Excel 依赖 `openpyxl`（`pip install -r requirements.txt`）；缺依赖或无 Python → 按 `output-spec.md` 的 8 表规范手工建表，或降级为 CSV 集 + 在回复中说明。
- HTML 无任何依赖（内联 CSS/JS、零外链、离线可开、打印成 PDF 即分发版）。
- 各 agent（chemclaw / workbuddy / Codex / Claude Code）的安装与能力映射见 [`README.md`](README.md) 与 [`references/porting-to-other-agents.md`](references/porting-to-other-agents.md)。

## 6. 样例

[`examples/soda-ash-flat-glass/`](examples/soda-ash-flat-glass/README.md) 是一个完整跑通的案例：纯碱销售首访福莱特玻璃集团。
包含契约实例 `visit_data.json`、成品 HTML、成品 Excel、一页 MD 卡，以及 README 讲解该样例示范的五个要点。
新项目开工前，先跑通一遍样例的步骤④验证环境。
