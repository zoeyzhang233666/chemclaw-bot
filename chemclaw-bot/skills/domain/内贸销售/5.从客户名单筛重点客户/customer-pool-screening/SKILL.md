---
name: customer-pool-screening
description: Use when a domestic (China) chemical/materials sales rep uploads a company or customer list (Excel/CSV) and wants it screened into a verified, ranked target-customer pool — standardize company names, match business-registry entities (统一社会信用代码/经营状态), classify into 成功匹配/名称歧义/暂未找到 for user confirmation BEFORE demand matching, judge 生产企业 vs 贸易商, grade product-demand relation (强/弱/不相关), score & rank with a transparent rubric, exclude peers/irrelevant/dead entities, dedup against the existing customer pool. Product-agnostic (any chemical or material). Delivers an Excel workbook + a self-contained interactive HTML. Triggers: 客户名单筛选, 客户池, 筛重点客户, 内贸销售, 工商主体核验, 客户分级排序, 排重, screen customer list, prioritize customers.
---

把一份粗糙的客户名单，变成一张**主体已核实、需求已分级、能直接打电话**的优先级客户池。
产品无关：任何化工品/材料都适用——需求逻辑不是写死的，而是在运行时按当次产品现场构建。
交付固定为 **Excel（6 表）+ 自包含交互 HTML（可筛选/排序/勾选/导出）**，由 `scripts/build_deliverables.py` 从同一份 `pool.json` 生成。

本 skill 只假设四种能力：读写文件、联网检索/抓取、能向用户提问、（可选）子代理并发。
不依赖特定 agent 框架或专有工具，可在任何具备上述能力的环境运行（DeepSeek Harness / Codex / 其他 CLI 或网页 agent）。
运行环境需要 Python 3.8+ 与 openpyxl（`pip install openpyxl`）。

## 四条不可谈判的约束

1. **确认门：先主体，后需求。** 必须先产出「成功匹配 / 名称歧义 / 暂未找到」三类结果并让**用户确认歧义主体**，之后才能做产品匹配与排序。跳过确认门，整份结果作废。
2. **没有 trace 的字段写「未核实」。** 统一社会信用代码、经营状态等多来源冲突或查不到时如实标注；宁可留白，不可编造一个像样的 18 位代码。
3. **peer 不是客户。** 自产该产品的企业（同行、配套自供）进排除清单，不进客户池。每条 lane 收口前跑一次 peer gate（见 `references/scoring-and-gates.md`）。
4. **排除必须留痕。** 需求不相关、同行自产、主体消亡、排重命中——每一条排除都要写明**类别 + 依据 + 证据**，不许静默丢弃。

## 输入契约

开工前**一次性问全**（有提问工具就用，没有就列清单等用户回复）：

1. 产品：是什么、主要给谁用（如"纯碱，卖给玻璃/洗涤/氧化铝厂"）
2. 重点区域（具体到省/区域带，不接受"全球"）
3. 偏好：真实工厂 / 贸易商 / 大客户 / 中小客户 / 指定下游行业（默认：真实工厂优先）
4. 名单文件路径（Excel/CSV，至少含"企业名称"列；可有地区线索、来源备注列）
5. 现有客户池（文件或口述，含等级/成交状态；用于排重。默认：无）

缺 1、2、4 无法开工；3、5 可默认。

## Steps

### 1. 读名单，建批次
读入名单，逐行取「企业名称 + 地区线索 + 备注」。对名称做轻度标准化（去空格/全半角/括号后缀），但**不臆改原文**——标准化结论属于核验产出。按行业语感分批，每批 ≤6 家（玻璃类一批、日化类一批……），批间无依赖。

### 2. 主体核验（fan-out）
每批一个子代理（无子代理能力则顺序处理）。brief 必含六件套：①任务边界（只核主体，不判需求）②本批企业清单 ③证据通道与 URL 模板（`references/evidence-channels.md`）④固定 JSON 字段 ⑤落盘路径 `leads_raw/NN_批次.json` ⑥抓取纪律（每家 ≤6 页，宁缺毋假）。

每家产出字段（完整定义见 `references/data-schema.md`）：
`原始名称 / 标准化企业名称 / 统一社会信用代码 / 经营状态 / 省市 / 类型(生产企业|贸易商|不确定) / 实际主营产品 / 规模信号 / 证据来源 / 置信度 / 备选主体 / 备注`

