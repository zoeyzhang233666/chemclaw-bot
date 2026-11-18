# 就近供应商寻源（Nearby Supplier Sourcing）

一个可移植的 agent skill：输入「产品 + 收货地 + 批量」，输出**可复核的供应商清单**与
**两份成品**（交互 HTML + 8 表 Excel）。不是"搜一堆公司名"，而是把「产品匹配」和
「距离」拆成两条独立的轴，并强制暴露每一个没查到的信息。

- 适用：化工品/材料的内贸采购寻源（纯碱、液碱、甲醇、钛白粉、树脂、溶剂……）
- 产物：`dataset.json`（唯一数据源）+ `<产品>_采购雷达.html` + `<产品>_供应商运距清单.xlsx`
- 平台：Claude / chemclaw / workbuddy / codex / 任意能跑 Python 的 agent

---

## 1. 一分钟理解它做什么

```
产品规格 + 收货地 + 批量
      ↓  （六步：锁参数 → 建候选池 → 定角色坐标 → 算距离 → 两轴评分 → 生成自检）
候选企业（工厂 / 交割库 / 仓库 / 贸易商）
      ↓  每条事实带证据等级 A/B/C/D
匹配度 M（能不能真供货）   ‖   物流分 L（距离值多少）
      ↓  排序：先档位，再距离 —— 绝不用一个加权总分
HTML（地图+抽屉+矩阵）  +  Excel（8 表台账）  +  缺口清单（每条一个动作）
```

**它拒绝做的事**：因为近就推荐不匹配的企业、编造运费金额、把没查到的写成"约"。

---

## 2. 安装

### 2.1 Claude / chemclaw / workbuddy（Agent Skills 格式）

把整个 `nearby-supplier-sourcing/` 目录放进平台的 skills 目录即可（`SKILL.md` 带
YAML frontmatter，会被自动索引）：

```bash
# 常见位置（按你的平台实际路径调整）
~/.claude/skills/nearby-supplier-sourcing/
<平台安装目录>/skills/nearby-supplier-sourcing/
```

也可以只把目录放到任意位置，然后对该 agent 说：

> 读取 `<路径>/nearby-supplier-sourcing/SKILL.md`，按里面的流程执行。

### 2.2 Codex / 其他 AGENTS.md 型 agent

把 `AGENTS.md` 的内容并入项目根的 `AGENTS.md`，或直接把本目录放进项目并引用：

```markdown
## 供应商寻源
需要"找附近供应商/运距评估"时，读 `nearby-supplier-sourcing/SKILL.md`，
按 `assets/scripts/run_all.py` 的流程产出 dataset.json + HTML + Excel。
```

### 2.3 纯命令行（不依赖任何 agent）

```bash
python assets/scripts/run_all.py --dataset my_dataset.json --out ./output
```

---

## 3. 依赖

| 项 | 要求 | 说明 |
|---|---|---|
| Python | 3.9+ | 只用标准库 + openpyxl |
| openpyxl | 3.x | `pip install openpyxl`（Excel 必需） |
| 网络（可选） | OSRM + DataV | 失败会自动降级并在报告里标注「估算」 |

**完全离线也能跑**：加 `--no-osrm`，公路里程按"直线 × 系数"估算，报告里明确写"估算"。

---

## 4. 快速开始（3 步）

### 第 1 步：填数据

复制 `assets/dataset.template.json`，按注释逐项替换。两种来源：

- **让 agent 研究**：让它按 `references/research-playbook.md` 的搜索模板去查，
  每家企业凑够 `evidence[]`（claim/kind/source/url/date/level/supports）和 `gaps[]`
- **你有现成数据**：只填企业名、地址、坐标、匹配分，evidence 可以先留 1 条

> 坐标是关键：宁可标"区县中心 ±10 km"，也不要随手填一个看起来对的点。

### 第 2 步：跑

```bash
python assets/scripts/run_all.py --dataset dataset.json --out ./output
```

脚本会依次：校验结构 → 拉底图 → 算距离（haversine + OSRM）→ 计算分数与排序 →
生成 HTML → 生成 Excel。任一步失败即中止，不会产出半成品。

### 第 3 步：看自检清单

