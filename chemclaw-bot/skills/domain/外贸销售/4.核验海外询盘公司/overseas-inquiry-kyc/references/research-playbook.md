# 检索手册（Research Playbook）

## 一、检索的固定顺序

不要一上来就搜公司名。按下面顺序走，效率高十倍：

```
1. 先查负面（对方名字 + 停产/事故/处罚/破产/诉讼）
   → 搜不到负面也有用：说明公开负面检索这一环已完成
2. 再查官方登记（唯一标识优先：登记号 / NIB / 税号）
   → 拿到登记号之前，任何"关于这家公司"的说法都不能当事实
3. 再查官网与一手材料（About / Contact / Products / 团队页）
   → 同时截图存档，标抓取时间
4. 最后查行业与新闻（本币语言关键词，不是英文）
   → 印尼语、西班牙语、土耳其语、越南语各自的检索词不同
```

## 二、检索式模板

把 `{公司}`、`{城市}`、`{产品}` 替换掉。**每种语言都要单独跑一遍**，不要只用英文。

### 2.1 通用（任何国家）

```
"{公司}" + "investigation OR lawsuit OR penalty OR bankruptcy OR fraud"
"{公司}" + "{城市}" + "{产品}"
"{公司}" site:linkedin.com
"{公司}" + "annual report OR prospectus OR 10-K"
"{域名}" + "whois"
"@{域名}" + "email OR contact"
```

### 2.2 印尼（Bahasa Indonesia）

```
"{公司}" + "gugatan OR pailit OR sanksi OR sengketa"
"{公司}" + "berita"
"{公司}" + "pabrik OR kapasitas OR produksi"
"kaca" OR "soda ash" + "importir" + "Indonesia"
"PT" + "{公司简称}" + "NIB"
```

注意：印尼公司名常缩写（`PT Sinar Kaca Nusantara` → `PT SKN`），两种都要搜。

### 2.3 印度（India）

```
"{公司}" + "MCA OR CIN OR ROC OR GSTIN"
"{公司}" + "NCLT OR insolvency OR default"
"{公司}" + "export import code OR IEC"
```

### 2.4 越南（Vietnam）

```
"{公司}" + "mã số thuế"          # 税号即 MST
"{公司}" + "giấy phép kinh doanh"
"{公司}" + "kiện OR phá sản OR xử phạt"
```

### 2.5 土耳其（Türkiye）

```
"{公司}" + "MERSIS"
"{公司}" + "Ticaret Sicil Gazetesi"
"{公司}" + "dava OR icra OR iflas"
```

### 2.6 巴西（Brazil）

```
"{公司}" + "CNPJ"
"{公司}" + "consulta situação cadastral"
"{公司}" + "processo OR falência OR recuperação judicial"
```

### 2.7 海湾国家（UAE / Saudi / Egypt）

```
"{公司}" + "CR OR commercial registration"
"{公司}" + "chamber of commerce"
"{公司}" + "زكاة OR مقاضاة OR شكوى"     # 阿语
```

## 三、查不到怎么办（这是本 skill 出现频率最高的场景）

按下面四步走，**每一步都要写进报告**：

| 情况 | 处理 | 写进哪里 |
|---|---|---|
| 名称写法不同 | 换 3 种写法再搜（全称 / 去后缀 / 缩写） | `extraction[].note` |
| 平台需付费/需登录 | 写"入口已知、本次未付费查询"，并要求对方自证 | `checks[].unknowns` |
| 需要唯一标识才能查 | 把索取该标识列为 **P0** | `requests[]` |
| 确实没有公开记录 | 写"公开渠道未覆盖"，**不写"不存在"** | `checks[].boundary` |

> 判断标准：**"这个国家是否把该信息作为公开信息"** —— 不是"我搜没搜到"。
> 例如印尼 AHU 提供名称检索但完整档案付费，这属于"入口已知、未付费"，而不是"查无此公司"。

## 四、来源可信度分级（与 evidence-grading.md 配套）

| 级别 | 例子 | 能证明什么 |
|---|---|---|
| **A 官方** | AHU / OSS / MCA / CNPJ / 法院公告 / 制裁名单 / 海关 | 主体存在、许可状态、是否受限 |
| **B 一手独立** | 企业官网 About/Contact、年报、认证证书编号、协会会员目录 | 企业在做什么、在哪里、规模 |
| **C 二手** | 媒体报道、行业名录、黄页、社媒 | 只能作为线索 |
| **D 自述** | 对方邮件、名片、公司介绍 PDF | **只能提取，不能作结论** |

## 五、存档规范

每一条来源至少存四样：

1. `url`（打不开的写"对方提供/内部文件"）
2. `retrieved`（检索日期，精确到天）
3. `note`（这条能证明什么、不能证明什么）
4. 页面截图或 PDF（放 `evidence/` 目录，文件名含日期）

**链接会失效**，截图不会。没有截图的 A 级来源，下次复核时等于没有。

## 六、AI / 搜索引擎使用时的高危点

- 模型会**编造**看起来很像真的登记号。任何登记号必须去官方入口核一次才能写进报告。
- 搜索摘要里的"公司简介"多半是 SEO 文案，不能当 B 级证据。
- 同名企业的负面新闻极容易被搜索引擎混在一起——**先确认登记号再采信**。
- 域名注册信息里的"注册人"常是代理商，不能直接等同于企业主体。
