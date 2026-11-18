---
name: overseas-inquiry-triage
description: Use when a chemical / industrial-materials export sales rep hands over an inbound inquiry from an overseas buyer — email, forwarded thread, WhatsApp/WeChat screenshot, RFQ PDF or Excel, or tender extract, in English / Spanish / Portuguese / Indonesian / Vietnamese / Arabic / Japanese… — and needs it turned into a bilingual (中英) evidence-traced field sheet across 8 fixed categories (buyer, product & chemistry, specification, quantity, delivery & Incoterms, commercial, documents & compliance, buyer-side context), with what-was-said vs what-is-missing separated, 2-column HTML review board where every field links back to the original sentence, a pre-quotation confirmation checklist, and a paste-ready English reply built on a company template with EVERY number and commercial commitment rendered as a visible placeholder. Never invents a price, an effective date, stock, a sailing date, a lead time, a payment term, a document-set promise, a CAS number or a company. Triggers 处理一封海外询盘 / 海外客户询盘 / 外贸询盘 / 询盘解析 / 询盘提取 / 缺失信息 / 待确认问题 / 英文回复草稿 / 回复模板 / 询盘润色 / overseas inquiry / inbound RFQ / inquiry triage / what to ask the customer before quoting. Product-agnostic: 纯碱 soda ash, 烧碱 caustic soda, 尿素 urea, 甲醇 methanol, 钛白粉 TiO2, PVC, SBS, 钴粉 cobalt powder, 氢氧化锂 lithium hydroxide… Delivers a self-contained offline HTML review board, a 7-sheet Excel workbook, a standalone copy-paste English reply draft, fields.json / reply.json, and a Chinese one-page briefing.
---

# 处理一封海外询盘（外贸销售 · 化工品）

一封海外询盘真正难的不是"读懂英文"，是**分清哪句是客户说的、哪句是我方以为客户说的**。
这封询盘读完，销售必须能回答四个问题：

1. 客户到底要什么？（产品、规格、数量、目的地、单证）
2. 哪些是**客户原话**，哪些是**没人说过**的？
3. 报价前必须先问客户哪几个问题？
4. 现在我该怎么回这封邮件——而且一个数字都不许自己编。

整套技能只围绕一句话：**只搬运客户说过的话，其余一律留空并显式占位。**

## 0. 解决什么 / 不解决什么

| 解决 | 不解决 |
|---|---|
| 把多语言、多格式的询盘抽成 8 类标准化字段 | 不给客户打分、不评估"真实性"或"成交可能性"（明确禁止） |
| 每个值都带原文依据 + 语言 + 位置，可一键回原文 | 不判断客户信用、不查工商、不查海关数据（转「核验海外询盘公司」） |
| 明确拆开「已明确」/「缺失或歧义」/「报价前必须先确认」 | 不计算任何价格（转「算出口报价」） |
| 按我方模板生成可编辑英文回复草稿 | 不承诺价格、库存、船期、交期、账期、单证 |
| 输出 HTML 双栏审阅板 + Excel 工作簿 + 独立英文草稿 | 不替销售发邮件 |
| 收到销售已写好的英文稿时，只做语言润色 | 不在润色时新增任何商务承诺（硬约束，见 §6） |

> 特殊约束：**不得对询盘真实性或成交可能性打分**。任何"可信度 80%""成交概率 60%""A/B/C 级客户"都不许出现。
> 本技能只有两种"等级"：字段置信度（高/中/低，指**我读得准不准**）和缺口等级（A/B/C，指**不加假设能不能报价**）。

## 1. 给 Agent 的读取顺序

1. 本文件（流程 + 硬约束）；
2. `references/inquiry-categories.md` — 8 类字段、判定口径、易混案例；
3. `references/extraction-rules.md` — 切块、多语言锚点、单位、脏数据；
4. `references/chemical-standardization.md` — CAS、品名、规格、HS、DocSet 规范化；
5. `references/commercial-terms.md` — Incoterms 2020、付款、L/C、交期、有效期；
6. `references/missing-and-questions.md` — 缺口分级 + 英文问句库（按语言给原文问法）；
7. `references/reply-email.md` — 英文回复结构、占位符协议、语气、润色红线；
8. `references/writing-conventions.md` — 真实国际化工销售邮件的写作习惯（**生成邮件前必读**）；
9. `references/qa.md` — 交付前逐项打勾；
10. `references/failure-log.md` — 输出不对劲时先看这里。

