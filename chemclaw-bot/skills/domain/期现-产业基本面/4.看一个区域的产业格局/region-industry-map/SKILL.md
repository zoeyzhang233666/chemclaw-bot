---
name: region-industry-map
description: Use when someone needs to understand the industry structure of a product in a region — 看一个区域的产业格局 / 某品种在某省有多少生产企业、产能在哪、装置在哪个园区、上游原料从哪来、下游谁在买、有没有新项目、为什么各地价格不一样。Covers per-province/per-city counts of real producers and traders, verified plant sites with registered address vs actual plant address kept apart, chemical parks and their supporting infrastructure, upstream feedstock origins, downstream consuming industries, representative firms with process route and public capacity, new/under-construction/planned projects with gross-vs-net capacity, regional price/logistics/supply-demand features, and the objective factors behind regional price spreads. Delivers a self-contained interactive HTML regional industry map plus a 14-sheet Excel workbook, every number carrying a source id, and every missing datum explicitly marked as a gap instead of estimated. Product- and region-agnostic.
license: MIT
---

# 区域产业格局地图（品种 × 区域）

把「某品种在某区域到底是个什么产业」变成一张能点、能查、能溯源的地图 + 一本能直接核数的表。
**品种无关、区域无关**：纯碱、尿素、钛白粉、烧碱、磷酸铁锂都走同一套流程；换品种只换一份 `regions.json`。

## 什么时候用

用：要回答「这个区域的产业基础是什么、供需结构长什么样、物流关系怎么走、为什么各地价格有差」。

不用：
- 只要报价与行情 → `chem-market-brief` / `chem-procure-brief`
- 只要走访优先级与客户名单 → `chemical-region-market-map` / `b2b-lead-sourcing`
- 只要项目线索 → `project-lead-sourcing`

本 skill 的输出是**产业底稿**：点位、产能、园区、上下游、项目、价格特征、集中度。

## 交付物

| 文件 | 内容 |
|---|---|
| `<品种>-<区域>产业格局地图.html` | 自包含单文件（约 1.4 MB，离线可开）：中国/区域底图 + 5 类图层、点省市/园区看企业数与产能、工艺/规模/角色筛选、工厂总表、产能对比图、上下游桑基图、价格序列、集中度、口径与缺口、来源清单。 |
| `<品种>-<区域>产业格局数据包.xlsx` | 14 表：封面目录 / 核心结论 / 生产企业总表（注册地址 vs 生产地址分列） / 区域汇总 / 点位核验 / 化工园区 / 产能与工艺 / 上下游关联 / 新增在建项目 / 价格与供需 / 集中度与价差 / 数据缺口 / 口径与核验 / 来源清单。 |

两个文件都从同一份 `regions.json` 生成，**数字天然一致**（`qa.py` 会交叉核对）。

## 三步走

```
① 研究（本 skill 的取证通道）  → 结构化事实
② 写 regions.json（数据契约）  → 一份 JSON 描述一个品种在一个区域
③ 生成 + 体检                 → HTML + Excel + qa
```

### ① 研究：八个必答问题

用户问的八件事，每一件都有对应的取证通道和产出字段：

| # | 问题 | 取证通道 | 字段 |
|---|---|---|---|
| 1 | 各省市实际生产企业数、贸易商数、公开产能 | 上市公司年报"主要产品产能"表、行业协会分企业产量表、省市工信/发改公示、资讯机构产能表 | `sites[]`、`cities[].registered` |
| 2 | 工厂 / 基地 / 企业位置，注册地址 vs 生产地址 | 工商注册地（国家企业信用信息公示系统）≠ 环评公示建设地址 ≠ 招聘/官网地址 | `reg_address` + `plant_address` + `precision` |
| 3 | 化工园区、园内企业、产业配套 | 省级化工园区认定名单、园区规划环评、园区官网"入园企业" | `parks[]` |
| 4 | 上游原料产地、下游消费产业、贸易节点 | 年报采购构成、采矿许可、港口分货种吞吐、铁路专用线、交易所交割库/指定厂库 | `upstream[]`、`downstream[]`、`nodes[]` |
| 5 | 各地代表企业、工艺、公开产能 | 年报 + 排污许可证 + 研报；工艺不明就写"未知" | `sites[].route`、`capacity` |
| 6 | 近期新增 / 在建 / 拟建项目 | 环评一次/二次公示、发改委备案、交易所公告、开工通稿 | `projects[]`（毛新增 + 退出 + 净增量） |
| 7 | 各主要地区的价格、物流或供需特征 | 资讯机构分大区报价、地方政府价格监测、交易所交割规则、港口/铁路资料 | `prices`、`nodes[]` |
| 8 | 集中度与区域价差的客观因素 | 样本口径 CR3/CR5/HHI + 运距/货源结构/合同形式/交割基准 | `_agg`（自动算）、`narrative.price_diff_factors` |

