# chem-market-brief · 化工品行情简报

给内贸销售一份**能拿去和客户对话**的行情底稿：当前价、区间涨跌、历史分位、区域价差、
上下游成本、事件时间线，落成 **单文件 HTML 看板 + 13 表 Excel 工作簿**。

**品种无关。** 换品种只换 `research.json`，脚本里没有一个品种字面量。

```
research.json  ──assemble.py──▶  build/data.json  ──▶  build_html.py  ──▶  *_行情看板.html
   （人写事实）        （算派生）      （唯一数据源）   ──▶  build_xlsx.py  ──▶  *_行情与销售事实.xlsx
                                                      ──▶  check_html.py / qa_render.py（自检）
```

## 三条硬规矩

1. **只陈述已发生的事实**——不预测涨跌，不写“预计/看涨/抄底”。
2. **每个价格六项齐全**——数值 · 规格 · 地区 · 含税 · 日期 · 来源。缺一项进“缺口”。
3. **拿不到就写缺口**——不近似、不插值、不用行业均值顶替、不跨日期拼价差。

## 快速开始

```bash
pip install openpyxl

# 用现成范本跑一遍（纯碱，全量数据）
cd scripts
python build_all.py ../examples/01-soda-ash-national/research.json \
                    --out ../examples/01-soda-ash-national/output --name 纯碱-全国

# 换品种：先确认有没有期货
python fetch_futures.py 玻璃 --probe
python fetch_futures.py 玻璃 --out ../examples/my-glass/raw/玻璃_daily.json

# 然后写 research.json（照 examples/02-glass-shahe/），再
python build_all.py ../examples/my-glass/research.json --out ../examples/my-glass/output
```

一条命令内部依次执行：`validate` → `assemble` → `build_html` → `build_xlsx` → `check_html` → `qa_render`。
校验有 error 会直接停，不出半成品。

## 目录

```
chem-market-brief/
├── SKILL.md                      # 给模型看的六步流程（入口）
├── research.template.json        # 空骨架
├── references/
│   ├── research-playbook.md      # 按品种找数的渠道顺序、单位陷阱、假数据识别
│   ├── data-contract.md          # research.json 全字段
│   ├── quoting-rules.md          # 报价口径与对外话术边界
│   ├── qa-checklist.md           # 交付前逐项打勾
│   └── adapters.md               # 装到 chemclaw / workbuddy / codex / DSH
├── scripts/
│   ├── common.py                 # 共享库：品种表、单位、序列、统计、链式提示
│   ├── fetch_futures.py          # 期货日线抓取（东财，多交易所）
│   ├── validate.py               # research.json 契约校验
│   ├── assemble.py               # 全部派生指标（唯一的计算入口）
│   ├── build_html.py             # 注入数据 + 内联 ECharts
│   ├── build_xlsx.py             # 13 表工作簿
│   ├── build_all.py              # 一条命令全流程
│   ├── check_html.py             # HTML 静态自检：占位符/外链/禁用词/数字一致
│   ├── check_xlsx.py             # 工作簿自检：表结构/缺口/禁用词/与 HTML 同数
│   ├── qa_render.py              # 浏览器实测（可选）
│   ├── selftest.py               # 一键回归：范本 + 降级 + 反例
│   ├── templates/dashboard.html  # 看板模板
│   └── assets/echarts.min.js     # 内联用（无需联网）
└── examples/
    ├── 01-soda-ash-national/     # 全量：8 条现货、13 事件、6 缺口
    └── 02-glass-shahe/           # 跨品种：真实玻璃数据，含单位换算与区域价差
```

## 看板长什么样

首屏四张 KPI（现货锚 / 期货收盘 / 7 日涨跌 / 一年分位），往下十节：

`01 走势`（K线+K线量，可切 30 天/90 天/1 年/3 年，可叠加成本线）·
`02 现货表`（六项口径，点行看详情）· `03 涨跌幅`（5 个窗口逐条列基准日）·
`04 历史分位`（区间条 + 成本线位置）· `05 区域价差`（柱状 + 表，标明基准区）·
`06 上下游与毛利`· `07 供需库存`· `08 事件时间线`（点异常波动看当时发生了什么）·
`09 事实卡与话术`（一键生成微信/邮件/短句）· `10 缺口·口径·来源`

## 自检强度

| 工具 | 检查内容 |
|---|---|
| `validate.py` | 契约、日期、单位量级、价差可比性、方向性表述 |
| `check_html.py` | 占位符残留、外部 `<script>`、ECharts 是否存在、24 个必需节点、数字是否一致、禁用词（客户原话豁免） |
| `qa_render.py` | 真实浏览器：JS 报错、KPI 数量、canvas 是否画出像素、7 模块渲染、1600/1280/420 三档无溢出、抽屉、话术生成与合规 |
| `build_xlsx.py` | 写入时对每个字符串扫禁用词 |

两个范本均为 **0 error / 0 失败**。改过模板或脚本后跑 python scripts/selftest.py：
它会验证两个范本、一条降级路径（无期货 + 只有 1 条现货），并用三个反例确认检查器真的会拒绝
（预测词、坏日期、囤货建议）。必须打印“全部通过”。

## 降级

无期货 → 只出手现货；无现货 → 首屏明示“无现货报价”；无 `openpyxl` → `--html-only`；
无 `playwright` → `--no-render`；无网络 → 用 `examples/` 已有数据出样品并标注“未更新至最新”。

详见 [`references/adapters.md`](references/adapters.md)。
