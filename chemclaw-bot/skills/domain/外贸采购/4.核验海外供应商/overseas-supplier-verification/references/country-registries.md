# 各国官方登记入口与编号格式

> 用途：查"这家企业是否合法存在"。**优先官方，其次监管披露，再次企业官网。**
> ⚠️ 访问情况因地区网络而异；打不开时如实标注「未知」并索取证书原件，不要用第三方名录替代。

---

## 通用检索顺序

```
1. 企业注册登记系统（Registrar of Companies）
2. 税务/统一识别号系统
3. 证券监管披露（若上市）
4. 商会/行业协会名录
5. 企业官网（含注册号披露）
```

---

## 亚洲

### 沙特阿拉伯 🇸🇦（化工进口高频）

| 渠道 | 地址 | 能查什么 |
|---|---|---|
| 商务部（Ministry of Commerce, MC） | `mc.gov.sa` → eServices → 商业登记查询 | CR 号、公司名、状态、地址 |
| 全国统一门户 | `my.gov.sa` → 服务"Query about Commercial Registration Data" | 同上 |
| Wathq（官方数据平台） | `wathq.sa`（API 版，部分需付费） | CR、合伙人、股权、章程 |
| Tadawul（沙特交易所） | `saudiexchange.sa` | 上市公司发行人名录、公告 |
| 工业与矿产资源部（MIM） | `mim.gov.sa` | 工业许可证、工厂地址 |

**编号格式**：CR 为 **10 位数字**，前 2 位为地区码（10xx 利雅得、20xx 吉达/西部、2055 朱拜勒一带、47xx 麦地那/延布）。
**工业许可**：形如 `S/1367`（S = 序列，后接编号）。
**易混**：公司名常用"商业名称+法定名称"双轨（如 PETROKEMYA = Arabian Petrochemical Company），检索要用法定名称。

### 阿联酋 🇦🇪

| 渠道 | 地址 | 说明 |
|---|---|---|
| 迪拜 DED | `ded.ae` / Dubai Trade | 贸易执照号（License No.） |
| 阿布扎比 ADDED | `added.gov.ae` | 同上 |
| 各自由区管理局 | JAFZA / DMCC / SAIF Zone 等官网 | 自由区公司执照 |

**编号格式**：Dubai Mainland 贸易执照多为 7 位数字；自由区执照各局不同。
**注意**：FZE / FZCO / FZ-LLC 表示自由区企业，不能在迪拜本土直接经营，需代理。名称含 `FZE` 常见于大宗商品贸易公司。

### 印度 🇮🇳

| 渠道 | 地址 | 能查什么 |
|---|---|---|
| MCA | `mca.gov.in`（Company Master Data） | CIN、公司状态、董事、财务报表 |
| GST 门户 | `gst.gov.in`（Search Taxpayer） | GSTIN、注册地址、状态 |
| DGFT | `dgft.gov.in`（IEC 查询） | 进出口编码 |
| UDYAM | `udyamregistration.gov.in` | MSME 登记 |

**编号格式**：CIN 21 位（如 `U24100MH1990PLC056789`）；GSTIN 15 位；IEC 10 位。

### 日本 🇯🇵

| 渠道 | 地址 | 说明 |
|---|---|---|
| 法人番号公表サイト | `houjin-bangou.nta.go.jp` | 13 位法人番号 |
| 商業登記（法務局） | 登记簿誊本需付费取得 | 官方证明 |

### 韩国 🇰🇷

| 渠道 | 地址 |
|---|---|
| 国税厅 事业者登录番号 | `hometax.go.kr`（10 位） |
| 法人登记所 | 法院登记所（登记事项证明书） |

### 新加坡 🇸🇬

| 渠道 | 地址 | 说明 |
|---|---|---|
| ACRA Bizfile+ | `bizfile.gov.sg` | UEN（9–10 位）、公司状态 |

### 中国台湾地区 / 香港 / 其他

