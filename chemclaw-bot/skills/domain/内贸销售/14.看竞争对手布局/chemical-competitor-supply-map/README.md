# 化工品竞争供给地图 · 可移植 Agent Skill

把“某个化工品在一个区域谁在供、离客户多远、哪里空白、未来谁扩产、先打哪些客户”固化成一套可复用的研究流程和交付物。

- **产品无关**：纯碱、烧碱、甲醇、钛白粉、塑料、新材料……只换 `data.json`，不改代码。
- **两个成品**：单文件交互式 HTML + 9 工作表 Excel。
- **一个数据源**：HTML 和 Excel 都从同一个 `data.json` 生成，避免“图里一个数、表里一个数”。
- **可追溯**：每条产能有来源；A/B/C/D 证据分级；冲突并列；缺口单列。
- **可移植**：Python 3 + openpyxl，无 DSH 专有依赖，构建时不需要联网（ECharts/GeoJSON 已内联）。

## 快速开始

```bash
cd chemical-competitor-supply-map

# 1) 检查数据
python scripts/validate.py examples/01-soda-ash-guangdong-jiangmen/data.json

# 2) 一键生成 HTML + Excel
python scripts/build_all.py examples/01-soda-ash-guangdong-jiangmen/data.json \
  examples/01-soda-ash-guangdong-jiangmen

# 3) 验收成品
python scripts/qa.py \
  --data examples/01-soda-ash-guangdong-jiangmen/data.json \
  --html examples/01-soda-ash-guangdong-jiangmen/纯碱_广东江门_竞争供给地图.html \
  --xlsx examples/01-soda-ash-guangdong-jiangmen/纯碱_广东江门_竞争供给地图.xlsx
```

看到 `PASS: 0 hard errors` 即可交付。

## 两个示例

| 示例 | 用途 | 说明 |
|---|---|---|
| `examples/01-soda-ash-guangdong-jiangmen/` | 真实案例，作为“成品长什么样”的参考 | 广东江门，纯碱，17 家企业 / 22 座工厂 / 3,070 万吨样本，37 条来源，9 项冲突 |
| `examples/02-minimal-template/` | 最小结构模板 | **全虚构**，3 家企业 / 3 座工厂 / 4 条来源；只用来复制字段和跑流程，不是研究结论 |

## 自己的产品怎么用

1. 复制 `examples/02-minimal-template/data.json` 为你的 `data.json`；
2. 填 `meta` + `target`（目标经纬度必填）；
3. 填 `companies` + `plants`（工厂必须挂在企业下，产能合计一致）；
4. 填 `projects`、`prospects`、`sources`、`conflicts`、`gaps`、`boundaries`；
5. 写 `narrative`（结论、锚点、动作卡）；
6. `build_all.py` → `qa.py`。

字段说明见 [`references/data-contract.md`](references/data-contract.md)，研究流程见 [`references/research-playbook.md`](references/research-playbook.md)。

## 输出目录

```text
out/
├── 产品_区域_竞争供给地图.html
├── 产品_区域_竞争供给地图.xlsx
└── build_report.json
```

HTML 可直接双击打开；Excel 可直接筛选/打印。HTML 里的“下载 Excel”按钮默认指向同目录的 xlsx 文件，因此**两个文件要放在一起交付**。

## 环境

```bash
python --version             # 3.10+
python -c "import openpyxl"  # 必须
node --check scripts/templates/app.js   # 可选，检查 JS 语法
```

若没有 openpyxl：

```bash
python -m pip install openpyxl
```

只装一次；构建本身不联网。

## 目录

```text
chemical-competitor-supply-map/
├── SKILL.md                  # agent 入口（YAML frontmatter + 完整说明）
├── scripts/
│   ├── build_all.py          # 一键构建
│   ├── build_html.py         # HTML
│   ├── build_xlsx.py         # Excel
│   ├── common.py             # 归一化/距离/聚合
│   ├── validate.py           # 数据校验
│   ├── qa.py                 # 成品验收
│   ├── templates/            # app.js + style.css
│   └── assets/               # ECharts + 中国 GeoJSON
├── references/               # 研究手册/数据契约/设计规范/验收/适配
└── examples/                 # 真实案例 + 最小模板
```

## 边界

- 不做市场份额；样本覆盖只是覆盖度。
- 不做价格预测/投资建议。
- 直线距离不是运费；项目毛增量不是净增。
- 所有推算用量都标 `*`；所有缺口都写成下一步取证任务。

## License

MIT。示例中的真实企业数据仅用于研究演示；引用来源见各示例 `data.json` 的 `sources`。
