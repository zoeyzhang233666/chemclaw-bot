# 数据源手册（免费、可核实、无需付费库）

原则：**能拿到官方原始数据的，就不要用二手转述**；每类数据都准备了 A/B 两个来源，
A 拿不到时用 B，并把“用的是 B”写进来源清单。

---

## 1. 贸易数据（报告的骨架）

### A. UN Comtrade 公开预览 API（首选，免密钥）

```
https://comtradeapi.un.gov/public/v1/preview/C/A/HS
  ?reporterCode=360          # 目标国（UN M49 / Comtrade reporterCode）
  &period=2021,2022,2023,2024,2025
  &partnerCode=              # 留空 = 全部伙伴
  &cmdCode=283620            # HS6，6 位纯数字，不要点
  &flowCode=M                # M=进口；X=出口
```

同时再拉一次 `reporterCode=156&flowCode=X&partnerCode=360`（中国对目标国出口）与
`reporterCode=156&flowCode=X&partnerCode=`（中国对世界出口，用于算占比）。

**处理要点（脚本已内置）**
- 过滤 `partner2Code == 0`：海关统计把“特殊类别”也当成伙伴返回，不过滤会重复计数。
- 按 `(partnerCode, year)` 去重。
- `primaryValue` = 美元；`netWgt` = 净重 **kg**，转吨 ÷1000。
- **净重为 0 或 null 就是没报送**，不要用金额÷单价去反推数量，也不要跨年插值。
- 伙伴代码 0 = 世界；`1000+` 系列是“特殊未分类”，展示时单独列或剔除。

**限流与失败**：预览 API 有频率限制。`fetch_trade.py` 每次请求间隔 1.5 s、失败重试 3 次、
写 `raw/comtrade_<rep>_<product>.json` 存档。**原始文件要留着**，报告里“取数记录”字段引用它。

### B. 各国海关 / 统计局官网（A 拿不到时）
- 印尼：BPS（bps.go.id）对外贸易统计、INSW（insw.go.id）
- 印度：Ministry of Commerce / DGCIS
- 越南：GSO
- 通用：UN Comtrade 网页版（comtradeplus.un.org，可导出 CSV）
- 备选汇总：WITS（wits.worldbank.org）、ITC Trade Map（免费注册）、TradingEconomics

⚠️ WITS / Trade Map / 第三方汇总站的数字可以**引用但要标 tier 4**，
不能当作“官方核实过的分录数”——它们常常滞后一年以上，且四舍五入。

### C. 中国侧数据
- 海关总署统计月报（HS 8 位）
- 中国五矿化工进出口商会（CCCMC）行业报告
- 联合国 Comtrade 中国 reporter 156（最便于与目标国数据同构对比）

---

## 2. 产能、消费、产业链

| 数据 | 首选来源 | 说明 |
|---|---|---|
| 全球/主要国产能产量 | USGS Mineral Commodity Summaries、各协会年报 | 纯碱看 USGS Soda Ash；official tier 1 |
| 目标国下游产量 | 目标国统计局年报、行业协会 | 精细化工多为缺口，直接写进 `gaps` |
| 在建/规划项目 | 企业公告、园区新闻、总统/部长站台报道、环评公示 | 用 `status` + `status_asof` 锁死时点 |
| 企业产品线与规模 | 企业官网、年报、招股书、当地工商登记 | „产能“不等于“产量”，`capacity_basis` 必须写清 |
| 市场规模估算 | IndexBox / Mordor / Grand View 等 | **只能标成机构估算**，方法不公开，不能作事实 |

**常用检索路径**
- 中文：`<产品> <国家> 进口`、`<国家> <产品> 项目 投产`、`中国 <产品> 出口 <国家> 份额`
- 印尼语/当地语：`sodium carbonat impor Indonesia`、`pabrik soda ash Indonesia`、`kaca lembaran kapasitas`
- 企业级：`<公司名> site:company.com`、`<公司名> annual report pdf`、`<公司名> TKDN`
- 官方：`site:go.id <关键词>`、`site:trade.gov <country> import tariffs`、`site:usgs.gov soda ash`

