# 英文回复 · 结构、占位符协议、语气与模板

## 1. 三种回复渠道

| 渠道 | 触发 | 长度 | 目的 |
|---|---|---|---|
| **A · 确认式（默认）** | A 类未齐 | 140–200 词 | 让客户知道"我们读懂了、我们在动、还差这几点" |
| **B · 报价式中继** | A 类已齐、价格已确认 | 200–320 词 | 给出可执行的结构化报价，占位符全部被替换 |
| **C · 润色** | 用户已写稿 | 原长度 | 只改语言 |

## 2. 结构（A 渠道）

```
Subject: Re: Inquiry – Dense Soda Ash (Na2CO3) – PT … / 300 MT CFR Semarang

① 称呼       Dear Mr. Santoso,
② 感谢+在场  Thank you for your inquiry of 19 October regarding dense soda ash.
③ 复述事实   （只复述客户说过的；逐条对齐，便于客户核对）
④ 我们缺什么 （≤6 条编号问题，带客户原话锚点）
⑤ 下一步     （不含日期承诺 → 占位符）
⑥ 商务口径   （付款/有效期类的我方立场只写"将由财务/我们在正式报价中确认"）
⑦ 签名       Best regards, ‹SIGNER_NAME› ‹SIGNER_TITLE› ‹OURCOMPANY_NAME›
                Tel ‹OURCOMPANY_PHONE› | ‹OURCOMPANY_WEBSITE›
```

**复述段落的写法是这套技能最值钱的部分**：把客户的话按"产品/规格/数量/条款/单证"重新组织，
客户一眼能看出我们读懂了，也能顺手纠正我们理解错的地方。

参考句式：

```
We understand from your email the following:
· Product        : Dense soda ash (sodium carbonate, CAS 497-19-8)
· Specification  : Na2CO3 99.2% min; Fe 0.003% max; +80 mesh 75% min
· Quantity       : 300 MT for the first shipment, approx. 3,000 MT per year
· Delivery       : CFR Semarang, Indonesia
· Documents      : COA, SDS and TDS
```

（`·` 用普通列表符号，别用特殊字符——很多邮件网关会过滤。）

## 3. 占位符协议（生成时必须遵守）

占位符格式：`‹KEY›`（U+2039/U+203A 单书名号，邮件里很显眼，不会被当成正文）。

| 占位符 | 含义 | 谁来填 |
|---|---|---|
| `‹PRICE_…›` | 单价，含术语与港口，如 `‹PRICE_DENSE_CNF_SEMARANG›` | 销售/报价系统 |
| `‹QUOTE_VALIDITY›` | 报价有效天数 | 销售 |
| `‹SHIPMENT_TIME›` | 装运期 | 销售/排产 |
| `‹DELIVERY_DATE›` | 到货日 | 销售/物流 |
| `‹PAYMENT_TERMS›` | 我方可接受的付款条件 | 财务 |
| `‹PAYMENT_TERMS_REQUESTED›` | 客户提出但未定的付款条件 | 原样引用客户 |
| `‹STOCK_AVAILABILITY›` | 库存/可供量 | 销售 |
| `‹SAMPLING_POLICY›` | 样品政策 | 销售 |
| `‹FREIGHT›` | 运费 | 物流 |
| `‹LEAD_TIME_FOR_OFFER›` | 我方出正式报价所需时间 | 销售 |
| `‹DOC_…›` | 我方尚未确认能否提供的单证 | 单证员 |
| `‹SIGNER_NAME›` `‹SIGNER_TITLE›` `‹OURCOMPANY_NAME›` `‹OURCOMPANY_PHONE›` `‹OURCOMPANY_WEBSITE›` | 签名块 | 销售/市场 |

规则：

