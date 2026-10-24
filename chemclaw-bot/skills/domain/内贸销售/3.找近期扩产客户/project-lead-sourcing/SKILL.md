---
name: project-lead-sourcing
description: Use when a sales rep wants prospects found through the CAPEX projects that will create new demand for their product — locating projects that are newly built, expanded, technically retrofitted, or about to start up in a region and time window, then grouping them by when to make contact (项目级潜客 / 新建项目 / 扩建 / 技改 / 即将投产 / 未来6个月 / 未来一年 / 环评 / 备案公示 / 在建项目 / 项目时间线 / 找客户). Product-agnostic across chemicals and materials; delivers an Excel workbook plus a self-contained interactive HTML with a project-timeline and a company view.
---

把「未来一段时间里，**哪些正在建的项目**会新增对本产品的需求」变成一张能打电话的表，并告诉你**什么时候打**。

这个 skill 的组织单位是**项目**，不是公司：一条记录 = 一个具体项目（业主企业 + 项目 + 建设阶段 + 投产时间 + 在哪用本产品 + 可点开的出处）。同一家公司有三个在建项目就是三条线索——因为它们是三个不同的销售时点。

引擎在 [`scripts/b2bctl.py`](scripts/b2bctl.py)，**不依赖任何特定 agent 的工具**：任何能执行 shell 的 agent 都能跑（codex / chemclaw / workbuddy / Claude Code / 本机终端）。语义判断仍然是你的活。

## 四条不可谈判的约束

1. **没有 trace 的线索不算线索。** `来源` 必须是能点开、能在电话里复述的原始页面（公告原文 / 环评公示原文）。取不到就写 `来源=未核实`、`置信度=低`——**编一个像样的 URL 比留空有害得多**。
2. **宁可写「无法估算」，也不要给一个没出处的数字。** 单耗必须有依据（化学计量式 / 配合料配比 / 公告原文）。有出处的粗算 >> 无出处的精算。
3. **peer 不是客户。** 自己也生产该产品的主体是同行。`peer_keywords` 必须按本次产品重写，检索中发现名单外的自产者也要剔除并单独报告。
4. **换机器先探通道。** 数据源可用性因机器、网络、国家而异。第 2 步的 `probe` 把它变成**记录在案的事实**，之后所有 lane 只用被证实可用的通道。

## Steps

### 1. 定契约

一次问全：**产品**、**地区**、**时间窗**（未来 6 个月 / 1 年 / 2 年）、**交付物**（默认 Excel + HTML）。
可补充输入：用户重点区域、重点行业、已有项目名单。时间窗是「预计投产时间落入的区间」，不是「现在在建」。

```bash
python scripts/b2bctl.py new <项目目录> --product 纯碱 --formula Na2CO3 \
       --region 华东 --provinces 山东,江苏,浙江,安徽,上海,福建,江西 --months 6
```

- 完成判据：`config.json` 里 `product` / `region` / `window_months` / `today` 都已确定；**`peer_keywords` 已按该产品填入同行清单**（先查清楚这个产品国内还有谁在生产）。

### 2. 探通道

```bash
python scripts/b2bctl.py probe <项目目录>
```

逐条实测 `channels.default.json` 里的通道，结果写进 `channels.json`。**每一级只试一次**，不灵就换，不反复重试。

**`probe` 只证明「可达」——URL 能取到内容，不等于能解析出项目条目。**
JS 渲染的列表页会返回 200、HTML 有几十上百 KB、看起来完全正常，但项目清单是前端注入的，**一条都抽不出来**。
（实测：用「HTML 长度」或「中文项目名关键词命中数」都判别不出来，壳页的关键词命中数甚至比真列表页更高。）
所以对列表型通道（环评/备案/招标）**必须再用适配器实测一次可解析性**：

```bash
python -m tools.eia selftest      # 逐个 EIA 通道报告能抽出多少条
```

- 完成判据：`channels.json` 里有非空的 `reachable_ids`；不可达通道及其**失败原因**（跳 HTTPS / 反爬 / 连接失败）已记录；`needs_adapter_test` 里的通道**都已跑过适配器**，抽不出条目的要如实标为不可用（**不要因为 probe 显示"可达"就把它算进覆盖率**）。
- **若宿主 agent 自带联网搜索，它是你最强的通道**——把它登记进 `channels.json` 的 `host_tools`，并让 lane 优先用它。
- 通道细节与 URL 模板见 [`references/channels.md`](references/channels.md)。

