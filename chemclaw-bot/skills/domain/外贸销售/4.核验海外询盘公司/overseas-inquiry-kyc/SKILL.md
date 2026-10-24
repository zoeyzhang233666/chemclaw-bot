---
name: overseas-inquiry-kyc
description: Use when an overseas customer sends an inquiry and the sales rep must know whether the counterparty is real before quoting, producing, or shipping — 核验海外询盘公司 / 海外询盘企业核验 / 询盘方是否真实 / 客户背调 / 外贸客户资质核验 / 验公司 / 对方是不是真买家 / inquiry KYC / overseas buyer due diligence / verify overseas inquiry company. Product-agnostic and country-agnostic: soda ash, TiO2, solvents, resins, fertilizers, battery materials, food additives, machineries — Indonesia, India, Vietnam, Turkey, Brazil, etc. Delivers one self-contained interactive HTML report plus a 14-sheet Excel workbook generated from one inquiry.json, splitting every finding into 已核实 / 存在疑点 / 未核实, each bound to a clickable source and a concrete next-step document request, with ready-to-send English messages.
license: MIT
compatibility: Python 3.9+ with openpyxl>=3.1. No network at build time; all data, CSS and JS are inlined. playwright is optional and only for render QA.
metadata:
  version: 1.0.0
  author: chemclaw-skill-library
  output: [html, xlsx, json]
  languages: [zh-CN, en]
  category: foreign-trade-inquiry-kyc
---

# 核验海外询盘公司（Overseas Inquiry KYC）

把"这家海外公司是真的吗"拆成**可以逐条回答的核验项**：哪些成立、哪些对不上、哪些查不到、还差哪份材料。

适用于任何化工品和任何国家。方法与产品无关、与国别无关——**只有"这个国家去哪查"和"这个产品什么算合理业务"需要替换**，见 [`references/country-playbook/`](references/country-playbook/) 与 [`references/product-fit-rules.md`](references/product-fit-rules.md)。

整件事只有一个原则：

> **证据不混层，缺失不越界。** 对外宣称、"查不到"、"互相矛盾"是三种完全不同的东西，永远不能写成同一句话。

---

## 六条不可谈判的约束

1. **三分法，不许合并。** 每条核验结论只能是 `已核实` / `存在疑点` / `未核实` 之一。
   「未核实」是本 skill 最常用的结论，也是最容易被销售"顺手改写"的一项——不许改。
2. **查不到 ≠ 虚假。** 公开渠道没有登记资料是常态（很多国家要付费、要 NIB 号、要本地代理）。
   **不得**把"检索无结果"写成"企业不存在 / 空壳 / 虚假"。
3. **"存在疑点"必须有具体矛盾。** 写清是哪个字段和哪个字段对不上（名称拼写？地址行政区？规模口径？资料前置条件？），
   并同时写 `boundary`：为什么它还不算致命。只写"感觉可疑"的疑点一律不合格。
4. **不给概率、不判动机。** 不出现"诈骗概率 30%""大概率是骗子"。本 skill 只列**可核对的事实与矛盾**。
5. **不以域名注册时间判真伪。** 域名新/旧、网站好坏、邮箱是 gmail 还是企业域名，**单独都不构成判据**，
   最多作为"发信基础设施是否正规"的佐证项。同理：名片、公司介绍 PDF、官网"since 1998"，都只是 D 级自述。
6. **同名企业严格隔离。** 只有唯一标识（登记号 / NIB / 统一社会信用代码 / LEI / SWIFT / 税号）相同，
   才允许把两处信息合并到同一主体。名称相同、域名相似、Logo 相似、城市相同——都不够。

---

## 什么时候用 / 什么时候不用

**用**

- 收到海外询盘，要决定"能不能报价""要不要先要资料""能不能给他账期"；
- 客户自称"我们做过 20 年、有两座窑、年采购 2 万吨"，需要核实这些自述；
- 对方要求先签 NDA 才给证照，需要判断这是流程问题还是风险信号；
- 老客户换了联系人 / 换了收款账户 / 换了公司抬头，需要复检；
- 老板问"这个印尼客户靠不靠谱"，需要一份能拿出去的书面记录。

**不用**

- 只要报价、算价格、做 PI（用报价类 skill）；
- 只要查产品出口要求 / HS 编码（用合规类 skill）；
- 需要法律尽调结论、资信评级、征信报告、反洗钱最终判定（本 skill 只做到"可核对的公开信息 + 缺口清单"）；
- 想拿到"对方是不是骗子"的结论——本 skill 不给，也不建议任何工具给。

