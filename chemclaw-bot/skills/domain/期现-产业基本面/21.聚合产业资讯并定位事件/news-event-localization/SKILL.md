---
name: news-event-localization
description: Use when a futures/spot or industrial research user needs recent industry news for a chemical product, value chain, or company cluster aggregated and turned into located events — 聚合产业资讯 / 最近7天行业新闻 / 某产品产业链资讯 / 装置检修停车复产新闻 / 政策公告汇总 / 这条新闻到底说了什么事 / 哪些新闻是同一件事的重复报道. Delivers a self-contained interactive HTML (news feed + deduplicated event board + event drawer linking sources, companies, plants, capacity and value-chain position) plus a 15-sheet Excel workbook that records sources, raw news, unique event IDs, dedupe relations, company/plant matches, fact-confirmation status, chain nodes and a to-verify list. HARD RULES: never convert news aggregation into a plain news digest; never draw price-direction conclusions from news; never treat a search-result title as verified fact; always disclose paywalled or inaccessible sources instead of implying absence; never fabricate news content or events.
---

# 聚合产业资讯并定位事件（News Event Localization）

把一个时间窗口内的公开产业资讯，收敛成**可核验、可定位、可下钻的产业事件**。

核心不是"读新闻"，而是三件事：

1. **判重** —— 多条报道 = 一个事件，但来源与版本全部保留；
2. **定位** —— 事件要挂到产业链节点 · 企业 · 装置 · 产能上；
3. **分级** —— 已确认事实 / 有数据支持的客观描述 / 尚未确认的信息，三类严格分开。

---

## 何时使用

触发场景（任一）：

- "给我 XX 产品/产业链/企业群最近 7 天（或 24h / 30d）的产业资讯"
- "这些新闻里哪些是同一件事？"
- "这条装置停车新闻影响多大 / 涉及哪家企业哪套装置？"
- "最近有没有影响 XX 的政策、公告、检修、投产？"
- 用户上传链接 / 截图 / 文本，要求"帮我看看这些资讯能不能对上"
- 需要一份"事件看板"而不只是一份"新闻摘要"

**不适用**：只要价格行情 → 用 `chem-market-brief`；只要找客户 → 用 `b2b-lead-sourcing` / `project-lead-sourcing`。

---

## 六条硬约束（违反即失败）

| # | 约束 | 具体含义 |
|---|---|---|
| 1 | 不是新闻摘要 | 必须输出"事件"而非"条目罗列"。一个事件一个编号，多篇报道合并，来源与版本保留。 |
| 2 | 不给价格结论 | 禁止从新闻推导涨跌、目标价、"利多/利空"结论。价格数字只能作为**事件背景**并标注来源与日期。 |
| 3 | 标题 ≠ 事实 | 只取得标题的条目（付费墙/反爬），其内容按标题解析，**不推断正文**，并在内容深度栏标"仅标题"。 |
| 4 | 不可访问必须披露 | 付费墙、需登录、反爬拦截要写进"访问限制日志"。**不得用"未发现"替代"未能访问"。** |
| 5 | 不编造 | 不得编造资讯内容、事件、企业、装置、产能、日期。取不到就留空写"未取得"。 |
| 6 | 冲突不取舍 | 两个来源对同一事实说法不同时，**并置保留**（relation=conflict），不做"A 对 B 错"的判断。 |

---

## 工作流（九步）

详细做法见 `references/method.md`，此处为骨架。

### 步骤 1 · 选窗口（先验证再开干）

窗口不能凭感觉定。**先确认三件事**，否则整个工作会建立在标题上：

1. 窗口内有没有**可读的官方原文**？（政府/交易所/企业公告全文）
2. 窗口内的关键装置事件能否被 **≥2 家独立机构**记录？
3. 核心报道**正文能不能读到**？

> 实战教训：本技能的第一个案例原本想用 10-06~10-12，结果该窗口核心事件（渤化/联泓停车）正文全被会员墙拦住，只剩标题级证据，最终改为 10-13~10-19——那里既有生态环境部原文，又有金联创可读正文。

### 步骤 2 · 立源（先分层，再取数）

按 `references/sources-playbook.md` 建立信息源分层：

