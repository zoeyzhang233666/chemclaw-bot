# 缺失项识别与待确认问题库

缺口不是"资料不全"，是**报价的不同风险**。所以先分级，再决定问不问、怎么问。

## 1. 三桶分级矩阵

| 桶 | 定义 | 成员（默认） | 缺了怎么办 |
|---|---|---|---|
| **A · 报价前必须先确认** | 没有它算不出价，或算出来一定错 | 产品形态、规格关键项、数量（试单+年量至少一个）、目的港、术语、币种、成本承担边界 | 锁"生成报价"；进客户问题清单 |
| **B · 可带我方假设先准备** | 有默认值，标出来就行 | 包装细节、唛头语言、报价有效期（我方定）、交期（我方定）、样品政策（我方定） | 渲染成 `(our assumption – to be confirmed)` |
| **C · 我方内部先定** | 客户问不到的 | 我方出口主体、装运港、是否含税、我方能否出 FORM E、我方库存与排产 | 进「待内部确认」，**不进客户问题** |

## 2. 按字段的风险口诀

| 字段 | 缺失/歧义时的报价后果 | 是否阻塞报价 |
|---|---|---|
| 产品形态（dense vs light） | 完全不同产品线，价格与包装都不同 | 是 |
| 纯度/杂质/粒度 | 规格不同成本差很大；报高了客户走，报低了亏 | 是 |
| 数量（试单/年量/批次） | 无法报阶梯价，无法算运费摊销 | 是 |
| 目的港 | 算不出海运费（运费常占 CFR 价 5–12%） | 是 |
| 贸易术语 | 成本责任边界不明 | 是 |
| 币种 | 汇率敞口 | 是（我方默认 USD） |
| 付款方式类型 | 资金占用与收汇风险 | 部分（可给价，注明前提） |
| 包装 | 影响成本 1–5%，影响柜内体积 | 否（可假设） |
| 交期 | 影响排产，不影响单价 | 否（可假设） |
| 报价有效期 | 影响调价权 | 否（我方定） |
| 单证（COA/SDS/TDS） | 常规单证成本低 | 否（可承诺常规，特殊需确认） |
| FORM E / 第三方检验 / 认证 | 有额外费用与资质要求 | 否，但**不得承诺** |
| 卸货条件 | 影响运输组织 | 否（DAP 时必问） |
| 客户全称与工商信息 | 影响合同主体、开证 | 否（但开证前必有） |

## 3. 问题设计四原则

1. **一句一问**：不要写 "Please provide all details regarding packing, payment, delivery and documents."
2. **带锚点**：引用客户原话，让客户知道我们在认真读。
3. **给选项**：`25 kg bags or 1,000 kg jumbo bags?` 比 `what packing?` 回得快。
4. **先给下一步**：结尾说明"收到这几项后我方会在 X 个工作日内给出正式报价"——X 用占位符，不自己编。

## 4. 英文问句库（可直接粘）

**产品与规格**
- `You mentioned "industrial grade" – could you confirm the specification you will check on arrival, especially Na2CO3 content, Fe content and particle size (+80 mesh)?`
- `Could you confirm whether you require dense or light soda ash for your furnace?`
- `Would you like us to propose our standard glass-grade specification for your confirmation?`

**数量**
- `Could you confirm the quantity for the first shipment, and your estimated annual volume, so that we can structure the price accordingly?`
- `Do you plan a single shipment or monthly deliveries? If monthly, what quantity per month?`

**目的港与术语**
- `You wrote "CFR Semarang" – may I confirm the port of discharge is Semarang (IDSRG) and that you require CFR, not CIF?`
- `If insurance is needed, should we quote CIF instead, and at which coverage (ICC A / ICC B)?`
- `Could you advise whether you have a nominated forwarder for FOB terms?`

**包装与卸货**
- `Which packing do you prefer: 25 kg PP woven bags on pallets, or 1,000 kg jumbo bags with inner liner?`
- `Please confirm whether the bags need to be palletized and whether your site has a forklift for unloading.`
- `Do you require marking or labels in Bahasa Indonesia?`

**付款**
- `For the payment terms, would T/T be acceptable, and do you prefer an advance + balance against B/L copy structure?`
- `If you require L/C, could you confirm the L/C type (at sight or usance), its validity, and the issuing bank?`

**单证**
- `Could you confirm the documents you require: COA per shipment, SDS (English), TDS, Certificate of Origin?`
- `Do you require a Form E for ACFTA preferential duty, or is a general Certificate of Origin sufficient?`
- `Do you require third-party inspection (SGS / BV / Intertek), and at loading port or destination?`

**交期与有效期**
- `What is your required delivery window, and when do you expect to place the order?`
- `Please note our offer validity will be confirmed with the formal quotation; could you advise your decision timeline?`

**公司信息**
- `To prepare the documents correctly, could you provide your full registered company name, address and tax ID?`

## 5. 多语言问句（附英文对照）

| 语言 | 问句 | 英文 |
|---|---|---|
| Bahasa Indonesia | `Mohon konfirmasi kuantitas untuk pengiriman pertama dan estimasi kebutuhan tahunan Bapak/Ibu.` | Please confirm the first shipment quantity and estimated annual requirement. |
| Bahasa Indonesia | `Apakah kemasan yang Bapak/Ibu butuhkan 25 kg karung atau 1.000 kg jumbo bag?` | Do you need 25 kg bags or 1,000 kg jumbo bags? |
| Bahasa Indonesia | `Mohon konfirmasi apakah harga yang diminta adalah CFR Semarang sesuai ketentuan Incoterms 2020.` | Please confirm the requested price is CFR Semarang per Incoterms 2020. |
| Tiếng Việt | `Xin vui lòng xác nhận khối lượng cho lô hàng đầu tiên và sản lượng dự kiến theo năm.` | Please confirm the first shipment quantity and estimated annual volume. |
| Tiếng Việt | `Quý công ty cần bao bì 25 kg hay bao jumbo 1.000 kg?` | Do you need 25 kg bags or 1,000 kg jumbo bags? |
| Español | `¿Podría confirmar la cantidad del primer envío y su volumen anual estimado?` | Could you confirm the first shipment quantity and estimated annual volume? |
| Português | `Poderia confirmar a quantidade do primeiro embarque e o volume anual estimado?` | Could you confirm the first shipment quantity and estimated annual volume? |
| العربية | يرجى تأكيد الكمية للشحنة الأولى والكمية السنوية المتوقعة. | Please confirm the first shipment quantity and expected annual quantity. |
| 日本語 | 初回出荷数量と年間見込み数量をご確認いただけますか。 | Could you confirm the first shipment quantity and annual volume? |

> 非英语客户：回复语言跟客户走，但**规格与商业条款同时给英文对照**，避免翻译误差进合同。

## 6. 不该问的

- 不要问客户"你们的预算价是多少"（P2 不是缺口，是谈判）；
- 不要问已经回答过的事（问完被客户嫌弃不专业）；
- 不要在第一次回复里一次抛 15 个问题——超过 6 个就分优先级，先问阻塞报价的；
- 不要问客户"能否接受我们的价格"，价格还没出。

## 7. 优先级排序（选题上限 6 条）

排序逻辑：①阻塞报价的 → ②会改变价格的 → ③影响执行成本的 → ④双方留痕的。
同一封邮件最多放 6 条，其余放进 HTML 的"第二轮问题"折叠区，避免邮件看起来像问卷。