打开 `SKILL.md` 第 7 节，逐项打勾。最常见的三处返工：

1. 有工厂只有 C 级证据却给了 A 档 → 校验脚本会直接拦下
2. 缺口少于企业数的一半 → 说明查得太浅
3. 出现了运费金额 → 必须删掉，改成计费口径

---

## 5. 目录

```
nearby-supplier-sourcing/
├── SKILL.md                     # 主流程（agent 首先读这个）
├── README.md                    # 本文件
├── AGENTS.md                    # codex 风格入口
├── references/
│   ├── research-playbook.md     # 搜索式模板、来源阶梯、常见陷阱
│   ├── scoring-model.md         # 五维评分与档位（两轴独立）
│   ├── distance-protocol.md     # 距离口径、OSRM、降级系数
│   ├── hazmat-classification.md # 危化判定与运输条款
│   ├── evidence-grading.md      # A/B/C/D 判定细则
│   └── output-spec.md           # HTML/Excel 字段与版式
├── assets/
│   ├── dataset.template.json    # 填空模板
│   ├── dataset.schema.json      # JSON Schema
│   ├── template/report.html     # 数据驱动模板（勿改结构）
│   └── scripts/
│       ├── run_all.py           # 一键流程
│       ├── validate_dataset.py  # 交付前校验
│       ├── prepare_geo.py       # 省界底图（带缓存）
│       ├── compute_routes.py    # 距离与路径
│       ├── compute_scores.py    # 分数、档位、排序
│       ├── build_html.py
│       └── build_xlsx.py
└── examples/
    ├── 01-soda-ash-shahe/       # 纯碱：非危化，厂家远、仓库近
    └── 02-caustic-soda-changzhou/  # 液碱：危化品，厂家就在门口
```

---

## 6. 两个示例分别演示什么

| | 纯碱（沙河） | 液碱 32%（常州滨江） |
|---|---|---|
| 危化 | 非危险化学品 | 8 类腐蚀品 / UN1824 |
| 近场 | 只有交割库（2.6 km，不生产） | 厂家就在园区（5.2 km） |
| 主供距离 | 423–531 km | 34–57 km |
| 关键结论 | 100 km 内没有碱厂 | 300 km 内竞争充分，瓶颈是危运力 |
| 演示点 | "近 ≠ 匹配"、长距离铁路议价 | 危化品整块判定、同园区短驳、园区管输可能 |

两者共用同一套脚本与模板 —— 这就是"产品无关"的证明。

---

## 7. 自定义

| 想改什么 | 改哪里 |
|---|---|
| 评分维度/权重 | `dataset.json → match.dims`（合计建议 100） |
| 档位线 | `match.tiers` |
| 半径选项 | `logistics.rings`（UI 自动生成按钮） |
| 物流分曲线 | `logistics.anchors` |
| 无路网时的估算系数 | `logistics.fallback_factor`（平原 1.15–1.20，丘陵 1.25，山区 1.35） |
| 报告配色/版式 | `assets/template/report.html` 顶部 CSS 变量 |
| Excel 列 | `assets/scripts/build_xlsx.py` 的 `heads/widths` |
| 底图源 | `prepare_geo.py --geojson your.geojson`（非中国项目） |

---

## 8. 排错

| 现象 | 原因 | 处理 |
|---|---|---|
| `OSRM 失败 → 降级估算` | 公共服务限流/网络 | 加 `--sleep 2`、换自建 OSRM、或 `--no-osrm` |
| 底图空白 | DataV 拉取失败且无缓存 | 保留 `geo_cache.json`；或 `--geojson` 指定 |
| 校验报"工厂证据不足" | 只有 C/D 级来源 | 补 A/B 证据，或把分数降到 C 档（<70） |
| HTML 打开是空白 | 直接编辑了模板占位符 | 恢复 `__DATA__`/`__GEO__`，重新 `build_html.py` |
| Excel 打不开 | openpyxl 版本过旧 | `pip install -U openpyxl` |
| 中文乱码（Windows 控制台） | 编码 | `set PYTHONIOENCODING=utf-8` |

---

## 9. 许可

MIT。示例数据来自公开渠道，引用链接保留在 `evidence[]` 中；商用前请自行复核。
