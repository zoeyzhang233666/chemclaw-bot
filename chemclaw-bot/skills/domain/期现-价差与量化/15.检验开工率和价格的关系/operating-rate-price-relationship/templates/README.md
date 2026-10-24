# templates 说明

| 文件 | 用途 |
|---|---|
| `config_template.json` | 参数模板。复制到新案例目录后只需改 5 个字段 |
| `report_template_pvc_case.html` | 交互式报告模板（由 `build_outputs.py` 从真实数据渲染，可作视觉基准） |
| `workbook_template_pvc_case.xlsx` | 14 表工作簿模板（同上） |

## config.json 最少要改的字段

```jsonc
{
  "util_csv":  "data/util_weekly.csv",   // 开工率序列
  "value_col": "util_total",             // 用哪一列作主指标
  "horizons":  {"1w": 5, "2w": 10, "4w": 20},
  "level_bands": [65, 70, 75],           // 绝对水平切点
  "chg_threshold_pp": 1.0,               // 周变化阈值（百分点）
  "min_history_periods": 52,             // 分位最少历史
  "min_n_eff": 30                        // 低于此判 insufficient
}
```

## 关于"不要寻优"

`level_bands` 与 `chg_threshold_pp` 必须**在跑结果之前定好并锁定**。

定阈值的合法依据（按优先级）：
1. 产业盈亏平衡对应的开工水平
2. 近 3 年分布的 25/50/75 分位（四舍五入到整数）
3. 行业报告常用分档

**不合法**：跑一遍看哪组差异大就用哪组。

## 模板与示例的区别

- `examples/` 是**可复现的完整案例**（含数据、产出、一键脚本）
- `templates/` 只是**视觉与结构基准**，不含数据依赖

如需新的报告样式，改 `scripts/build_outputs.py` 里的 `HTML_TPL` 与 `build_workbook()`，
然后用 `node scripts/check_report.js` 验证输出仍然自洽。