1. 一个占位符不要在同一封邮件出现两种写法；
2. 占位符**不许**出现在 Subject 行（会被当成乱码）；
3. 占位符必须进 `reply.json.placeholders`，含 `label / owner / status`;
4. `status` 三态：`open`（未定）/ `confirmed_by_us`（已由我方确认）/ `waived`（本次不用）。
   `build_md.py --pack` 只允许全 `confirmed_by_us`/`waived` 时输出"可发送版"。

## 4. 承诺句式红线

| ❌ 不要写 | ✅ 改写 |
|---|---|
| `We can supply 300 MT immediately.` | `We will confirm availability ‹STOCK_AVAILABILITY› together with the formal offer.` |
| `Our price is competitive.` | 删掉；竞争力让价格说话 |
| `Delivery within 25 days.` | `Shipment : ‹SHIPMENT_TIME› after receipt of ‹PAYMENT_TERMS›.` |
| `We accept L/C 60 days.` | `We have noted your payment requirement and will revert with our proposal.` |
| `COA, MSDS, CO, Form E, SGS report all can be provided.` | `We will attach COA, SDS and TDS. Please advise if any additional document is required.` |
| `Our plant is ISO 9001 certified.` | 未核实就不写；如需写必须是我方已确认事实 |
| `Please confirm your best price.` | （客户问价格时不要反问价格） |

**自检句**：把邮件里每一句"we will/we can/we guarantee/we accept"读一遍，问自己：
"这句如果我方做不到，客户能不能拿它告我们？"——能，就必须改成占位符或条件句。

## 5. 三种语气

| 语气 key | 适用 | 开场 | 问题提法 | 结尾 |
|---|---|---|---|---|
| `formal` | 国企/大型终端/招标 | `We thank you for your inquiry dated …` | `We would be grateful if you could advise …` | `Yours faithfully` |
| `friendly-professional`（默认） | 大多数工厂与贸易商 | `Thank you for your inquiry …` | `Could you please confirm …` | `Best regards` |
| `concise-direct` | 有长期往来、WhatsApp 型客户 | `Thanks for your inquiry.` | `Please confirm:` + 项目符号 | `Regards` |

语气只改措辞，**不改承诺密度**。`concise-direct` 也不能省掉"待确认"标注。

## 6. 模板文件（`templates/`）

| 文件 | 场景 |
|---|---|
| `reply_A_confirm.md` | A 渠道：缺参数先确认（默认） |
| `reply_B_quote_structure.md` | B 渠道：报价结构，价格全占位 |
| `reply_C_sample.md` | 客户先要样品/技术资料 |
| `reply_D_docs_only.md` | 客户只要单证与规格（如招标预审） |
| `company_template_blank.md` | 让用户把自己的公司模板套进来的骨架 |

模板占位符（脚本替换）：

| 变量 | 内容 |
|---|---|
| `{{greeting}}` | `Dear Mr. Santoso,` |
| `{{thanks_line}}` | 感谢句 |
| `{{restatement}}` | 事实复述列表 |
| `{{questions}}` | 编号问题 |
| `{{next_step}}` | 下一步（含占位符） |
| `{{terms_block}}` | 商务口径段 |
| `{{docs_block}}` | 单证段 |
| `{{closing}}` `{{signature}}` | 结尾与签名 |
| `{{notes_internal}}` | 内部备注（不会被复制进邮件） |

未识别的 `{{…}}` 原样保留，方便一眼看出漏改。

## 7. 长度与排版

- 段落 2–4 行，别写大段；
- 列表用 `-` 或 `·`，不用 emoji、不用全大写强调；
- 数字与单证名加粗可读性更好，但**纯文本邮件请勿加粗**（HTML 邮件才用）；
- 一封邮件只讲一件事：确认就只确认，报价就只报价（报价邮件里再问 6 个问题会显得不专业）。

## 8. 主题行写法

```
Re: Inquiry – Dense Soda Ash – PT Glassworks Nusantara – CFR Semarang
```

`Re:` + 产品 + 客户名 + 术语港口。不用 `Urgent!!`、不用 `Best price`、不用全大写。
