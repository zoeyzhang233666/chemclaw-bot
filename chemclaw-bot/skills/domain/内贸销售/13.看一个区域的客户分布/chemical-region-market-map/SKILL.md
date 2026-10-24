---
name: chemical-region-market-map
description: Use when a domestic chemical sales rep needs to decide which cities and parks in a region to visit first for a specific product — building a regional market map that covers client concentration by city and chemical park, producer-vs-trader split, downstream industry structure, head enterprises plus unnamed SME clusters, new/expansion project pipeline, and local price level versus other regions, ending in a visit-priority ranking and route. Delivers a self-contained interactive HTML map plus a 12-sheet Excel workbook. Product-agnostic across chemicals and materials. Triggers 区域市场地图 / 市场地图 / 区域客户分布 / 走访优先级 / 先跑哪些城市 / 区域打法 / 哪个城市客户多 / regional market map for a chemical product.
---

# 区域市场地图（化工品内贸）

把「某产品在某区域有多少客户」变成一张能直接安排行程的地图 + 一本能直接查的表。
**产品无关**：纯碱、钛白粉、环氧丙烷、助剂、颜料、树脂都走同一套流程；换产品只换数据。

## 什么时候用

用：销售/区域经理拿到一个产品和一个大区，要决定「先跑哪几个城市、进哪几个园区、先见谁」；或者要给老板一份带数字的区域打法。

不用：只要一份客户名单 → 用 `b2b-lead-sourcing`；只要有标杆找相似客户 → 用 `benchmark-lead-sourcing`；只要项目级线索 → 用 `project-lead-sourcing`。本 skill 是**区域级地图**，名单只是其中一节。

## 交付物（至少这两个）

1. **自包含 HTML**（约 1.6 MB，离线可开）：地图 + 区域汇总首屏，点城市/园区过滤企业，4 种度量切换，企业/项目抽屉，价格对比，走访路线，口径与缺口。
2. **12 表 Excel**：概览结论 / 省级 / 城市明细 / 园区清单 / 客户线索 / 中小集群 / 重点项目 / 价格 / 走访计划 / 下游行业 / 同行与误判 / 方法与缺口。

两个文件都由同一份 `data.json` 生成，所以**数字天然一致**。

## 三步走

```
① 研究（本 skill 的方法）   → 得到结构化事实
② 写 data.json（数据契约）  → 一个 JSON 描述一个区域
③ 生成 + 体检               → HTML + Excel + qa
```

### ① 研究：六个问题，每个都有取证通道

| 问题 | 怎么取证 | 产出字段 |
|---|---|---|
| 客户集中在哪些城市/园区 | 园区名单、地方工信/发改公示、行业协会集群报道 | `cities[]` + `parks[]` |
| 生产 vs 贸易 | 工商/贸易市场（如临沂化工市场）商户数，与园区工厂数分开数 | `firms` / `traders` |
| 主要下游 | 产品消费结构（协会/期货公司研报）+ 单耗反推 | `lanes[]` |
| 头部与中小 | 上市公司公告/年报、协会名单；中小只报数量口径 | `companies[]` / `smb` |
| 新建扩产 | 环评/备案公示、交易所公告、行业资讯（点火/复产/冷修） | `projects[]`（含负增量） |
| 价格水平 | 价格机构日更（同花顺 iFinD、隆众、卓创）+ 运距折算到厂价 | `prices` |

细节通道、单耗表、估算校准方法见 `references/research-playbook.md`。

### ② 写 data.json

字段与校验规则见 `references/data-contract.md`。最小可用骨架：

```json
{"meta": {"product":"…","region":"…","asof":"2026-10-19","demand_label":"用量","demand_unit":"万吨/年",
          "anchor":{"label":"华东主流价","value":1150,"unit":"元/吨","date":"2026-10-16"}},
 "cities":[{"city":"佛山","prov":"广东","firms":18,"traders":6,"demand":12.5,
            "inds":[{"id":"coating","name":"涂料","n":9}],
            "parks":[{"name":"某涂料园","ind":"涂料","n":10}],
            "head":["某公司"],"smb":"…","note":"…"}],
 "lanes":[{"id":"coating","name":"涂料","share":45,"unit_txt":"0.05–0.12 t/t","intensity":4,
           "logic":"…","who":"技术/采购","hook":"…","misread":"…"}],
 "companies":[{"name":"…","type":"生产","conf":"高","city":"佛山","lane":"coating","kt":3.2,
               "need":"…","action":"…","src":"2025 年报"}],
 "projects":[…], "prices":{…}, "route":[…], "narrative":{…}}
```