**顺序不许反。** 先写邮件再倒推字段，缺失项一定会被"行文需要"填上。

## 2. 五条不可谈判的约束

1. **不产生价格。** 没有默认价、参考价、区间价、建议价、市场价、历史成交价。
   回复里价格位一律渲染成 `‹PRICE_PER_MT_CFR_SEMARANG›` 这样的显式占位符（术语与港口未定时统一用 `‹PRICE_PER_MT_TERMS_TBC›`），并在邮件正文外附「占位符清单」说明每一项要谁、何时填。
2. **不产生商务承诺。** 库存、船期、装运港、交期、付款条件、账期、单证清单、认证、样品费——
   客户没说的、我方没确认的，**都不能写成"我们可以提供"**。要么渲染成占位符，要么写进「待内部确认」区块。
3. **不补 CAS、不补公司、不补 HS。** CAS 号只能来自：客户原文、我方提供的产品资料、或权威库查证（Wikidata / PubChem / 官方名录），
   且必须记录来源与查证日期。**翻译品名时绝不用模型记忆填 CAS**（典型事故：棕刚玉被填成三氧化二铝 1344-28-1）。
4. **抽不到就留空。** 值只能是三态：`已明确`（有原文）/ `缺失`（客户没说）/ `歧义`（说了但不唯一）。
   「待客户确认」「我方假设」都不是值。允许的"假设"只有 B 类默认值，且**只能出现在渲染层**，必须带英文标注
   `(our assumption – to be confirmed)`。
5. **润色不许加料。** 用户贴来自写英文稿时，只能改语言，不能新增任何商务承诺（见 §6）。

## 3. 输入契约

| 输入 | 处理方式 |
|---|---|
| 邮件 `.eml` / `.txt` / 转贴正文 | 保留 From / To / Cc / Date / Subject / 正文 / 签名；签名里常有公司全称、电话、地址 |
| Outlook/Gmail 转发串 | 按 `From:…Sent:…` / `On … wrote:` 拆成"历史轮次"，只把**最新陈述**当有效数据，旧的留痕 |
| WhatsApp / WeChat / Line 截图 | 先 OCR 成"发送人：内容"逐行文本；语音条标"未转写"进 unreadable |
| RFQ PDF / Excel 需求表 | 文本型直接抽；扫描件先 OCR；表格保留表头，空白格就是空白 |
| Tender / P.O. 草稿 | 关键词是 `terms`、`required documents`、`validity`、`penalty`；条款性内容最容易漏 |
| 产品目录 / 规格书 / COA | 用来**校验**客户规格，不能用来替换客户规格 |
| 公司英文回复模板 | 有就用，没有用 `templates/` 里的 4 套默认模板 |
| 已有英文草稿 | 进 §6 润色通道，不进抽取通道 |
| 公司报价要求 | 只进「待内部确认」，不进邮件承诺 |

输入一律落到 `examples/…/input/` 式的素材块，编号后每条提取值挂它：

```text
素材01  客户邮件 .eml      2026-10-19 08:42 (+07:00)
素材02  历史邮件（转贴）    2026-10-15
素材03  RFQ 附件 .xlsx      2026-10-18（第 2 页有手写数量）
```

## 4. 流程（三处停下等人）

### 第 1 步 · 素材清点与证据编号

编号规则：`素材NN` 稳定不复用；每条提取值记录 `source_id` + `quote`（原句，原语言）+ `lang` + `locator`（行号/页码/时间戳）。

顺手标三类脏数据，进 `unreadable`：
- 数字被遮挡：`45? t`、`1?000 MT`；
- 语音条 / 图片未转写；
- 扫描件表格被裁切。

### 第 2 步 · 八类字段抽取（逐类抽，不跳类）

| 类 | 中 | 关键要素 | 桶 |
|---|---|---|---|
| A | Buyer & contact | 客户全称、国家、联系人、职位、邮箱、电话、WhatsApp、网站、地址 | A |
| B | Product & chemistry | 品名（原语言 + 英文）、CAS、EC、化学式、别称、产品形态 | A |
| C | Specification | 纯度/含量、关键杂质、粒度、堆密度、水分、外观、标准（GB/ASTM/ISO/客户内控）、TDS 版本 | A |
| D | Quantity | 试单量 / 年量 / 月量 / 单批量 / 年节奏 / 起始日 / 单位（MT vs t vs kg vs 包） | A |
| E | Delivery & Incoterm | 目的港/目的站、Incoterms 2020 术语 + 地点、装运港、运输方式、包装（类型/净重/托盘）、危险品信息 | A |
| F | Commercial | 币种、价格基础（per MT）、付款方式、L/C 类型与有效期、交期/装运期、报价有效期、是否含检测费、佣金/代理 | A |
| G | Documents & compliance | COA、SDS（MSDS）、TDS、原产地证（CO/FORM E/AK/E1）、IMO/DG 声明、检验报告（SGS/BV/CIQ）、第三方/客户审计、标签、语言版本 | A |
| H | Buyer-side context | 应用/工艺、现有供应来源、年采购规模、样品需求、首次/复购、时间压力、价格敏感度 | B |