详细的通道清单、反爬绕行、口径陷阱见 `references/source-playbook.md`；
点位核验与聚合规则见 **`references/geo-verification-and-aggregation.md`（必读）**。

### ② 写 regions.json

字段全表见 `references/data-contract.md`。最小可用骨架：

```json
{
  "meta": {"product": "纯碱", "region": "山东省", "asof": "2026-10-20",
           "capacity_unit": "万吨/年", "capacity_basis": "设计产能", "capacity_scope_total": 450},
  "sites": [{
    "site_id": "sd-xx", "company_id": "xx", "site_name": "XX 纯碱厂",
    "role": "production", "route": "氨碱", "capacity": 280,
    "raw_capacity": "年生产能力达 280 万吨", "capacity_basis": "设计产能",
    "province": "山东省", "city": "潍坊市", "park_id": "park-1",
    "reg_address": "...", "reg_address_type": "注册地址",
    "plant_address": "...", "address_type": "园区地址",
    "precision": "精确", "lon": 119.0246, "lat": 37.1318,
    "coord_source": "地图地名库", "evidence_grade": "A", "source_ids": ["S1"]
  }],
  "sources": [{"id": "S1", "publisher": "...", "title": "...", "url": "...",
               "date": "2026-03", "doc_type": "上市公司年报", "grade": "A", "note": "引用的是哪一句"}]
}
```

**只有 `precision = 精确` 的站点会成为装置点位**；其余按园区级/县级/市级落点。
注册地址永远不生成点位——这是本 skill 最硬的一条规则。

### ③ 生成 + 体检

```bash
cd scripts
python validate.py ../regions.json --strict        # error 阻断，warning 逐条看
python build_all.py ../regions.json --out ../out --name 山东纯碱 --qa --shot ../out/qa/shot.png
```

产物：
- `out/山东纯碱产业格局地图.html`
- `out/山东纯碱产业格局数据包.xlsx`
- `out/qa/shot.png`（真浏览器截图，人工扫一眼）

## 五道门禁（`validate.py` 自动跑）

| 门禁 | 拦什么 |
|---|---|
| 口径门 | 产能必须能对上原文（吨/万吨单位错、把产量当产能） |
| 缺口门 | 城市产能合计超过公开口径 2% → 报错（重复计数）；覆盖率 < 60% → 要求标"样本口径" |
| 净增门 | 项目净增量为负却没填 `capacity_retired`（把置换当扩产） |
| 来源门 | 引用了未登记的 source id、项目缺 `status_asof`、预测性措辞 |
| 地址门 | 精确点位 + 总部/写字楼关键词、注册地址当装置位置 |

## 四条不能破的规则

1. **注册地址 ≠ 地址。** 注册地只用于确认法人主体；装置位置只认"生产地址/园区位置"。
2. **企业 ≠ 厂区。** 一个集团多厂区分行列示；集团总部不是一个厂。
3. **产能 ≠ 产量 ≠ 可售量。** 数字一律标口径；两个公开口径冲突时并列，不取平均。
4. **缺就写缺。** 没有公开数据的地区、企业、产能，明确标"未取得"，写进缺口表并给出补齐路径；**绝不假设填补**。

## 目录

