---
name: overseas-supplier-verification
description: >
  Use when a Chinese importer / chemical buyer needs to verify an overseas supplier before
  contracting or paying — 核验海外供应商 / 供应商背景调查 / 这家公司是不是真的生产商 /
  帮我查一个国外供应商 / 收到 PI 但收款方和合同方不一样 / 供应商说是工厂但查不到厂.
  Covers entity identification (registration, legal name, address), product-fit checks,
  manufacturer-vs-trader determination, plant and manufacturing evidence, website /
  e-mail / bank consistency, public risk screening (sanctions, litigation, supply
  interruptions, trade remedies), cross-checking uploaded PI / CR / SDS / COA / catalogue,
  and issuing an English due-diligence enquiry list. Works for any country, any chemical
  product and any supplier type. Delivers an interactive HTML dossier, an 8-sheet Excel
  workbook and a supplier record that feeds downstream import-cost / document checks.
  Never outputs a risk score.
allowed-tools: web_search, web_fetch, research, advanced_search, platform_search, domain_search, read, write, edit, pwsh
---

# 海外供应商核验（Overseas Supplier Verification）

> 一句话：**先把「谁在签合同、谁在生产、谁在收钱」这三件事分开查清楚，再谈价格。**
> 本 Skill 的中心原则：**只陈述可追溯的事实与状态，不给风险分数。**

---

## 0. 什么时候用

| 触发场景 | 典型说法 |
|---|---|
| 拿到一家海外供应商，准备询价/签约 | 「帮我核一下这家印度/沙特/土耳其供应商」 |
| 拿到 PI，但觉得哪里不对 | 「收款人和合同方不一样」「邮箱看着怪」 |
| 供应商自称工厂 | 「说是自有工厂，但官网找不到」 |
| 采购前合规审查 | 「这家有没有被制裁/有没有诉讼」 |
| 上传了注册证书/SDS/COA | 「这几个文件你帮我看看对不对得上」 |

**不适用**：国内供应商准入（用内贸线）、价格行情（用行情 Skill）、合同条款审查（用合同审阅 Skill）。

---

## 1. 第一原则（读取本 Skill 的模型必须遵守）

1. **不给分数**：不输出风险分、信用评级、"低/中/高风险"标签。用五态词：`已核实 / 存在疑点 / 未核实 / 未知 / 不适用`。
2. **宣传 ≠ 证据**：官网/宣传册上的话，任何公司都能写。只有带标识符的（CR 号、许可证号、证书编号、批号、装置名、可查产品页）才算证据。
3. **差异 ≠ 欺诈**：收款主体与合同主体不一致，是「必须验证的阻断项」，不是「欺诈认定」。必须写清"需要进一步验证"。
4. **未知照写**：查不到就写「未知」，并给出补件动作。**不要用推测填空**。
5. **不认定三件事**：真实产能、资金实力、履约能力——这三件事公开信息几乎无法证明，只能用文件与交易结构去约束。
6. **区分法人**：同集团不同公司（生产公司 / 销售公司 / 出口公司 / 收款方）是常态，名字像不等于同一主体。
7. **每条结论挂证据**：证据 ID → 来源 → 发布时间 → 原文摘录 → 用途 → 局限。二手来源只能作线索。

---

## 2. 工作流程（七步）

```
① 识别主体 → ② 查注册与身份 → ③ 查产品匹配 → ④ 查制造关系
          → ⑤ 查官网与联系一致性 → ⑥ 查公开风险 → ⑦ 比对文件 + 出询证单
```

### ① 识别主体（先做，永远先做）
拆成四层，**逐层找证据**，不要跳层：

| 层 | 问什么 | 常见证据 |
|---|---|---|
| 股东层 | 最终控制人是谁？国有/民营？ | 上市公司公告、年报股权结构 |
| 集团层 | 是否属于某集团？集团产品线覆盖？ | 集团官网产品页、年报 |
| 生产层 | 哪家法人真正生产？工厂在哪？ | 工业许可证、装置投产新闻、行业数据库 |
| 交易层 | 谁签合同、谁发货、谁收钱？ | PI 抬头、B/L 发货人、付款指令 |

