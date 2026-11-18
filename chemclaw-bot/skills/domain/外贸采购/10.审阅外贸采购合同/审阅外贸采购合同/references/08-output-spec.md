# 交付物规格（output-spec）

本文件定义 Skill 的四类交付物：**交互式 HTML 审阅报告**、**Excel 问题清单工作簿**、**中英对照合同 DOCX**、**英文澄清函**。所有交付物由同一份数据（`contract.json` + `review.json`）渲染，保证 HTML / Excel / 函件三处口径完全一致。

---

## 0. 数据源：两个 JSON

审查的第一步不是写报告，而是把合同**结构化**。两份 JSON 是所有交付物的唯一事实来源。

### 0.1 `contract.json` — 合同本体

```jsonc
{
  "demo": true,                       // true = 模拟合同，所有交付物必须带「模拟」标识
  "demo_label": "【模拟合同】…",
  "language": "en-zh",                // en | zh | en-zh；决定是否输出中文对照
  "contract_meta": {
    "title": "…", "title_en": "…", "contract_no": "…", "sign_date": "2026-10-08",
    "buyer": "…（模拟）", "buyer_en": "…", "buyer_addr": "…",
    "supplier": "…", "supplier_en": "…", "supplier_addr": "…",
    "review_as": "中国买方（进口商）— Buyer / Importer",
    "our_side": "buyer",              // buyer | seller
    "product": {"name_cn": "…", "name_en": "…", "cas_written": "…", "hs_6": "…", "hs_cn": "…"},
    "incoterms": {"rule": "CIF", "year": "2020", "place": "宁波港 Ningbo Port", "named_port": "Ningbo"},
    "payment_summary": "…", "shipment_period": "…",
    "page_count": 7,
    "files_received": ["…"],
    "files_missing": ["…"]
  },
  "sections": [                       // 章节索引，clause_ids 决定左栏的展示分组
    {"id": "s6", "no": "第 8 条", "title": "Payment｜付款", "page": 3, "clause_ids": ["C16", "C17"]}
  ],
  "clauses": [
    {
      "id": "C16",                    // 唯一锚点键，全项目用它定位
      "sec": "s6", "no": "8.1", "page": 3,
      "page_line": "第3页 第3段",       // 页内位置，供人工核对原件
      "text": "Advance payment: 30% …",   // 原文，逐字，不得改写
      "zh": "预付款：合同金额的 30%…",     // 中文对照（我方理解，非官方译文）
      "kind": "payment"               // 见 0.3
    }
  ]
}
```

**硬约束**

| 约束 | 说明 | 校验点 |
|---|---|---|
| `text` 逐字 | 必须与原件完全一致，包括拼写错误、大小写、标点 | `check_quotes()` |
| `id` 唯一 | 建议 `C01…Cnn` + `A1-*`/`A2-*` 表示附件行 | `validate_case()` |
| `page` + `page_line` | 必须能在原件上翻到 | 人工抽查 |
| `zh` 不替代原文 | 中文是解释，不是约定文本 | 报告双栏呈现 |
| 附件逐行拆分 | 表格每一行独立成条（`table_row`），才能被风险引用 | 见 0.3 |

### 0.2 `review.json` — 审查结论

