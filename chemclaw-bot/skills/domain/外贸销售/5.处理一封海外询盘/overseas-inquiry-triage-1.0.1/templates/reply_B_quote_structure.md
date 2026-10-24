# 模板 B · 报价式中继（参数齐了，价格还没定）

> **什么时候用**：A 类字段基本齐全（产品、规格、数量、贸易术语、目的港、币种都明确），
> 销售还没有最终价格，但客户已经等急了——先发出一封"**报价结构确认**"邮件，
> 让客户确认口径、包装、交期节点的理解，避免价格出来后又改。
>
> **红线**：**不含单价**。价格位置一律是 `‹PRICE_PER_MT_...›`。
> 这封信的作用是"把报价单的格式先跟客户对齐"，不是"先给个大概价"。

---

## Subject

```
Re: {客户原主题} - Offer structure for {产品} {贸易术语} {目的港}
```

---

## Body

```
Dear {Mr./Ms.} {姓氏},

Thank you for your inquiry dated {日期} regarding {产品} for {用途}.

Before we issue the formal offer, please find below the structure we intend
to use, so that the offer matches your requirement on the first attempt:

- Price basis : {PRICE_PER_MT_...} (per MT, {贸易术语} {目的港}, Incoterms 2020,
                in {币种})
- Quantity    : {首批数量}
- Packing     : {我方标准包装} (our standard export packing)
- Shipment    : {SHIPMENT_TIME} after receipt of {PAYMENT_TERMS}
- Validity    : {QUOTE_VALIDITY} days from the date of issue
- Documents   : COA (per lot), SDS, TDS

Specification as we understand it: {规格}
The values will be certified on the COA of the shipped lot.

{如果还有 1-2 个未定项，用编号列出，不多于 2 条}

Once you confirm the structure above, we will issue the formal offer with the
price within {LEAD_TIME_FOR_OFFER}.

Best regards,

{SIGNER_NAME}
{SIGNER_TITLE} | {公司名}
```

---

## 为什么这样写给客户不会反感

| 做法 | 原因 |
|---|---|
| 先说"结构"不说"价格" | 采购经理最烦"我们没有价格，先给我资料"，但愿意确认贸易术语和包装 |
| 写 `per MT, CFR Semarang, Incoterms 2020` | 把口径钉死，避免后面"你说的是 CIF 吧？" |
| 有效期写 `‹QUOTE_VALIDITY› days` | 有效期是商务决定，由销售定，不由模型定 |
| 明说 `our standard export packing` | 包装是我方标准方案，客户不改就按标准走 |

---

## 必须填实才能发的占位符

| 占位符 | 谁填 |
|---|---|
| `‹PRICE_PER_MT_...›` | 销售（价格由报价环节定） |
| `‹SHIPMENT_TIME›` | 生产/物流 |
| `‹PAYMENT_TERMS›` | 商务 |
| `‹QUOTE_VALIDITY›` | 销售 |
| `‹PACKING_PROPOSAL›` | 我方标准包装（若有客户指定包装，另算成本） |
| `‹LEAD_TIME_FOR_OFFER›` | 销售 |

---

## 常见错误

| 错误 | 为什么错 |
|---|---|
| 用 `TBA` 代替占位符 | TBA 看起来像"我们已经定了但先不说"，占位符才是诚实的"还没定" |
| "Price will be around USD 250/MT" | 区间价 = 报价，绝对禁止 |
| "Shipment within 15-20 days" | 区间天数也是承诺 |
| 把有效期写成 "valid for 30 days" 当作事实 | 有效期由销售定，不能由模型默认 |

---

## 与模板 A 的区别

| | A 确认式 | B 报价式中继 |
|---|---|---|
| 前提 | A 类字段有缺 | A 类字段齐全 |
| 邮件主体 | 提问清单 | 报价结构表 |
| 客户感受 | "专业但慢" | "看得见进度" |
| 风险点 | 客户不耐烦 | 客户把结构当承诺 |
