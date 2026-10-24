---
name: foreign-trade-contract-review
description: Use when a chemical/industrial-goods exporter or importer needs a foreign-trade sales or purchase contract reviewed clause by clause (审阅外贸合同 / 外贸销售合同审查 / 采购合同审查 / 合同风险清单 / 条款核验 / contract review checklist). Identifies parties, product, trade terms and clause structure; then flags issues on payment, delivery, quality, claims, compliance and dispute resolution. Every finding is anchored to verbatim contract text, carries a commercial consequence and a confirmation item. Delivers an interactive HTML双栏报告 (original text ↔ risk notes, click-to-locate, topic filters, owner/status/notes) plus a multi-sheet Excel review checklist. Works for any country pair, any chemical product, any language, and FOB/CIF/CFR/DAP/EXW.
---

# 审阅外贸合同 / Foreign Trade Contract Review

把一份外贸合同拆成 **「原文位置 → 问题 → 商务后果 → 待确认事项 → 处理状态」** 的可核查清单，
交给外贸业务人员与法务共同过账。

适用于任何国家、任何化工品、任何语言、任一贸易术语。**不预设结论，只锚定原文。**

---

## 0. 三条不可谈判的底线

1. **每条问题必须锚定原文。** 没有原文位置的问题不写。找不到原文时，写「条款缺失」并从反面说明——**不得推测条款存在**。
2. **不得编造法律。** 每条法律依据要么给出可核实的来源，要么明确标注「需律师复核 / 待核实」。把「我记得是这样」写成结论，会让整份报告在法务面前作废。
3. **不把正常商业安排判成违法。** 高违约金、境外仲裁、单方解约权，这些本身都是谈判结果。要说的是**我方承担什么后果**，不是「这条违法」。

> 报告定位：**业务风险提醒，不是法律意见。** 这句话必须在 HTML 与 Excel 里都出现，不得省略。

---

## 1. 先问清楚四件事（一次问完）

| 要素 | 为什么必须先问 | 缺失时的默认 |
|---|---|---|
| **我方身份**：卖方 / 买方 | 决定所有条款的成本落在谁身上。同一句「检验以卖方报告为准」，卖方看是保护，买方看是失权 | **必须问，不能猜** |
| **贸易术语 + Incoterms 版本** | CIF 还是 FOB 决定谁订舱、谁付运费、风险在哪转移 | 从合同读；读不到就问 |
| **合同语言 / 是否需要双语** | 决定语言条款与效力条款怎么审 | 从合同读 |
| **产品是否危险化学品** | 决定是否要审 SDS / 危包证 / 运输资质 | 默认按「一般工业品」审，并在报告里注明未核实 |

可选的补充材料：公司标准模板、客户国家、历史争议、SDS。有就用，没有也能做——
但要在报告的「审阅范围」里写清楚**没拿到什么**。

---

## 2. 六步审阅法

### 第 1 步：结构化识别（不要一上来就挑毛病）

先回答四个问题，形成**条款索引**：

- **主体**：双方是谁？注册地？签字人有授权吗？签署日期填了吗？
- **产品**：名称、规格、HS 编码、质量标准及其测试方法。
- **交易条件**：术语、金额、币种、数量与溢短装、交期。
- **条款结构**：一共几章几条，附件有哪些，附件与正文谁优先。

这一步的产出是 `02 条款索引` 表：每个条款一个块编号（block id），后面所有风险都挂在这个编号上。

### 第 2 步：内部一致性扫描（最高产出的一步）

**同一件事在合同多处出现时，是否互相矛盾？** 这类问题最容易被漏掉，也最致命。

常见冲突点：

- 术语版本：正文写 `Incoterms 2020`，另一句又说「其他单据引用别的版本就以那个为准」
- 交期起算：5.1 说某日起算，6.1 又把起算系于一个已经过期的日期
- 风险与所有权：风险装船转移，所有权保留到付款——中间这段谁承担什么
- 质量标准：Annex 写一套，正文又说「并入买方装运前通知的任何要求」
- 责任上限：正文给卖方封顶 5%，另一条又说买方责任无限