```jsonc
{
  "review_meta": {
    "review_id": "IPCR-2026-MEG-001",
    "our_role": "中国买方（进口商）— Buyer / Importer",
    "counterparty": "…",
    "review_date": "2026-10-20", "reviewer": "…", "pages": 7,
    "signed": "候签（尚未签署）",
    "review_scope": "审阅范围 + 未取得材料（必须写清）",
    "data_cutoff": "2026-10-20",
    "law_check_date": "2026-10-20",
    "disclaimer": "本结果仅作为商务审查提醒，不构成法律意见。"
  },
  "roles": {"legal": "公司法务", "procurement": "采购/进口部", "supplier": "海外供应商"},
  "topics": [ {"id": "payment", "name": "付款与交单"} … ],       // 界面筛选按钮由此生成
  "method": {"steps": ["第 0 步 …", "第 1 步 …"], "product_specific": ["MEG 的 CAS 是 …"]},
  "findings": [ {
      "id": "R01", "topic": "payment",
      "kind": "写了但对我方不利",        // 缺失 | 表述不清 | 写了但对我方不利
      "severity": 5,                     // 1–5
      "likelihood": "高",
      "title": "30% 预付款无任何担保且约定不予退还",
      "title_en": "30% advance payment is unsecured and expressly non-refundable",
      "clause_ids": ["C16", "C27"],
      "quotes": [{"clause_id": "C16", "text": "逐字原文片段"}],
      "what_written": "合同怎么写的中文解释",
      "what_missing": "缺失/不清楚的部分（kind=缺失 时必填）",
      "business_impact": "对我方（中国买方）的业务后果",
      "impact_basis": "金额/量级测算口径（无数字则留空）",
      "consequences": ["分条后果 1", "分条后果 2"],
      "to_confirm": ["需确认事项 1", "需确认事项 2"],
      "owner": ["procurement", "legal"],
      "law_refs": ["《中华人民共和国民法典》（2020年5月28日通过，2021年1月1日施行）"],
      "status": "待处理", "owner_internal": "", "supplier_feedback": ""
  } ],
  "legal_refs": [ {
      "name": "…", "scope": "用来对照什么", "status": "现行",
      "status_basis": "核验依据：发布/施行日期 + 来源", "relevance": "与本合同哪条相关",
      "url": "https://…"
  } ],
  "confirmations": {
    "legal":       [{"finding_id": "R01", "priority": "高", "question": "…"}],
    "procurement": [ … ],
    "supplier":    [{"finding_id": "R01", "priority": "高", "question": "…", "question_en": "…"}]
  },
  "summary": {
    "headline": "一段话说清最要命的几条",
    "missing_list": ["未约定事项…"],
    "high_points": ["…"],
    "calc_basis": {"quantity_mt": 5000, "unit_price_usd": 512, "contract_value_usd": 2560000,
                   "advance_pct": 0.3, "advance_usd": 768000, "balance_usd": 1792000,
                   "liability_cap_usd": 768000, "ld_per_day_usd": 1280, "ld_cap_pct": 0.05,
                   "ld_cap_usd": 128000, "note": "汇率仅用于量级换算…"},
    "stats": {}                        // 由 _recount() 生成，不要手写
  },
  "negative_results": [                // 「已审未见风险」——见 reference 01 第 7 节
    {"clause_ids": ["C01"], "note": "封面：仅声明文件性质，未发现风险。"}
  ]
}
```

### 0.3 `kind` 取值（条款类型，仅影响排版，不是风险类型）

`cover` `parties` `goods` `quality` `spec_error` `annex_ref` `price` `delivery` `shipment`
`docs` `payment` `inspection` `claims` `risk` `title` `insurance` `penalty`
`force_majeure` `dispute` `language` `signature` `annex_head` `table_head` `table_row` `note`

---

## 1. 交互式 HTML 审阅报告

**生成**：`python scripts/build_review_html.py --dir <案例目录> --out <报告.html> [--letter <澄清函.txt>]`

单文件、零依赖、双击即开（无 CDN、无外链字体、可离线在会议室内打开）。**不要**为了好看而引入在线资源——进口合同经常在客户内网环境下查看。

### 1.1 页面结构（7+1 个页签）

