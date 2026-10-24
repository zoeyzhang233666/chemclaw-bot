# 八类字段 · 定义、判定口径与易混案例

字段结构冻结在 `scripts/_common.py` 的 `CATEGORIES` / `FIELD_SPEC` 常量里。要加字段，必须同步改
`build_workbench.py`、`build_xlsx.py`、`build_md.py`、`selfcheck.py` 四处，否则四个产物会漂移。

每一个字段的 JSON 形状：

```jsonc
{
  "key": "cas",
  "label_cn": "CAS 号",
  "label_en": "CAS No.",
  "cat": "B",
  "bucket": "A",              // A 必确认 / B 可假设 / C 我方定
  "value": "497-19-8",
  "raw": "Sodium carbonate (CAS 497-19-8)",
  "status": "stated",         // stated 已明确 / missing 缺失 / ambiguous 歧义 / assumed 假设 / internal 我方待定
  "confidence": "high",       // high / medium / low（只表示读得准不准）
  "lang": "en",
  "source_id": "S01",
  "quote": "Sodium carbonate (CAS 497-19-8), dense granular",
  "locator": "S01:L9",
  "note": "",
  "assume": "",                // 仅 B 桶：我方默认值（渲染时自动加 our assumption 标记）
  "affects_quote": true
}
```

## A 类 · 客户与联系人（Buyer & contact）

| key | 中 | 说明 | 易混 |
|---|---|---|---|
| `buyer_name` | 客户公司全称 | 英文法定名称，如 `PT …`；`PT` = Perseroan Terbatas（印尼有限公司） | 邮件签名只有简称/贸易名 → `ambiguous`，标"待核验工商登记" |
| `buyer_country` | 国家/地区 | 用 ISO 名 + 代码，`Indonesia (ID)` | 从邮箱域名猜国家 → 只能 `low` 置信 |
| `buyer_site` | 地址/厂区 | 城市 + 详细地址 | 只有城市不给门牌 → `ambiguous`（但不阻塞报价，影响运费） |
| `contact_name` | 联系人 | 含称谓 `Mr./Ms./Mrs.`、全名 | `Pak Andi`（印尼语"安迪先生"）→ 保留原文 + 英文 `Mr. Andi`，别把 `Pak` 当名字 |
| `contact_title` | 职位 | `Purchasing Manager` 等 | `Procurement` 是部门不是职位 |
| `contact_email` | 邮箱 | 保留大小写 | 转发的 `Cc` 里可能有真正决策人，不要丢 |
| `contact_phone` | 电话 | 国际格式 `+62 21 …` | 印尼手机号 `08…` 需转 `+62 8…`，转格式要记录"客户原文写法" |
| `buyer_type` | 公司类型 | 终端厂 / 经销商 / 贸易商 / 工程公司 | 只能标 `stated` 或 `missing`，**不许推断** |

## A 类 · 产品与化学身份（Product & chemistry）

| key | 中 | 说明 |
|---|---|---|
| `product_raw` | 客户原话品名 | 原语言原样，含形态词（`dense granular`） |
| `product_std` | 标准化品名 | `Soda Ash Dense (Sodium Carbonate, Dense)`；**中英都要给** |
| `cas` | CAS 号 | 只能来自客户原文 / 我方资料 / 权威库查证；必须带来源 |
| `ec` | EC / EINECS 号 | 欧盟出口、SDS 要写 |
| `formula` | 化学式 | `Na2CO3` |
| `synonyms` | 常见别称 | `disodium carbonate, soda ash, Carbonic acid disodium salt, Natrium karbonat (id)` |
| `appearance_form` | 形态 | `dense granular` / `light powder` / `flake`（片碱）/ `pearl` |

## A 类 · 规格（Specification）