### 3. 画应用地图，定 lane

一个 **lane** = 一个下游应用方向（不是企业名单）。填 `lanes.json`：每个 lane 写清**用料逻辑**（在哪个工序、起什么作用）、**用量强度**（★数）、**产业集聚地**、**5~8 家具名候选企业**。

产品在这条 lane 里的角色决定判断方向：`主原料`（进入产品分子，有化学计量关系）／`辅料`（参与但不进入最终分子，如 pH 调节、浸出、中和）／`助剂`（配合料组分、助熔剂、澄清剂等）。

- 完成判据：`python scripts/b2bctl.py lanes-check <项目目录>` 无待修正项；lane 数 ≥ 6，每个 lane ≥ 3 家具名候选。
- **易漏方向要主动找**：把本产品当配方单体再复配转售的厂、本产品自身深加工的厂、环保末端（脱硫脱硝/废水中和）用它的厂。
- 方法与 lane 设计见 [`references/method.md`](references/method.md)；纯碱的可复用范例见 [`examples/soda-ash-huadong/lanes.json`](examples/soda-ash-huadong/lanes.json)。

### 4. 铺 lane（fan-out）

```bash
python scripts/b2bctl.py brief <项目目录>      # 生成 briefs/NN_<lane>.md + workplan.md
```

每个 lane 一个执行单元。**并发上限 8**；起满就等一个结束再补。

- 有子代理能力的宿主（如 DSH）：把 `briefs/NN_*.md` 的**全文**作为子任务指令交给一个子代理。
- 没有子代理能力的宿主（如 codex）：**顺序跑**，每个 lane 做完再下一个。brief 自包含，不影响质量。
- **不要在派工时改写或摘要 brief**——里面的纪律（禁止编造、peer gate、地区闸门、工具调用上限、增量落盘）就是这个方法论的质量来源。
- 完成判据：每个 lane 都有 subagent/执行单元在跑，且 `workplan.md` 的 lane 数与 `lanes.json` 一致。

### 5. 收 lane

lane 用 `write` 把 JSON 数组落盘到 `leads_raw/NN_<lane>.json`，**18 个采集字段一个都不能少**（schema 见 [`references/schema.md`](references/schema.md)）。

```bash
python scripts/b2bctl.py collect <项目目录>     # 逐文件校验 schema
```

lane 崩溃、零产出或条数偏低时，**不要原样重发同一个 brief**（探索动作本身就是崩溃源）。改用**枚举式 brief**：把候选企业名单连同股票代码直接写进 brief，禁用一切检索，限定「每家最多 1~2 个页面、总调用 ≤30 次、每 5 条增量落盘」。见 [`references/failure-log.md`](references/failure-log.md)。

- 完成判据：`collect` 报告无待修项；每个 lane 要么有产出文件，要么在最终报告里写明放弃原因与原因类别。

### 6. 合并

```bash
python scripts/b2bctl.py merge <项目目录>
```

它做五件事：地区闸门、peer gate、按「归一化公司名 + 项目名前 24 字」去重、**销售时点推导**、优先级打分（用量强度 × 置信度，间接需求降权）。

- 完成判据：`leads.json` 条数 = 各文件产出之和 − 去重数 − peer 剔除数 − 地区剔除数；`merge_stats.json` 里的 `by_timing` 三个桶都有合理分布（**若「仅需关注」压倒性占多数，说明 `预计投产时间` 大量缺失，去看 `references/timing.md` 的处理规则**）。

### 7. 抽检（link gate）

```bash
python scripts/b2bctl.py qa <项目目录>
```

抽 **≥40 条**来源实测可达性，结果写 `leads_raw/_qa_report.json`（结论进 `抽检结论` 字段，**不拼进 `来源`**——拼了 URL 就变成坏链）。

必须区分两类失败：**反爬拦截**（403/406，浏览器里其实能打开）标注「建议人工复核」即可；**跳转 HTTPS / 空壳 / 404** 才是真坏链。

- 完成判据：抽检 ≥40 条并已落盘；坏链逐条在交付说明里列出。

### 8. 出表

```bash
python scripts/b2bctl.py build <项目目录>      # 或 all，一把跑完 6~9
```

