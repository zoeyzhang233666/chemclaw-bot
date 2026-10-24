# 06 输出规格与字段字典

## 1. 交付物

| 文件 | 用途 | 说明 |
|---|---|---|
| `<清单名>_批量寻源报告_YYYYMM.html` | 主交付物，给客户看 | 单文件，双击打开；无外部 CDN；可离线 |
| `<清单名>_批量寻源报告_YYYYMM.xlsx` | 归档/二次编辑 | 13 表；矩阵为真单元格填充 |
| `project.json` | 可复现的源数据 | 全部数据 + 证据 + 计算方法入口 |

命名：去掉 `purchase_list`、`_simulated` 等前缀，保留业务名（如 `东北某厂2027`）。

## 2. HTML 结构

```
① 概览与结论      KPI 卡片 + 结论摘要（每条都可回溯） + 三条硬规则
② 物料标准化表    可编辑单元格；导出 CSV；localStorage 留存改动
③ 待确认事项      P0/P1/P2
④ 候选企业        过滤：关键词 / 身份 / 省份；点行看证据
⑤ 双向匹配矩阵    两个视角切换；过滤：身份/省份/覆盖数/危化品；点格看证据抽屉
⑥ 跨物料企业      打包谈判对象 + 覆盖比
⑦ 稀缺与风险      按厂家数升序
⑧ 证据库          全部证据，可点击外链
⑨ 危险与监管      逐物料
⑩ 询价与核验清单  一键生成 RFQ（复制/下载 .txt）
```

交互契约（改代码时不要破坏）：

| 交互 | 实现位置 | 备注 |
|---|---|---|
| 点格子 → 抽屉 | `cellDetail(itemCode, supId)` | 抽屉里必须同时出现“判定理由 + 直接证据 + 企业其他证据”。**矩阵每格都必须可点**，未评估的格子也要弹“未评估”说明，不能是死格 |
| 点行首 → 物料/企业画像 | `itemDrawer` / `supDrawer` | |
| 生成 RFQ | `makeRFQ(supId)` → `window.__rfq` | 只包含 `ach=1` 的物料 |
| 编辑单元格 | `initEdit()`，`data-k` 做键 | 键必须全局唯一：`物料码-字段`；`afterRender()` 会重复调用，必须靠 `td.__bound` 幂等 |
| 导出编辑 | `exportEdits()` → UTF-8 BOM CSV | Excel 打开不乱码 |
| 表内筛选 | `wrapScrolls()` + `openFilterPop()` | 绑在 `.tablebar` 上（不绑 `.scroll`，避免被 `#mxHost` 重绘冲掉）；点表头任意列即弹出 Excel 式值筛选，筛选后自动隐藏首行遮挡 |
| 复制表格 | `copyTable(sc)` | TSV 写剪贴板，粘贴进 Excel 自动分列 |
| 矩阵过滤/视图 | `setMx / setView` | 状态存 `window.__mxFilter` |

### 布局硬约束（踩过的坑）

1. **表头只能相对 `.scroll` 容器吸顶，不能相对页面 `sticky`。** 一旦写成 `th{position:sticky;top:44px}`，导航栏高度变化时表头会盖住第一行数据。
2. `.scroll` 必须有 `position:relative`，`thead th` 用 `position:sticky; top:0; z-index:10`。
3. 矩阵行/列标识区（`.rowh`）用 `left:0` 吸顶，`z-index` 要高于表头。
4. `renderMatrix()` 之后必须调用 `afterRender()` 重新包壳和绑定，否则动态生成的表没有筛选/复制条。
5. 矩阵列取自 `supplier_rank` 时，**`id` 字段叫 `supplier_id`**（不是 `id`）；行取自 `items` 时字段是 `code`。统一先归一化成 `{id,label,...}` 再渲染，避免整列静默丢格（历史 bug：378 格全部空白、无点击）。

## 3. Excel 表结构

