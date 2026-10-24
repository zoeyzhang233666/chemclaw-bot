# 模板说明

本目录放"可直接改写"的成品模板。两个模板都由真实案例（`examples/pp-lldpe-px-pta/`）导出，
结构和样式即是最终交付形态。

---

## 1. `产业链异常背离扫描-模板.xlsx`（16 张表）

| # | Sheet | 改成自己的内容时改哪里 |
|---|---|---|
| 00 | 说明与使用指南 | 改"品种池/关系数/参数/生成时间"几行 |
| 01 | 品种池与口径 | 换品种时整表替换 |
| 02 | 产业链关系图谱 | 换关系时整表替换 |
| 03 | 配对构建规则 | 一般不改（规则是通用的） |
| 04 | 候选组合清单 | 自动生成，不用手改 |
| 05 | 异常背离榜单 | 自动生成；**带筛选器，可直接按判定/强度筛选** |
| 06 | 统计口径与阈值 | 改了参数一定要同步改这里 |
| 07 | 统计详情 | 自动生成 |
| 08 | 价格价差明细 | **原生公式**：换 B/C 两列价格即可全表重算 |
| 09 | 滚动相关明细 | **原生公式**：滚动 60 日 CORREL，与 Python 内核值并排校验 |
| 10 | 多重检验与稳健性 | 自动生成；下半区是历史回看命中率 |
| 11 | 基本面清单 | 把"未取得"改成你实际拿到的口径 |
| 12 | 事件与解释 | 换成你的事件库（日期/事实/来源） |
| 13 | 可比性与稳定性 | 自动生成 |
| 14 | 来源清单 | **每条必须有 标题+URL+日期+用途** |
| 15 | 方法与限制 | 按你的数据源调整限制条款 |

**重算方式**：`08` 与 `09` 两张表里的比价、对数价差、滚动 z、滚动相关全部是原生 Excel 公式
（`LN()` / `AVERAGE()` / `STDEV()` / `CORREL()`），替换价格列即可重算，无需宏、无需插件。

**交叉校验区**：`08` 表底部把 Excel 公式算出的"最新比价 / 最新对数价差 / 全期相关"
与 Python 内核值并列。两边应一致（差异 < 1e-6）；若不一致，说明数据被改动过。

---

## 2. `看板-模板.html`（自包含单文件）

- 单文件嵌入全部数据与脚本（典型 6–7 MB），**双击即可打开，不需要服务器、不需要联网**。
- 六个页面：榜单 / 图谱 / 关系规则 / 历史回看 / 来源 / 方法限制。
- 每个组合有独立研究页（5 个 tab）：概览与判定、价格价差、统计与检验、基本面与事件、可比性与历史回看。
- 图表为纯 canvas 手绘（无 Chart.js 等外链），离网可用。

**怎么改成你的数据**：不要手改 HTML，而是改数据后重新生成：

```bash
python scripts/run_scan.py --data data --out out
python scripts/run_hist.py --data data --out out
python scripts/build_html.py --pack out/scan_pack.json --web out/series_web/web_series.json \
    --hist out/hist_scan.json --out 我的看板.html
```

---

## 3. 生成新模板

若你改了 `build_html.py` / `build_excel.py` 的结构，用真实案例重新导出模板即可：

```bash
python scripts/build_excel.py --pack out/scan_pack.json --hist out/hist_scan.json \
    --out assets/templates/产业链异常背离扫描-模板.xlsx
python scripts/build_html.py --pack out/scan_pack.json --web out/series_web/web_series.json \
    --hist out/hist_scan.json --out assets/templates/看板-模板.html
```
