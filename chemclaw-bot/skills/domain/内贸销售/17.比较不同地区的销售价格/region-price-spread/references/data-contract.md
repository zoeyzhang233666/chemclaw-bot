# 数据契约（data.json）

一份数据 = 一个产品、一个规格、一个时间窗、2–5 个区域。`build_all.py` 只读这个文件。
UTF-8，snake_case，数值单位统一写在 `meta.unit`，正文不重复单位。

---

## 1. 顶层

```json
{
  "meta":      { ... },   // 必填
  "regions":   [ ... ],   // 必填，2–5 条
  "series":    { ... },   // 必填，价格序列
  "freight":   { ... },   // 必填，运费模型
  "narrative": { ... }    // 必填，结论/方法/缺口/免责
}
```

## 2. meta

| 字段 | 类型 | 说明 |
|---|---|---|
| `product` | str | 产品名，如「纯碱（重质纯碱）」 |
| `spec` | str | 规格与等级，必须能区分报价 |
| `unit` | str | 默认 `元/吨` |
| `basis` | str | 价格口径：含税出厂 / 含税到厂 / 主流成交价 … |
| `basis_note` | str | **口径混合时必须写**：哪些区偏出厂、哪些偏到厂、误差多大 |
| `asof` | str | `YYYY-MM-DD` |
| `window` | obj | `{start, end, label}`，label 给人看 |
| `freq` | str | 等距/非等距说明，如「7 月 1 个样本 + 8–10 月 9 个样本」 |
| `benchmark` | str | 基准区 id，价差与残差都相对它 |
| `default_origin` | str | 默认发货地 id |
| `default_mode` | str | 默认运输方式 id（water/road/rail） |
| `title` / `subtitle` | str | 标题与首屏一句话 |
| `tags` | [str] | 3–5 个标签，每条必须能被数据支撑 |
| `coverage_note` | str | 数据覆盖度一句话 |
| `est_note` | str | 估算声明（产能/需求是量级估算） |

## 3. regions（核心）

```json
{
  "id": "east", "name": "华东", "hub": "连云港",
  "lon": 119.22, "lat": 34.60,
  "price_basis": "主流价·含税（产区出厂与港口到厂混合）",
  "price_conf": "高",
  "light_range": "980–1400", "heavy_range": "1100–1200",
  "water_ok": true, "water_surcharge": 0,
  "water_note": "长江江运需中转，另加 45 元/吨",
  "supply": { "capacity": 780, "output": 690, "cr3": 41, "net": -223,
              "producers": [{"n":"连云港碱业","c":130,"t":"氨碱"}], "note": "…" },
  "demand": { "total": 913, "float": 260, "pv": 240, "light": 413, "note": "…" },
  "customers": [{ "n":"福莱特（嘉兴）","t":"光伏玻璃","s":"万吨级","note":"…" }],
  "gaps": [{ "k":"逐日到厂价","lvl":"中","t":"只有主流价" }],
  "judge": "该区域报价环境一句话判断"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `lon` / `lat` | ✔ | 枢纽坐标，运距由它算；填错会系统性偏移运费 |
| `water_ok` | ✔ | 是否有水运条件；内陆枢纽填 false，前端显示「不可达」 |
| `water_surcharge` | – | 该枢纽的水运中转附加费（元/吨），如长江港口 +45 |
| `supply.capacity/output` | ✔ | 万吨/年，估算 |
| `supply.net` | ✔ | 净平衡（正=净调出）；与 capacity/demand 不必自洽，它是独立事实 |
| `supply.cr3` | – | 前三家企业产能占比（%），用于判断区域定价权 |
| `demand.float/pv/light` | – | 需求结构拆分，用于归因 |
| `price_conf` | ✔ | 该区价格置信度（高/中/低），与 `series.sources` 匹配 |
| `gaps` | ✔ | 至少一条；`lvl` ∈ 高/中/低 |
| `judge` | ✔ | 40 字内的报价环境判断，写进卡片与 Excel |

## 4. series

```json
{
  "unit": "元/吨",
  "dates": ["2026-07-17", "2026-08-28"],
  "values": { "east": [1240, 1150], "south": [1300, 1250] },
  "gap_note": "7/17 与 8/28 之间无公开样本，曲线上以断点表示，不插值",
  "sources": [{ "date": "2026-07-17", "url": "https://…", "publisher": "同花顺 iFinD" }]
}
```

- `dates` 必须升序；`values` 每个数组长度与 `dates` 相同，缺失填 `null`（不要填 0）。
- 所有区域必须共用同一组 `dates`，这是「统一时间口径」的技术保证。
- `gap_note` 不可省：有断点却不说明，等于伪造连续性。

## 5. freight

```json
{
  "note": "运距 = 球面距离 × 绕行系数（陆 1.28 / 水 1.18），四舍五入到 10 km",
  "modes": [
    { "id": "water", "label": "水运", "rate": 0.06, "base": 25, "unit": "元/吨·km", "conf": "中", "note": "…" },
    { "id": "road",  "label": "汽运", "rate": 0.28, "base": 0,  "conf": "中" },
    { "id": "rail",  "label": "铁运", "rate": 0.12, "base": 30, "conf": "低" }
  ],
  "calibration": [{ "from":"east","to":"south","mode":"water","cost":124,"src":"…","conf":"中" }]
}
```

`calibration` 是自检锚点：用真实询价反推费率，写在这里，方便下次校核。

## 6. narrative

| 字段 | 说明 |
|---|---|
| `conclusions` | 4–6 条，必须带数字，先结论后判断 |
| `judge_rules` | 残差怎么读：阈值、持续周数、需要额外核对什么 |
| `method` | `[{k,v}]` 口径块：价格口径、价差定义、运费模型、残差、置信度分级 |
| `gaps` | 全局缺口，点名到「哪类数据、哪个区域」 |
| `disclaimer` | 必须写：不构成套利建议 + 真实交易还需核对什么 |

## 7. 校验规则（`validate.py`）

**error（阻断）**
1. 缺顶层键 / 缺 `cities` 类核心字段（本 skill 为 `regions/series/freight/narrative`）。
2. `regions.id` 重复；缺 `lon/lat` 或经纬度越界。
3. `series.values.*` 长度与 `dates` 不一致；`dates` 未升序。
4. `meta.benchmark` 不在 `regions` 中。
5. `narrative` 缺 `conclusions/method/gaps/disclaimer`。
6. 运费 `modes` 为空或缺 `rate`。

**warning（可构建但要修）**
1. `price_basis` 混合出厂/到厂却没写 `basis_note`。
2. `series.sources` 为空（价格不可回溯）。
3. 缺 `gap_note`。
4. 缺 `judge_rules`（读者只会看到数字）。
5. `conclusions` 少于 3 条。
6. 某区域缺 `water_ok`（水运可持续性不明）。
