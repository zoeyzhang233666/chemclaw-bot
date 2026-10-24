# 公司模板骨架（复制后填，一次填好长期用）

> 用法：把本文件复制成 `company_my.md`，把所有 `‹…›` 换成真实信息，
> 然后 `python scripts/extract.py … --template company` 会用它覆盖默认签名与开场。
> **填不出来的项就留占位符**——留空比编造安全。

---

## 1. 公司与主体

```yaml
company_name_en:   ‹OURCOMPANY_NAME›
company_name_cn:   ‹公司中文名›
legal_entity:      ‹出口主体全称（与报关一致）›
country:           ‹China›
city_park:         ‹工厂所在地 / 化工园区›
website:           ‹https://…›
export_license_no: ‹对外贸易经营者备案号›
```

## 2. 对接人

```yaml
signer_name:  ‹SIGNER_NAME›
signer_title: ‹SIGNER_TITLE›
signer_email: ‹SIGNER_EMAIL›
signer_phone: ‹+86 …›
signer_wechat_whatsapp: ‹…›
```

## 3. 常用参数（写死的"我方标准"，不是承诺）

```yaml
standard_packing:      ‹25 kg PP woven bag with PE liner / 1000 kg jumbo bag›
loading_capacity_20gp: ‹20 MT (with pallet) / 25 MT (without pallet)›
port_of_loading:       ‹Shanghai / Ningbo / Qingdao›
common_incoterms:      ‹FOB, CFR, CIF (Incoterms 2020)›
quote_currency:        ‹USD›
default_validity_days: ‹由销售逐单确定，勿在此写默认值›
```

> 注意最后一项：**不要**在这里写"默认 30 天有效"。有效期是商务决定，
> 写进模板会变成不经思考的默认值，而默认值就是风险。

## 4. 单证能力（务必如实）

```yaml
docs_always:        COA (per lot), SDS (GHS), TDS
docs_on_request:    ‹Certificate of Origin / ACFTA Form E / 第三方检验›
docs_unavailable:   ‹明确列出我们不提供的，避免客户期待落空›
```

## 5. 开场与结尾句（语气档）

| 语气 | 开场 | 结尾 |
|---|---|---|
| friendly-professional（默认） | `Thank you for your inquiry dated {date} regarding {product}.` | `We look forward to your reply.` / `Best regards,` |
| formal | `We thank you for your inquiry dated {date} regarding {product}.` | `We look forward to your reply.` / `Yours faithfully,` |
| concise-direct | `Thank you for your inquiry re {product}.` | `Looking forward to your confirmation.` / `Regards,` |

## 6. 免责与合规句（可选，大公司常需要）

```
This message is intended only for the addressee. Prices, specifications and
delivery terms, if any, are indicative and subject to our written confirmation.
```

---

## 检查清单（填完自查）

- [ ] 主体全称与报关单、提单一致
- [ ] 签名人邮箱是我们域名
- [ ] 标准包装写了袋型 + 净重 + 是否托盘
- [ ] 单证能力三栏都填了（含"不提供"的）
- [ ] 没有任何一个价格、库存、交期数字
- [ ] 没有"保证 / 承诺 / 一定"这类词