> 详见 `references/entity-mapping.md`

### ② 查注册与身份
按国家找**官方登记源**（`references/country-registries.md` 给出 30+ 国家的查询入口与所需编号格式）：
法定名称 / 注册号（CR、Company No.、GSTIN、统一社会信用代码等）/ 注册地址 / 法人形式 / 存续状态 / 经营范围。
- 拿不到官方登记 → 标「未知」，**不要把第三方名录当官方登记**。
- 官网公布的注册号是**一手证据**（企业自述但可被第三方复核，如上市公司）。

### ③ 查产品匹配
产品目录里**有没有这个产品**、**有没有这个等级/规格**、**能不能对上包装与运输形态**。
缺等级名或缺 TDS → 「未核实」。集团有产品 ≠ 这个厂卖给你这个规格。

### ④ 查制造关系（最容易出问题的一步）
要回答的不是"它是不是大公司"，而是**"这批货是不是它生产的"**。
把"自称生产商"拆成四类，分别取证：

| 身份 | 取证要点 |
|---|---|
| 实际制造商 | 装置名 + 工业许可证 + 产能表 + 批号级 COA |
| 集团销售公司 | 集团股权文件 + 生产公司授权 |
| 授权经销商 | 生产商授权书（写明产品、区域、有效期） |
| 一般贸易商 | 披露真实货源 + 生产商供货确认 |

> 详见 `references/manufacturing-evidence.md`

### ⑤ 查官网与联系一致性
域名、邮箱、电话、地址、开户行是否指向**同一个法人**。
**近似域规则**（必查）：`petrokemya-sabic.com` ≠ `sabic.com`；换 TLD；免费邮箱冒充企业；同形字符。
落入任一 → 停止用该邮箱谈交易，改由官网公布渠道回呼。

### ⑥ 查公开风险（只列事实）
制裁名单、出口管制、司法诉讼/破产、行政处罚、供应中断（不可抗力/停产/检修）、贸易救济（反倾销/反规避）、负面报道。
**「未检索到」不等于「不存在」**，必须写明检索了哪些名单、用什么标识符、什么时间。

### ⑦ 比对文件 + 出询证单
逐件核对：PI / 注册证书 / 产品认证 / SDS / COA / 形式发票 / 银行信息 / 名片 / 公司介绍。
每条给「✓ / ✕ + 说明」。缺失的进补件清单。
最后生成 **英文询证清单**（`references/rfi-standard.md` 有 14 条标准条款），可直接发给供应商。

---

## 3. 五态结论口径

| 状态 | 含义 | 判定门槛 |
|---|---|---|
| **已核实** | 事实成立 | 官方/监管来源，或 ≥2 个相互独立来源交叉印证 |
| **存在疑点** | 来源矛盾，或差异需解释后放行 | 至少 2 个来源说法不一致，或单据间要素冲突 |
| **未核实** | 有说法但证据不足 | 仅单一来源，或仅企业自述 |
| **未知** | 检索后没有可引用来源 | 明确记录检索范围 |
| **不适用** | 该国不存在对应制度 | — |

**总体结论（四选一）**：`仅识别身份` / `可推进但需补证` / `暂停推进` / `证据不足`。
> 详见 `references/evidence-grading.md`

---

## 4. 产出物

```
out/
├── 海外供应商核验报告_<产品>_<供应商>_<日期>.html   ← 交互式报告（自包含单文件）
└── 海外供应商核验报告_<产品>_<供应商>_<日期>.xlsx   ← 8 个工作表
```

**HTML 报告**（`assets/report-template.html` 是可直接打开的样式样板）：
区块顺序 = `企业身份 → 产品能力 → 工厂与生产证据 → 官网与联系信息 → 交易主体一致性 → 公开风险 → 文件核验 → 待索取材料`，
另加 `主体映射表 / 证据索引 / 时间轴 / 英文询证清单`。
交互：按状态筛选、页内搜索、点击证据编号弹出原文抽屉、打印导出 PDF。

**Excel 工作簿**（8 表）：

