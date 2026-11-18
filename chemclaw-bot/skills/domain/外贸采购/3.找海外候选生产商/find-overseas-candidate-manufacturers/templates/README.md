# 模板说明（templates/）

| 文件 | 用途 | 用法 |
|---|---|---|
| `case_input.template.json` | 案例输入（采购口径） | 复制为 `examples/<案例>/case_input.json`，填写产品/国家/规格 |
| `case_output.template.json` | 案例输出（数据契约） | 复制为 `examples/<案例>/case_output.json`，按字段填写证据 |
| `report_template.html` | HTML 报告模板 | **由 `scripts/build_report.py` 自动生成**，无需手改。它=「用一份真实数据渲染出来的成品骨架」，换 `case_output.json` 即得新报告 |
| `workbook_template.xlsx` | Excel 工作簿模板 | **由 `scripts/build_workbook.py` 自动生成**，含 12 个工作表与空白候选录入模板 |

## 为什么模板是"渲染产物"而不是"空白骨架"

手写一份带 10 家企业、27 条问题、28 个来源的空白 HTML，很快会与 `case_output.json` 脱节。因此本 Skill 的策略是：

```
case_output.json  ──build_report.py──▶  report.html
                  ──build_workbook.py──▶ workbook.xlsx
```

模板文件就是这条流水线的输出，**保证格式一致、可复现**。若要调整版式（配色、章节顺序、新增筛选），只改 `scripts/build_report.py` 里的 CSS/模板字符串，然后重跑即可，所有案例同步生效。

## 生成命令

```bash
# HTML 报告
python scripts/build_report.py examples/A_saudi_meg/case_output.json out/report.html

# Excel 工作簿
python scripts/build_workbook.py examples/A_saudi_meg/case_output.json out/workbook.xlsx

# 交付前自检
python scripts/self_check.py examples/A_saudi_meg/case_output.json
```

## 依赖

- Python 3.9+
- `openpyxl`（仅 workbook 需要）
- 无网络依赖（报告为单文件离线 HTML）
