# 模板 A · 确认式（缺参数，先不报价）

> **什么时候用**：客户询盘里缺了至少一个 A 类字段（币种、价格基础、付款方式细节、包装、数量口径……），
> **不能报价**，但又不该让客户觉得被敷衍。这是最常用的默认模板。
>
> **它承诺什么**：只承诺"补齐信息后发正式报价"，不承诺价格、库存、交期、付款条件、单证能力。
>
> **它长什么样**：感谢 → 复述理解 → 列出要问的点 → 说明随报价附哪些单证 → 说明下一步时间（占位符）。

---

## Subject

```
Re: {客户原主题} - {产品简称} / Our inquiry ref. {询盘号}
```

保留客户原主题，前面加 `Re:`，后缀加询盘号，方便客户在自己的邮箱里搜到。**不要**把主题改成
"Great price for soda ash!!!" 这类营销式标题——印尼、越南、印度的采购经理会直接当垃圾邮件。

---

## Body

```
Dear {Mr./Ms.} {姓氏},

Thank you for your inquiry dated {日期} regarding {产品全称} for {用途}. We
have reviewed your requirements carefully.

As we understand your inquiry:

- Product       : {产品 + 等级}
- Specification : {纯度}; {杂质}; {粒度}
- Quantity      : {首批数量}; {年量}
- Delivery      : {贸易术语} {目的港}, Incoterms 2020
- Documents     : {COA / SDS / TDS}
- Application   : {用途}

To prepare an accurate offer, could you please confirm the following:

1. {问题1}
2. {问题2}
3. {问题3}

{COA、SDS、TDS 随报价提供；若客户要其它单证，只说明"我们能做什么"，
不承诺"保证提供"}

Once you confirm the above points, we will send our formal offer with the
price on {价格基础占位符} and the related commercial terms within
{LEAD_TIME_FOR_OFFER}.

We look forward to your reply.

Best regards,

{SIGNER_NAME}
{SIGNER_TITLE} | {公司名}
Tel: {电话} | Web: {网址}
```

---

## 占位符

| 占位符 | 含义 | 谁填 |
|---|---|---|
| `‹PRICE_PER_MT_CFR_<PORT>›` | 价格基础（不含单价，单价由报价环节给） | 销售 |
| `‹LEAD_TIME_FOR_OFFER›` | 多久内给正式报价（如 2 working days） | 销售 |
| `‹SIGNER_NAME›` `‹SIGNER_TITLE›` | 签名 | 销售 |
| `‹OURCOMPANY_NAME›` 等 | 公司信息 | 公司模板 |

> 注意 **没有** `‹UNIT_PRICE›` 这个占位符：模板 A 里根本不该出现单价位置。
> 一旦出现，说明写的人已经在心里报了价，最容易出事。

---

## 语气微调

| 客户类型 | 调整 |
|---|---|
| 大型终端 / 招标 | 称 `Dear Mr./Ms.`，结尾 `Yours faithfully`，去掉 `We look forward to your reply` 之外的客套 |
| 中小贸易商 | `Dear {First name},` 结尾 `Best regards` |
| 已往来老客户 | 两句话内说清"查什么"，`Regards` |

---

## 常见错误

| 错误 | 为什么错 |
|---|---|
| "Our best price is USD XXX" | 价格由报价环节定，本环节不得出现数字 |
| "We have enough stock for 300 MT" | 库存是承诺，且没人核过库存 |
| "Delivery within 20 days" | 交期是承诺 |
| "L/C at sight is OK" | 付款条件是我方商务决定，不是默认值 |
| "We can supply any quantity" | 产能承诺，无依据 |



## 与其它模板的分工

- **B 报价式中继**：客户参数齐了、但价格还没定 → 只给**报价结构**（价格基础、包装、交期口径），价格仍留占位符。
- **C 样品 / 技术资料**：客户先要样品或 TDS。
- **D 只答单证与规格**：客户明确说"这次只要资料，别报价"。
