# 通用五步法（其它国家）

任何国家都能用这五步。**只有"去哪查"和"要哪份证"需要替换**，判定纪律不变。

## 五步

```
1 定位登记入口   —— 该国是否存在公开的商事登记查询？名称检索还是编号检索？
2 取得唯一标识   —— 登记号 / 税号 / 海关号 / LEI。没有它，就不能合并任何信息。
3 交叉两个独立源 —— 登记册 × 官网/年报/协会；单一来源永远不足以"已核实"。
4 业务分类对照   —— 该国是否有业务分类码（KBLI / CNAE / NIC / NACE）？对得上吗？
5 风险名单       —— 制裁、法院、破产、经营异常、行业黑名单。
```

## 快速索引表

| 国家 | 登记入口 | 唯一标识 | 业务分类 | 税号 |
|---|---|---|---|---|
| 印尼 ID | ahu.go.id（名称/登记号） | NIB（13 位） | KBLI | NPWP |
| 印度 IN | mca.gov.in / MCA21 | CIN（21 位） | NIC | GSTIN / PAN |
| 越南 VN | dangkykinhdoanh.gov.vn | 企业代码（MST） | 行业代码 | MST |
| 泰国 TH | dbd.go.th | 13 位注册号 | TSIC | 税号 |
| 土耳其 TR | mersis.tobb.org.tr / 商登记公报 | MERSIS 号 | NACE | VKN |
| 巴西 BR | Receita Federal CNPJ 查询 / Junta Comercial | CNPJ（14 位） | CNAE | CNPJ |
| 墨西哥 MX | SIGER / 商会 | RFC | SCIAN | RFC |
| 阿联酋 AE | 各酋长国 DED + 商会 | 营业执照号 / CR | — | TRN |
| 沙特 SA | MCI / 商会 | CR 号 | ISIC | VAT |
| 埃及 EG | GAFI | 商业注册号 | — | 税卡号 |
| 美国 US | 州务卿（Secretary of State） | EIN / 州注册号 | NAICS | EIN |
| 德国 DE | Handelsregister / Unternehmensregister | HRB/HRA 号 | NACE | USt-IdNr |
| 荷兰 NL | KVK | KVK 号（8 位） | SBI | BTW |
| 西班牙 ES | Registro Mercantil / BORME | CIF | CNAE | CIF |
| 波兰 PL | KRS / CEIDG | KRS / NIP | PKD | NIP |
| 俄罗斯 RU | EGRUL | OGRN / INN | OKVED | INN |
| 尼日利亚 NG | CAC | RC 号 | — | TIN |
| 南非 ZA | CIPC | 注册号 | — | VAT |
| 澳大利亚 AU | ASIC / ABN Lookup | ABN / ACN | ANZSIC | ABN |
| 巴基斯坦 PK | SECP | NTN | — | NTN |

> 上表只用于定位方向。**每次都要核对入口是否仍有效**（政府网站改版频繁），
> 并在 `sources[].retrieved` 里写下检索日期。

## 各国注意点

### 印尼
- 公司类型：PT（有限责任）/ CV（合伙）/ Perum（国企）/ PT PMA（外资）。
- `PT` 是法律形式前缀，**必须逐字比对是否含该前缀**。
- 名称检索靠 AHU；许可与 NIB 在 OSS；完整档案要付费。
- 详见 [`idn.md`](idn.md)。

### 印度
- CIN 前 3 位是上市状态（L/U），中间是行业码，可据此判断"自称制造业但 CIN 显示 U 类"等矛盾。
- 检查 NCLT（破产法庭）与 IBBI 公告。
- GSTIN 有校验位，可验证格式；GST 状态（active/cancelled）在 GST 门户可查。

### 越南
- 企业代码同时是税号（MST），10 位或 13 位（分支机构）。
- 国家企业登记门户可按名称查询，能拿到经营范围与法定代表人。

### 土耳其
- Ticaret Sicil Gazetesi（商登记公报）是公开的，能查到成立公告、章程、董事变更——这是最有价值的公开源之一。
- 检查 İcra（执行）/ İflas（破产）公告。

### 巴西
- CNPJ 的 "situação cadastral"（登记状态）必须是 ATIVA。
- CNAE 是业务分类，与经营范围强相关。
- 检查 Receita Federal 的异常名单与法院（processo）检索。

### 海湾国家
- 通常需要商会（Chamber of Commerce）会员身份，可作为 B 级交叉源。
- 自贸区公司（Free Zone）与本土公司（Mainland）权限不同，进口权不同。

### 美国 / 欧盟
- 美国公司不必在联邦登记（EIN 不发证），要找**州务卿**；跨州经营还需 foreign qualification。
- 欧盟多在商业登记簿 + 官方公报（如德国 Unternehmensregister、西班牙 BORME）。

## 风险名单（通用）

| 名单 | 用途 | 检索方式 |
|---|---|---|
| OFAC SDN / Consolidated | 美国制裁 | 官网搜索 |
| EU Consolidated List | 欧盟制裁 | 官网搜索 |
| UN Security Council List | 联合国制裁 | 官网搜索 |
| UK OFSI | 英国制裁 | 官网搜索 |
| 世界银行 Debarred Firms | 世行禁入名单 | 官网搜索 |
| 各国破产/执行公告 | 偿付能力 | 各国法院门户 |

**模糊命中不算命中**：名称相似但国家、行业、地址都不同，只能写"需核实"。

## 通用检索式

```
"{company}" + "registration number OR company number OR CIN OR CNPJ OR NIB"
"{company}" + "sanctions OR OFAC OR debarred"
"{company}" + "bankruptcy OR insolvency OR liquidation"
"{company}" + "court OR lawsuit OR judgment"
"{company}" + "chamber of commerce"
"{domain}" + "whois"
```

多语种：印尼语、西班牙语、葡语、土耳其语、越南语、阿语各跑一遍，不要只用英文。
