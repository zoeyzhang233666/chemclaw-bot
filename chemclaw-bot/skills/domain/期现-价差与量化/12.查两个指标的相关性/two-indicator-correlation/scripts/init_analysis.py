# -*- coding: utf-8 -*-
"""按 SKILL.md 的 7 步流程启动一次新分析（生成输入模板与可执行命令清单）。

用法：
  python scripts/init_analysis.py --product 甲醇 --dir D:\\工作\\corr_methanol
"""
import argparse
import os

CSV_TMPL = """date,inventory,price,coal
2024-01-03,62.5,2480,780
2024-01-10,64.1,2455,778
2024-01-17,,2450,775
"""

README = """# 相关性分析工作区：{product}

## 1. 填数据
把真实历史序列填入 `csv/{product}_weekly.csv`（列名保持 date / inventory / price / coal）。
- 缺失：留空，**不要**插值、不要填 0、不要"按趋势估计"。
- 若价格不是观测日当天的报价，请新增一列 `price_date` 记录实际使用日期。

## 2. 填口径
打开 `口径与来源.md`，逐项填写后**再**开始分析。

## 3. 跑质检
```
python ../scripts/data_quality.py --csv csv/{product}_weekly.csv --date-col date \\
    --x-col inventory --y-col price --x-name 库存 --y-name 价格 --freq 7 --out out/qc.json
```
ERROR 清零后再进入下一步。

## 4. 跑分析（主口径：库存差分 × 价格环比%）
```
python ../scripts/analyze.py --csv csv/{product}_weekly.csv --date-col date \\
    --x-col inventory --y-col price --x-form change --y-form pct \\
    --windows 12,26,52 --control-col coal --out out/result.json
```

## 5. 出交付物
```
python ../scripts/build_excel.py
python ../scripts/build_html.py
```

## 6. 对照检查清单
逐条打勾 `../references/03-伪相关检查清单.md`。

## 7. 写报告
按 `../references/05-报告写作模板.md` 的 8 段结构写，结论必须带（口径, 形态, 时间段, N, p）。
"""

QD_TMPL = """# 口径与来源（必须逐项填全）

| 项目 | 指标 X（库存） | 指标 Y（价格） |
|---|---|---|
| 指标全称 |  |  |
| 单位 |  |  |
| 频率 |  |  |
| 统计区域/样本 |  |  |
| 发布时点 |  |  |
| 数据来源与链接 |  |  |
| 口径断点（何时换过样本/方法） |  |  |
| 已知偏差 |  |  |

## 对齐规则
- 库存调查日：____（星期几）
- 价格取哪天：____（调查日当天 / 次日 / 周均价）
- 节假日与停报处理：____
- 缺失期数：____  缺失原因：____

## 数据状态
〔真实数据 / 客户提供 / 演示拟真〕——请删除不适用的项。
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--product', default='甲醇')
    ap.add_argument('--dir', default='.')
    a = ap.parse_args()
    base = os.path.abspath(a.dir)
    for sub in ('csv', 'out', 'events'):
        os.makedirs(os.path.join(base, sub), exist_ok=True)
    p = os.path.join(base, 'csv', f'{a.product}_weekly.csv')
    if not os.path.exists(p):
        open(p, 'w', encoding='utf-8-sig').write(CSV_TMPL)
    open(os.path.join(base, 'README.md'), 'w', encoding='utf-8').write(README.format(product=a.product))
    open(os.path.join(base, '口径与来源.md'), 'w', encoding='utf-8').write(QD_TMPL)
    print('工作区已创建:', base)
    print('  下一步：1) 填 csv/%s_weekly.csv  2) 填 口径与来源.md  3) 跑 data_quality.py' % a.product)


if __name__ == '__main__':
    main()