```
region-industry-map/
├── SKILL.md
├── README.md
├── references/
│   ├── geo-verification-and-aggregation.md   ← 地理数据核验与聚合规则（必读）
│   ├── data-contract.md                      ← regions.json 字段全表
│   ├── source-playbook.md                    ← 取证通道与口径陷阱
│   ├── evidence-grading.md                   ← A/B/C/D 分级与门禁阈值
│   ├── design-system.md                      ← HTML/Excel 视觉与交互规范
│   └── qa-checklist.md                       ← 交付前检查清单
├── scripts/
│   ├── common.py / validate.py / build_html.py / build_xlsx.py / build_all.py / qa.py
│   ├── selftest.py                           ← 自检：造一份小数据跑通全链路 + 负向门禁测试
│   ├── shot.py                               ← CDP 截图（绕开 --screenshot 挂住/写不出文件）
│   ├── package.py                            ← 打 ZIP（自动排除 __pycache__）
│   ├── templates/report.html
│   └── assets/                               ← echarts.min.js + china_prov.json（离线）
└── examples/01-shandong-soda-ash/            ← 山东纯碱完整工作示例（含成品 HTML + XLSX）
```

## 改完先跑自检

```bash
cd scripts
python selftest.py        # 期望末行：—— 自检通过：校验 / 聚合 / HTML / Excel / 门禁 均正常
python shot.py ../out/x.html ../out/qa/shot.png --w 1600 --h 2600   # 截图（见下方注意事项）
```

`selftest.py` 会造一份最小数据跑通 validate → normalize → build_html → build_xlsx，
并断言：派生装置不计入样本、净增量符号正确、表数 14、页面无外部资源，
另有两条负向测试（地址门、单位门必须真的报错）——门禁失效时自检会失败。

## 两个已知的渲染/环境坑（务必照做）

1. **地图必须是「geo 组件 + 全部 scatter」，绝不能用 `series:{type:'map'}` 打底。**
   这是本 skill 踩过的最隐蔽的坑：`type:'map'` 的底图属于该 series，与 `geo` 组件是**两个独立的
   可漫游实例**。结果是——用户滚轮缩放时底图变了、散点不跟（或反过来），**点位在地图上"漂"**，
   看起来就像园区/工厂标错了位置。实测证据：缩放后 `convertToPixel` 已变，但散点图形元素
   的 transform 仍是旧值（`[368.99,241.83]` 不动），直到一次 `resize` 才跳到 `[360.36,263.83]`。
   正确做法（模板已实现）：底图色块挂在 `geo.regions`（省份指标），visualMap 用 `geoIndex:0` 着色，
   所有点位用 `coordinateSystem:'geo', geoIndex:0` 的 scatter，滚轮/拖拽由 geo 统一驱动。
   点击省份的回调也随之改为判 `p.componentType==='geo'`。

   同源的第二个坑：`label.formatter` / `tooltip.formatter` 的入参 `p` 在部分渲染路径上**不带**
   自定义字段（如 `p.rec`），必须写 `(p&&p.rec)||dataArr[p.dataIndex].rec` 并判空，
   否则抛 `Cannot read properties of undefined (reading 'city')`，**整张地图一个 canvas 都不画**，
   而其它 6 个图表正常——极易误判成"ECharts 没加载"。

2. **截图的相对路径是相对 Chrome 自己的 cwd，不是你的 shell。**
   用 `--screenshot=out/x.png` 会静默失败（`Failed to write file ... 0x3`），
   而且 `--screenshot` 在部分环境会挂住 3 分钟以上。请用 `scripts/shot.py`（走 CDP），
   它传绝对路径、23 秒内出图。`qa.py --shot` 已内置此脚本并有原生 fallback。

## 换品种 / 换区域

只改 `regions.json`：把 `meta` 换成新品种新区域，`sites/parks/upstream/downstream/projects` 换成新事实，`sources` 换成新来源。
脚本、模板、样式、图例、聚合规则**一行都不用改**。

跨品种时唯一要注意：`route`（工艺）枚举按品种改。`common.py` 里 `PROCESSES` 是纯碱的，
换品种前先改这一行，否则 `validate.py` 会提示工艺不在枚举内。