| 页签 | 内容 | 关键要求 |
|---|---|---|
| 总览 | 顶部模拟标识条 → 合同基本信息 → 6 个统计数字 → 一句话结论 → 缺失清单 → 高风险清单 | 首屏必须能看见「模拟合同」与「不构成法律意见」 |
| 原文 × 风险 | **左栏合同全文（英文原文 + 中文对照）｜ 右栏风险卡片** | 左右各占 50%，两栏独立滚动 |
| 条款索引 | 条款ID / 编号 / 页码 / 位置 / 原文 / 关联风险 | 点风险编号跳到对应卡片 |
| 待确认清单 | 法务 / 采购 / 供应商 三张表 | 与 Excel 第 05 页一致 |
| 中英对照问题清单 | 中文问题 + English question | 可「复制为 CSV」 |
| 法规核对 | 名称 / 适用点 / 状态 / 核验依据 / 链接 | 状态非「现行」必须显性标注 |
| 英文澄清函 | 可复制全文（`--letter` 传入） | 无参时显示提示 |
| 方法说明 | 12 步审查法 + 本产品专属要点 | 让用户看懂「为什么这么审」 |
| 负结果 | 已审未见风险的条款 + 覆盖统计 | 防止把「没列为风险」误读为漏审 |

### 1.2 双栏交互（这是本交付物的核心）

- **定位**：右侧风险卡片上的条款胶囊（`C16 · 8.1 P3`）点击 → 左栏滚到该条款并高亮闪烁 1.5 秒。
- **筛选**：主题按钮（付款/交货/质量/索赔/违约/运输/争议解决…）、风险类型（缺失/表述不清/对我方不利）、严重度（5/4/3）、关键字搜索，四者可叠加；实时显示「显示 N / M 条」。
- **可维护**：每张卡片可填 **内部负责人**、**处理状态**（下拉）、**供应商反馈**、**备注**；
  存入 `localStorage`（键名 `ipcr-<标题>`），刷新不丢。
- **导出**：`导出状态 JSON`（交回 Skill 复用）、`导出中英对照 CSV`（BOM + UTF-8，Excel 直接打开不乱码）。

### 1.3 必须出现的三处声明

1. 顶部横幅：`⚠ 模拟合同（Simulated Contract）` — 仅当 `demo=true` 时渲染。
2. 总览区与页脚：`本结果仅作为商务审查提醒，不构成法律意见。`
3. 法规页：`核对日期` 与「未逐条核对」标记。

### 1.4 自检清单（发出去之前逐条过）

- [ ] 浏览器控制台无报错；`<script>` 单块能被解析（内联数据必须用 `json.dumps`，不要直接拼字符串）
- [ ] 左右两栏各 50%，页面无横向滚动条（`.card` 宽 778px / 视口 1600px 时正常）
- [ ] 任意主题筛选后，卡片数与 Excel「02 风险事项总表」用同一条件筛出的行数一致
- [ ] 点 5 个不同胶囊，左栏都能滚到并高亮
- [ ] 填一条负责人 → 刷新页面 → 仍在
- [ ] 导出的 CSV 用 Excel 打开中文不乱码
- [ ] 「模拟合同」「不构成法律意见」可见

---

## 2. Excel 问题清单工作簿

**生成**：`python scripts/build_review_xlsx.py --dir <案例目录> --out <清单.xlsx>`

9 张表，**顺序不可打乱**（下游可能按索引取表）：

| 表 | 名称 | 用途 |
|---|---|---|
| 00 | 使用说明与边界 | 文件性质、审查边界、6 条证据规则、谁该判断什么、免责声明 |
| 01 | 条款索引 | 条款ID/章节/编号/页码/位置/原文/中文/关联风险/是否覆盖 |
| 02 | 风险事项总表 | **主表**，24 列，含原文、中文解释、缺失内容、商务后果、测算、法规、办理人、状态 |
| 03 | 原文引用 | 每条风险的逐字引用 + 「✔ 是」逐字校验标记；缺失类给「不引用」说明 |
| 04 | 法规核对 | 名称/适用点/状态/核验依据/关联/链接/核对日期 |
| 05 | 待确认清单 | 法务/采购/供应商 三合一，含经办人、完成日、状态、结论列 |
| 06 | 中英对照问题清单 | 中文风险 + Risk issue (English) + 中文问题 + Question to Supplier (English) |
| 07 | 条款修改建议草稿 | 现状摘要 → 修改方向 → 修改方式 → 法务确认 → 谈判优先级 |
| 08 | 统计 | 严重度/类型/主题分布 + 量级测算表 + 测算说明 |