**判定要点（完整版见 references）：**

- **产品**：原文 `soda ash dense granular` → 标准化 `Soda Ash Dense (Sodium Carbonate, Dense)`；
  `soda ash light` 与 `dense` **不得混用**（决定包装、用途、价格）。
- **规格**：客户给了数字就抄原话和单位（`Na2CO3 ≥ 99.2% min`、`Fe ≤ 0.003%`、`+80 mesh ≥ 75%`）；
  客户只说 `industrial grade / standard grade` → 规格 = `歧义`，不要自己补数字。
- **数量**：必须分清**试单量**（trial / first / 1 container）、**年量**（annual / per year）、**单批量**（per shipment / per vessel）。
  拿 L/C 数量当试单量、拿年量当首单量，都是最容易报错价的地方。
- **Incoterm**：务必拆开"术语"与"地点"：`CFR Semarang, Indonesia` ≠ `FOB`；`CIF Jakarta` 与 `CIF Tanjung Priok, Jakarta` 是两回事；
  客户写 `CNF` 要按 Incoterms 2020 规范化为 `CFR` 并在备注里保留 `CNF` 原词。
- **付款**：`L/C` 不等于 `irrevocable confirmed at sight L/C`；客户没写类型/有效期/开证行 → 付款条件 = `缺失部分`。
- **单证**：区分 `required`（客户已明说）与 `assumed`（"出口常见""应该要"）。**后者一律不写进邮件承诺**。

### 第 3 步 · 三桶分级 + 双栏核对

| 桶 | 含义 | 处理 |
|---|---|---|
| **A 类 · 报价前必须先确认** | 没有它做不出有效报价，或做出来会报错 | 缺一项就锁「生成报价」按钮，并进待确认问题清单 |
| **B 类 · 可带我方假设先准备** | 有其默认值，但邮件里必须标 `(our assumption – to be confirmed)` | 逐条标注，进「待客户确认事项」 |
| **C 类 · 我方内部先定** | 币种报价基础、含税/不含税（出口通常不含）、装运港、公司抬头与签字人 | **只能由我方选**，不从询盘单向推断 |

每行都要有：标准化值、原文依据、置信度、状态（已明确/缺失/歧义/假设）、是否影响报价。
HTML 里缺失与歧义黄色高亮，点击字段 → 左栏原文高亮并滚动定位。

> **第一次停下**：把双栏核对板交给销售逐项修正。修正值进 `overrides`，**不改原文**。

### 第 4 步 · 缺口清单 → 待确认问题（可直接发客户）

只问 A 类缺口 + 真歧义。每条问题必须：
- 是**封闭或半封闭问句**（客户能一句话回）；
- 带客户原话锚点（`You wrote "CFR Semarang" – may I confirm …`）；
- 同时给出**我方需要客户提供的东西**（`Could you provide the port of discharge (UN/LOCODE)…`）；
- 敏感项（价格、账期）不问客户"给多少"，只问"口径"。

问题库见 `references/missing-and-questions.md`，含中英印尼越葡西阿日七语言问法。

### 第 5 步 · 回复渠道选择（三种，不混用）

| 渠道 | 什么时候 | 输出 |
|---|---|---|
| **A · 确认式回复**（默认） | 缺关键参数，先不报价 | 确认收到 + 复述已理解 + 列确认问题 + 说明我方下一步 |
| **B · 报价回复** | A 类已齐、价格已由我方确认 | 报价结构 + 占位符 + 商务条件 + 有效期 |
| **C · 润色** | 用户已写英文稿 | 只改语言，输出改动清单 + 新增承诺检查 |

A/B 都要先选**语气**（`formal` / `friendly-professional` / `concise-direct`）与**模板**（`templates/` 4 套或公司模板）。

### 第 6 步 · 生成英文回复（占位符协议）

生成时遵守三条渲染规则：

