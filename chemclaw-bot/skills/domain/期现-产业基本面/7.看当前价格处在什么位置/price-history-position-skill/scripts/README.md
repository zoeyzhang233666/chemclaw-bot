# 脚本清单

全部为 Python 3.9+，依赖：`openpyxl`（出 Excel）、`playwright`（HTML 验收，可选）。
模板与 ECharts 已内置，无需联网。

---

## 主流程

| 脚本 | 作用 | 用法 |
|---|---|---|
| `price_stats.py` | **统计核**（与品种无关）：经验分位、区间位置、描述统计、涨跌、年化波动、最大回撤、季节性、三判据异常、缺口 | `python scripts/price_stats.py --check build/data.json` |
| `assemble.py` | 把原始观测装配成 `build/data.json`（含覆盖率检测、口径断点、缺口） | `python scripts/assemble.py` |
| `build_html.py` | 由 data.json 生成**单文件**交互式 HTML（内联 ECharts） | `python scripts/build_html.py build/data.json --out out/x.html` |
| `build_xlsx.py` | 由 data.json 生成 14 表工作簿，**统计列全是活公式** | `python scripts/build_xlsx.py build/data.json --out out/x.xlsx` |

## 校验

| 脚本 | 作用 | 通过标准 |
|---|---|---|
| `validate.py` | 数据完整性：每条观测可追溯、分位可独立重算、统计量复算、日期单调、无重复 | `FAIL=0` |
| `check_html.py` | 用 Chromium 实跑：JS 零报错、三图真出像素、交互可用、CSV 可导出、三档宽度零溢出 | `FAIL=0`，退出码 0 |
| `check_xlsx.py` | 扫全簿错误值 + 逐窗口与 data.json 对账 + 确认关键格存的是公式 | `FAIL=0`，退出码 0 |
| `selftest.py` | 一条命令跑完 build→check 全链路 | `RESULT: ALL PASS` |

## 采集（100ppi 专用，可作参考实现）

| 脚本 | 作用 |
|---|---|
| `ppi_parse.py` | 解析生意社华东日评 / 基准价文章，输出统一观测结构（含按产品分段的调整量提取） |

> 反爬处理见 `references/pitfalls.md` 第 1 节：**全局限速 + 冷却并发递增**，切勿密集重试。

## 资源

```
scripts/
  templates/report.html    HTML 骨架（含 __占位符__）
  templates/app.js         图表与交互（ECharts）
  assets/echarts.min.js    内联用 ECharts 5（约 1 MB）
```

---

## 典型执行顺序

```bash
# 1 取数（或用你的适配器直接产出 raw/observations.json）
python scripts/ppi_parse.py            # 参考实现

# 2 装配
python scripts/assemble.py

# 3 数据校验 —— 必须 FAIL=0
python scripts/validate.py

# 4 HTML
python scripts/build_html.py build/data.json --out "out/报告.html"
python scripts/check_html.py "out/报告.html"

# 5 Excel（重算后对账）
python scripts/build_xlsx.py build/data.json --out "out/报告.xlsx"
node <libreoffice-kit cli.js> recalculate --input "out/报告.xlsx" --output "out/recalc.xlsx"
python scripts/check_xlsx.py "out/recalc.xlsx" build/data.json
```

## 关于重算

openpyxl **只写公式、不写缓存值**。不重算的话，用 `data_only=True` 读回来全是 `None`，
`check_xlsx.py` 会报「公式未被正确求值」——这是**预期的**，不是 bug。

环境里有 LibreOffice Kit 时：

```bash
node <cli.js> recalculate --input in.xlsx --output out.xlsx
```

`selftest.py` 会读环境变量 `DSH_NODE` 与 `DSH_LO_CLI` 自动完成重算。
