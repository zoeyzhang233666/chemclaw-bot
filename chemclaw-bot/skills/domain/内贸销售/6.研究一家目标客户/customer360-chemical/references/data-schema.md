# data.json 字段规范

Agent 研究完成后，把事实填入 `data.json`（参照 `examples/` 中的四个范例，其中 example-1 为真实研究，example-2/3/4 为虚构教学数据）。渲染器 `scripts/build.py` 按本规范消费；字段缺失时对应区块自动渲染为"待补充"，**不要为填满而编造**。

## 顶层结构

```jsonc
{
  "meta": { ... },                      // 页眉与Excel使用说明
  "entity_confirmation": { ... },       // 主体确认卡
  "summary": { ... },                   // 首屏三问 + 风险横幅
  "next_actions": { ... },              // 三个后续动作面板
  "products_plants": { ... },           // Tab1 产品与工厂
  "projects_news": { ... },             // Tab2 项目与动态
  "procurement": { ... },               // Tab3 采购关系
  "risks": { ... },                     // Tab4 企业风险（七项核查）
  "verification_checklist": [ ... ],    // Tab5 合作前核实清单
  "disclaimer_extra": ""                // 可选，追加到页脚免责声明
}
```

## 证据（evidence）通用格式

每个业务区块（entity_confirmation / summary / products_plants / projects_news / procurement / risks）都可带 `evidence` 数组：

```jsonc
{ "title": "2025年年度报告摘要", "date": "2026-03-21", "url": "https://..." }
```

渲染器自动去重并编号为 E01、E02…，生成 Excel"证据台账"sheet；各 sheet 证据块引用编号。聚合平台快照请在 title 里写明，如 `"爱企查档案快照（2026-07-01）"`。

## 各区块字段

### meta
| 字段 | 说明 |
|---|---|
| company_display | 展示名（全称） |
| uscc | 统一社会信用代码 |
| listing | 上市信息（无则空串） |
| registered_address | 注册地址 |
| sales_product | 用户销售的产品（视角） |
| research_date | 检索窗口（如"截至2026年10月"） |
| prepared_for | 用途（默认"内贸销售"） |
| notes | 其他页眉备注 |
| is_demo | 可选；true 时渲染器在页面顶部与 Excel 中标注"教学示例（虚构数据）" |

### entity_confirmation
- `conclusion`：一句话主体锁定结论
- `near_name_table[]`：`{name, identity, sales_meaning}` 近名主体区分表
- `evidence[]`

### summary
- `is_target_customer`：`{verdict, reason}` —— 是不是我要找的客户
- `likely_buy`：`{answer, reason}` —— 它可能买什么
- `why_buy_logic`：`{headline, detail}` —— 为什么（需求逻辑链，headline 放核心数字）
- `risk_banner`：风险横幅（含应对动作，禁止评级/额度/概率表述）
- `evidence[]`

### next_actions
三个字符串数组：`entry_points[]`（找最近切入点）、`departments[]`（先找哪个部门）、`visit_prep[]`（准备拜访）。

### products_plants
- `key_metrics[]`：`{label, value}` 产能/装置/行业地位/基地等指标卡
- `facts[]`：字符串列表（产品结构、许可资质、员工等）
- `value_chain[]`：字符串列表（建议"上游：…/自身：…/下游：…"开头）
- `evidence[]`

### projects_news
- `timeline[]`：`{date, text}` 近18个月事件
- `implications_for_my_product[]`：每条动态对用户产品的含义（编号对应时间线）
- `evidence[]`

### procurement
- `demand_estimates[]`：`{item, basis, value, estimate}`，`estimate:true` 时渲染"估算"标注
- `supply_layers[]`：`{layer, content, meaning}` 供应三层结构
- `decision_chain[]`：字符串列表（推断需验证）
- `caveats[]`：数据口径与诚信提示
- `evidence[]`

### risks
- `seven_checks[]`：`{item, finding, status}`，status ∈ `ok`（正常）/ `warn`（待复核）/ `risk`（关注）/ `todo`（待办）
- `key_concerns[]`：重点关注事项（事实+动作，不做评级）
- `evidence[]`

### verification_checklist
`[{item, purpose}]` 合作前补充核实材料清单（通常 6–8 条）。

## 附录：手工交付规格（无 Python 环境时）

**Excel（工作簿名 `客户360_{公司}_核查台账.xlsx`）固定 10 个 sheet，顺序如下：**
1 使用说明（meta+免责）｜2 销售摘要（三问+横幅）｜3 主体确认（结论+区分表+证据）｜4 七项核查（核查项/结果/状态）｜5 产品与工厂（指标+事实+产业链）｜6 项目与动态（时间线+含义）｜7 采购关系（需求测算/三层结构/决策链/口径）｜8 风险与关注（key_concerns）｜9 核实清单｜10 证据台账（E编号/标题/日期/URL，与各 sheet 证据块编号一致）

**HTML：单文件、无外部依赖、可点击展开证据；固定区块顺序：页眉徽章 → 主体确认卡 → 首屏三问+风险横幅 → 三个后续动作面板 → 五个Tab分区 → 免责页脚。** 可直接以 build.py 渲染结果为模板。