| key | 中 | 说明 |
|---|---|---|
| `spec_purity` | 主含量 | `Na2CO3 ≥ 99.2% min`；必须带单位与比较符 |
| `spec_impurities` | 关键杂质 | `Fe ≤ 0.003%`、`NaCl ≤ 0.5%`、`SO4 ≤ 0.03%` |
| `spec_particle` | 粒度/筛分 | `+80 mesh ≥ 75%`、`particle size 0.1–1.0 mm`；mesh/目 换算只在备注 |
| `spec_bulk` | 堆密度 | `bulk density 1.0 g/cm³`（重质碱典型 0.95–1.1） |
| `spec_moisture` | 水分/烧失 | `moisture ≤ 0.2%`、`LOI ≤ 0.5%` |
| `spec_std` | 标准 | `GB/T 210-2022`、`ASTM D 501`、`ISO 740`、或客户内控 |
| `grade` | 等级/牌号 | `industrial grade`、`glass grade`、`food grade (E500)` |
| `tds_ref` | TDS/规格书版本 | 客户要求附件版本 → 记文件名与版本 |

## A 类 · 数量（Quantity）

| key | 中 | 说明 | 易混 |
|---|---|---|---|
| `qty_trial` | 试单量 | `1 × 20'FCL`、`300 MT trial` | 拿 L/C 数量当试单量是常见错 |
| `qty_annual` | 年量 | `3,000 MT/year` | 年量不是首单量 |
| `qty_monthly` | 月量 | `250 MT/month` | 年量 ÷12 得出的月量要标"推算"，不进字段 |
| `qty_per_shipment` | 单批量 | `1,000 MT per shipment` | 单批量常受船舱/包装限制 |
| `qty_schedule` | 交付节奏 | `monthly from Jan 2027` | 节奏 ≠ 交期 |
| `qty_unit` | 计量单位 | `MT (metric ton)` / `kg` / `bag` | 客户写 `ton` 要确认是 MT 还是 long/short ton（默认 MT 但标注） |

## A 类 · 交付与贸易术语（Delivery & Incoterms）

| key | 中 | 说明 | 易混 |
|---|---|---|---|
| `port_dest` | 目的港/目的站 | `Semarang` / `Tanjung Priok (Jakarta)`；最好附 UN/LOCODE | `Jakarta` 不是港名，港是 `Tanjung Priok` |
| `incoterm` | 贸易术语 | Incoterms 2020：`CFR`/`FOB`/`CIF`/`EXW`/`FCA`/`DAP`；`CNF` 规范化为 `CFR` | `CIF` 要确认保险险别与加成 |
| `incoterm_place` | 术语地点 | `Semarang, Indonesia` | 术语和地点分开存 |
| `port_load` | 装运港 | 通常我方定（C 类） | 客户指定装运港时进 A 类 |
| `transport_mode` | 运输方式 | 海运整柜 / 散货 / 铁路 / 空运 | `FCL` vs `LCL` 决定价格结构 |
| `pack_std` | 包装类型 | `25 kg PP woven bag`、`1000 kg jumbo bag`、`bulk bag with liner` | 袋型、内衬、是否压包 |
| `pack_marking` | 唛头/标签语言 | `marking in English + Bahasa Indonesia` | 客户常漏说，B 类假设 |
| `pack_pallet` | 托盘/堆码 | `palletized, 20 bags/pallet` | 影响舱位与卸货 |
| `dg_info` | 危险品信息 | UN 号、PG、HS（纯碱非危化，但烧碱片碱是 UN1823 8 类） | 纯碱 ≠ 危险品，别乱标 |

## A 类 · 商务条件（Commercial）

| key | 中 | 说明 | 易混 |
|---|---|---|---|
| `currency` | 币种 | `USD` / `EUR` / `RMB` | `Rp`（印尼盾）→ `IDR` |
| `price_basis` | 价格基础 | `per MT CFR Semarang` | 术语、港口、单位三者必须齐 |
| `payment` | 付款方式 | `T/T 30% advance, 70% against B/L copy`、`L/C` | 只写 `L/C` → `ambiguous` |
| `lc_terms` | 信用证条件 | 类型、有效期、开证行、是否保兑、UCP600 | `L/C at sight` 缺开证行 |
| `delivery_time` | 交期/装运期 | `ship within 30 days after L/C` | 客户说 `asap` 不算交期 |
| `quote_validity` | 报价有效期 | `validity 15 days` | 客户没写 → `missing`（不要默认 30 天） |
| `sample_req` | 样品要求 | 数量、运费谁付、时间 | "样品免费"是我方决定，不是客户要求 |
| `inspection_cost` | 检测费承担 | CIQ/SGS 费用谁付 | |
| `commission` | 佣金/代理 | 百分比、付款方 | |

