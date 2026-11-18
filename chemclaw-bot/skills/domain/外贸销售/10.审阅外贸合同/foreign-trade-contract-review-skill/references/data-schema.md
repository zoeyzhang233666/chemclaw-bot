# 数据格式说明

三个输入文件、一个中间文件，构成报告的全部数据。
改脚本前先读完本页。

---

## 1. `contract_source.txt` — 合同原文（带标记）

纯文本，UTF-8。用 `templates/contract_markup.md` 的标记把每个段落包起来。
解析后每段获得一个**稳定的 block id**，全系统靠它定位。

```
@@DOC ZJSA-2026-0417-SIM
@@BANNER SIMULATED — not a real contract
@@TITLE SALE CONTRACT
@@META Contract No. | ZJSA-2026-0417-SIM
@@H1 ARTICLE 1 — DEFINITIONS          <- 章
@@H2 1.1 Definitions                  <- 条
@@P The following terms have...       <- 段
@@TABLE                              <- 规格表
@@TR Item | Value
```

---

## 2. `contract_parsed.json` — 解析结果

```jsonc
{
  "source": "contract_source.txt",
  "blocks": [
    { "id": "p-article-6-payment-067",   // 全局唯一，所有锚点用它
      "kind": "p",                        // h1|h2|p|exec-col|exec-line|table|annex-title
      "text": "…",                        // p / h1 / h2 / annex-title 有
      "rows": [["Item","Value"]],         // table 有
      "lines": [{"id":"xl-001","text":"…"}], // exec-col 有
      "article": "ARTICLE 6 — PAYMENT",   // 所属章（便于索引与展示）
      "section": "…", "part": "…" }
  ],
  "index": [
    { "id": "art-…", "title": "ARTICLE 6 — PAYMENT",
      "blocks": ["p-…","tbl-…"],
      "clauses": [ { "id": "clause-…", "title": "6.1 Payment method",
                     "blocks": ["p-…"] } ] }
  ]
}
```

**block id 的构成**

| kind | id 形式 | 例 |
|---|---|---|
| 章 | `art-<slug>` | `art-article-6-payment` |
| 条 | `clause-<slug>` | `clause-6-1-payment-method` |
| 段 | `p-<slug>-<NNN>` | `p-article-6-payment-067` |
| 表 | `tbl-<slug>` | `tbl-specification` |
| 签署栏 | `p-exec-left` / `p-exec-col` | — |
| 签署行 | `xl-NNN` | `xl-001` |

> id 里带序号（`-067`），意味着**改动合同段数会导致后续编号位移**。
> 因此改合同后必须**重新解析并重跑 QA**，不能沿用旧 id。

---

## 3. `data_meta.json` — 元信息

```jsonc
{
  "meta": {
    "title": "英文销售合同",
    "contract_no": "ZJSA-2026-0417-SIM",
    "contract_date": "17 April 2026",
    "our_role": "seller",              // ← 必填。seller | buyer
    "our_role_cn": "卖方",
    "counterparty_country": "印度尼西亚",
    "product": "Heavy Soda Ash (Dense Sodium Carbonate)",
    "product_cn": "重质纯碱",
    "hs_code": "2836.20.00",
    "trade_term": "CIF Jakarta (Incoterms 2020)",
    "amount": "USD 268,000.00",
    "quantity": "1,000 MT ±10%",
    "review_date": "2026-04-18",
    "reviewer": "外贸业务部 / 法务",
    "disclaimer": "本报告仅为业务风险提醒，不构成法律意见。…",
    "review_scope": "审阅范围：合同正文 16 章及附件 A/B/C。未审……",
    "store_key": "ftc-review:ZJSA-2026-0417-SIM"  // 可选，localStorage key
  }
}
```

---

## 4. `data_issues_*.json` — 问题数据（核心）

可拆成多个文件（按批次/章节），构建时按顺序合并并按 `seq` 排序。

