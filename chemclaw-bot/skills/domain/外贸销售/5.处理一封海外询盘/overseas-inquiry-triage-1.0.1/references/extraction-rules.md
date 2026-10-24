# 抽取规则 · 从原始询盘到可追溯字段

目标不是"抽得全"，而是**抽错了能被一眼看见**。所以每条值必须带：原文、语言、位置、置信度。

## 1. 素材切块

文本素材用块标记分隔，`extract.py` 按标记切成独立素材并编号：

```
【素材01 客户邮件 .eml · 2026-10-19 08:42 (+07:00)】
…
【素材02 历史邮件 (转贴) · 2026-10-15 16:20】
…
```

也认 `### 素材01 …`。没有标记时整篇算一块（`素材01`）。
邮件文件按 header（From/To/Cc/Date/Subject）单独成块，正文再按 `>` 引用、`On … wrote:`、`-----Original Message-----` 拆轮次。

**编号一旦生成不得复用。** 三个月后复核靠的就是它。

## 2. 多语言锚点

同一字段在不同语言下的常见写法（词表见 `scripts/_common.py: ANCHORS`）：

| 字段 | English | Bahasa Indonesia | Tiếng Việt | Español | Bahasa Melayu |
|---|---|---|---|---|---|
| 询价 | inquiry / enquiry / RFQ / kindly quote | permintaan penawaran / mohon penawaran / penawaran harga | yêu cầu báo giá | solicitud de cotización | permintaan sebut harga |
| 数量 | qty / quantity / MT / tons | jumlah / kuantitas / ton / metrik ton | số lượng / tấn | cantidad / tonelada | kuantiti / tan |
| 目的港 | port of discharge / POD / destination port | pelabuhan bongkar / pelabuhan tujuan | cảng đích / cảng dỡ hàng | puerto de destino | pelabuhan destinasi |
| 交付条款 | INCOTERMS / CIF / FOB / CFR | syarat penyerahan / incoterms | điều kiện giao hàng | términos de entrega | terma penghantaran |
| 付款 | payment terms / T/T / L/C | syarat pembayaran / letter of credit | điều khoản thanh toán | condiciones de pago | terma pembayaran |
| 纯度 | purity / assay / content / min | kemurnian / kadar | độ tinh khiết / hàm lượng | pureza | ketulenan / kandungan |
| 包装 | packing / packaging / bag / jumbo bag | kemasan / karung / jumbo bag | bao bì / bao | embalaje / saco | pembungkusan / guni |
| 单证 | COA / MSDS / SDS / TDS / CO | sertifikat analisa / lembar data keselamatan | giấy chứng nhận phân tích | certificado de análisis | sijil analisis |

阿拉伯语/日语等：先做"语种识别 → 机翻成英文 → 保留原句 → 人工核对数字"，数字与单位一律以原语言字符为准。

## 3. 数字与单位

| 陷阱 | 处理 |
|---|---|
| `300 TON` / `300 MT` / `300 metric tons` | 一律记 `300 MT`，`raw` 保留原文；`ton` 默认按 MT，但标注"客户未写 MT，按公吨理解" |
| `3,000 MT/year` 千分位逗号 | 解析 `3000`；欧洲写法 `3.000 MT`、印尼 `3.000` 也是千分位 → 记 `3000` 并标 `low` |
| 印尼盾 `Rp`、`IDR` | 币种记 `IDR`；印尼数字用 `.` 作千分位、`,` 作小数 |
| `1 x 20' FCL ≈ 25–27 MT` | 这是**我方的装箱常识**，不是客户说的数量；只能进备注，不进 `qty_trial` |
| `20,000 bags` | 不是吨数；需要换算必须先知道袋重，换算结果标"推算" |
| `+80 mesh ≥ 75%` | mesh/µm 换算只在备注给一次参考值 |
| `99,2 %`（欧陆逗号小数） | 解析为 `99.2%`，`raw` 保留 |

**不做单位换算进字段。** 字段里写客户原单位 + 我方标准化单位，两者并排。

## 4. 置信度

| 级别 | 含义 | 处理 |
|---|---|---|
| high | 原文直述、数字明确、无歧义 | 可直接 `stated` |
| medium | 需上下文拼接（如签名里拼出公司缩写、术语地点拆开） | 让销售点头 |
| low | 推断或翻译所得（邮箱域名推国家、品名翻译推 CAS） | **一律不许作为报价依据**，A 桶字段必须降为 `ambiguous` |

## 5. 脏数据三类（必须进 unreadable）

1. 数字被遮挡/涂改：`45? MT`、`1?000`；正则 `\d\s*\?\s*\d`
2. 未转写语音条 / 图片附件无文字；
3. 扫描件表格裁切、跨页字段名与值错位。

`unreadable` 会进：HTML 提示条、Excel 04 表、中文简报、回复草稿里的"请客户补录"一句（只能问，不能猜）。

## 6. 冲突处理

同一字段多处不一致时：

- **时间晚的优先**，但旧值必须留在 `note`（`S01 写 25 kg bags，S02 改为 1,000 kg jumbo bags`）；
- 数量、付款、交期、术语四类冲突**不自动取值** → `ambiguous`；
- 包装冲突要判断是"不同产品不同包装"还是"改口"，判断不了就列两个选项问客户；
- 产品形态冲突（light vs dense）→ 直接进 A 类必确认。

## 7. 别做的事

- 不要用"行业通常""我们平时都这样"补字段值；
- 不要把客户问价（`please advise best price`）当成客户给了任何商务条件；
- 不要把**我方模板里的默认条款**当成客户要求；
- 不要为了"看起来专业"在回复里补客户没提的单证与认证；
- 不要对询盘真实性、客户购买力、成交可能性做任何打分或分级。
