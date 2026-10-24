# basis-term-structure-research · 看当前基差强不强

面向化工品期现价差的可复用研究 Skill。回答一个问题：**当前基差处于什么历史位置、近期为什么变化、
有哪些基本面数据支持或不支持。**

## 它解决什么

同一个"基差"，能算出 +823、+596、+1,100 三个数，全都没错——因为合约、地区、口径不同。
本 Skill 的价值在于：**先把口径钉死，再报数字；样本不够就拒绝给分位；极端分位不等于必然回归。**

## 目录

```
SKILL.md                     技能主文件（流程、红线、交付物）
references/
  01-口径核查清单.md          六项口径 + 四项可比性核查（第一道闸门）
  02-公式与统计口径.md        基差/基差率/归因/分位/复权 全部公式
  03-合约换月与连续序列.md    gap vs shift、复权符号陷阱、验证方法
  04-数据源与口径清单.md      免费数据源、解析要点、已知不可用来源
  05-报告写作模板.md          页面骨架、结论模板、写作禁忌、自检清单
scripts/
  basislib.py                 纯标准库内核（基差/统计/换月/复权/充分性）
  calc_basis.py               命令行：输入 CSV → 输出 JSON
  selftest.py                 47 项已知答案自测
  build_report.py             生成交互式 HTML（纯内联 SVG + JS，无 CDN）
  build_workbook.py           生成 14 表 Excel（原生公式）
examples/methanol-taichen-ma/
  README.md                   完整真实案例复盘（含踩坑记录）
  basis-report.html           交互式报告（可直接打开）
  basis-workbook.xlsx         14 表工作簿
  basis.json                  calc_basis.py 的真实输出
  data/                       原始数据（现货/期货/仓单/库存/事件/来源）
assets/templates/
  basis-report-template.html  报告模板
  basis-workbook-template.xlsx 工作簿模板
工作区/说明.txt                输入输出目录约定与三条命令
```

## 三条命令

```bash
# 1) 算基差（品种无关，替换 CSV 即可）
python scripts/calc_basis.py --spot data/spot.csv --futures data/futures.csv \
    --asof 2026-10-20 --dates 2026-09-21,2026-10-09 --windows 1y,3y,5y --out build/basis.json

# 2) 出报告
python scripts/build_report.py --analysis build/analysis.json --out out/report.html

# 3) 自检
python scripts/selftest.py
```

## 依赖

- `basislib.py` / `calc_basis.py` / `selftest.py`：**仅标准库**
- `build_workbook.py`：`openpyxl`
- `build_report.py`：标准库

## 核心结论（来自真实案例，甲醇 2026-10-20）

| 项 | 值 |
|---|---|
| 现货（太仓出罐含税） | 3,980 |
| 期货 MA2701 收盘 | 3,157 |
| **基差** | **+823（基差率 20.68%）** |
| 近月 MA2611 基差 | +596（同一现货，差 227 元/吨） |
| 近 23 个交易日变化 | −170（期货主导） |
| 峰值以来 | −714（现货补跌主导） |
| 1/3/5 年历史分位 | **不可计算**（真实样本仅 13 个） |

## 红线

- 不因极端分位就断言回归
- 不拼接不可比合约
- 样本不足不给分位
- 不插值、不补数、不混算口径
- 基本面证据必须两边都列