| # | 表名 | 关键列 |
|---|---|---|
| 00 | 封面 | KPI、结论摘要、阅读顺序、免责声明 |
| 01 | 物料标准化表 | 物料码…状态…候选数/厂家数/风险 |
| 02 | 待确认事项 | 编号/优先级/物料码/问题/依据/负责人/时限 |
| 03 | 候选供应商表 | 身份/判定依据/覆盖/厂家/可达/可靠性/角色/风险 |
| 04 | 物料→供应商矩阵 | 行=物料，列=企业（绿=● 黄绿=◐ 黄=○ 粉=◆ 灰=×） |
| 05 | 供应商→物料矩阵 | 转置视角 + 覆盖比 |
| 06 | 多物料覆盖企业 | 已证实/可达两列 + 谈判要点 |
| 07 | 稀缺物料与风险 | 按厂家数升序 |
| 08 | 证据明细 | 等级/机构/原文引用/作用/链接/日期/关联物料 |
| 09 | 危险属性与监管 | 字典口径 vs 清单写法 |
| 10 | 询价与资质核验清单 | Q 行（询价包）+ G 行（缺口任务） |
| 11 | 来源库 | 按等级降序，链接可点 |
| 12 | 方法与字段映射 | 口径 + 字段别名全表 |

## 4. `project.json` 字段字典

### `meta`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `title` / `subtitle` | string | ✅ | 报告标题 |
| `buyer` / `buyer_region` | string | | 采购方与所在地 |
| `delivery_point` | string | | 交付地（缺省用于所有物料） |
| `as_of` | `YYYY-MM-DD` | ✅ | 数据截止日 |
| `accept_trader` | bool | | 是否接受贸易商（false 时 T 只作线索） |
| `version` | string | | 报告版本 |
| `sources_scope` | string[] | | 来源范围声明 |
| `headline` | string[] | | 结论摘要（HTML/Excel 封面用） |
| `code_remap` | object | | 解析后物料码重映射 `{旧: 新}` |

### `items[]`

`code, raw_name, name, en, aliases[], cas, form, spec, purity, qty, unit, unit_raw, qty_annual, packing, delivery, application, hazard, hazard_raw, status, issues[], notes, source_row, dup_of`

### `suppliers[]`

`id, name, short, identity, province, identity_note, evidence_ids[], roles[], route, notes`

### `evidence[]`

`id, grade, org, topic, quote, detail, url, date, items[], caveat?, conflict_with?, family?`

### `links[]`

`item_code, supplier_id, identity, coverage, confidence, degree, current_relation(bool), potential_relation(bool), rationale, link_id?`

`degree`：`independent | confirmable | conditional | co_list_only | not_covered | not_recommended`

### `ambiguities[]`

`id, level(P0|P1|P2), code, row, type, question, extra[], detail, owner, status, source_row`

## 5. 计算时机

```
load_project()
  → 注入 _meta（rules.json）
  → code_remap 重映射
  → apply_degrees()   每条 link 计算 _deg.{current, achievable} 与 reliability_score
  → compute_coverage() 物料侧 / 企业侧 / 多物料 / 稀缺
build_actions()       询价包 + 缺口任务 + 来源清单
build_excel() / build_html()
```

`validate_project.py` 在 `_calc` 生成后跑，能反查“可达 > 覆盖”“U 级当厂家”这类逻辑漏洞。

## 6. 不改动契约的扩展方式

- **加物料**：只改 `items` + `links`，不要动模板。
- **加企业**：只改 `suppliers` + `evidence` + `links`。
- **改配色/文案**：`lib_html.py` 的 `CSS` 与模板；`lib_excel.py` 的 `FILL`。
- **改阈值**：改 `assets/rules.json`，不要改代码。
- **加一张表**：在 `lib_excel.py` 加 `sheet_xxx()` 并在 `build_excel()` 注册，同时更新 §3。