1. 任何**数字型商务承诺**（价格、运费、交期、船期、库存、账期天数、样品费、有效期天数）→ 占位符；
2. 任何**我方尚未确认的单证/认证/服务** → 不承诺，改写为条件句或移入「待内部确认」清单；
3. 客户原话的**事实复述**可以直接写（`You asked for 300 MT dense soda ash`）。

占位符命名与清单见 `references/reply-email.md` §3；脚本层还有一道闸：
`reply.json` 中 `placeholders` 里任何一项 `status != confirmed_by_us` 时，`build_md.py --pack` 拒绝生成可发送版（exit 3）。

> **第二次停下**：把占位符清单交给销售/商务确认，逐项填值。

### 第 7 步 · 交付与审阅

- HTML 双栏审阅板（单文件离线）：左原文 + 右结构化字段 + 缺失 + 待确认 + 回复草稿（可编辑、可复制）+ 润色模式 + 「交给下游场景」导出；
- Excel 7 表：`01 询盘概要` / `02 标准化字段` / `03 原始询盘` / `04 缺失与歧义` / `05 待确认问题` / `06 英文回复草稿` / `07 证据与素材`；
- `回复_<客户>.md`：可直接复制的英文正文（占位符可见）；
- `fields.json` / `reply.json`：系统对接；
- `中文简报_<客户>.md`：给老板/同事的 30 秒版。

### 第 8 步 · 润色通道（§6 的落地）

用户贴自写稿 → 不重写结构、不换观点、不新增承诺 → 输出「润色后」+「改动清单（原文→改后→理由）」+「新增承诺检查：无 / 发现 N 处，已回退」。

## 5. 润色红线（硬约束）

| 不许做 | 正确做法 |
|---|---|
| 把 `We can supply` 改成 `We are pleased to offer at USD ‹PRICE›` | 保留原意，只改措辞 |
| 用户没写交期，润色时补一句 `Delivery within 20 days` | 不补；或提示"你的稿里没有交期，是否要加占位符？"（需用户点头） |
| 用户写 `best price`，润色时换成 `competitive price` 并加 `we guarantee` | 只改语言，不加保证性承诺 |
| 用户写 `please pay in advance`，润色成 `100% T/T before shipment, non-negotiable` | 保留语气强度，不升级为不可协商 |
| 润色时"顺手"改了数量/规格/港名 | 事实值一律不动；怀疑有误只提示，不修改 |

改动清单里每一项都要能回答："这句改完，承诺变多了吗？" 变多了就回退。

## 6. 命令速查

```bash
PY="<python 3.9+>"; S="scripts"; EX="examples/example-1-id-soda-ash-dense"

# 1) 回复前自检：缺口 + 问句 + 占位符清单 + 承诺扫描（不产价）
$PY $S/extract.py --email "$EX/input/询盘邮件.eml" --fields "$EX/fields.json" --emit out/

# 2) 双栏审阅板（单文件离线 HTML）
$PY $S/build_workbench.py "$EX/fields.json" "$EX/reply.json" -o 询盘审阅板.html

# 3) 7 表 Excel 工作簿
$PY $S/build_xlsx.py "$EX/fields.json" "$EX/reply.json" -o 询盘工作簿.xlsx

# 4) 独立可复制英文草稿（--pack 会检查占位符是否已由我方确认）
$PY $S/build_md.py "$EX/fields.json" "$EX/reply.json" -o 回复_客户.md --pack

# 5) 润色自写稿：承诺扫描 + 改动建议
$PY $S/polish.py 我的稿.txt --lang en --report polish.json

# 6) 交付自检（产物齐全 / 字段有依据 / 无承诺 / 占位符登记 / HTML 无外链）
$PY $S/selfcheck.py "$EX"                 # 检查一个示例
$PY $S/selfcheck.py --skill .             # 发布前检查技能包结构

# 7) 浏览器自测（无头 Edge/Chrome，无第三方依赖；找不到浏览器会自动跳过）
node $S/selftest_workbench.mjs "$EX/04_询盘审阅板.html"

# 8) 一键重建一个示例的全部产物（推荐给新同学）
$PY $S/make_example.py examples/example-1-id-soda-ash-dense
$PY $S/make_example.py examples --all
```

## 7. 交付物