---

## 输入

### 必填

| 要素 | 说明 | 示例 |
|---|---|---|
| 询盘原文 | 邮件正文/EML/截图，越原始越好 | 含签名档的完整邮件 |
| 我方产品 | 名称 + 规格/形态 | 重质纯碱 Na₂CO₃ ≥99.2%、吨袋 |
| 询盘要素 | 数量、交期、贸易术语、目标港 | 25,000 MT/年，CFR Tanjung Priok |
| 核验基准日 `as_of` | 谁在哪天查的 | 今天 |

### 选填

名片、公司介绍 PDF、网站截图、营业执照/注册证、对方提供的银行资料、产品询价单、
我方已有的交易历史、该国的特殊要求（是否要求本地代理、是否涉及制裁）。

### 缺输入时

**不要停下来空等。** 先用现有材料把 `extraction` 跑完整，把缺的项写进 `requests`（P0 优先），
并用 `examples/` 里的模拟样例跑通流程，把"待对方回复"当正常状态交付。

---

## 输出

| 交付物 | 内容 | 硬要求 |
|---|---|---|
| `*_核验报告.html` | 单文件交互报告：封面结论、询盘原件（带模拟水印）、字段提取、注册主体、业务相关性、联系方式一致性矩阵、24+ 条可筛选核验结论、风险、资料清单、英文话术、三分结论、来源库 | 离线可开；状态/区块可筛选；来源可点开；可打印 |
| `*_核验工作簿.xlsx` | 14 个表：封面 / 询盘原文 / 字段提取 / 注册主体 / 业务相关性 / 联系方式一致性 / 核验结论 / 公开风险 / 待索取资料 / 行动清单 / 状态透视 / 来源库 / 英文话术 / 方法与边界 | 每表有标题、筛选、状态底色；`08_待索取资料` 可直接抄 English 发给对方 |
| `inquiry.json` | 唯一数据源，可复核、可复现 | 过 `validate.py` |
| `build_report.json` | 构建回执：校验结果、产物 sha256、统计 | 由 `build_all.py` 生成 |

文件命名建议：`{国家}_{产品}_{客户简称}_核验报告.html`。

---

## 七步流程

### Step 0 · 收料与打标（5 分钟）

先确定这份材料是什么：**真实询盘** 还是 **演示/模拟**。

- 真实询盘：`meta.synthetic = false`。
- 演示、培训、样例：`meta.synthetic = true`，并写 `synthetic_note` 说明哪些字段是虚构的。
  **真实企业不得被写成"曾向我们发过询盘"**——可以把真实企业作为"公开资料研究对象"，
  但询盘主体必须虚构，且页面必须有模拟横幅。

### Step 1 · 提取字段（只看"对方说了什么"）

把邮件拆成 `extraction[]`：公司名、地址、网站、域名、邮箱、联系人、职位、电话、产品、规格、数量、
交付条款、付款方式、**每一句背景自述**（成立年份、产能、工厂数量、仓库、客户）。

每条写 `evidence`（原文哪一句）+ `confidence` + `note`（哪里需要小心，例如"PT 前缀要逐字比对"）。

> 提取阶段**不做判断**。看到矛盾也只写进 `note`，结论留到 Step 3。

### Step 2 · 定位主体（本 skill 最关键的一步）

```text
邮件里的公司名
   ├─ 去掉贸易称谓（PT / Co., Ltd. / S.A. / LLC / GmbH）
   ├─ 在「登记册」检索全称 → 命中条目（含登记号、成立日、注册地址、经营范围）
   ├─ 在「营业执照类平台」用唯一号（NIB / 税号 / 关税号 / CNPJ / GSTIN）反查
   └─ 三项互相对齐 → 才能说"这个主体存在且是它"
```

各国的入口见 [`references/country-playbook/`](references/country-playbook/)。
印尼：AHU Online + OSS/NIB + NPWP；印度：MCA21 + GSTIN；越南：National Business Registration Portal + MST；
土耳其：MERSIS / Ticaret Sicil Gazetesi；巴西：Receita Federal CNPJ + Junta Comercial。

**没有唯一标识时，只能写"未核实"，不能写"存在"。**

