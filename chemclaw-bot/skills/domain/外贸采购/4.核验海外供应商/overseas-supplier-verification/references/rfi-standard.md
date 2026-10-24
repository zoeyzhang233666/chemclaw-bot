# 标准英文询证清单（Supplier Due-Diligence Enquiry）

> 可直接复制发给海外供应商。覆盖六类：**主体 / 收款 / 工厂 / 产品 / 文件 / 合规**。
> 使用规则：要求对方**公司抬头纸 + 有权签字人（含姓名职务）**回函；只接受**企业域名邮箱**发出的回复。

---

## 发送模板（Email body）

```text
Subject: Supplier Due-Diligence Enquiry — [Product] — Ref: [Buyer-DDQ-XXXX]

Dear [Supplier],

We are conducting pre-qualification checks ahead of a prospective purchase of
[product, grade, quantity]. Please answer each item below in writing, on your
company letterhead, signed by an officer with authority to bind the company.

Please note that replies from e-mail addresses other than your official
corporate domain cannot be treated as binding, and that payment instructions
will only be acted upon after written confirmation through the channels
published on your official website.

We would be grateful for your reply by [date].

Kind regards,
[Name / Title / Company]
```

---

## 十四条标准条款（英文原文）

| # | 类别 | Clause |
|---|---|---|
| A1 | 主体 | Confirm the full legal name, commercial registration (CR) number, address of the registered office, and legal form of the contracting entity, and attach a scan of the CR certificate. |
| A2 | 主体 | Identify the exact entity that will issue the commercial invoice and the bill of lading as shipper, and state its relationship to the contracting entity. |
| A3 | 收款 | If payment is to be made to an entity other than the contracting party, provide a signed payment instruction on company letterhead, a bank confirmation letter from the receiving bank, and a declaration of the relationship between the two entities. |
| A4 | 工厂 | Identify the production site(s) (plant name, city, country) from which the goods supplied under this contract will originate, and attach the industrial licence covering those products. |
| A5 | 工厂 | State the annual and monthly nameplate capacity for the offered grade at the producing site, and the volume earmarked for this enquiry with indicative loading windows. |
| A6 | 产品 | Provide the TDS for the grade offered, including all specified limits and test methods. |
| A7 | 文件 | Provide a batch-level COA for a recent production batch of the same grade, on the producer's letterhead, showing test methods and results. |
| A8 | 文件 | Provide the current SDS (revision number and date) issued by the producer named on the COA. |
| A9 | 产品 | Confirm packaging and transport mode (bulk vessel, ISO tank, drum or flexitank) and, for bulk, the nominated load port and vessel/space arrangements. |
| A10 | 文件 | Provide copies of valid management-system certificates (e.g. ISO 9001, ISO 14001, ISO 45001) with certificate numbers, issuing bodies and validity dates. |
| A11 | 文件 | Provide two recent bills of lading (redacted) for the same product to confirm actual export performance and shipper identity. |
| A12 | 合规 | Confirm whether any sanctions, export restrictions or force majeure currently affect your ability to perform, and describe any such measure with dates. |
| A13 | 合规 | Provide an ultimate beneficial owner (UBO) declaration and a group structure chart from the contracting entity to its ultimate parent. |
| A14 | 主体 | Confirm the offer's validity period, delivery terms, governing law and dispute-resolution venue to be used in the contract. |

---

## 补充条款（按场景加用）

| 场景 | 补充条款（英文） |
|---|---|
| 自称生产商但证据弱 | State whether you are the manufacturer of the goods offered or a reseller/trader, and support your answer with documents. |
| 经销商 | If you are a reseller, provide the producer's written authorisation for you to sell the goods in our market, or the producer's supply confirmation for this order. |
| 使用免费邮箱 | Provide an official corporate e-mail address on your registered domain; replies from free webmail accounts cannot be treated as binding. |
| 需要财务信息 | Provide the annual report or audited financial summary for the last financial year. |
| 需要制造商同意书 | Provide the producer's written consent to disclose the COA and SDS to us for this transaction. |
| 拒提供 UBO | Confirm, on letterhead, the identity of persons holding more than 25% of voting rights. |
| 账户变更 | Confirm the change of bank account through a written notice signed by two authorised signatories, and arrange a verification call to the number published on your website. |

---

## 回复评价表（收到回函后填）

| # | 条款 | 已回复 | 附件 | 内容是否具体 | 备注 |
|---|---|---|---|---|---|
| A1 | | ☐ | ☐ | ☐ | |
| A2 | | ☐ | ☐ | ☐ | |
| A3 | | ☐ | ☐ | ☐ | |
| A4 | | ☐ | ☐ | ☐ | |
| A5 | | ☐ | ☐ | ☐ | |
| A6 | | ☐ | ☐ | ☐ | |
| A7 | | ☐ | ☐ | ☐ | |
| A8 | | ☐ | ☐ | ☐ | |
| A9 | | ☐ | ☐ | ☐ | |
| A10 | | ☐ | ☐ | ☐ | |
| A11 | | ☐ | ☐ | ☐ | |
| A12 | | ☐ | ☐ | ☐ | |
| A13 | | ☐ | ☐ | ☐ | |
| A14 | | ☐ | ☐ | ☐ | |

**判定**：
- A1–A4 + A7 全部满足 → 可进入商务谈判
- 仅 A1 满足 → 只能作为"待验证联系人"
- A3 拒答或不执行 → **不得付款**

---

## 常见推诿与正确回应

| 供应商说 | 正确回应 |
|---|---|
| "这些信息是保密的" | 询证信息仅用于内部合规审查，可签 NDA；但注册号、收款户名、生产商名称不属商业秘密 |
| "我们一直是这么收款的" | 首次合作需银行确认函，属标准流程；如已完成过交易则可豁免 |
| "COA 出货时再给" | 先给同等级历史批次 COA 以确认规格与检测方法 |
| "产能是商业机密" | 只需说明量级与装置地点，不需要精确数值也无需客户名单 |
| "用 WhatsApp 说更快" | 正式信息以公司抬头纸邮件为准，WhatsApp 仅作沟通提醒 |

---

## 输出到 project.json

```json
"rfi": {
  "title": "Supplier Due-Diligence Enquiry — [Product]",
  "to": "The Authorised Representative of [Supplier]",
  "from": "[Your Company / Procurement]",
  "date": "YYYY-MM-DD",
  "ref": "Buyer-DDQ-XXXX",
  "intro": "…",
  "clauses": [{ "id": "A1", "text": "Confirm the full legal name …" }]
}
```
