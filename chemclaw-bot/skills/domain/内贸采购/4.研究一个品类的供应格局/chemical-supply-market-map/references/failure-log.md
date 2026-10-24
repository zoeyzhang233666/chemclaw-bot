# 失败日志（踩过的坑与修法）

按「症状 → 原因 → 修法」记录。遇到报错先搜这里。

---

## 数据类

### 1. 工艺产能之和 ≠ 全国产能
**症状**：`routes` 的 `cap` 加总比 `capacity_total` 多出几十万吨。
**原因**：小路线被重复计入（例如「ADC 副产法」既单列又含在联碱里）。
**修法**：删掉小路线，写进 `routes_note`：「ADC 副产法约 X 万吨，规模小，未单列，已含在…口径中」。
用 `--check` 后手工核对一次加总。

### 2. 样本合计和 metrics 对不上
**症状**：`--check` 警告 `metrics.sample_capacity=3570 与 plants 加总 3560 不一致`。
**原因**：手工填了 `sample_capacity`，后来改了 plants 没同步。
**修法**：删掉 `metrics.sample_capacity`，让脚本自动算（脚本会用 plants 加总填充）。

### 3. 区域合计低于全国，被当成算错
**原因**：样本只覆盖公开披露企业。
**修法**：这**不是错**。在 `basis_notes` 写清「样本合计 X 万吨，占全国 Y%，差额为未披露的中小企业」，
并把「小型企业产能」登记为缺口。

### 4. 省份识别错
**症状**：企业表里出现「未标注」或者省份串了。
**原因**：`province` 写成了「内蒙」「广西壮族自治区」等别名。
**修法**：`_common.PROVINCE_ALIAS` 已覆盖常见别名；仍是「未标注」就在 plants 里补标准省名。

### 5. 经纬度缺失导致地图气泡少
**症状**：`--check` 提示 N 个基地没有经纬度。
**修法**：不要估算坐标。要么补真实坐标（企业官网/环评/地图），要么留着——
报告仍可用，缺口表里会多一条「部分基地经纬度」。

---

## 脚本类

### 6. `JSON 解析失败`
**原因**：手工编辑 JSON 时多了/少了逗号，或用了中文引号。
**修法**：用编辑器校验；`python -c "import json;json.load(open('x.json',encoding='utf-8'))"` 定位。

### 7. `找不到 project.json`
**原因**：`--dir` 指到了产物目录而不是项目目录。
**修法**：`--dir` 必须是包含 `project.json` 的那一层。

### 8. `ModuleNotFoundError: openpyxl`
**原因**：只装了标准库。
**修法**：`pip install -r requirements.txt`；或在无网环境用 `--html-only`，交付说明里写明 Excel 未生成。

### 9. Excel 保存报 `MergedCell ... value is read-only`
**原因**：向已合并区域的非左上角单元格写值。
**修法**：先把整行（含所有列）填好，**最后**再做 `merge_cells`；合计行先着色再写值。

### 10. 图表引用的行列全错
**症状**：图表里出现标题文字或空行。
**原因**：`Reference(min_row=..., max_row=...)` 用了「在写入过程中变化的变量」。
**修法**：先用变量把 `first_row`/`last_row` 固定下来，再创建图表；`add_data` 的 `min_col` 要指向真正的数值列。

### 11. `TypeError: unhashable type: 'StyleProxy'`
**原因**：`cell.font = cell.font`（把自己赋值给自己）。
**修法**：`cell.font = Font(name=..., size=..., bold=..., color=...)` 新建一个。

### 12. LibreOffice 重算输出 `EEXIST`
**原因**：输出文件已存在。
**修法**：换一个新文件名（`recalc_v2.xlsx`），重算成功后再覆盖最终交付物。

### 13. 沙箱里 LibreOffice / Chrome 起不来（`spawn EPERM` / `OpenProcess 拒绝访问`）
**原因**：受限沙箱不允许子进程管道与进程句柄。
**修法**：需要放宽执行权限再重试；若环境不允许，跳过重算与截图，靠 `check_project.py` 的结构检查兜底，
并在交付说明里写明「公式未重算验证」。

### 14. PowerShell 里 `python - <<'PY'` 不work
**原因**：PowerShell 没有 heredoc。
**修法**：用 `python -c "..."`（注意引号嵌套）或写成 `.py` 脚本文件再执行。

---

## 呈现类

### 15. HTML 打开是空白
**原因**：`window.DATA` 注入失败（JSON 里有非法字符）或 JS 报错。
**修法**：`check_project.py` 会检查 `window.DATA` 是否存在；再用浏览器控制台看报错。
`data_bundle.json` 可以用 `json.load` 单独验证。

### 16. 中文乱码
**原因**：缺 `<meta charset="utf-8">` 或文件不是 UTF-8 保存。
**修法**：模板已带；Windows 下写文件务必 `encoding="utf-8"`。

### 17. 打印 PDF 只有一页
**原因**：`@media print` 没展开其他标签页。
**修法**：样式里已有 `.tab-panel{display:block!important}`；若自定义样式覆盖了，注意优先级。

### 18. 页面能滚但内容重叠 / 溢出
**原因**：自定义卡片宽度写死。
**修法**：用 `grid-template-columns: repeat(auto-fit, minmax(Npx,1fr))`；`check_project.py` 之外可用
`ui_check.py` 的溢出检查思路（Playwright 里比 `scrollWidth` 与 `clientWidth`）。

---

## 判断类（最容易错，不是脚本问题）

### 19. 把峰值当年度均价
2021 年峰值 3,681 元/吨是 10 月单点，年均要看 2022 年的 2,859。价格表里 `avg` 与 `high` 必须分列。

### 20. 把毛产能当净增
搬迁/置换项目必须扣 `capacity_retired`。无法确认就 `net: null`，显示「待确认」。

### 21. CR5 分母用错
分母必须与分子同口径。样本 CR5 的分母是样本合计，不是全国产能。

### 22. 用「CR5 不高」得出「供应安全」
要看**低成本量**的集中度（工艺/子市场 HHI）。整体 CR5 45% 的品种，最便宜那段可能 CR1 = 70%。

### 23. 折百没折
液碱 32% 的「1 吨」与片碱 99% 的「1 吨」不是一回事；合同与测算统一折算 100%。

### 24. 用产能直接乘开工率当可售量
可售量还要扣自用、长约锁定、出口订单、检修。报告中写「名义产能 / 产量 / 可售量」三层，
拿不到可售量就写「数据缺口」。
