# two-indicator-correlation ｜ 查两个指标的相关性

面向化工品（及任何成对指标）的**相关性研究**工具包：判断两个指标到底相不相关、在什么条件下相关、什么时候不相关、这个相关可不可信。

## 一句话用法

```bash
python scripts/data_quality.py --csv 你的数据.csv --date-col date --x-col 指标X --y-col 指标Y --out build/qc.json
python scripts/analyze.py --csv 你的数据.csv --date-col date --x-col 指标X --y-col 指标Y \
        --x-form change --y-form pct --windows 12,26,52 --control-col 控制变量 --out build/result.json
python scripts/build_excel.py && python scripts/build_html.py
```

## 交付物

| 交付物 | 位置 | 特点 |
|---|---|---|
| 交互式 HTML 研究报告 | `assets/templates/correlation-report-template.html` | 11 区块；改口径/形态/窗口/起止/离群处理全页实时重算；点滚动曲线看区间明细 + 同期事件 |
| Excel 工作簿 | `assets/templates/two-indicator-correlation-workbook.xlsx` | 14 表；**全部原生公式**，换数据即重算，无宏无加载项 |
| 统计内核 | `scripts/corrlib.py` | 纯标准库：Pearson/Spearman/t分布/Fisher-z/HAC/有效样本量/滚动/偏相关/滞后 |
| 数据质检 | `scripts/data_quality.py` | 8 类检查，ERROR 未清零不许往下走 |
| 主分析 | `scripts/analyze.py` | 一条命令出全量 JSON（总体/滚动/分阶段/敏感性/滞后/伪相关） |
| 自测 | `scripts/selftest.py` | 20 项已知答案校验（t 分布查表、并列秩、去趋势等） |
| 校验 | `scripts/verify_excel.py`、`scripts/js_check.js` | Excel 与 HTML 内嵌内核分别与 Python 逐项对账 |
| 方法文档 | `references/01-方法说明.md` ~ `05-报告写作模板.md` | 方法、公式、伪相关清单、数据源口径、报告话术 |
| 完整案例 | `examples/methanol-inventory-vs-price/` | 甲醇港口库存 × 太仓现货价（DEMO 拟真 + 真实期货数据对照） |

## 核心原则

1. **水平对水平 ≠ 变化对变化**：库存用差分、价格用环比% 作为主口径，水平口径只作背景。
2. **样本不足不算**：滚动窗口有效配对 < 窗口×80% 时输出"样本不足"，绝不插值、不外推。
3. **p 小 ≠ 相关强**：同时报 |r| 档位、95% CI、N。
4. **自相关要修正**：ρ₁ 高时报 N_eff 与修正 p。
5. **相关不是因果**：报告必须声明"共变强度描述，不构成因果判断，不构成交易建议"。

## 环境

- Python 3.9+（标准库即可跑 `analyze.py` / `data_quality.py` / `corrlib.py` / `selftest.py`）
- 生成 Excel 需 `openpyxl`
- 生成 HTML 仅需标准库
- 校验 Excel 用 LibreOffice 重算（可选）

## 完整说明

见 `SKILL.md`。执行时严格按 7 步流程，并逐条对照 `references/03-伪相关检查清单.md`。