```jsonc
{
  "issues": [
    {
      "id": "R-01",                    // 唯一，展示用编号
      "seq": 1,                        // 排序
      "category": "payment",           // payment|delivery|quality|claim|compliance|dispute|missing
      "severity": "high",              // high|medium|low
      "issue_type": "commercial",      // ambiguous|unilateral|conflict|missing|unbalanced|unenforceable|commercial
      "title": "信用证开证日期早于合同签署日",       // 中文，一句话
      "title_en": "LC opening date precedes signature",
      "clause_title": "6.1 Payment method",         // 显示在卡片头部

      "anchors": [                                  // ≥1；缺失条款用空数组
        { "block": "p-article-6-payment-067",       // 必须存在于 parsed.blocks
          "clause": "6.1(B)",
          "quote": "The Letter of Credit shall be opened…" }   // 必须逐字命中
      ],

      "finding": "合同签署日为…，但条款要求…。",     // 中文；说清「写了什么 + 为何有问题」
      "finding_en": "…",

      "consequence": "卖方无法在形式上取得…",        // 中文；场景 + 量级 + 我方失去什么
      "consequence_en": "…",

      "confirm": [                                  // 可执行动作，一条一个
        "确认合同实际签署日与生效日",
        "与买方书面确认信用证最迟开证日"
      ],

      "legal_refs": [                               // 可为空
        { "label": "CISG 第 6 条（当事人可排除适用）",
          "note": "印尼非缔约国，此条款属巩固性安排" }
      ],

      "suggested_wording": "The Buyer shall open the Letter of Credit …",  // 英文草案

      "owner": "",                    // 留空，由业务填写
      "status": "待处理",              // 待处理|处理中|需法务确认|已解决|不适用
      "note": ""
    }
  ]
}
```

### 字段约束（由 `scripts/qa_report.py` 强制）

| 约束 | 违反后果 |
|---|---|
| `anchors[].block` 必须能在 `contract_parsed.json` 找到 | 构建失败，定位按钮失效 |
| `anchors[].quote` 必须是该 block 文本的**连续子串** | QA 报错；防止「概括式引用」 |
| `id` 全局唯一 | 卡片与 localStorage 冲突 |
| `severity` / `category` / `issue_type` / `status` 取值必须在枚举内 | 筛选与配色失效 |

> `quote` 的逐字校验是本 Skill 最重要的一道闸。
> 它把「我记得合同里是这么写的」挡在门外。

### 缺失条款怎么写

```jsonc
{
  "id": "R-35", "category": "missing", "issue_type": "missing",
  "title": "【条款缺失】未约定迟延交付的违约金",
  "anchors": [],                          // ← 空数组，这是唯一合法的情况
  "finding": "合同第 5 条只约定装运期，未约定迟延交付的违约金或解除权。",
  "consequence": "迟延责任回到一般违约规则，赔偿范围可能包含对方间接损失。",
  "confirm": ["确认是否接受迟延交付无违约金上限的状态"],
  "suggested_wording": "0.3% of the value of the delayed Goods per day, capped at 5%."
}
```

**规则**：`category: "missing"` 的条目必须有 `anchors: []`（或只锚定「相关但不完整」的条款并说明）。
**不得**为了让条目好看而虚构造一句原文。

---

## 5. 构建产物

| 文件 | 说明 |
|---|---|
| `review.html` | 自包含单文件（CSS/JS 内联），可直接发邮件、离线打开 |
| `review.xlsx` | 9 页工作簿，见 `SKILL.md` |

HTML 内嵌 `window.__REVIEW__ = {...}`，包含 meta + issues 全量数据；
修改数据后必须重新构建，不能只改 HTML。

---

## 6. 常见改动与对应操作

| 想做的事 | 改哪里 | 之后必须做 |
|---|---|---|
| 增加一条问题 | `data_issues_0X.json` 新增对象 | 重跑 qa + build_report + build_workbook |
| 修改合同文本 | `contract_source.txt` | **重新 parse**，再修 id 引用的位移 |
| 增减筛选项 | 确定枚举（category/severity） | 同步改 `report.js` 与 `build_workbook.py` 的映射表 |
| 换语言 | `finding` / `consequence` 等字段 | `title_en`、`finding_en` 保持英文版 |
| 换客户/产品 | `data_meta.json` | 全部 issues 需重写（锚点全变） |
