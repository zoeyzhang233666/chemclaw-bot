# 模板说明

| 文件 | 用途 | 怎么用 |
|---|---|---|
| `events-template.csv` | 事件表模板（含 8 条真实示例 + 2 条反面样例） | 复制到你的项目根目录改名为 `events.csv`，替换成你的事件；列名不要改 |
| `project-template.json` | 项目口径配置 | 复制为 `project.json`，改 `slug`/`title`/`product`/阈值 |

## 新建项目最快路径

```bash
mkdir my-product-study && cd my-product-study
mkdir -p data output
cp <skill>/assets/templates/events-template.csv ./events.csv
cp <skill>/assets/templates/project-template.json ./project.json
# 编辑 events.csv / project.json 后：
python <skill>/scripts/build_event_table.py --project . --out output/事件样本确认表.html
python <skill>/scripts/build_all.py . --benchmark market_model
```

## events.csv 必须保留的列

`event_id, event_name, company, unit_name, product, capacity_wt, region, country, event_type,
announce_date, first_market_date, actual_start_date, actual_restart_date, duration_days,
in_comparison_set, include_flag, screening_reason, evidence_grade, product_verified,
source_title, source_media, source_url, quote, notes`

缺列会导致 `build_all.py` 校验失败。中文表头也可识别（见 `core.py` 的 `COLUMN_ALIASES`）。

## 注意

- `capacity_wt` 是**单套**产能（万吨/年），不是集团合计；
- `quote` 必须能在 `source_url` 里逐字搜到；
- `product_verified=否` 的行会进样本表但被排除出可比集（用于展示剔除理由）。