| 地区 | 渠道 |
|---|---|
| 台湾 | 经济部商业司「商工登记公示资料查询服务」 |
| 香港 | 公司注册处 ICRIS（CR No. 7 位） |
| 越南 | 国家企业登记门户 `dangkykinhdoanh.gov.vn` |
| 泰国 | DBD `dbd.go.th` |
| 马来西亚 | SSM `ssm.com.my` |
| 印尼 | AHU Online `ahu.go.id` |

---

## 欧洲

### 德国 🇩🇪
- `handelsregister.de`：HRB/HRA 号、公司状态、管理者
- 增值税号：USt-IdNr.（DE + 9 位）

### 英国 🇬🇧
- `find-and-update.company-information.service.gov.uk`：Company No.（8 位）、董事、财务报表

### 荷兰 🇳🇱
- KVK `kvk.nl`：KvK 号（8 位）

### 法国 🇫🇷
- `annuaire-entreprises.data.gouv.fr`：SIREN（9 位）/ SIRET（14 位）

### 意大利 🇮🇹
- `registroimprese.it`：REA 号、Codice Fiscale / P.IVA

### 西班牙 🇪🇸
- `registradores.org`：CIF（如 B-12345678）

### 波兰 / 东欧
- 波兰 KRS（10 位）+ NIP（10 位）：`krs-online.com.pl` / `rejestr.io`
- 捷克：ARES 系统

### 欧盟层（对化工尤为重要）
- REACH：`echa.europa.eu`（物质注册、唯一代表 OR 信息）
- 制裁：EU Consolidated Financial Sanctions List

---

## 美洲

### 美国 🇺🇸
| 渠道 | 说明 |
|---|---|
| Secretary of State（各州） | LLC/Corp 注册、EIN（9 位，需通过 IRS 或经销商查询） |
| SEC EDGAR | 上市公司财报 |
| OFAC SDN / BIS Entity List | 制裁与出口管制 |
| EPA / TSCA | 化学品合规 |

**编号**：EIN 9 位（XX-XXXXXXX）；州注册号因州而异。

### 加拿大 🇨🇦
- Corporations Canada（联邦）；企业编号（BN，9 位）

### 巴西 🇧🇷
- Receita Federal：CNPJ（14 位，如 `12.345.678/0001-90`）

### 墨西哥 🇲🇽
- `rpc.economia.gob.mx`：RFC（12–13 位）

---

## 中东与非洲

| 国家 | 渠道 | 编号 |
|---|---|---|
| 卡塔尔 🇶🇦 | MOCI `moci.gov.qa` | CR（数字） |
| 科威特 🇰🇼 | MOCI | CR |
| 阿曼 🇴🇲 | 商务部 | CR |
| 巴林 🇧🇭 | `sijilat.bh` | CR |
| 埃及 🇪🇬 | GAFI | Tax Card / Commercial Register |
| 南非 🇿🇦 | CIPC | 注册号（如 2015/123456/07） |
| 土耳其 🇹🇷 | 贸易登记公报（TTSG） | MERSİS（16 位） |
| 以色列 🇮🇱 | 司法部公司登记处 | 公司号（9 位） |

---

## 供应商提交文件核对要点

收到注册证书时，检查：

- [ ] 编号位数/前缀是否符合该国格式（见上）
- [ ] 公司名与 PI / 合同完全一致（含标点、缩写）
- [ ] 注册地址与合同地址一致
- [ ] 状态为「存续/Active」
- [ ] 是否有 QR / 验证码（现代证书多有）
- [ ] 签发日期是否在合理范围
- [ ] 图纸/字体是否有拼接痕迹（看边缘、印章位置）
- [ ] **能用手持核验的，一定做实名核验**（必要时委托当地代理或律师）

---

## 打不开官方系统时的标准写法

```markdown
| 要素 | 核验结果 | 状态 |
|---|---|---|
| 商业登记号 CR | 公开来源未检索到；官方查询页在本次网络环境下无法直连 | 未知 |

注：属核验环境限制，需在可访问网络下补做或委托当地代理；不得以第三方名录替代官方登记。
```