### Step 3 · 五区块核验（写 `checks[]`，建议 16–30 条）

| 区块 | 要回答什么 | 典型条数 |
|---|---|---|
| **A 身份** | 是否真实存在？名称与登记是否一致？有无同名企业？自述背景能否印证？ | 5 |
| **B 业务** | 主营/产品目录/经营活动和询价产品相关吗？KBLI/NAICS 分类对得上吗？规模口径算得通吗？ | 5 |
| **C 联系方式** | 官网、域名、邮箱、地址、电话五项是否自洽？发信是否可核？ | 6 |
| **D 风险** | 经营异常、诉讼、制裁、负面报道、收款路径。 | 6 |
| **E 缺口** | 现有资料够不够支撑报价与合同？缺什么、按什么顺序要？ | 2–4 |

每条必须写全：

```text
id / section / title / question
status          verified | discrepancy | unverified
severity        high | medium | low      （仅 discrepancy 必填）
finding         一段话，说"我看到什么"，不说"我觉得"
verified_facts  已核实的事实（列表）
doubts          疑点 —— 必须是具体矛盾（列表）
unknowns        无法确认的项（列表）
boundary        边界说明：为什么这个结论不能往前推一步
source_ids      来源 ID（verified 必填）
next_ids        绑定的资料索取项
action          下一步动作
```

### Step 4 · 联系方式一致性矩阵（写 `matrix[]` + `email_auth[]`）

把每一个"同一个事实的不同说法"并排放：公司名（邮件 vs 官网 vs 登记）、域名 vs 公司名、
邮箱域 vs 官网 Contact 页、签名地址 vs 注册地址 vs 工厂地址、电话（手机 vs 总机）……

比对结果只有五种：`一致` / `部分一致` / `不一致` / `无法比对` / `疑似错配（同名/异主体）`。

`email_auth[]` 单独检查 SPF、DKIM、DMARC、Reply-To 跳转、Received 链——
**这些是佐证，任何一项缺失都不能单独判为造假**。

### Step 5 · 风险与资料清单（`risks[]` + `requests[]`）

风险分三段写：**事实（看到什么）→ 影响（影响我方什么）→ 动作（谁来做什么）**。
不要写"有一定风险"这种不落地的句子。

资料清单按"能否独立证明主体"排序：

- **P0**：登记号 / NIB / 营业执照 / 官网 Contact 页 / 公司总机 —— 决定"能不能报价"；
- **P1**：经营范围分类、产能数据、合同主体与收货人一致性、付款账户 —— 决定"怎么报价"；
- **P2**：技术问卷、品牌偏好、验厂 —— 报价后再补。

每条都要有 `en`（英文原文，可直接发给对方）和 `why`（为什么需要）。

### Step 6 · 行动与话术（`actions[]` + `messages[]`）

行动给到"谁、什么时候、做什么"；话术至少三段：

1. **首次索取**（礼貌 + 标准化 + 给替代路径）
2. **追问业务规模**（用"匹配合适等级与包装"解释为什么问）
3. **NDA 前置的回应**（不拒绝 NDA，只把"证照"与"商业机密"拆开）

另外建议一段"资料收到后的闭环确认"（先说核对了什么，再列未闭合项）。

### Step 7 · 出结论 + 自检

结论**不由你自由发挥**，由 `verdict_line` 规则生成：

```text
有 high 级疑点            → 暂停报价与发运，先完成 P0 资料核验
有疑点但无 high           → 可继续沟通并同步补齐资料
无疑点但有未核实          → 适合继续沟通并索取补充资料
全部已核实                → 公开信息范围内未发现矛盾（仍需保留单据与复核）
```

然后跑：

```bash
python scripts/validate.py inquiry.json
python scripts/build_all.py inquiry.json outdir --name 前缀
python scripts/selfcheck.py inquiry.json --outdir outdir
```

---

## 数据契约（`inquiry.json`）