- **T0 官方原文**：政府公示、交易所公告、企业公告/互动问答
- **T1 一手行业资讯**：隆众、金联创、卓创、Mysteel、SMM
- **T2 转载与媒体**：新浪财经、东方财富、行业门户、自媒体

每个源都要记录：`可访问性`、`访问限制说明`、`可靠性评级`。

### 步骤 3 · 采集（记录六要素）

每条资讯记录：**标题、原始来源、首发时间、转载时间、正文要点、相关链接**。

时间规则（最容易出错的地方）：

- `first_pub` 取**发布方原生时戳**，不是采集时间；
- 转载页面的时间 = **转载时间**，不等于首发；
- 页面 meta 里的 `publishTime` 如果是采集工具写入的，**绝对不能当发布时间**；
- URL 内嵌日期（如 `26-1019-15-xxxx.html`）可作为日期佐证，但要标注为"URL 内嵌"。

### 步骤 4 · 判重（六种关系）

| 关系 | 判定 |
|---|---|
| `primary` | 首发报道（主记录） |
| `republish` | 同一稿件被转载，内容一致 → **不增加确认度** |
| `followup` | 同一事件的后续更新（同装置不同日期快讯、新增进展） |
| `index_entry` | 索引/列表/数据表形态，非独立报道 |
| `selfmedia` | 自媒体/社区转述 → **降级为旁证** |
| `conflict` | 关键事实不一致 → **并置保留** |

每条合并都要写**判定依据**（可审计）。算法见 `scripts/dedupe.py`。

### 步骤 5 · 立事件（一事件一动作）

事件编号：`EVT-<品种代码>-<YYYYMMDD>-<序号>`

**事件只描述一个动作，不描述一个话题。** "烯烃集中停车"是话题；"南京诚志 10-18 停车"是事件。

易错点：同一集团不同基地是**不同装置**（宁波富德 vs 富德常州）；同类动作但实体不同（多家企业复产）若被资讯机构作为**一个整体**发布，可合并为一个事件并在 plants 内保留逐厂信息。

### 步骤 6 · 提实体（企业→装置→产能→区域）

事件类型八选一：`项目投产` `装置检修` `停车复产` `产能扩建` `贸易政策` `环保安全` `下游需求` `其他产业事件`

**产能必须有来源，无来源留空**，绝不填估计值。区分"存量状态"与"窗口内新发生"——汇总表上的"停车"可能已经停了两年。

### 步骤 7 · 定确认度（C1–C4）

| 级别 | 标准 |
|---|---|
| **C1** | 官方原文可读（政府/交易所/企业公告） |
| **C2** | ≥2 家**独立**机构口径一致且正文可读 |
| **C3** | 单一来源，或仅标题级证据 |
| **C4** | 待核实，或来源之间存在冲突 |

铁律：**同源转载不增加确认度**（新浪 + 东方财富转同一篇金联创 = 一家）。企业端无公告时，资讯机构口径最高只到 **C2**。

### 步骤 8 · 挂节点 + 分三层 + 定量级

- **挂节点**：事件挂到产业链节点（上游原料/生产/流通进口/下游需求/衍生路线），才能回答"这条新闻在产业链哪一段"。
- **分三层**：`confirmed_facts` / `data_supported` / `unconfirmed`，不得混写。
- **定量级**：只有可靠产能数据才给客观规模描述，并注明口径与期间。

### 步骤 9 · 列待验证（行动清单，不是免责声明）

每条必须写清：**为什么重要 → 需要什么证据 → 去哪里取 → 当前卡点**。
"去巨潮按 000990 检索公告"是可执行项；"继续关注"不是。

---

## 交付物

| 文件 | 内容 |
|---|---|
| `news-event-dashboard.html` | 单文件交互看板：资讯流 + 事件看板 + 多维筛选 + 事件抽屉（来源/企业/装置/产能/产业链定位图）+ 跟踪清单 |
| `news-events.xlsx` | 15 表工作簿，见下 |

### Excel 15 表

`00_案例概览` · `01_信息源` · `02_原始资讯` · `03_事件唯一编号` · `04_去重关系` · `05_未归入事件台账` · `06_企业装置匹配` · `07_事实确认状态` · `08_产业链节点` · `09_产业链连接` · `10_跟踪指标` · `11_待验证事项` · `12_访问限制日志` · `13_方法论与禁止事项` · `14_采集与核验日志`

