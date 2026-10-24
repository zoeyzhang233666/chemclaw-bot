# chem-lead-sourcing 内部接口契约（所有模块必须遵守）

本 skill 是**产品无关**的：任何化工品（纯碱、烧碱、钛白粉、MDI、硫酸、双氧水…）都走同一套流程。
所有脚本**只读 `config.json`**，**不得硬编码任何产品名 / 地区 / 日期**。

## 1. 目录约定（相对项目根）

```
<project>/
  config.json          复制自 config.example.json 后填写
  lanes.json           应用地图（lane 列表），由 agent/人填写，见 §4
  channels.json        通道能力探测结果，由 `b2bctl probe` 生成
  workplan.md          派工单，由 `b2bctl brief` 生成
  leads_raw/*.json     每个 lane 一个文件，文件名 `<lane_id>_<lane名>.json`
  leads_raw/_qa_report.json   链接抽检报告
  leads.json           合并去重后的最终数据
  merge_stats.json     合并统计
  <out_stem>.xlsx      Excel 交付物
  <out_stem>.html      交互式 HTML 交付物
  方法与边界说明.md      交付四块文字版
```

`out_stem` 由 `config.paths.out_stem` 模板渲染：
`{product}`=产品名，`{region}`=地区名，`{months}`=窗口月数。

## 2. config 结构

见 `config.example.json`。关键字段：

- `product.name` / `formula` / `aliases[]` / `grades[]` / `roles_vocab[]`
- `region.name` / `provinces[]` / `cities[]`
- `window_months`（整数）、`today`（`YYYY-MM-DD`）
- `peer_keywords[]`：**自身生产该产品的同行**关键词，命中即剔除（peer gate）
- `stages_vocab[]`：`拟建/备案/在建/试车/已投产`
- `source_types_vocab[]`：`备案/环评/招标/公告/新闻`
- `qa.min_sample` / `qa.max_total`
- `lane_fanout.max_concurrency`（默认 8）

## 3. 线索记录 schema（产品无关）

lane 文件与 `leads.json` 都是**同一 schema 的 JSON 数组**。

### 3.1 采集字段（lane 子代理产出，共 18 个，缺一不可）

| 字段 | 说明 |
|---|---|
| `公司` | 业主企业全称（可带括号注明母/子公司关系） |
| `细分行业` | 如 光伏玻璃 / 印染 / 锂盐 |
| `省市` | `省/市`，必须落在 `region.provinces` 内 |
| `项目名称` | 项目全称；确实无名称时写 `未披露（原因）` |
| `建设阶段` | 必须 ∈ `stages_vocab` |
| `项目产品` | 该项目产出什么 |
| `设计产能` | 带单位；未披露写 `未披露` |
| `预计投产时间` | `YYYY-MM` 或 `YYYYQn` 或 `未披露` |
| `所在园区` | 园区/厂址 |
| `需求点` | 本产品在该项目**哪个工序、起什么作用** |
| `产品角色` | 必须 ∈ `product.roles_vocab`（主原料/辅料/助剂） |
| `单耗依据` | 单耗的**依据**（反应式/配合料配比/公告原文）。拿不到就写 `无法估算` |
| `年需求量估算` | 由 `单耗依据` 推出的量级；无依据写 `无法估算`。**严禁无出处估算** |
| `规模线索` | 投资额、进度、建设周期等 |
| `来源类型` | 必须 ∈ `source_types_vocab` |
| `来源` | **可点击、可复现的 URL**（原始公告/环评原文）。取不到就写 `未核实` |
| `发布日期` | `YYYY-MM-DD` |
| `置信度` | `高`/`中`/`低`，判定规则见 [`evidence.md`](evidence.md) |

### 3.2 派生字段（由 `b2bctl merge` 写入，lane 不得自行填写）

`lane`、`lane_id`、`用量强度`（`★★★★★` 字符串，1~5 星）、`需求性质`（`直接`/`间接`）、
`销售时点`、`时点理由`、`优先级`、`抽检结论`。

