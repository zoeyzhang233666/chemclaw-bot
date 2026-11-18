# 输出规范（Output Spec）

> 本文件是**数据契约**：`contract.json` 与 `review.json` 的字段定义，以及 HTML / Excel 的呈现要求。
> 构建脚本 `scripts/common.py::validate_case` 会按本规范做硬校验，校验不过直接失败。

---

## 一、目录结构

```
<案例目录>/
  contract.json                 合同结构（必填）
  review.json                   审查结果（必填）
  <输出>.html                   交互式审查页面（可选）
  <输出>.xlsx                   Excel 工作簿（可选）
```

`contract.review.json` 之外的同名 JSON 会被忽略；两个文件按内容自动识别（含 `clauses` 的为合同，含 `findings` 的为审查）。

---

## 二、contract.json

### 2.1 顶层

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `demo` | bool | 否 | `true` 时所有交付物必须显示「虚构演示合同」标记 |
| `demo_label` | string | 否 | 演示标记文案 |
| `contract_meta` | object | ✓ | 合同元信息 |
| `sections` | array | ✓ | 章节（含附件） |
| `clauses` | array | ✓ | 条款（含附件表格行） |
| `attachments` | array | 否 | 附件呈现内容（表格/列表），与 `clauses` 中附件条款对应 |

### 2.2 contract_meta

| 字段 | 说明 |
|---|---|
| `title` / `contract_no` / `sign_date` | 基本信息 |
| `buyer` / `buyer_addr` / `supplier` / `supplier_addr` | 双方 |
| `review_as` | 我方身份，如「买方（甲方）」 |
| `framework` | 是否框架合同 |
| `files_received` | 已收到文件清单 |
| `files_missing` | 缺失文件清单（必须在交付物中展示） |
| `page_count` | 合同总页数（可选） |

### 2.3 sections[]

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✓ | `preamble` / `s1`…/`a1`… |
| `no` | ✓ | 章节编号（`第一条`、`附件一`、`—`） |
| `title` | ✓ | 章节标题 |
| `page` | ✓ | 起始页 |
| `clause_ids` | ✓ | 本章节包含的条款 ID（顺序即呈现顺序） |
| `notes` | 否 | 结构说明 |

### 2.4 clauses[]

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✓ | 主键，`C01` / `A1-T3` |
| `sec` | ✓ | 所属 section.id |
| `no` | ✓ | 条款编号（原文编号） |
| `page` | ✓ | 页码 |
| `page_line` | ✓ | 页内位置 |
| `text` | ✓ | **逐字原文**，不得改写 |
| `kind` | 否 | `table_row` / `note` 等，用于呈现缩进与样式 |

### 2.5 attachments[]（呈现用，可选）

```json
{"no": "附件一", "title": "产品技术规范", "page": 5,
 "table": {"caption": "表1", "cols": ["项目","指标"], "rows": [["…","…"]], "note": "…"}}
```
或 `{"list": ["1. …", "2. …"]}`。

---

## 三、review.json

### 3.1 顶层

| 字段 | 必填 | 说明 |
|---|---|---|
| `review_meta` | ✓ | 审查元信息（含 `disclaimer`） |
| `roles` | 否 | 部门名称映射（legal/procurement/supplier…） |
| `method` | 否 | 审查步骤（写进 HTML「方法与边界」页） |
| `topics` | ✓ | 主题枚举 `[{id, name, short}]` |
| `findings` | ✓ | 风险条目 |
| `legal_refs` | ✓ | 法规标准核对表 |
| `confirmations` | ✓ | 按办理人拆分的待确认问题 |
| `summary` | ✓ | 结论、统计、缺失清单、测算依据 |

### 3.2 review_meta

`review_id`、`contract_title`、`contract_no`、`product`、`our_role`、`supplier`、`review_date`、`reviewer`、`pages`、`signed`、`review_scope`、`data_cutoff`、`law_check_date`、`disclaimer`。

`disclaimer` 必须包含「业务审查提示」「不是法律意见」「不替代律师或法务」三个要素。

### 3.3 topics

固定 12 个，`id` 与 `name` 必须一一对应：

| id | name |
|---|---|
| quality | 质量 |
| quantity | 数量 |
| delivery | 交货 |
| packaging | 包装容器 |
| measure | 计量 |
| price | 价格税费 |
| payment | 付款 |
| safety | 安全合规 |
| breach | 违约责任 |
| forcemajeure | 不可抗力 |
| dispute | 争议解决 |
| general | 通用 |

### 3.4 findings[]