要点：`05_未归入事件台账` 记录**为什么某条资讯不构成事件**（不能悄悄丢掉）；`12_访问限制日志` 记录所有受阻的来源；`14` 记录失败与排除项（被拒用的内容也留痕）。

---

## 快速开始

```bash
PY=python3   # 需要 openpyxl

# 1) 用模板初始化一个案例
python scripts/new_case.py --product 甲醇 --start 2026-10-13 --end 2026-10-19 \
    --scope "中国甲醇产业链" --out ./cases/methanol

# 2) 边采集边填 src/*.json（先 sources，再 news，再 events，最后 dedupe）
#    填完立刻校验，不要等画图
python scripts/validate.py ./cases/methanol/src

# 3) 判重辅助（给出疑似同一事件的候选对，人工确认后写入 dedupe.json）
python scripts/dedupe.py ./cases/methanol/src/news.json

# 4) 引文可追溯性审计：每个引号片段都必须能在保存的原文里找到
python scripts/audit_quotes.py ./cases/methanol/src ./cases/methanol/raw

# 5) 出成品
python scripts/build_xlsx.py ./cases/methanol
python scripts/build_html.py ./cases/methanol
python scripts/check_outputs.py ./cases/methanol
```

---

## 数据模型（七文件）

```
src/
  sources.json   # 信息源分层 + 访问限制 + limitations
  news.json      # 原始资讯条目（六要素 + content_level）
  events.json    # 事件（唯一编号 + 三层事实 + 产能规模 + 确认度）
  entities.json  # 企业档案 + 装置台账
  chain.json     # 产业链节点 + 连接 + 跟踪指标
  dedupe.json    # 去重关系 + 未归入事件的资讯
  toverify.json  # 待验证事项
```

字段定义见 `references/data-model.md`，模板见 `templates/`。

**关键字段 `content_level`**：`full`（全文）/ `partial`（摘要或被截断）/ `summary_only`（仅搜索摘要）/ `title_only`（仅标题）。这个字段决定了该条目能支持多强的结论——`title_only` 只能证明"隆众在某时发布了这条快讯"，不能证明快讯内容。

---

## 质量门（出稿前逐项过）

- [ ] 每个事件有唯一编号，且 `dedupe.primary_news` 非空
- [ ] 每条资讯要么挂到事件，要么进 `05_未归入事件台账` 并写明理由
- [ ] 每处合并都有判定依据；`republish` 未被计入确认度
- [ ] 冲突项以 `conflict` 并置保留，没有"仲裁"
- [ ] 所有产能数字带来源；无来源的留空
- [ ] 每个事件的 `verify_basis` 说明了为什么是这个级别
- [ ] 引文审计 100% 可追溯到保存的原文（`audit_quotes.py` 零 untraced）
- [ ] 访问限制已逐条披露
- [ ] 全文检索无价格涨跌结论
- [ ] HTML 离线可开，交互无 JS 错误

前 9 项 `scripts/validate.py` + `audit_quotes.py` 可自动检查；第 10 项 `scripts/check_outputs.py` 检查。

---

## 常见失败模式

| 症状 | 原因 | 处理 |
|---|---|---|
| 一堆条目点开都是同一件事 | 没做判重，直接罗列 | 回步骤 4，编 `dedupe.json` |
| 事件说得很大但落不到装置 | 缺企业/装置匹配 | 回步骤 6，用装置汇总表建台账 |
| 结论被质疑"哪来的" | 引用了标题或二手转述 | 看 `content_level`，相应降级 |
| 页面打不开就说"没发生" | 违反约束 4 | 写入 `12_访问限制日志` |
| 数字对不上 | 混用了不同口径（如 280 万吨/年甲醇 vs 50 万吨烯烃） | 一个数字一个来源一个量纲 |
| 两个来源矛盾被强行合并 | 违反约束 6 | 标 `conflict`，并列展示 |

---

## 参考

- `references/method.md` —— 九步法的完整做法与判例
- `references/sources-playbook.md` —— 各信息源的可访问性、抓取要点、已知坑
- `references/data-model.md` —— 七文件字段定义与枚举
- `references/qa-checklist.md` —— 详细质检清单
- `examples/01-甲醇-中国-2026年10月第3周/` —— 完整案例（14 事件 / 66 资讯 / 16 源）