| 文件 | 内容 | 什么时候用 |
|---|---|---|
| `04_询盘审阅板.html` | 左原文右字段、点击定位、修正、语气/模板切换、回复编辑与复制、缺失与待确认、下游场景跳转 | 主战场；浏览器直接开，纯前端，素材不出本机 |
| `05_询盘处理工作簿.xlsx` | 8 表（阅读说明 + 上面 7 表），可直接走内部评审/转同事 | 需要留痕、审批、交接 |
| `03_英文回复草稿.md` | 英文正文 + 占位符清单 + 内部备注 | 贴进 Outlook 发送 |
| `01_标准化字段.json` / `02_英文回复草稿.json` | 结构化字段与回复 | 系统对接、二次加工 |
| `06_中文缺口简报.md` | 一页中文说明 | 给老板/未读原文的同事 |

## 8. 失败模式（踩过的坑）

| 症状 | 根因 | 改法 |
|---|---|---|
| 邮件里出现一个没人确认过的价格 | 为了"看起来完整"填了占位价 | 占位符 + `--pack` 闸门；占位价一律禁止 |
| 把 `soda ash light` 回复成 dense | 品名只按"soda ash"匹配 | 品名词表长词优先，形态词单独成字段 |
| 客户写 `industrial grade`，回复里出现 `≥99.2%` | 拿我方常规规格当客户规格 | 规格只能来自客户原话或"我方建议，请确认" |
| 回复里写了 `COA, MSDS, CO, and Form E will be provided` | 把"出口常规"当客户要求 | 单证只承诺客户**明说且我方确认**的 |
| `CFR Semarang` 被写成 `CIF Semarang` | 术语与地点混写 | 术语、地点、是否含保险三件套分开抽 |
| 翻译品名后 CAS 号变了 | 用模型记忆填 CAS | CAS 必须带来源字段；查不到就留空并标"待我方产品资料确认" |
| 客户是中间商，被我方当成终端厂 | 没抽"公司类型/是否最终用户" | H 类必抽 `end_user_or_trader`，只标"未明确"，不下结论 |
| 润色后客户权益变多了 | 润色时"优化"了商务语言 | 改动清单逐条问"承诺变多了吗" |
| 给客户打了"真实性 85 分" | 越界 | 本技能禁止任何真实度/成交概率评分 |

## 9. 文件地图

| 文件 | 什么时候看 |
|---|---|
| `references/inquiry-categories.md` | 8 类字段定义、三桶、易混案例 |
| `references/extraction-rules.md` | 切块、多语言锚点、单位换算边界、脏数据 |
| `references/chemical-standardization.md` | CAS/品名/规格/HS/DocSet 规范化 |
| `references/commercial-terms.md` | Incoterms 2020、付款与 L/C、交期与有效期 |
| `references/missing-and-questions.md` | 缺口分级矩阵 + 七语言问句库 |
| `references/reply-email.md` | 邮件结构、占位符协议、语气、模板占位符 |
| `references/writing-conventions.md` | 真实国际化工销售邮件怎么写（长度、称呼、复述、承诺句） |
| `references/qa.md` | 交付前打勾 |
| `references/failure-log.md` | 输出不对劲 |
| `products/*.json` | 换品类时的标准化词表与规格画像 |
| `templates/workbench.template.html` | HTML 审阅板模板（纯前端） |
| `templates/reply_*.md` | 4 套默认英文回复模板 |
| `INSTALL.md` / `AGENTS.md` / `PORTABLE_PROMPT.md` | 移植到别的 agent |

## 10. 示例

- `examples/example-1-id-soda-ash-dense/` — **印尼玻璃厂 · 重质纯碱**（主案例，本轮交付对象）：
  英文邮件、CFR Semarang、300 MT + 年量、Na2CO3 ≥ 99.2% / Fe ≤ 0.003% / +80 mesh ≥ 75%，
  故意缺：付款方式、报价有效期、样品要求细节、卸货条件、公司全称核验、是否需要第三方检验。
- `examples/example-2-vn-caustic-soda-vi/` — **越南经销商 · 烧碱片碱（越南语询盘）**：
  多语言 + `FOB` + `L/C` + 包装冲突（客户一处写 25kg、一处写 1000kg）+ 数量单位混用（kg 与 MT）。
- `examples/_skeleton/` — 空白骨架，换品类时整目录复制，把 `input/` 换成客户真邮件。

每个示例目录里都有一份**已跑通的产物**（01–07），可以直接打开看效果，也可以当交付样式参考：
`04_询盘审阅板.html`（双栏审阅板）、`05_询盘处理工作簿.xlsx`、`03_英文回复草稿.md`、`06_中文缺口简报.md`。