**格式规范**

- 表头深蓝底白字（`#0F3D5C`），冻结在数据区首行，`auto_filter` 覆盖全表。
- 严重度用底色编码：5 极红、4 橙、3 黄、2 浅绿、1 浅蓝；类型：缺失黄 / 表述不清蓝 / 对我方不利红。
- 「处理状态」列必须挂 **数据验证下拉**（待处理/已确认/待供应商回复/已解决/不适用），不要让人手打。
- 「内部负责人」「供应商反馈」「备注」留空，给人填 —— 这是工作簿，不是只读报告。
- 行高按内容长度估算（`max(17, 12.5*(len/62+1))`），不要全部默认高度导致文字被截断。
- `08 统计` 的金额必须能由合同原文数字复算，并在「测算说明」写明口径与汇率假设。

**自检**：读回 xlsx，确认每张表的 `max_row`、冻结窗格、筛选范围与预期一致；确认 02 表必需列无空值、06 表英文列无空值。

---

## 3. 中英对照合同 DOCX

**生成**：`python scripts/build_contract_docx.py --dir <案例目录> --out <合同.docx> [--with-tags]`

用途：用户手上没有真实合同 PDF 时，由本脚本产出**明确标注模拟**的完整双语合同，作为审查对象与示例附件。**真实合同不要用本脚本改写正文。**

版式：每条「编号 | 英文原文 | 中文对照」三列单行表格，章节标题带页码标记，页脚含合同号与「模拟合同」。

- `--with-tags`：在条款下方标注关联风险编号（R01…），便于对照阅读；对外发送时**不要**带这个参数。
- 首行必须是与 HTML 一致口径的模拟声明。
- 文末注释说明「刻意保留的条款问题用于演示，不代表真实交易」。

---

## 4. 英文澄清函

**生成**：`python scripts/build_clarification_letter.py --dir <案例目录> --out <函.txt>`

规则（比版式重要）：

1. **全英文**，不夹中文（生成后脚本应 0 个 CJK 字符）；条款定位串也要翻译（`Clause 8.1, Section 3, p.3`）。
2. 按主题分组：付款与信用证 → 交货与装运 → 质量与规格 → 检验索赔与救济 → 运输风险与保险 → 争议解决与语言 → 单据包装与合规。
3. 每条标注：`[R01 · High priority] [AGREEMENT REQUIRED]`，标签三档：
   `[AGREEMENT REQUIRED]`（要求改条款）/ `[AGREEMENT PREFERRED]`（希望改）/ `[INFORMATION]`（只要事实与文件）。
4. **只问事实、文件、承诺，不问法律结论**；不写「你必须」「根据法律你应当」。
5. 附「Contract wording referred to (verbatim)」引号原文（超 300 字符截断并加 `[...]`），让对方无法说「不知道你指哪句」。
6. 每条留 `Supplier response: ______` 空行。
7. 结尾带 `[DRAFT — INTERNAL USE ONLY]` 与「发出前须由采购与法务确认」。

---

## 5. 命名约定

| 交付物 | 文件名 |
|---|---|
| HTML | `外贸采购合同审阅报告-<标的>-<术语><港口>-模拟.html` |
| Excel | `外贸采购合同问题清单-<标的>-<术语><港口>-模拟.xlsx` |
| DOCX | `模拟合同-<标的>-中英对照.docx` |
| 函件 | `英文澄清函草稿-<标的>-合同<编号>.txt` |

真实项目把 `-模拟` 去掉，并在文件名中带上我方项目号。

---

## 6. 一句话验收标准

> 用户拿到 HTML 后，**不读合同原文也能在 10 分钟内说出**：钱在什么时候出去、回来靠什么、货不对时还能不能停付、出了争议在哪里打；并且知道**每一条该找谁去确认**。Excel 让这件事可以分派、可以跟踪、可以回应供应商。