> 判据：**能不能用两句话把同一件事说清楚？** 不能，就是冲突。

### 第 3 步：代入我方身份

对每一条问三个问题：

1. 这条给**谁**设了义务？
2. 履行失败时，**谁**掏钱？
3. 我方现在**有没有**这个能力去履行？（产能、船期、资金、批文）

同一份合同，卖方视角和买方视角的结论经常相反。**报告里必须写明我方身份**。

### 第 4 步：缺失条款检核（用清单，不靠记忆）

对照 `references/review-checklist.md` 的 11 类逐一过。
**没写的条款要说「缺失」，不能说「未发现问题」。** 这两句话在法务眼里完全不同。

### 第 5 步：法律依据检索与标注

- 只引用**能给出处**的规则。
- 每条法律引用标三档：`已核实来源` / `需律师复核` / `待核实（未取得一手文本）`。
- 涉及对方国家法的，一律标「需当地律师确认」，**不要用中文资料替代当地法**。

### 第 6 步：落到商务后果

**不要写「存在法律风险」。** 要写：

> 逾期 90 天按 5% 年息计，约 USD 3,350，低于融资成本，利息不构成付款压力；
> 且条款已放弃中止履行与扣单权，货物出运后我方无操作杠杆。

模式：**具体场景 + 可以估的量级 + 我方失去什么**。

---

## 3. 问题怎么分级

| 等级 | 判据 | 例子 |
|---|---|---|
| **高风险** | 可能导致货款收不回、货物被扣、责任无法追索、争议解决失败 | 开证日早于签约日；检验以对方单方报告为准；仲裁地/语言完全单边 |
| **中风险** | 可能导致成本增加、举证失败、议价能力下降 | 异议期短于航程；允许对方货币支付；SDS 语言不满足目的国 |
| **低风险** | 文本瑕疵，短期不必然造成损失 | 合拼提单无分票约定；装运通知内容不全 |

问题类型统一用这七种（便于筛选统计）：
`表述不清` / `单方有利` / `内部冲突` / `条款缺失` / `权利义务失衡` / `可能不可执行` / `商业不合理`

---

## 4. 每条问题的必填字段

| 字段 | 要求 | 反例 |
|---|---|---|
| `anchors[].block` | 合同块编号（必须真实存在） | 凭印象写「第6条附近」 |
| `anchors[].quote` | **原文逐字**（会被脚本校验） | 自己概括的一句话 |
| `finding` | 说清「条款写了什么 + 为什么有问题」 | 「该条款不合理」 |
| `consequence` | 具体场景 + 量级 + 我方失去什么 | 「存在法律风险」 |
| `confirm[]` | 可执行的确认动作，一条一个动作 | 「请关注」 |
| `legal_refs[]` | 来源 + 核实状态 | 「根据国际惯例」 |
| `suggested_wording` | 可直接放进修订稿的英文条款草案 | 「建议修改该条」 |

`quote` 会被 `scripts/qa_report.py` 逐字比对，对不上会导致构建校验失败——这是故意的。

---

## 5. 交付物与构建流程

### 标准流程（在同一目录内执行）

```bash
# 1) 合同原文 -> 结构化块（每块一个 block id）
python scripts/parse_contract.py contract_source.txt contract_parsed.json

# 2) 校验所有原文引用是否逐字命中
python scripts/qa_report.py --parsed contract_parsed.json \
    --issues data_issues_*.json

# 3) 生成 HTML（双栏交互报告）
python scripts/build_report.py contract_parsed.json data_meta.json \
    data_issues_*.json --out review.html

# 4) 生成 Excel（9 页审阅清单）
python scripts/build_workbook.py contract_parsed.json data_meta.json \
    data_issues_*.json --out review.xlsx

# 5) 浏览器行为自测（可选，需要本机 Chrome）
python scripts/cdp_test.py review.html
```

