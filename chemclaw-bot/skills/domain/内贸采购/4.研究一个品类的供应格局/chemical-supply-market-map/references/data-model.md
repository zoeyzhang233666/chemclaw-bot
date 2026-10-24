# 数据模型：project.json + 三个数据文件

四个文件构成**一个事实来源**。脚本对所有字段做兜底：缺字段不报错，只降级（例如没有经纬度就不画气泡）。
但**口径类字段缺失会导致报告说错话**，因此下表中标 ⚠ 的字段建议必填。

命名约定
- 产能单位默认 `万吨/年`，由 `product.unit` 统一控制；价格单位由 `product.price_unit` 控制。
- 所有来源用 `S1`、`S2`… 编号，与 `sources[].id` 一一对应。
- 拿不到的值写 `null` 或字符串 `"数据缺口"`，**不要写 0**。0 代表「确实没有」，两者含义完全不同。

---

## 1. project.json

### 1.1 product（品类）

| 字段 | 类型 | 说明 |
|---|---|---|
| ⚠ `name` | str | 全名，含化学名与分子式，如「纯碱（碳酸钠，Na₂CO₃）」 |
| ⚠ `short` | str | 简称，用于文件名与标题，如「纯碱」 |
| `aliases` | list[str] | 别名，便于检索与交叉验证 |
| `grades` | str | 规格/等级，如「重质/轻质」「32%/50% 液碱、片碱」 |
| `cas` | str | CAS 号（同时用作封面品牌位） |
| ⚠ `unit` | str | 产能单位，默认「万吨/年」 |
| ⚠ `price_unit` | str | 价格单位与税则口径，如「元/吨（含税）」 |
| `hs_code` | str | 海关编码（做进出口分析时需要） |

### 1.2 scope（范围与口径）

| 字段 | 说明 |
|---|---|
| ⚠ `geography` | 地域，必须具体 |
| ⚠ `boundary` | 统计边界：含什么、不含什么（「不含小苏打深加工产能」） |
| ⚠ `base_year` | 基准年（int） |
| `forward_years` | 前瞻年份 `[2026, 2028]`，第一个用于「预测年」标签 |
| `report_date` / `data_cutoff` | 报告日期与数据截止日（都显示在页头页脚） |
| ⚠ `basis_notes` | 口径提示列表，逐条写「为什么有多个数字、本报告怎么处理」 |

### 1.3 buyer（采购方参数，可选）

`applies` `volume_10kt`（年用量万吨）`landed_price` `freight` `stock_days` `grade` `delivery` `note`。
用于采购量测算：年度金额 = 年量 × (到厂价 + 运费)；月提货 = 年量/12；安全库存 = 年量 × 天数/365。

### 1.4 metrics（关键指标）

| 字段 | 说明 |
|---|---|
| ⚠ `capacity_total` | 全国产能（基准年）。有多个口径时填采用值，其余写进 `capacity_total_note` |
| `capacity_total_label` | 标签，如「2025 年全国产能」 |
| `capacity_total_source` | 来源 ID |
| `capacity_total_note` | 其他口径说明，如「其他公开口径 4,078–4,500」 |
| `capacity_forward` / `capacity_forward_label` | 预测年名义产能 |
| `capacity_forward_alt` | `{value,label,source}` 有效产能等替代口径 |
| `output` / `output_alt` | 产量与替代口径（list of `{value,label,source}`） |
| `utilization` | 开工率 % |
| `producers` / `cr5` | 在产企业数、CR5 |
| `cr5_forward` | `{low, high, note}` |
| `sample_capacity` / `sample_coverage` | 样本合计与覆盖率（脚本会校验是否与 plants 加总一致） |
| `price_now` / `price_now_label` / `drawdown` | 当前价与较峰值跌幅 |
| `export` / `inventory` | 出口、库存 |

脚本会额外算：`sample_groups` `sample_sites` `hhi_industry` `cr5_computed` `hhi_region`
`top4_region_share` `top5_region_share`，不必手填。

### 1.5 verdicts（核心结论，1–6 条）

```json
{"id":"V1","title":"一句话结论","evidence":"数字 + 口径 + 来源",
 "implication":"对采购意味着什么（可执行）","confidence":"高|中高|中|中低|低",
 "sources":["S1","S12"],"memo":"补充说明"}
```

### 1.6 routes（工艺路线）

```json
{"name":"联碱法","cap":2058,"share":46.1,"color":"#1d4ed8",
 "producers":"代表企业","raw":"主要原料","unit":"单耗与副产",
 "energy":"能耗特征","byproduct":"副产物",
 "cost_low":1050,"cost_high":1200,"advantage":"优势","risk":"风险","source":"S1"}
```
+ `routes_note`：未单列的小路线说明（防重复计数）。

### 1.7 markets（区域价差）

```json
{"region":"华东","price":1150,"note":"覆盖省份与市场特征","source":"S16"}
```

### 1.8 region_meta（区域画像）

```json
{"河南":{"activity":"B","downstream":"主要下游/流向","hub":"代表园区/城市"}}
```
`activity_legend` 定义 A/B/C 含义（**不要编造贸易商数量**，只能定性分级）。

### 1.9 prices（价格）

