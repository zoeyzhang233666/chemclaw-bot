# 移植说明（跨 agent、跨环境）

这个技能不绑定任何特定 agent 框架。核心是：**一份 JSON + 几个纯 Python 脚本 + 一个 HTML 模板**。

## 一、依赖

| 项 | 要求 | 检查 |
| --- | --- | --- |
| Python | 3.9+ | `python -V` |
| openpyxl | 3.0+（Excel） | `python -c "import openpyxl"` |
| Node.js | 可选，仅用于 HTML 的 QA | `node -v` |
| 浏览器 | Edge/Chrome，可选，仅用于 QA | — |
| 网络 | 取证阶段需要 | — |

没有 pandas / numpy / 第三方图表库依赖。HTML 图表是手写 SVG，**不需要 echarts**。

## 二、目录

```
chem-topic-research/
├── SKILL.md                    # 技能入口（frontmatter + 流程）
├── references/                 # 方法论文档（12 篇）
├── examples/
│   ├── soda-ash-2026/          # 完整案例
│   └── templates/              # 提纲/执行记录样例
└── scripts/
    ├── common.py               # 校验、索引、payload 组装（核心库）
    ├── new_case.py             # 生成空白 case
    ├── build_all.py            # 一键生成全部
    ├── build_html.py           # HTML
    ├── build_xlsx.py           # Excel 13 页
    ├── build_md.py             # 提纲/执行记录/全文
    ├── qa.py                   # 交付物静态自检
    ├── qa_dom.mjs              # HTML 运行时 QA（无头浏览器）
    ├── qa_xlsx.py              # 工作簿 QA
    └── templates/report.html   # HTML 模板
```

## 三、在别的 agent 里怎么用

只需要告诉 agent：

1. 读 `SKILL.md` 与 `references/workflow.md`。
2. 按流程产出 `case.json`。
3. 依次运行 `common.py validate` → `build_md.py outline` → **等用户确认** → `build_all.py`。
4. 用 `qa_dom.mjs` 检查页面。

不需要任何专有工具调用。所有步骤都是命令行。

## 四、路径与编码

- 脚本用 `os.path.dirname(__file__)` 定位自身，可从任意工作目录调用。
- 中文路径可用；Windows 控制台若出现乱码，设置 `PYTHONIOENCODING=utf-8`。
- 命令行传中文参数时，`new_case.py` 与 `build_all.py` 已做编码兜底；其他脚本请用英文受众键。

## 五、模板改动的边界

`templates/report.html` 只读取注入的 `PAYLOAD`，两处占位符：

- `__TITLE__`：`<title>` 与打印标题
- `__DATA__`：`<script type="application/json">` 内的 JSON

改样式随便改；改结构时注意这些约定：

- 全局变量 `PAYLOAD / META / PROF / DS / SRC / GAPS / CALCS / CONC / CHARTS`
- 函数 `renderChart / showConclusion / showRawData / switchView / exportMarkdown`
- `window.__BOOT_ERRORS` 保存启动阶段异常
- 每个区块的 `data-*` 属性是事件绑定的依据（`data-concl` `data-raw` `data-jump` `data-src` `data-gap`）

## 六、扩展新产品/新主题

1. `python scripts/new_case.py --title "..." --product 尿素 --audience procurement`
2. 只改 `audience_frameworks`（提纲阶段），让用户确认。
3. 与研究阶段填 `sources / projects / datasets / calculations / conclusions / sections`。
4. 图表：在 `sections[].blocks` 里加 `{"type":"chart","chart_type":"line","data_key":"你的顶层键","keys":[...]}`。

**不需要改任何 Python 代码**——除非新增一种图表类型（在模板的 `RENDERERS` 里加一个函数）。

## 七、离线与安全

- HTML 完全离线，无外链、无 CDN、无埋点。
- 数据只在本机处理。
- 若需分发给外部，注意 `meta.disclaimer` 与敏感信息（企业联系人、内部产能数据）需自行脱敏。