### 3. 三类分箱 + 用户确认（确认门）
- **成功匹配**：唯一对应存续主体；备注里预标"疑似与现有池命中"
- **名称歧义**：列出 2-3 个候选主体 + 辨识要点，交给用户选
- **暂未找到**：如实报告检索无果；能给相近名/历史沿革线索就附上，**禁止默认替换**

用一次批量提问收齐所有歧义项的确认（每个问题给出推荐项与理由）。确认结果写入最终交付的「名称歧义-确认记录」表。

### 4. 构建当次产品的需求地图（产品无关的核心步骤）
基于产品用途列一张**用料逻辑表**：`下游行业 | 使用工序 | 起什么作用 | 吨耗强度(5星制) | 判定要点`。
用行业常识起草 + 快速检索验证吨耗口径；同时列出**同行清单**（谁也在产这个产品）。
模板与 3 个已填示例（纯碱/烧碱/柠檬酸）见 `references/scoring-and-gates.md`。这张表决定第 5 步所有判断，必须先于匹配完成。

### 5. 需求匹配与一票否决
对每家成功匹配的企业判定：**强 / 弱（间接需求或渠道价值）/ 不相关**，写一句需求逻辑（在哪个工序、为什么买、大致量级）。
**一票否决 → 排除清单**：需求不相关、同行自产（peer gate）、主体消亡（用户已确认的沿革死项）、排重命中。

### 6. 四维评分排序
综合分 = 产品匹配(0-40) + 工厂真实性(0-25) + 规模(0-20) + 地区(0-15)，权重可按产品在 `meta.scoring` 里调整。
分级：P0 ≥80 重点开发；60-79 P1 机会开发；40-59 P2 渠道/观察；<40 或触发一票否决 → 排除。
打分锚点与示例见 `references/scoring-and-gates.md`。排序依据必须能被销售复述，不许黑盒。

### 7. 排重
用「标准化企业名称」与现有客户池做精确 + 归一化匹配（去"股份/集团/有限"等后缀再比对）。命中项标注客户等级与合作状态，转入排除清单（类别=排重），并保留其核验信息以更新老客户档案（如 *ST 风险提示）。

### 8. 生成 pool.json → 一键出双交付物
把全部分析结果按 `references/data-schema.md` 的契约写成 `pool.json`（六个部分：meta / pool / ambiguity / not_found / excluded / existing_pool），然后：

```bash
python scripts/build_deliverables.py --input pool.json --outdir out --basename {产品}_{区域}_客户池
```

产出 `{basename}.xlsx`（说明与方法 / 重点客户池(排序后·带筛选) / 名称歧义-确认记录 / 未找到 / 排除企业及原因 / 现有客户池(输入)）和 `{basename}.html`（自包含：搜索、下拉筛选、点表头排序、勾选批量导出 CSV）。脚本会校验必填字段，报错先修数据再重跑。用工作簿检查工具或重新打开验证后再交付。

### 9. 交付报告（四块缺一不可）
1. **条数与分布**：输入 N 条 → 三类各几条 → 池内几条（P0/P1/P2）、排除几条；地区/类型分布
2. **置信度分级**：高置信靠什么证据（公告原文/双源 USCC），哪些字段"未核实"
3. **被剔除名单**：每家的类别与一句话依据（同行 / 不相关 / 主体消亡 / 排重）
4. **缺口与负结果**：哪些名称检索无果、哪些只能电话核实、哪些字段建议官方终核

## 迁移到其他电脑 / 其他 agent

- 本目录自包含，整目录拷走即可（或用打包的 zip）。
- **Claude 式 agent（skills 目录）**：拷到其 skills 根目录（如 `~/.agents/skills/customer-pool-screening/`），SKILL.md 的 YAML frontmatter 负责 name/description 注册。
- **Codex / CLI agent**：无需注册，把任务描述写为"按 `customer-pool-screening/SKILL.md` 的流程处理我上传的名单"，让 agent 先读 SKILL.md。
- **网页 agent**：把 SKILL.md 全文贴进系统提示/项目指令，同样生效。
- 唯一环境要求：Python 3.8+、openpyxl；无子代理能力的环境在第 2 步顺序处理即可。

## 失败模式速查

- 子代理返回"查不到"→ 别原样重发 brief；改枚举式 brief（把候选名称+股票代码写死、限抓取次数）重开一次。
- 名称歧义用户不选 → 该条进"未找到"，不许替用户做主。
- USCC 多来源冲突 → 标"未核实"并降置信度，绝不动手"合成"一个。
- 巨潮/交易所被反爬 → 换 F10 通道或百科兜底，每级只试一次，不要反复重试同一通道。