```text
meta            title / as_of / synthetic / synthetic_note / disclaimer / product / quantity ...
inquiry         原文邮件（subject/from/to/date/body_lines/attachments/notes）
extraction[]    提取字段（X01…）：field, value, evidence, confidence, note
subject         主体识别：registry_check, nib_oss, npwp_tax, customs_id, summary_rows[]
domains[]       域名核验：resolve, whois, website, ssl, mx, note
email_auth[]    发信认证：item, observed, expected, mismatch, note
matrix[]        一致性矩阵：item, claimed, other, mismatch, note
business_fit    headline, product_use, demand_math[], keywords[]（KBLI 等）, signals[]
checks[]        五区块核验（K01…）—— 见 Step 3
linkage[]       同名/错配排查：name, relation, detail, rule
risks[]         风险（R01…）：category, severity, status, fact, impact, action, source_ids
sources[]       来源库（SRC01…）：name, org, url, grade(A/B/C/D), kind, date, retrieved, note
requests[]      资料清单（Q01…）：priority(P0/P1/P2), category, zh, en, why
actions[]       行动（T01…）：phase, action, detail, owner, priority, status
messages[]      英文话术（MSG01…）：title, purpose, body_en, notes
boundaries[]    使用边界（至少 3 条）
```

完整字段说明见 [`references/data-schema.md`](references/data-schema.md)；
最小可跑骨架见 [`templates/inquiry.skeleton.json`](templates/inquiry.skeleton.json)。

---

## 换国家 / 换产品怎么改

**换国家**：只改 `subject` 的检索入口 + `sources` 里的官方链接 + `requests` 里的"要哪份证照"。
核验框架、矩阵结构、三分法、话术结构全部不变。见 [`references/country-playbook/`](references/country-playbook/)。

**换产品**：只改 `business_fit`。要替换的是"这个产品什么算合理业务"：
谁买、买来干什么、吨级/单量级怎么算、什么规格是行业惯例、什么规格缺失该补。
见 [`references/product-fit-rules.md`](references/product-fit-rules.md)。

---

## 文件索引

| 文件 | 用途 |
|---|---|
| [`references/00-quickstart.md`](references/00-quickstart.md) | 从一封邮件到两份附件的 30 分钟路径 |
| [`references/research-playbook.md`](references/research-playbook.md) | 检索式、官方入口、查不到怎么办、印尼语/西班牙语关键词 |
| [`references/evidence-grading.md`](references/evidence-grading.md) | A/B/C/D 证据分级与"自述不能进结论"的判定 |
| [`references/verdicts.md`](references/verdicts.md) | 三分法的边界案例：什么该写疑点、什么只能写未核实 |
| [`references/mismatch-rules.md`](references/mismatch-rules.md) | 联系方式一致性的 12 类矛盾与处置 |
| [`references/request-materials.md`](references/request-materials.md) | 资料清单模板 + 英文话术骨架 |
| [`references/data-schema.md`](references/data-schema.md) | `inquiry.json` 逐字段说明 |
| [`references/product-fit-rules.md`](references/product-fit-rules.md) | 纯碱/钛白粉/溶剂/树脂/化肥/锂电材料的业务相关性口径 |
| [`references/portability.md`](references/portability.md) | 装到另一台机器 / 另一个 Agent |
| [`references/qa.md`](references/qa.md) | 交付前逐项打勾 |
| [`references/failure-log.md`](references/failure-log.md) | 输出不对劲时按症状找处方 |
| [`references/country-playbook/idn.md`](references/country-playbook/idn.md) | 印尼（AHU / OSS / NIB / KBLI / NPWP） |
| [`references/country-playbook/generic.md`](references/country-playbook/generic.md) | 其它国家的通用五步法 |
| [`examples/id-soda-ash-demo/`](examples/id-soda-ash-demo/) | 印尼重质纯碱**模拟**询盘完整案例 |

## 示例

| 案例 | 产品 / 国家 | 演示重点 |
|---|---|---|
| `examples/id-soda-ash-demo` | 重质纯碱 / 印度尼西亚 | 24 条核验（4 已核实 / 2 疑点 / 18 未核实）；模拟询盘邮件与名片；AHU+NIB+KBLI 口径；地址与规模两处口径矛盾；NDA 前置的处置；四段英文话术 |
| `examples/_skeleton` | 任意 | 空白骨架，复制即用 |

> 示例中的 `PT Sinar Kaca Nusantara`、`sinarkacanusa.co.id`、联系人、地址均为**虚构**，
> 仅用于演示方法；报告内不含任何对真实企业的询盘指控。

---

## 边界

本 skill 输出的是**公开信息核验辅助材料**，不是法律尽调、资信评级或反洗钱最终结论。
所有"未核实"必须以对方提供的证照、银行资料、第三方核验或现场审核为准；
最终是否交易、是否给账期，由业务与风控决策，不由本报告决定。
