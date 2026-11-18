# case.json 字段说明（schema：chem-topic-research/1.0）

一份 JSON 驱动全部交付物。**先填提纲相关字段，用户确认后再填数据与结论。**

快速起步：`python scripts/new_case.py --title "..." --product X --audience industry-researcher`

---

## 1. 顶层字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| schema_version | str | 是 | 固定 `chem-topic-research/1.0` |
| meta | dict | 是 | 报告元信息 |
| audience_frameworks | dict | 是 | 各受众的章节设计 |
| research_brief | dict | 是 | 问题、范围、假设 |
| sources | list | 是 | 证据来源（S 编号） |
| data_gaps | list | 是 | 资料缺口（G 编号） |
| conclusions | list | 是 | 结构化结论 |
| sections | list | 是（出正式报告时） | 正文章节 |
| calculations | list | 建议 | 计算结果（C 编号） |
| kpis | list | 建议 | 首屏指标 |
| projects / companies | list | 按题目 | 项目台账 / 企业清单 |
| key_variables | list | 建议 | 监测清单 |
| method_notes | list | 建议 | 口径与规则 |
| glossary / history / chain | list | 可选 | 术语 / 大事记 / 产业链 |
| capacity_structure / cost_curve / profit / supply_demand / price_history / price_points / inventory / output_weekly / demand_structure / glass_runrate / macro / cr5 / projects_by_status / add_waterfall / supply_scenarios | 各类型 | 按题目 | 图表数据集，键名即图表的 `data_key` |

## 2. meta

```json
{
  "slug": "soda-ash-2026-supply",
  "title": "中国纯碱行业新增产能对未来供应格局的影响",
  "subtitle": "自下而上核验……并测算有效供给增量与供需缺口",
  "product_cn": "纯碱", "product_shape": "重质纯碱",
  "topic_type": "供给冲击/产能扩张",
  "audience": "industry-researcher",
  "audience_label": "产业研究员",
  "region": "中国", "horizon": "2026Q4–2027Q4",
  "report_date": "2026-10-20", "data_cutoff": "2026-09-25",
  "version": "v1.0", "org": "", "author": "",
  "disclaimer": "本材料为方法论示例……不构成投资建议"
}
```

`audience` 取值：`management / sales / procurement / rnd / industry-researcher`。

## 3. audience_frameworks.<受众>

```json
{
  "audience_key": "industry-researcher",
  "label": "产业研究员",
  "positioning": "回答什么、给谁看",
  "focus": "重点",
  "answer_style": "推导完整 + 口径可复算",
  "length_target": "8–10 章",
  "evidence_policy": "每章至少 1 条 A/B 级证据",
  "suppressed_topic_packs": ["region", "policy"],
  "chapters": [
    {"no": "01", "title": "……", "question": "要回答的问题",
     "why": "为什么需要这一章", "verify": "验证/证伪什么",
     "data": ["依赖数据1", "依赖数据2"], "method": "方法"}
  ]
}
```

## 4. sources（S 编号）

```json
{"id": "S01", "org": "期货日报 / 新华财经", "title": "……", "date": "2025-12-31",
 "url": "https://……", "tier": "B", "kind": "媒体引用第三方数据", "note": "口径说明"}
```

`tier`：A / B / C / D（见 `data-sourcing.md`）。`note` 写口径，越具体越好。

## 5. data_gaps（G 编号）

```json
{"id": "G01", "topic": "装置级产能清单", "missing": "……", "why": "……",
 "impact": "……", "workaround": "……", "next_step": "……", "severity": "high"}
```

## 6. projects（项目台账）

```json
{"id": "P01", "name": "……", "company": "……", "region": "西北", "province": "内蒙古",
 "process": "天然碱法", "capacity": 280, "start": "2023-12", "plan_date": "2025-12",
 "actual_date": "2025-12", "status": "已投产", "status_basis": "行业统计显示 2025 年 12 月投产",
 "evidence": "S07", "strength": "A", "net_add": true, "for_exit": "", "note": "……"}
```

`status` ∈ 已投产 / 在建 / 规划 / 退出 / 暂停。`net_add=false` 时须在 `note` 写替代对象与扣减。

## 7. calculations（C 编号）

```json
{"id": "C-SUP-01", "title": "2027 年有效新增供给（基准）", "statement_type": "计算",
 "formula": "Σ 名义产能 × 爬坡率 × 时间权重 − 同步退出",
 "inputs": "金山 80×0.6×0.5=24；……", "output": "净约 285 万吨/年",
 "result_note": "口径与置信说明", "evidence": ["S07", "S01"]}
```

## 8. conclusions（CC 编号）

```json
{"id": "CC-01", "rank": 1, "type": "计算", "confidence": "中",
 "text": "结论正文（一句话说清量级与含义）",
 "evidence": ["S06", "S07"], "calcs": ["C-ADD-01"],
 "falsify": "可观测的反证条件", "audience_note": "对不同受众的提示"}
```

`type` ∈ 事实 / 计算 / 解释 / 判断。**判断与解释必须有 falsify。**

## 9. sections（正文）

```json
{"id": "s04", "no": "04", "pack": "calculation", "title": "……", "lede": "本章干什么",
 "audience_weight": ["industry-researcher"], "question": "要回答的问题",
 "blocks": [ … ]}
```

区块类型：

| type | 关键字段 | 渲染 |
| --- | --- | --- |
| para | text | 段落 |
| callout | title, text, tone(info/warn/gap) | 提示框 |
| table | title, cols, rows 或 rows_key | 表格 |
| chart | title, chart_type, data_key, source, note, conclusion_ids, keys/bands, ref | 图表 |
| calc | calc_id | 计算卡 |
| conclusions_full | — | 全部结论（含反证条件） |

`chart_type` 支持：`stacked_bar` `bar_chart`(即 `bar`) `line` `dual_axis` `donut` `range_bar` `waterfall`。
折线/柱状建议显式给 `keys: [{"k":"字段","name":"显示名"}]`，避免自动推断错列。

`pack` 取值见 `research-design.md` 章节包目录。

## 10. 校验规则（validate）

会检查：必填字段、meta 必填项、引用 ID 是否登记、结论是否为空、项目状态是否合法、缺口是否缺 next_step、来源数量下限等。

```bash
python scripts/common.py validate case.json   # RESULT PASS / FAIL
```

## 11. 编辑建议

- 用 `indent=2` 保存，便于 diff。
- 编号规则：S=来源，G=缺口，C=计算，CC=结论，P=项目，V=变量，K=指标，Q=问题。
- 新增数据系列时，`data_key` 要能在 `build_payload` 中取到（顶层键或点号路径）。