### 合同怎么变成 `contract_source.txt`

用 `templates/contract_markup.md` 的轻量标记把合同抄一遍。
标记只解决一件事：**让每个段落都有 ID**，其它什么都不改。
已有 Word/PDF 合同时，先转成纯文本再套标记；扫描件要先 OCR。

### 两件交付物

- **`review.html`** — 左右双栏：左原文右风险；点风险定位原文；按主题/等级/状态筛选；
  每条可填负责人、处理状态、备注（存本机 localStorage）；可导出 CSV 给法务。
- **`review.xlsx`** — 9 页：使用说明 / 审阅总览 / 条款索引 / 问题清单 / 确认事项 / 缺失条款 / 原文摘录 / 法律引用 / 依据与边界。
  「问题清单」的负责人、状态、备注列带下拉与筛选，可直接当工作底稿流转。

---

## 6. 质量门（交付前逐条打勾）

- [ ] 报告首页写明**我方身份**与**模拟/真实**性质
- [ ] 每条问题都有 block id，且 `qa_report.py` 校验通过
- [ ] 缺失的条款单独成表，明确写「合同未约定」，没有推测
- [ ] 法律引用逐条标了核实状态；境外法一律写明需当地律师确认
- [ ] 商务后果可估量（金额/天数/比例），不是空泛表述
- [ ] 免责声明在 HTML 与 Excel 中都出现
- [ ] HTML 在浏览器里点得动：定位、筛选、填写、导出（`cdp_test.py` 通过）
- [ ] Excel 打开无损坏，筛选与下拉可用
- [ ] 合同中的公司名、账号、金额确认为模拟或不涉密

---

## 7. 常见翻车点

| 现象 | 原因 | 处理 |
|---|---|---|
| 报告写得像法律意见书 | 用了「无效」「违反法律」等定性词 | 改成「可能导致…」「我方将面临…」 |
| 法务不认账 | 引用了没有出处的规则 | 只留可核实来源，其余标「待核实」 |
| 漏掉最致命的一条 | 没做内部一致性扫描 | 第 2 步不能跳 |
| 客户觉得被冒犯 | 把对方的正常商业要求称为不合理 | 只描述我方面临的后果 |
| 定位点不上 | block id 写错或合同改过没重新解析 | 每次改合同都重跑 parse + qa |
| 双语合同结论错 | 只看了英文版 | 双语必须比对两版并说明优先版本 |

---

## 8. 参考文件

| 文件 | 用途 |
|---|---|
| `references/review-checklist.md` | 11 类必查事项的完整清单（含危险化学品专章） |
| `references/clause-library.md` | 常见风险条款模式 × 中文说明 × 英文修改草案 |
| `references/incoterms-and-payment.md` | 贸易术语与付款方式的核验要点 |
| `references/legal-verification.md` | 可核实规则清单与核实状态（CISG / 纽约公约 / Incoterms / 印尼法等） |
| `references/data-schema.md` | 数据字段定义，改脚本前必读 |
| `references/html-report.md` | 报告页面的结构与交互说明 |
| `templates/contract_markup.md` | 合同标记语法 |
| `templates/data_meta.template.json` | 元信息模板 |
| `templates/report.css` / `report.js` | 报告样式与交互层，可直接改 |
| `examples/soda-ash-indonesia-cif/` | 完整样例：重质纯碱 → 印尼，CIF，38 条问题 |

---

## 9. 边界

本 Skill 产出的是**业务审阅材料**：

- 不做法律意见，不对合同效力下结论；
- 不核验对手资信、货物实测品质、目的国监管现状；
- 不做税务、外汇、海关归类结论。

以上任何一项需要结论时，须由具备中国法及对方国家法执业资格的律师出具意见。
报告中的「建议修改措辞」仅为**谈判起点草案**，不是终稿。

> 若把本 Skill 的输出直接当作法律意见使用，责任不在工具。
