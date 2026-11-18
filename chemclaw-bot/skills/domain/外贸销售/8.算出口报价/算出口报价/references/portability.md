# 可移植性与运行环境

> 目标：任何人拿到这个 Skill 的压缩包，在**没有本机特定依赖**的条件下也能跑通。

---

## 1. 运行环境要求

| 组件 | 版本 | 用途 | 是否必需 |
|---|---|---|---|
| Python | 3.9+ | 计算引擎、生成 HTML/Excel | 是（生成期） |
| `openpyxl` | 3.0+ | 生成带公式的 Excel | 生成 Excel 时需要 |
| 浏览器（Chrome/Edge/Safari/Firefox 现代版） | 近 3 年内 | 打开 HTML 计算器 | 使用期 |
| Node.js | 18+ | 仅用于无头自测 `selftest_html.mjs` | 开发期可选 |
| LibreOffice | 任一近期版 | 仅用于"重算 Excel 验证" | 开发期可选 |

**使用期零依赖**：HTML 计算器是单文件、离线、无 CDN、无网络请求。

---

## 2. 目录结构

```
算出口报价/
├── SKILL.md                       # Skill 主文件（AI 读这个）
├── README.md                      # 人读的快速上手
├── INSTALL.md                     # 安装/放置说明
├── VERSION
├── CHANGELOG.md
├── PORTABLE_PROMPT.md             # 给其他 AI 的独立提示词
├── references/
│   ├── incoterms.md               # 术语与责任矩阵
│   ├── formulas.md                # 全部公式
│   ├── parameters.md              # 参数口径与补数来源
│   ├── sensitivity.md             # 敏感性方法
│   ├── validation.md              # 校验规则
│   ├── qa.md                      # 交付前 QA 清单
│   ├── portability.md             # 本文件
│   └── citations.md               # 外部事实出处
├── scripts/
│   ├── calc_engine.py             # 权威计算引擎
│   ├── build_html.py              # 生成交互式 HTML
│   ├── build_xlsx.py              # 生成带公式 Excel
│   └── selfcheck.py               # 一键自检
├── templates/
│   └── calculator.template.html   # HTML 模板（含 __DATA__ 占位）
├── products/
│   ├── soda-ash.json              # 纯碱产品画像
│   └── _template.json             # 新品画像模板
└── examples/
    └── soda-ash-qingdao-jakarta/
        ├── input.json
        ├── sim_preset.json
        ├── 案例说明.md
        └── output/
            ├── 出口报价计算器_纯碱_青岛-雅加达.html
            ├── 出口报价工作簿_纯碱_青岛-雅加达.xlsx
            └── result.json
```

---

## 3. 路径无关性

所有脚本使用 `os.path.dirname(os.path.abspath(__file__))` 定位自身目录，**不含绝对路径**，可整目录搬迁。

`build_html.py` 与 `build_xlsx.py` 通过 `sys.path.insert(0, HERE)` 导入 `calc_engine`，因此从任意工作目录调用都可用：

```bash
python /any/path/算出口报价/scripts/calc_engine.py /any/path/input.json -o out.json
```

---

## 4. 中文与编码

- 所有 `.py` / `.md` / `.json` 文件均为 **UTF-8（无 BOM）**；
- 生成 HTML 时在 `<head>` 声明 `<meta charset="utf-8">`；
- **Windows 命令行**建议先设 `set PYTHONIOENCODING=utf-8`，否则中文可能显示乱码（不影响计算）；
- **不要用 PowerShell 的 `-replace | Set-Content` 编辑这些文件**——默认 GBK 回写会把中文毁掉。用编辑器或 Python 读写。

---

## 5. 跨 AI 平台使用

见 `PORTABLE_PROMPT.md`：把该文件连同 `references/`、`input.json` 交给任意具备文件读写能力的 AI，即可复现同一套计算与交付物。

需要 AI 具备的最小能力：
1. 读 `SKILL.md` 与 `references/`；
2. 写 JSON 输入；
3. 能执行 Python（生成 HTML/Excel），或至少能按 `formulas.md` 手算并在表格中呈现。

---

## 6. 与已有 Skill 的关系

本 Skill 是独立自洽的，但可与其他外贸 Skill 组合：

| 上游 | 提供 | 本 Skill 消费 |
|---|---|---|
| 询盘转报价（inquiry-to-quotation） | 客户需求清单 | 品名/规格/数量/术语/港口 |
| 客户线索（b2b-lead-sourcing） | 潜在客户 | 报价对象 |
| 行情（chem-market-brief） | 现货价参考 | 出厂价的合理性交叉验证（**不作为成本输入**） |

> 注意：行情简报给出的是**市场价格**，不是工厂给贸易商的**出厂成本**。两者不能直接互换。

---

## 7. 已知限制

1. **不做实时运价/汇率获取**——这是设计选择，不是缺陷。
2. **不自动判断 HS 归类**——编码错，退税率全错。
3. **不涵盖特殊监管**（危险品、两用物项、反倾销）——需另行核查。
4. **不生成正式法律文本**——报价草稿仅供内部起草，合同条款需法务确认。
5. **Excel 公式依赖 Excel/LibreOffice/WPS 的计算引擎**——在 Google Sheets 中打开可能有少量函数兼容差异（`CHOOSE/MATCH` 正常，但 `Nilai Lain` 类非标准写法不存在，本工作簿未使用）。
