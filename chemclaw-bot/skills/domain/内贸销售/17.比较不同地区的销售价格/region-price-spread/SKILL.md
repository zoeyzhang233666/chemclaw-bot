---
name: region-price-spread
description: Use when a domestic (China) sales rep needs to compare the market price of one product/spec across 2–5 regions over a unified time window — naked spread, spread history, freight-adjusted residual, and what part of the gap is explained by transport vs regional supply/demand. Delivers a self-contained interactive HTML (region multi-select, price & spread curves, spread matrix, freight decomposition, region drill-down into local customers and supply structure) plus a 10-sheet Excel workbook. Product-agnostic. Triggers 比较不同地区的销售价格 / 区域价差 / 多地区价格对比 / 地区价差历史 / 裸价差 / 运费折算 / 各区域报价环境 / regional price comparison for a chemical product.
---

# 多地区价格与区域价差对比（化工品内贸）

把「同一个产品在不同地区卖多少钱」变成一张**能判断报价环境**的图和一本能查的表。
核心纪律只有一条：**裸价差、运费、结构因素必须分开说，价差本身不是套利结论。**

## 什么时候用

用：销售要进一个新区域、要给老板解释「为什么华南贵 100 元」、要判断某个区域是不是被运费锁死、要看价差是在扩大还是在收敛。

不用：只要区域客户名单 → `b2b-lead-sourcing`；只要某区域该先跑哪些城市 → `chemical-region-market-map`；只要同行动向 → `chemical-competitor-supply-map`。

## 交付物（至少这两个）

1. **自包含 HTML（约 1 MB，离线可开）**：区域多选（2–5）自动重算；价格曲线 + 价差曲线；价差矩阵；价差分解图；当前价差表（含运距/运费/残差/判读/置信度）；价差历史统计；区域卡片点开是当地客户与供应格局抽屉；口径、缺口、免责常驻。
2. **10 表 Excel**：概览 / 口径与时间轴 / 价格序列 / 价差分解 / 价差矩阵 / 价差统计 / 运费矩阵 / 供需与客户 / 数据缺口 / 方法与免责。

两个文件都由同一份 `data.json` 生成，**数字天然一致**。

## 三步走

```
① 取值（同一口径、同一时间轴）→ 写入 data.json
② 写供需与运费假设          → 同一个 data.json
③ 生成 + 体检              → HTML + Excel + qa
```

### ① 取值：先定口径，再找数

| 要什么 | 从哪来 | 注意 |
|---|---|---|
| 分区主流价（逐日/逐周） | 同花顺 iFinD「各地区现货价格」、隆众/卓创日评、期货公司周报 | 必须同一天、同一规格、同一含税口径 |
| 出厂 vs 到厂 | 产区偏出厂、销区偏到厂 | 混合口径会在价差里塞进 20–50 元/吨噪声，必须在 `basis_note` 说明 |
| 运费 | 公开运价区间 + 里程估算，或逐票询价 | 水运/汽运/铁运结论可能相反，必须分开算 |
| 供需 | 协会/年报/资讯的产能、产量、需求 | 只能做量级归因，不能当结算依据 |

**没有可分区的原始价格就不要做**：拿全国均价去拆区域，是这类需求最常见的伪交付。

### ② 写 data.json

字段见 `references/data-contract.md`。最小骨架：

```json
{"meta":{"product":"纯碱（重质）","spec":"重质纯碱 II 类","unit":"元/吨","basis":"含税主流价",
         "asof":"2026-10-16","benchmark":"east","default_origin":"east","default_mode":"water"},
 "regions":[{"id":"east","name":"华东","hub":"连云港","lon":119.22,"lat":34.60,
             "water_ok":true,"price_conf":"高",
             "supply":{"capacity":780,"output":690,"cr3":41,"net":-223},"demand":{"total":913}}],
 "series":{"dates":["2026-10-16"],"values":{"east":[1150]},"sources":[{...}],"gap_note":"…"},
 "freight":{"modes":[{"id":"water","rate":0.06,"base":25}]},
 "narrative":{"conclusions":[…],"method":[…],"judge_rules":[…],"gaps":[…],"disclaimer":"…"}}
```

### ③ 生成 + 体检

```bash
python scripts/build_all.py data.json --out out --name 纯碱多地区价格对比
# 或分步
python scripts/validate.py data.json
python scripts/build_html.py data.json --out out --name 纯碱多地区价格对比
python scripts/build_xlsx.py data.json --out out --name 纯碱多地区价格对比
python scripts/qa.py data.json out/xxx.html out/xxx.xlsx
```

`qa.py` 会核对：占位符是否清空、HTML 内嵌数据能否解析、区域/样本数、Excel 十张表是否齐全、价格是否与 JSON 一致、缺口是否逐条入表。

## 质量红线（不达标别交付）

1. **同一时间口径**。所有区域必须取同一天/同一周的样本；日期不一致就要在 `gap_note` 点名，不许插值冒充连续序列。
2. **裸价差与运费分开列**。表里必须有「裸价差 / 运费 / 残差」三列，只给价差的表等于没做。
3. **运费按方式分算**。水运、汽运、铁运各算一遍，至少给出默认方式 + 一种对照；同一价差在两种口径下结论相反是常态（本案华南即是）。
4. **不能把价差写成机会**。判读只允许用「运费已解释 / 本地偏紧 / 运费反超 / 价格趋同」这类描述，并附 `disclaimer`。
5. **残差不是归因**。残差 = 裸价差 − 运费，里面混着供需、库存、品质、账期和口径噪声；写报告时必须列至少两种可能原因，不能一句话归因。
6. **缺口点名到项**。每个区域至少一条 `gaps`，写清缺什么、缺到什么程度、下一步怎么补。
7. **供需数字标估算**。产能/产量/需求是万吨/年量级估算，不能写成统计口径。
8. **价格可回溯**。`series.sources` 每条带 URL 与发布日期，`price_conf` 与来源匹配（拿不到原始文章就只能给「中/低」）。

## 别踩的坑（都是真踩过的）

- **整数主流价会假装稳定**：同花顺主流价是 50 元步长的整数，9–10 月五区全部持平。这不是数据坏了，是口径特征——要在结论里说明「价差被锁定」，而不是硬找波动。
- **水运对内陆枢纽不成立**：成都、沙河没有直达水运，模型必须给 `water_ok:false` 并让前端显示「不可达」，否则会算出一段不存在的运距。
- **江运要加中转费**：武汉这类长江港口到沿海需要中转（+40~50 元/吨），不加会把「江海联运」算得比实际便宜，凭空造出套利空间。
- **运距系数要固定**：球面距离 × 1.28（陆路）/ × 1.18（水运），四舍五入到 10 km；否则每次生成的里程都不一样。
- **模板占位符**：用 `%%DATA%%` 不要用 `__DATA__`，后者会连 JS 变量名一起替换。生成器已内置占位符清零校验。
- **HTML 里不能出现 `</script>`**：数据里的 URL 或正文若带这个串会截断脚本，`build_html.py` 会直接报错。

## 示例

- `examples/01-soda-ash-5-regions/`：纯碱（重质）华东/华南/华北/华中/西南，2026-07-17 至 2026-10-16，10 个样本，含 data.json 与成品 HTML/Excel，可当写作范本。

## 换产品怎么用

只换 `data.json`：改 `meta`、`regions`（含枢纽坐标与 `water_ok`）、`series`、`freight.modes` 的费率、`narrative` 的文字。脚本一行不用改。
产品跨区流动越强（纯碱、甲醇、PP），价差越贴运费；越弱（区域性强、运费占比高），残差越大——这本身就是判断依据。
