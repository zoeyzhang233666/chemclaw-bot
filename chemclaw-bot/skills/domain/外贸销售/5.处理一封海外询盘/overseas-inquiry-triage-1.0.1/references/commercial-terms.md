# 商务条件标准化 · Incoterms / 付款 / 交期 / 有效期

一封海外询盘的商务条件，一半以上会写成中国销售看不懂或看错的样子。
这一份就是把"客户写的那句话"翻译成"我方能不能接、要问什么"。

## 1. Incoterms 2020

只认 2020 版 11 个术语：

| 术语 | 全称 | 卖方责任到哪 | 客户中文常问 | 典型风险 |
|---|---|---|---|---|
| EXW | Ex Works | 工厂交货 | 出厂价 | 客户清关能力弱会卡住 |
| FCA | Free Carrier | 交承运人 | 送站价 | 与 FOB 混用 |
| FAS | Free Alongside Ship | 船边交货 | 散货/大包 | 少见 |
| FOB | Free On Board | 装上船前 | 离岸价 | 指定货代费用扯皮 |
| CFR (CNF/C&F) | Cost and Freight | 付到目的港运费 | CFR/CNF | 保险买方买；**`CNF` 旧写法统一转 CFR** |
| CIF | Cost Insurance and Freight | 运费+保险 | 到岸价 | 险别（ICC A/B/C）、加成 110% 要写清 |
| CPT | Carriage Paid To | 付至指定点 | | 多式联运 |
| CIP | Carriage and Insurance Paid To | 付至+保险 | | 2020 版要求 ICC A |
| DAP | Delivered at Place | 送达未卸货 | 到门价 | 目的港清关谁做 |
| DPU | Delivered at Place Unloaded | 送达并卸货 | | 少数场景 |
| DDP | Delivered Duty Paid | 完税后交货 | 到门含税 | 买方国别关税/进口资质 |

**必拆三件套**：`术语` + `地点` + `地点层级`。

- `CFR Semarang` → `incoterm=CFR`, `incoterm_place=Semarang (ID)`
- `CIF Jakarta, Indonesia` → 港口是 `Tanjung Priok, Jakarta`，要在备注里请客户确认 exact port
- `FOB China port` → 地点缺失 → `ambiguous`（问：指定哪个装运港/是否买方指定货代）
- `CFR Semarang port, Indonesia, Incoterms 2020` → 最完整，直接引用客户原话

**回复里的写法**（避免歧义）：

```
Price basis : USD ‹PRICE_DENSE_CNF_SEMARANG› per MT, CFR Semarang, Indonesia (Incoterms 2020)
```

## 2. 付款方式

客户写的东西 ≠ 可执行的付款条件。按"能落到合同"的标准拆：

| 客户原话 | 能落地的解读 | 还缺什么 | 是否可据此报价 |
|---|---|---|---|
| `T/T` | 电汇 | 预付比例 / 尾款条件 | 部分（价格可给，条款要问） |
| `T/T 30% advance, 70% against B/L copy` | 可执行 | 无（除非我方不接受） | 是 |
| `L/C` | 信用证 | 类型（at sight / usance）、有效期、开证行、是否保兑、UCP600 | 否 → 问 |
| `L/C at sight` | 即期信用证 | 开证行、有效期 | 部分 → 价格可给，需注明前提 |
| `100% D/P` | 付款交单 | 银行、单据条件 | 需我方审批（风险高） |
| `D/A 60 days` | 承兑交单 | 我方可接受？ | 走信用审批 |
| `COD / cash on delivery` | 货到付款 | 我方基本不接受 | 需谈判 |

**红线**：回复里绝不主动给账期、绝不写"we accept any payment terms"。
客户要账期时，标准做法是"记下并向内部申请，不在邮件里答应"：

```
Payment terms: We note your request for ‹PAYMENT_TERMS_REQUESTED›. Our standard terms are
confirmed case by case by our finance team; we will revert with our proposal together with the
formal offer.
```

## 3. 交期 / 装运期

必须分清四种时间：

| 类型 | 客户写法 | 我方回什么 |
|---|---|---|
| 期望到货日 | `need delivery by 15 Dec 2026` | 不能承诺 → 占位符 ‹DELIVERY_DATE› |
| 下单后装运期 | `ship within 30 days after order` | 占位符 ‹SHIPMENT_TIME›，并注明前提（收到预付款 / L/C 开到） |
| 到港时间 | `arrive Semarang by ...` | 只能给"预计"，不能给"保证" |
| 现货 | `prompt shipment` | 库存是内部信息 → 占位符 ‹STOCK_AVAILABILITY› |

**回复里**：不写任何具体天数，统一写

```
Shipment : ‹SHIPMENT_TIME› from receipt of ‹PAYMENT_TRIGGER›; to be confirmed after order confirmation.
```

## 4. 报价有效期

- 客户写了 `validity 15 days` → 记录；我方能否接受由销售定（C 类）。
- 客户没写 → `missing`；**不得**默认写 30 天（大宗化学品行情波动大，30 天等于白送调价权）。
- 回复里统一 `Validity : ‹QUOTE_VALIDITY› days from the date of our formal offer.`

## 5. 海运与港口常识（用于提问，不用于报价）

| 主题 | 提问点 |
|---|---|
| 印尼 | 主要卸货港：Tanjung Priok (Jakarta)、Tanjung Perak (Surabaya)、Tanjung Emas (Semarang)、Belawan (Medan)；雅加达的港在 Tanjung Priok，客户常只说"Jakarta" |
| 柜型 | 20'FCL 装纯碱袋装一般 25–27 MT（视袋重与托盘），客户写 300 MT ≈ 12 个柜左右 → 只能写"约"，且属我方测算 |
| 卸货 | 是否需要托盘、是否可用抓斗/叉车、有没有地磅、是否要卸到桶仓 |
| 清关 | 印尼进口需 SNI（部分化工品）、API 进口商号；客户没提不代问，但内部备注 |
| 旺季 | 春节前、斋月前运力紧张 → 只影响内部排产沟通 |

## 6. 客户侧常见"看起来给了其实没给"

- `price should be competitive` → 没有价格信息，只有敏感度；
- `standard packing` → 没给袋型；
- `documents as usual` → 没有单证清单；
- `delivery as soon as possible` → 没有交期；
- `we are a big buyer` → 没有年量；
- `please quote FOB` → 没有装运港、没有货代；
- `payment: bank transfer` → 没有比例与节点。

这七句是新手最常误判成"客户已明确"的句子，HTML 里专门有 `AMBIGUITY_TRAPS` 标记。
