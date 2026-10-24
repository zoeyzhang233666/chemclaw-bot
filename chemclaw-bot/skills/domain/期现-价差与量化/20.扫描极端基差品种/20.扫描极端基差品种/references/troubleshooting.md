# 故障排查

## 抓取层

### 只拿到 636 字节的「正在进行安全检查」

100ppi 的 JS 挑战页。`http.py` 本应自动处理：

```python
m = re.search(r'var _0x2\s*=\s*"([0-9a-fA-F]+)"', text)
if m:  # 带 HW_CHECK cookie 重发
    headers['Cookie'] = 'HW_CHECK=' + m.group(1)
```

若仍失败：
- 确认 `retries` ≥ 6（挑战需要几次往返）
- 确认请求间隔 `sleep` ≥ 0.3，过快会连续触发挑战
- 手动在浏览器打开一次该栏目，观察是否整站限流

### 详情页 404

**同一 URL 重试通常就成功**（实测 404 率约 3–5%）。
`Http.get` 对 404 返回 `None` 且**不写缓存**，所以重跑会自动重试。
不要因为一次 404 就判定该品种无数据。

### 栏目页返回空 / 页数比预期少

`n_pages()` 逐页探测，遇到空页即停。若某品种只有 5 页而别家有 10 页，
通常是该商品本身文章少（如乙二醇、苯乙烯每页仅 10 条），不是故障。

### 抓取很慢

期货：每品种约 90–108 个合约 × 0.3 秒 ≈ 20–130 秒（有缓存时 <1 秒）。
现货：每篇基差稿都要抓详情页，约 150 篇/品种 ≈ 3–6 分钟。

**提速办法：分品种并行跑多个进程**（不同品种互不冲突）：
```bash
python -m basis_scan.fetch_spot --codes MA,SA,V,PP --max-pages 12 ... &
python -m basis_scan.fetch_spot --codes L,TA,EG,UR   --max-pages 12 ... &
```
实测并行 3 个进程可把总时间从 ~25 分钟压到 ~8 分钟。

## 计算层

### 某品种交叉校验通过率很低（<95%）

按顺序排查：

1. **单位系数错了** —— 最可能。看 `spot_unit_basis` 字段是否显示"由源站换算式反解"。
   如果显示"品种池声明"，说明没取到换算式，系数可能是错的。
   → 重新抓该品种：`--codes XX`（早期抓的 CSV 可能缺 `unit_divisor` 列）
2. **日期没对齐** —— 现货与期货必须同日。
3. **合约不同源** —— 源站稿写的主力合约 vs 我方 `argmax(oi)` 可能不一致。
   看 `fut_src_check` 字段的 `n/m` 比值。

### 基差数量级明显不对（如玻璃 −607）

单位没换算。玻璃现货 元/平方米，期货 元/吨，相差 80 倍。
检查 `spot_to_fut_factor` 是否为 80 而不是 1。

### 某品种被判「数据不足」但其实有数据

看 `n_obs` 与 `--min-obs`。若 n 略低于 120（如乙二醇 118、PTA 96），
说明该品种在栏目窗口内的文章确实少。三个选择：
- 放宽 `--min-obs`（会降低统计稳健性，需在报告里说明）
- 用 `archive.py` 持续归档，等样本够了再扫
- 就承认它扫不了，写进「无法扫描」清单

### 分位显示 100% 但没有历史最高

用错口径。严格分位最大值是 `(n−1)/n`，不会是 100%；含当日分位才会到 100%。
极端判定统一用中位秩，三个值都要报。

## 交付层

### HTML 打开是空白

检查是否还有未替换的占位符：
```bash
grep -c '__DATA__' out/极端基差扫描看板.html   # 应为 0
```
若 ECharts 没内嵌，`/*__ECHARTS__*/` 会残留 → 检查 `assets/echarts.min.js` 是否存在。

### HTML 有外链

```bash
grep -o 'src="http[^"]*"' out/极端基差扫描看板.html   # 应为空
```
必须完全离线可用。

### Excel 打开报错

用官方检查器：
```bash
python <office-skills>/scripts/check_office.py out/xxx.xlsx --out checks.json --count 13
```
常见原因：合并单元格与写入单元格重叠、sheet 名超过 31 字符或含非法字符。

### HTML 与 Excel 数字不一致

两者必须都从 `out/scan_result.json` 渲染。
如果手工改过其中一边，或 `scan.py` 跑完没重新生成另一个，就会出现不一致。
重跑顺序：`scan.py` → `make_html.py` → `make_xlsx.py`。

## 环境

### `ModuleNotFoundError: No module named 'basis_scan'`

```bash
export PYTHONPATH=$PWD/src        # Windows: $env:PYTHONPATH="$PWD\src"
```

### `unsupported format character 't'` 

URL 里的 `%20` 与 Python `%` 格式化冲突。用字符串拼接或 `.replace()`，不要用 `%` 格式化含 `%20` 的 URL。

### Windows 控制台中文乱码

```bash
python -X utf8 -m basis_scan.scan ...     # 加 -X utf8
```
并在脚本里 `sys.stdout.reconfigure(encoding='utf-8')`。