## A 类 · 文件与合规（Documents & compliance）

| key | 中 | 常见写法 | 备注 |
|---|---|---|---|
| `doc_coa` | COA 质量分析单 | `COA per shipment / per lot` | 逐批 vs 合并批次 |
| `doc_sds` | SDS/MSDS | `SDS in English`、`GHS-compliant SDS` | 印尼要求 `SDS Bahasa Indonesia` 时属客户额外要求 |
| `doc_tds` | TDS 技术数据表 | `TDS latest version` | |
| `doc_coo` | 原产地证 | `Certificate of Origin (CO)` | 一般 CO vs FORM E（ASEAN–China FTA） |
| `doc_form_e` | FORM E 等自贸协定证书 | `Form E for ACFTA duty preference` | 涉及关税优惠，必须核实我方能否出 |
| `doc_inspection` | 第三方检验 | `SGS / BV inspection at loading port` | 谁指定、谁付费 |
| `doc_dg` | 危险品单证 | `IMO declaration`、`DG certificate` | |
| `doc_audit` | 工厂审计/认证 | `ISO 9001`、`HALAL`、`Kosher`、`REACH`、客户现场审计 | 不能承诺没做过的认证 |
| `doc_lang` | 单证语言 | `documents in English` | |
| `doc_other` | 其他 | `packing list, invoice, B/L` | 常规单证不算"客户另外要求" |

## B 类 · 买方背景（Buyer-side context，可带假设）

`application`（应用/工艺）、`current_supplier`（现有来源）、`annual_scale`（年采购规模）、
`sample_stage`（是否首次询价）、`urgency`（时间压力）、`price_sensitivity`（价格敏感线索）。

这些字段**只做沟通参考**，不进报价，也绝不用于"成交可能性"打分。

## C 类 · 我方内部先定（Internal）

| key | 说明 |
|---|---|
| `our_entity` | 我方出口主体全称、地址、电话、网站、签字人 |
| `price_currency_basis` | 报价币种与基础（`USD/MT`） |
| `port_load` | 装运港（如客户未指定） |
| `tax_basis` | 出口报价是否含税（一般不含 VAT，需注明） |
| `incoterm_confirm` | 我方能否按客户术语承接 |

## 易混案例（背下来）

| 情形 | 正确记法 | 为什么 |
|---|---|---|
| `Soda ash dense granular, 300 MT trial, CFR Semarang` | 产品 = dense；数量 = 300 MT 试单；术语 = CFR + 地点 Semarang | 三件事三个字段 |
| `Please quote your best price CNF Semarang` | `incoterm=CFR`（规范），`raw="CNF"` | CNF 是旧写法，Incoterms 2020 为 CFR |
| `We need industrial grade` | 规格 = `ambiguous`；不要填 99.2% | 等级词不是数值规格 |
| `Payment: L/C` | `payment=ambiguous`，缺类型/期限/开证行 | 无法据此做价格 |
| `Kindly advise COA and MSDS` | `doc_coa=stated`, `doc_sds=stated`；`doc_form_e=missing` | 客户没说 Form E 就没有 |
| `Price should be competitive` | 进 H 类 `price_sensitivity`，**不填任何数字** | 敏感度不是价格 |
| 邮件签名 `Budi Santoso – Purchasing – PT Glassworks Nusantara` | 公司 = 全称；职位 = Purchasing Manager? 否，`Purchasing` 是部门 → `contact_title=ambiguous` | 别升格 |
| 客户转发里 `PT … (our plant in Semarang)` | `buyer_site` 有了，但目的港仍是港口不是厂区 | 目的地是港，厂址是地址 |

## 状态机

```
stated 已明确 ──销售修正──▶ stated（值变了，原文不变，记 overrides）
   │
   ├─ 客户没说 ─▶ missing（A 桶锁报价；B 桶用 assume 渲染）
   └─ 说了但不唯一/需客户点头 ─▶ ambiguous
```

- A 桶字段只允许 `stated` 才解锁"可报价"。
- `assumed` 只用于 B 桶，渲染时强制加 `(our assumption – to be confirmed)`。
- `internal` 只用于 C 桶，表示"等我方内部确认"，不进客户问题清单。