| 子字段 | 结构 |
|---|---|
| `lines` | `[{name,color}]` 图表系列 |
| `annual` | `[{year,avg,low,high,note,source}]`，峰值与均价分开写 |
| `periods` | `[{period,time,light,heavy,avg,change,driver,source}]` 阶段复盘 |
| `current` | `[{label,value,date,source}]` 当前各口径报价 |
| `outlook` | `{base,up,down,procurement}` 情景与采购含义 |
| `caveat` | 口径免责 |

### 1.10 strategies / supplier_mix

```json
[{"title":"双源，但不平均","how":"具体做法","terms":"关键条款","kpi":"可验收指标"}]
[{"type":"天然碱主供","share":0.55,"candidates":"候选企业","role":"作用","color":"#0f766e"}]
```
`share` 之和应为 1。

### 1.11 risks / gaps / dd / scorecard / sources

```json
{"risk":"…","likelihood":"高|中|低","impact":"…","level":"高|中高|中|低","evidence":"…","action":"…"}
{"gap":"…","impact":"…","status":"…","fill":"怎么补、找谁补","priority":"高|中高|中|中低"}
["类别","尽调问题"]                              // dd
["维度", 权重, "评分要点"]                        // scorecard，权重合计 100
{"id":"S1","name":"…","publisher":"…","date":"2026-04-29","url":"https://…","used":"…","confidence":"高"}
```

---

## 2. plants.json（基地级产能）

```json
{"plants":[
  {"id":"P01","company_id":"博源化工","site":"阿拉善塔木素","province":"内蒙古","city":"阿拉善盟",
   "lat":39.4,"lon":104.2,"route":"天然碱","capacity_base":500,"capacity_forward":780,
   "product":"重质/轻质纯碱","raw":"天然碱矿","status":"在产","listed":"000683",
   "source":"S2","note":"二期爬坡","dx":8,"dy":8}
]}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✅ | 唯一；重复会报错 |
| `company_id` | ✅ | 必须与 companies.json 的 `id` 对应（不一致只告警） |
| `site` | ✅ | 基地名（工厂，不是集团） |
| `province` | ✅ | 省级行政区；缺失时从 `city` 里识别，识别不到用「未标注」 |
| `city` | | 地级市 |
| `lat` / `lon` | | 经纬度：**只填查得到的，不估算** |
| `route` | | 工艺，与 routes 名称对应（允许缩写：联碱 ↔ 联碱法） |
| `capacity_base` | ✅ | 基准年产能 |
| `capacity_forward` | ✅ | 预测年产能 |
| `status` | | 在产 / 爬坡 / 达产 / 在建 / 拟建 / 停产 / 退出（缺省按产能变化推断） |
| `listed` | | 股票代码 |
| `source` | ⚠ | 来源 ID；没有就写「未核实」 |
| `note` | | 口径备注 |

也支持直接写成数组 `[...]`，不包 `{"plants": [...]}`。

---

## 3. companies.json（集团画像）

```json
{"companies":[
  {"id":"博源化工","name":"博源化工（原远兴能源）","code":"000683","hq":"内蒙古",
   "nature":"民营","route":"天然碱","capacity_base":680,"capacity_forward":960,
   "output_base":711.12,"utilization":"数据缺口",
   "strengths":["…"],"risks":["…"],
   "procurement":"采购判断","sources":["S2"],
   "dd":["企业特有的尽调问题"]}
]}
```
`capacity_base/forward` 不填时用 plants 加总；`dd` 为空时抽屉会显示通用尽调问题前 8 条。
**没有公开画像的集团可以不写**，脚本会生成最小画像并标注「数据缺口」。

---

## 4. projects.json（项目与净增）

```json
{"projects":[
  {"id":"J01","name":"博源阿拉善二期","company_id":"博源化工","province":"内蒙古",
   "route":"天然碱","capacity":280,"capacity_retired":0,"type":"扩建","status":"在建",
   "date":"2025-12","year":2026,"step":"投料试车","net":280,
   "impact":"对供给的影响","source":"S11"}
]}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `capacity` | ✅ | 毛产能（项目规模） |
| `capacity_retired` | ⚠ | 置换/退出产能；置换类**必填** |
| `type` | ⚠ | 新建 / 扩建 / 技改 / 置换 / 搬迁 / 退出 |
| `status` | | 已投产 / 在建 / 拟建 / 规划 |
| `date` | ✅ | `YYYY-MM`，时间线按此排序与分组 |
| `net` | ⚠ | 净影响。填数字即采用；`null`/缺省时：有 `capacity_retired` 则自动算差，否则显示「待确认」 |
| `impact` | | 对供给的影响（一句话） |

---

## 5. 校验规则（validate_dataset 会检查）

- 错误：`product.name` 为空、`plants` 为空、`sources` 为空、plant id 重复、source id 重复。
- 警告：缺 province、有产能为 0 的行、无 source、无经纬度、status 不在枚举、工艺未在 routes 注册、
  来源无 URL、置换项目没填退出产能、`scorecard` 权重≠100、`metrics.sample_capacity` 与 plants 加总不一致。
- 警告不影响出文件，但**交付前必须逐条确认**：要么已修正，要么已是登记在案的缺口。