**取网页正文**：搜索摘要经常是残缺的，命中后用 `https://r.jina.ai/<url>` 取正文再摘录，
**摘录时把原文句子抄下来**放进 `facts`，方便日后复核。

---

## 3. 关税与政策（最容易被客户抓住的地方）

| 要查什么 | 去哪查 | 可信度 |
|---|---|---|
| 目标国 HS 8/10 位税率 | 目标国官方税则库（印尼 INSW / BTKI，可查 MFN 与 FTA 税率） | ★★★★★ 唯一可作为报价依据 |
| 协定税率资格与单证 | 中国海关总署原产地规则、东盟秘书处 ACFTA/RCEP 文本 | ★★★★★ |
| 平均关税与政策概览 | trade.gov Country Commercial Guides（美国 ITA） | ★★★★ 二手但权威，写明版本日期 |
| 非关税措施（许可/配额/标准） | 目标国部委法规原文；WTO I-TIP；trade.gov “Import Requirements” | ★★★★ |
| 增值税/预缴所得税 | 目标国税法 + 会计师事务所解读 | ★★★ |

**硬规则**：官方税则库没打开核过的税率，一律 `rate_pct: null` + `status: "gap"`，
正文写“第三方汇总站称 X%（WITS 20XX 口径），待核实”。见 `tariff-policy-guide.md`。

---

## 4. 国别经贸指南（第 8 问的“标准答案”）

- **中国商务部《国别贸易投资环境报告》《对外投资合作国别指南》**——中文，覆盖市场、政策、风险
- **中国贸促会 / 商协会国别报告**
- **US ITA Country Commercial Guides**——最有结构的一份，含关税、进口要求、贸易壁垒
- **World Bank / IMF 国别报告**——宏观与产业背景
- **目标国投资协调机构**（印尼 BKPM、越南 MPI 等）——准入门槛与本地化要求

这些都算 T2；引用时写明出版年份，因为政策章常常滞后。

---

## 5. 企业级信息的合法来源

1. 企业官网（产品页、工厂页、新闻稿）
2. 年报 / 招股书 / ESG 报告（印尼用 IDX 官网，中国用巨潮资讯）
3. 环评与项目公示（中国：环境影响评价信息平台；印尼：AMDAL 公示）
4. 当地主流媒体对开工/投产/签约的报道（Kompas、Bisnis、Antara 等）
5. 展会名录、海关提单类数据（付费，能不用就不用）
6. MSDS / SDS 上的进口商与分销商信息

**不要做**：把“某公司可能用我们的产品”写成事实；把 B2B 平台的“年采购量”当数据。

---

## 6. 抓取与解析的工程技巧

| 问题 | 处理 |
|---|---|
| 搜索结果摘要不全 | 用 `https://r.jina.ai/<url>` 取正文 |
| 页面是 PDF | jina 同样能转文本；政府 PDF 常有验证码（peraturan.bpk.go.id、部分 kemenperin.go.id），改用新闻稿或法规摘要站 |
| 站点 403 / 422 | 换官方镜像、换语言版本、找同内容的新闻稿 |
| 语言是印尼语/越南语/西语 | 让模型直接读原文并**原文摘录关键句**再翻译，不要用机翻结果当引文 |
| 时间是关键 | 每条来源必须有 `date`；政策类超过 12 个月要标“需复核” |

---

## 7. 数据质量自查（每次取数后）

1. 目标国进口合计 vs 中国对该国出口合计：同一产品同一年应该在同一量级（差距 10–30% 常见，差 3 倍就要查口径/单位）
2. 单位价值是否合理：纯碱 200–400 美元/吨，如果算出 20 或 20000，就是单位错了
3. 份额合计是否 100%（前 8 位可能不到 100%，剩下的写“其他”）
4. 数量与金额的年度趋势是否大体同向；背离通常是数量未报送造成的假象
