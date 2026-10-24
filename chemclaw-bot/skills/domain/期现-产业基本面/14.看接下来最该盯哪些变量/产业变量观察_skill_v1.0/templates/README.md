# templates 说明

| 文件 | 用途 | 怎么用 |
|---|---|---|
| `payload_template.py` | **空白数据契约模板** — 换品种时的起点 | 复制 → 填空 → `make.py` |
| `workbook_template.xlsx` | 8 sheet 空白工作簿（全部"数据缺失"） | 看结构长什么样；也可直接手工填 |
| `template_demo_index.html` | 上一份空白工作簿对应的 HTML 看板 | 看模板页面长什么样 |
| `dashboard_template.html` | 甲醇完整案例的看板副本 | 看**填满后**的样子（推荐先看这个） |
| `case_template.xlsx` | 甲醇完整案例的工作簿副本 | 看填满后的 Excel |

## 建议顺序

1. 先打开 **`dashboard_template.html`**（甲醇完整案例）——看清成品应该是什么信息密度
2. 再打开 **`case_template.xlsx`**——看 8 个 sheet 各自装什么
3. 然后打开 **`template_demo_index.html`** 和 **`workbook_template.xlsx`**——这是你要填的空白版
4. 最后复制 **`payload_template.py`** 开始填

## 关于"数据缺失"

空白模板里所有数值都写 `数据缺失`，这是**故意的**——它示范了本框架的规矩：

> 拿不到就明确写"数据缺失"，绝不臆造。

填空过程中如果某项暂时拿不到，**保持 `数据缺失` 并登记到 `GAPS`**，不要用估计值填补。
正式交付时，`数据缺失` 只应出现在"确实不可得且已登记"的项目上。

## 重新生成模板

若修改了渲染器，重新生成模板以保持一致：

```bash
python scripts/gen_templates.py
```