| 表 | 名称 | 内容 |
|---|---|---|
| 00 | 封面与结论 | 结论口径、状态计数（公式）、不下的结论 |
| 01 | 企业信息 | 身份要素逐项 + 主体档案 |
| 02 | 制造证据 | 工厂/产能/制造关系 + 主体映射 + 证据索引 |
| 03 | 产品匹配 | 产品与规格匹配逐项 |
| 04 | 文件核验 | 逐件文件 + 逐项检查 ✓/✕ |
| 05 | 交易主体一致性 | 核对矩阵 + 交易四象限 |
| 06 | 公开风险与事件 | 风险事实 + 事件时间轴 |
| 07 | 待确认事项与询证 | 缺口清单 + 英文询证表（可勾选回填） |

---

## 5. 怎么跑

```bash
# 1) 复制模板，按 references/data-contract.md 填内容
cp templates/project.template.json my-project.json

# 2) 校验（阻断项必须清零）
python scripts/validate.py my-project.json --strict

# 3) 一键生成 HTML + Excel
python scripts/build_all.py my-project.json -o out/
```

依赖：Python ≥ 3.9；Excel 需要 `openpyxl`（缺失时只出 HTML）。
**没有 Python 也能用**：把 `SKILL.md` + `references/` 作为方法读，按 §2 七步手写出结论结构化 JSON；HTML 可基于 `assets/report-template.html` 手工替换。

---

## 6. 质量闸门（交付前自检）

- [ ] 7 个必备区块齐全，每块都有状态与证据
- [ ] 每个「已核实」都有官方来源或 ≥2 独立来源
- [ ] 模拟件全部明确标注「模拟」，且**没有**被当成真实事实引用
- [ ] 收款主体不一致处写明「需进一步验证」，**没有**写"欺诈/骗子"
- [ ] 没有出现任何风险分数、评级或"低风险"表述
- [ ] 所有「未知」都对应一条补件动作（Gap Register）
- [ ] 英文询证清单 ≥ 14 条，覆盖 主体/收款/工厂/产品/文件/合规
- [ ] `validate.py --strict` 通过

> 完整清单见 `references/qa-checklist.md`

---

## 7. 文件地图

```
overseas-supplier-verification/
├── SKILL.md                        ← 本文件（平台入口）
├── README.md                       ← 安装、首次运行、故障排除
├── CHANGELOG.md
├── references/
│   ├── method.md                   ← 七步法详版（含判断分支）
│   ├── entity-mapping.md           ← 四层主体拆解 + 同集团不同法人陷阱
│   ├── evidence-grading.md         ← 五态门槛 + 证据分级 + 冲突处理
│   ├── country-registries.md       ← 30+ 国家官方登记入口与编号格式
│   ├── manufacturing-evidence.md   ← 制造关系取证（工厂/产能/授权链）
│   ├── document-checks.md          ← PI/CR/SDS/COA/银行信息 逐项核对清单
│   ├── risk-screening.md           ← 制裁/司法/供应中断/贸易救济 检索法
│   ├── rfi-standard.md             ← 14 条标准英文询证条款（可复用）
│   ├── data-contract.md            ← project.json 字段规范
│   └── qa-checklist.md             ← 交付前自检
├── scripts/
│   ├── ovslib.py / validate.py / build_html.py / build_xlsx.py / build_all.py
├── templates/
│   └── project.template.json       ← 可运行的空模板
├── assets/
│   └── report-template.html        ← 无 Python 时可直接改的 HTML 样板
└── examples/
    ├── example-01-saudi-meg/       ← 完整案例：沙特 MEG（生产商，含模拟 PI）
    └── example-02-saudi-tradeco-mock/ ← 反例：贸易商自称生产商
```

---

## 8. 边界声明

本 Skill 输出的是**采购决策辅助材料**，不是法律意见、审计结论或信用报告。
不替代：海关 AEO 验证、第三方工厂审核、银行资信调查、律所尽调、原产地核查。
付款前的一切结论，都必须建立在「主体 + 收款 + 单据」三者闭环之上。