## 4. lanes.json（应用地图）

```json
{
  "product": "纯碱",
  "lanes": [
    {
      "id": "01",
      "name": "光伏玻璃",
      "logic": "每吨光伏玻璃配合料需 0.20~0.24 t 纯碱作助熔剂",
      "intensity": 5,
      "intensity_basis": "5★=千吨级以上/年，2★=十吨级",
      "clusters": ["安徽滁州", "江苏宿迁"],
      "seeds": ["福莱特", "凯盛新能", "亚玛顿"]
    }
  ]
}
```

- `intensity` 1~5：5★=单点年需求千吨级以上，4★=千吨级，3★=百吨级，2★=十吨级，1★=更小/不确定。
- `seeds`：5~8 家具名候选企业（用于派工，不要求全部命中）。
- **lane 的划分依据是"下游应用方向"**，不是企业名单。同一产品可有多个 lane。

## 5. 模块函数签名（`scripts/lib/` 内必须严格实现）

所有函数**只能通过参数拿到数据，不读全局变量**；用 `utf-8` 读写。

```python
# scripts/lib/html_out.py
def build_html(cfg: dict, leads: list[dict], out_path: str) -> str: ...

# scripts/lib/excel_out.py
def build_workbook(cfg: dict, leads: list[dict], out_path: str) -> str: ...

# scripts/lib/excel_out.py
def build_workbook(cfg: dict, leads: list[dict], out_path: str,
                   stats=None, lanes=None, channels=None, qa=None) -> str: ...
def build_csv(cfg: dict, leads: list[dict], out_path: str) -> str: ...   # 无 openpyxl 时降级

# scripts/lib/report_out.py
def build_report(cfg: dict, leads: list[dict], stats: dict, out_path: str,
                 channels: dict | None = None, qa: dict | None = None,
                 gaps_text: str | None = None, excluded_text: str | None = None) -> str: ...

# scripts/lib/merge.py
def merge(cfg, root) -> tuple[list[dict], dict]   # (leads, stats)，并写出 leads.json / merge_stats.json
def load_qa(cfg, root) -> dict                    # 来源 URL -> 抽检结论
# 契约别名（实现在 common，这里 re-export 以免调用方踩空）：
load_config = common.load_config
render_stem = common.render_stem
window_bounds = common.window_bounds

# scripts/lib/qa.py
def sample_and_check(cfg, leads, out_path, timeout=25, workers=8, log=True) -> dict

# scripts/lib/common.py —— 配置、schema、归一化、销售时点推导（产品无关的共享层）
load_config(path) -> (cfg, root)
render_stem(cfg) -> str
window_bounds(cfg) -> (today, now_ym, win_ym, window_end)
normalize_record(cfg, raw, lane_id, lane_name, intensity) -> (rec, drop_reason)
derive_timing(cfg, stage, ramp) -> (销售时点, 理由)
```

**注**：`build_workbook` / `build_html` 的额外信息通过**可选参数**传入；不传时模块从 cfg 或磁盘读取，
读不到就如实标注"未提供"，**不编造**。

## 6. 硬性纪律（所有模块与 agent 都必须遵守）

1. **不得编造**任何公司名、产能、日期、URL、单耗。缺数据写 `未披露` / `无法估算`。
2. 每条线索必须有 `来源`（可点击 URL）。无来源 → `来源=未核实`、`置信度=低`。
3. **peer gate**：命中 `peer_keywords` 的主体是同行，剔除并在交付说明中列名。
4. **地区闸门**：`省市` 不在 `region.provinces` 内的一律剔除。
5. 同一窑炉/产线的多次披露要去重（保留最新、信息最全的一条）。
6. 交付必须包含四块：条数与分布 / 置信度分级 / 被剔除的 peer 名单 / 未覆盖缺口与负结果。
7. 链接抽检 ≥ `qa.min_sample` 条，坏链必须报告，不得隐藏。
8. Excel 与 HTML **都是必须的**；Excel 缺少 openpyxl 时降级为 CSV 并明确告知。