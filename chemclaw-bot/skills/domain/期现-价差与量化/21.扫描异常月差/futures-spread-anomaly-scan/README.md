# 扫描异常月差 · futures-spread-anomaly-scan

把一批化工期货品种的当日期限结构，**逐组合**放进**各自专属**的历史分布里，
找出处在极端分位的位置，并附上解释这个位置的产业面证据。

> 输出的是"哪里不对劲 + 该去查什么"的清单，
> **不是跨期套利建议**。

---

## 快速开始

```bash
# 1. 自检（24 项已知答案）
python scripts/selftest.py

# 2. 一键跑（数据已在 data/raw，276 个逐合约日线）
python scripts/run_pipeline.py --products MA SA PP TA --as-of 2026-10-20 --skip-fetch --outdir build

# 3. 校验产物
node scripts/check_html.js build/dashboard.html
python scripts/verify_excel.py
```

产物：`build/dashboard.html`（交互看板）、`build/异常月差扫描工作簿.xlsx`（11 表 293 公式）。

## 目录

```
SKILL.md                    技能主文档（触发条件、流程、红线）
references/
  01-方法说明.md             月差定义、可比样本、分位、为何如此设计
  02-合约规则对照.md         四品种交易所规则与交割仓单规则
  03-执行手册.md             逐步命令、参数、换品种怎么改
  04-产业面数据源.md         库存/仓单/现货/事件来源与可信度分级
  05-交付检查表.md           交付前逐项打勾
  06-常见错误.md             14 个真实踩过的坑
scripts/
  run_pipeline.py           一键全流程
  fetch_contracts.py        抓逐合约历史日线
  fetch_quotes.py           抓当日行情 + 官方仓单
  scan_spreads.py           规则校验 + 月差 + 分位扫描
  build_html.py             生成交互看板
  build_excel.py            生成工作簿
  spreadlib.py              月差引擎（可比样本/分位/Z/期限结构）
  rule_matcher.py           合约代码解析与组合合法性校验
  selftest.py               24 项已知答案自测
  check_html.js             看板渲染逻辑断言（需 Node）
  verify_excel.py           公式与 Python 侧一致性核对
data/
  raw/                      276 个逐合约日线 CSV（2021-01 ~ 2026-10）
  contract_rules.json       四品种交易所规则（已核验）
  industry_data.json        产业面数据（含日期/来源/可信度）
examples/2026-10-20-化工四品种/
  README.md                 完整案例解读
  化工期货异常月差扫描看板.html
  异常月差扫描工作簿.xlsx
  scan_result.json / quotes_2026-10-20.json / 重点合约当日行情.csv
assets/templates/
  spread-scan-template.html   看板模板
  spread-scan-workbook.xlsx   工作簿模板
```

## 核心设计决策（三条）

### 1. 每个月份组合一个独立分布
SA 1–5 的样本只能和 SA 1–5 的历史比。不同月份组合**绝不合并** ——
比的是完全不同的交割季节性，合并后做出的分位没有经济含义。

### 2. 可比样本 = 同品种 × 同月份组合 × 同剩余期限(整周) × 每年 1 个
剩余期限 `floor((近月交割月结束日 − 观测日).days / 7)` 必须一致。
**每个历史年度只取 1 个样本** —— 早期用 ±N 周窗口会把约 20 个自相关日度点塞进一个年度，
把 N 从 5 虚增到 57，导致 Z 虚高、分位被压缩（详见 `references/06-常见错误.md` 错误 1）。

### 3. 样本不足就不给分位
N < 3 时只报当前月差 + 标"样本不足"。不补数、不插值、不放宽口径凑样本量。

## 红线

1. 不把异常月差当作跨期交易建议
2. 不同月份组合不合并分布
3. 样本不足不硬算分位
4. 不用主力连续合约算月差（换月假跳变）
5. 不插值、不向前填充
6. 月差未扣仓储费/资金成本/交割费/品质与地区升贴水

## 已知局限

- 历史合约仅覆盖近 5 个年度，N 上限 5，分位分辨率有限
- 不同品种月差的绝对元数不可横比，**可比的是分位**
- PP 走东方财富**最新价**口径（大商所官网对脚本返回 412），与 CZCE 结算价口径不同且不混算
- 保证金分级与限仓额度未收录，需查交易所最新公告
