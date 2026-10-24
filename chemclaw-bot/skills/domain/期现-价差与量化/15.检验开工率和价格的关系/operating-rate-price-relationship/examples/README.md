# 示例索引

| 示例 | 品种 | 结论类型 | 演示了什么 |
|---|---|---|---|
| [pvc-caulking-utilization](pvc-caulking-utilization/README.md) | PVC（电石法 / 乙烯法） | **数据不足，不可检验** | 公开开工率只有 7 周时，如何诚实地量化"能检出多大效应"而不是编造相关系数 |

## 为什么把"失败"的案例当主案例

多数 Skill 的示例都是"成功"的：数据齐、结论显著、图表好看。
但开工率研究最常见的真实情形恰恰相反——**公开数据根本不够**。

PVC 案例演示的是本 Skill 最难也最有价值的部分：

1. 只用 7 期真实公开数据（隆众资讯周报，经 Mysteel 转载），每期都有原文链接
2. 不插值、不用产量倒推、不做图表数字化
3. 算出每个单元的最小可检测效应（MDES 1.14–3.96 个标准差）
4. 结论直说「7 期数据只能检出巨幅效应；任何温和效应都不可检验」
5. 报告里同时写出「要多少期才够」——答案是约 197 个有效样本

## 复现

```bash
cd examples/pvc-caulking-utilization
python ../../scripts/pipeline.py --self-test          # 三组合成数据自检
python ../../scripts/pipeline.py --config config.json # 跑 PVC 案例
python ../../scripts/build_outputs.py output narrative.json
node ../../scripts/check_report.js output/报告.html
python ../../scripts/float_numbers.py                 # 必须 exit 0
```

## 换成自己的品种

1. 复制 `pvc-caulking-utilization/` 为 `my-product/`
2. 改 `config.json`：`util_csv`、`value_col`、`horizons`、`level_bands`、`chg_threshold_pp`
3. 按 `references/01`、`02` 的口径准备 `data/util_weekly.csv`（字段见 01 文档 §2）
4. 按需改 `narrative.json` 的文案字段
5. 跑上面四条命令

**不需要改任何 `.py` 文件**——阈值、窗口、分组规则全部由 config 驱动。