| 字段 | 必填 | 规则 |
|---|---|---|
| `id` | ✓ | `R01`…，唯一 |
| `topic` | ✓ | 必须在 `topics` 中 |
| `kind` | ✓ | `缺失` / `表述不清` / `写了但对我方不利` |
| `title` | ✓ | ≤40 字，说明「哪里、什么问题」 |
| `clause_ids` | ✓ | ≥1，必须存在；跨条款时全部列出 |
| `what_written` | ✓ | 合同写了什么 |
| `what_missing` | ✓（缺失类） | 缺失类必填，写「没写什么」，不得写建议 |
| `business_impact` | ✓ | 落到环节 + 量级 |
| `consequences` | ✓ | ≥1 条 |
| `to_confirm` | ✓ | ≥1 条，写「确认什么」 |
| `owner` | ✓ | 办理方数组 |
| `severity` | ✓ | 1–5 整数 |
| `likelihood` | 否 | 1–5 |
| `law_refs` | 否 | 必须在 `legal_refs` 中能匹配到 |

### 3.5 legal_refs[]

| 字段 | 必填 | 规则 |
|---|---|---|
| `name` | ✓ | 含编号与年份 |
| `scope` | ✓ | 适用点 |
| `status` | ✓ | 现行 / 现行（条件说明）/ 被替代 / 未核实 |
| `status_basis` | ✓ | 来源 + 核对日期；`现行` 必须写依据 |
| `relevance` | ✓ | 与本合同的关联 |
| `url` | ✓ | 官方来源链接 |

### 3.6 confirmations

```json
{"legal": [{"finding_id": "R04", "question": "…", "priority": "高"}],
 "procurement": [...], "supplier": [...]}
```

- `finding_id` 必须存在；
- `priority` ∈ {高, 中, 低}；
- 三张清单都要有内容，**供应商清单要能直接对外发送**（只问事实/文件/承诺，不问法律判断）。

### 3.7 summary

```json
{"headline": "一句话结论",
 "stats": {"total": 36, "by_kind": {"缺失": 20, "表述不清": 16},
           "by_severity": {"5": 3, "4": 14, "3": 13, "2": 6}},
 "calc_basis": {"annual_tonnage": 2000, "unit_price": 1150,
                "contract_value": 2300000, "liability_cap_5pct": 115000, "note": "…"},
 "high_points": ["…"], "missing_list": ["…"]}
```

`stats` 必须与 `findings` 实测一致（脚本会核对）。

---

## 四、HTML 呈现要求

| 区块 | 要求 |
|---|---|
| 顶部横幅 | 演示合同显示「虚构演示合同」；同时显示合同名、编号、我方身份、供应商、签订与审查日期 |
| 总览 | 风险条数、缺失数、表述不清数、涉及条款数、待确认数；一句话结论；最需先处理的 8 条；缺失清单；已收/缺失文件 |
| 原文×风险双栏 | 左栏按章/条/页渲染原文，条款带锚点；右栏风险卡 |
| 定位 | 点风险卡「📍条款」→ 左栏滚动+高亮；点原文里的风险编号 → 右栏定位卡片 |
| 筛选 | 主题 / 类型 / 严重度 / 关键词，实时显示「显示 n / N」 |
| 问题清单 | 采购 / 法务 / 供应商三页签，行可点击定位 |
| 法规核对 | 表格含状态、核验依据、来源链接 |
| 方法与边界 | 审查步骤 + 业务提醒与法律意见边界 + 免责声明 |
| 状态与备注 | 每条风险可选状态、填备注；localStorage 持久化；可导出 JSON |
| 离线 | 单文件、无外部字体/CDN；打印时展开全部卡片 |

---

## 五、Excel 呈现要求

| 工作表 | 内容 | 必备格式 |
|---|---|---|
| 00 使用说明与边界 | 审查口径、六条证据规则、边界、免责声明 | 标题栏、分区着色 |
| 01 条款索引 | 条款ID/章节/编号/页码/位置/原文/关联风险/是否覆盖 | 冻结窗格、筛选、风险行着色 |
| 02 风险事项总表 | 20 列（见下） | 严重度色阶、状态下拉、筛选 |
| 03 原文引用 | 每条风险的逐字摘录 | 可核对 |
| 04 法规标准核对 | 名称/适用点/状态/依据/链接/核对日期/是否需再核 | 超链接 |
| 05 待确认清单 | 合并视图 | 优先级着色 |
| 06 采购待办 | 经办人/要求完成日期/状态 | 状态下拉 |
| 07 法务待办 | 同上 | 同上 |
| 08 供应商问题清单 | 可直接外发 | 同上 |
| 09 统计 | 主题/类型/严重度分布 + 量级测算 | 数值格式 |

「02 风险事项总表」列序：
`风险编号｜主题｜风险类型｜严重度(1-5)｜严重度｜风险标题｜引用条款ID｜条款编号｜页码｜原文位置｜合同写了什么｜未约定/未写清的内容｜业务风险与可能后果｜可能后果（分条）｜涉及法规/标准｜需确认事项（分条）｜建议办理部门｜待确认问题数｜状态｜备注`

---

## 六、校验失败示例

```
数据校验失败:
  R12 引用未知条款 C99
  章节 s2 引用未知条款 X01
  summary.stats.by_kind 与实测不一致: {...} vs {...}
```

出现上述错误时**不得**绕过校验出交付物，必须先修数据。