产出（文件名由 `config.json → paths.out_stem` 渲染）：

| 交付物 | 内容 |
|---|---|
| `<stem>.xlsx` | 6 表：说明与行业地图 / 项目线索总表（带筛选、来源可点）/ 项目时间线 / 重点客户TOP / 分布统计 / 剔除与缺口 |
| `<stem>.html` | **单文件、离线可开**：项目时间线 ↔ 企业表**双视图**；筛选（销售时点/建设阶段/省份/板块）；点项目开抽屉 = 企业背景 + 证据与来源 + **「找客户最近的切入点」** |
| `方法与边界说明.md` | 交付四块的文字版 |

- 完成判据：`python scripts/b2bctl.py check <项目目录>` 通过（Excel 表数/行数、HTML 关键区块、内联 JS 语法、说明四块齐全）。
- 本机没有 `openpyxl` 时 Excel 会自动降级为 CSV 并明确提示——**必须如实告知用户**，不要假装出了 xlsx。

### 9. 交付

报告必须含四块，缺一不可：

1. **条数与分布**（销售时点 / 建设阶段 / 省份 / 板块 / 产品角色 / 需求性质），并说明**有多少条真的能估出年需求量**；
2. **置信度分级**，并说明高置信度靠什么证据；
3. **被剔除的 peer 名单**（哪几家是同行不是客户，依据是什么）；
4. **未覆盖的缺口与负结果**（哪些通道失效因此漏了哪些省/哪些非上市企业、哪些板块在萎缩、哪些"有项目但缺厂址/产能"只能人工补证）。

第 3、4 块脚本只能算出**可计算的部分**：第 3 块只有 `merge` 真正拦下的条目（`peers_removed`），第 4 块只有产出偏薄的板块、无来源条数、坏链、地区剔除。

**判断性内容必须由你写进项目根的两个文件，`build` 时会自动嵌入：**

| 文件 | 补哪一块 | 为什么脚本算不出来 |
|---|---|---|
| `peers_excluded.md` | 第 3 块 | lane 在**检索阶段**就跳过了同行，它们从未进入 `leads_raw/`，所以 `merge` 的 peer 计数必然是 **0** |
| `gaps.md` | 第 4 块 | 哪些板块在萎缩、哪些通道失效、哪些只能人工补证——都是判断 |

这两个文件由 `b2bctl new` 生成时首行带 `<!-- STATUS: UNFILLED -->`；**写完把那一行删掉**。
`check` 会因下面任一情况**直接判不通过（退出码 1）**：线索数为 0、`STATUS` 标记未删、
`GAPS:BEGIN`/`PEERS:BEGIN` 还在、说明缺任一块、Excel/HTML 结构坏、HTML 内联 JS 语法错误。

- 完成判据：四块都在；第 3、4 块有**具体公司名或具体行业名**，不是套话。

## 判定规则速查

| 概念 | 规则 |
|---|---|
| 建设阶段 | 只取 `拟建 / 备案 / 在建 / 试车 / 已投产`。环评**受理/拟审批/批复**属 `备案`，不要写成"在建"（除非正文写明已开工） |
| 销售时点 | 试车 → 现在联系；已投产近 6 个月 → 现在联系；在建且 ≤ today+3个月 → 现在联系；在建且窗口内 → 3-6 个月；**在建但投产月份未披露 → 3-6 个月**（供应商入库/送样本身要 1~3 个月前置期）；备案窗口内 → 3-6 个月；其余 → 仅需关注 |
| 优先级 | 用量强度（★）× 置信度权重（高 3 / 中 2 / 低 1），间接需求额外 −4 |
| 用量强度 | 5★=单点年需求千吨级以上；4★=千吨级；3★=百吨级；2★=十吨级；1★=更小/不确定 |

完整规则、判据与常见误判见 [`references/timing.md`](references/timing.md) 与 [`references/gates.md`](references/gates.md)。

## 换电脑 / 换 agent

见 [`references/portability.md`](references/portability.md)。三条要点：

1. **只要 Python 3.8+**，其余全是标准库；只有出 xlsx 需要 `openpyxl`（缺了就降级 CSV）。
2. **先跑 `probe`**，不要假设任何站点可用。
3. **agent 无关**：所有重活都在 `scripts/` 的命令行里；宿主只需要能执行 shell 和读写文件。有没有子代理只影响快慢，不影响结果结构。