**只填 n 不填 share/kt 也行**——`share`、`kt`、`score`、`rank`、`tier`、`days`、`proj_kt` 全部自动算。

### ③ 生成 + 体检

```bash
python scripts/validate.py data.json          # 先验：error 必须清零
python scripts/build_all.py data.json --out out --name 纯碱-华东
python scripts/qa.py data.json "out/纯碱-华东区域市场地图.html" "out/纯碱-华东客户分布与走访优先级.xlsx"
```

`qa.py` 会用 headless Chrome 真实渲染页面，核对「城市行数 = 数据条数、企业行数、项目行数、下游卡数、canvas 数、侧栏数据条」，并检查 Excel 表数与合计。没有 Chrome 时退化为静态检查。

## 质量红线（这七条不达标就别交付）

1. **同行不是客户**。自己也生产该产品的企业，单独标 `type:"同行"`，并在 `narrative.peer_notes` 说明它们是价格/情报来源。混在客户名单里会直接毁掉可信度。
2. **误判单列**。看起来像客户但不消耗的下游（组件厂、玻璃深加工、用烧碱的氧化铝厂、无碱玻璃面板）标 `type:"误判"` 并写明"实际用什么"。
3. **每条线索带证据**。`conf:"高"` 必须能指向公告/年报/交易所/政府/协会/价格库；拿不到就 `conf:"低"` + `src` 写「未核实」。`validate.py` 会拦矛盾组合。
4. **估算必须标估算**。企业家数、用量都是估算，页面与 Excel 都要写口径；不要用"统计"措辞。
5. **增量要正负都收**。冷修、停产、限产是负增量；只加总正向项目会系统性高估（本次案例高估 45%）。
6. **中小集群不点名**。拿不到名单的，用「园区 + 家数 + 单厂区间」表达，写进 `smb` 与 06 表，不要编企业名。
7. **缺口要点名**。`narrative.gaps` 写清哪类数据拿不到、误差多大、下一步怎么补。没有缺口章节的调研通常意味着没查到东西。

## 别踩的坑（都是真踩过的）

- **占位符自替换**：模板里 `window.__DATA__=%%DATA%%;`，用 `str.replace('%%DATA%%', json)`。若用 `__DATA__` 作占位符，会把 **JS 变量名和值一起替换**，生成 `window.{...}={...}` 语法错误。生成器已内置占位符计数校验。
- **地图拉伸**：不要用 `geo.boundingCoords` 框区域——ECharts 会把 bbox 强行拉伸到容器长宽比，华东会被横向拉宽 2 倍。用 `center + zoom`（等比），再用 headless 探针确认经纬度角落点落在画布内。
- **内联元素设宽高无效**：进度条 `<span class="fill" style="width:73%">` 默认 `display:inline`，宽度和颜色都不渲染。CSS 必须 `display:block`。
- **CSS 优先级**：`.maptools .btn` 写在 `.btn.on` 之后会覆盖选中态背景，造成白底白字。选中态要用同等或更高优先级的选择器补回。
- **中文列宽/行高**：openpyxl 不会自动换行自适应，`build_xlsx.py` 里按 CJK 字符占 2 字宽估算行高。

## 不同 agent 上怎么用

见 `references/adapters.md`。要点：整个目录是一个单元，`SKILL.md` 是入口，`scripts/` 只依赖 Python 3 + openpyxl，`assets/` 自带 ECharts 与省界 GeoJSON（离线可用）。Claude Code 放 `~/.claude/skills/`，Codex/通用 agent 放项目内 `skills/` 或把 SKILL.md 作为系统指令并把目录挂到工作区。

## 示例

- `examples/01-soda-ash-east-china/`：完整真实案例（纯碱·华东，66 城 / 1,847 家 / 913 万吨），含 data.json 与产出成品，可当写作范本。
- `examples/02-skeleton-toy-region/`：最小骨架（6 城 / 5 下游 / 6 家企业，占位数据），用来学数据契约与最小可运行路径。

先读 01 的 `data.json` 看真实颗粒度，再用 02 练手。
