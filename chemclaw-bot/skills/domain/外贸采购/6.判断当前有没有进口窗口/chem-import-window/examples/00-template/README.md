# 示例 00 · 最小模板

复制这个目录，改名，然后把 `data/case.json` 里的占位内容换成你自己的品种即可。

## 三步上手

### 1. 复制目录

```bash
cp -r examples/00-template examples/03-我的品种
```

### 2. 替换占位数据

打开 `data/case.json`，按顺序改这几块：

| 字段 | 改成什么 | 提示 |
|---|---|---|
| `meta.case_id` / `title` | 你的案例名 | —— |
| `asof.date` | 基准日 | 海外价与国内价必须同一天 |
| `product.*` | 品种、CAS、HS 编码、**完整规格** | 规格字符串海外与国内必须完全一致 |
| `request.*` | 海外市场、国内区域、批量、航程 | —— |
| `quote.*` | 报价、**贸易术语**、口径、来源 ID | 必须写清 FOB/CFR/CIF |
| `domestic.*` | 国内价、含税与否、交货方式、来源 ID | 写清"全国均价"还是"区域单点" |
| `fx.*` | 当日汇率 + `rows` 历史汇率 | 历史回算需要逐日汇率 |
| `freight.*` | 运价；**拿不到就保持 none** | FOB 无运费 → 引擎拒绝折算（正确行为） |
| `tax.profiles[]` | 关税、增值税、生效日、**是否已核验** | 没核验就 `provisional: true` |
| `params.*` | 能否抵扣、境内费用 | 没实票就 `null`，不要填 0 |
| `quotes_hist` / `domestic_hist` / `events` | 历史序列与事件 | 没有就留空数组 |
| `sources[]` | 每条都要 URL + **含数字的原文摘录** | `source_id` 必须能对上 |
| `gaps[]` | 每个缺口都要有"补法" | 至少 1 条 |

### 3. 生成与校验

```bash
# 必做：先校验数据契约
node ../../scripts/validate.js data/case.json

# 生成看板
node ../../scripts/build_html.cjs data/case.json out/import-window.html

# 生成 Excel
node -e "const e=require('../../scripts/lib/import-window-engine.js'),fs=require('fs');const a=e.analyze(JSON.parse(fs.readFileSync('data/case.json','utf8')));fs.writeFileSync('out/engine-result.json',JSON.stringify({cif_cny:a.current.totals.cif_cny,duty:a.current.totals.duty,vat:a.current.totals.vat,cost:a.current.totals.net_cost,spread:a.current.spread.abs_cny},null,1))"
python ../../scripts/build_xlsx.py data/case.json out/import-window.xlsx --engine-json out/engine-result.json

# 校验
node ../../scripts/cross_check.js data/case.json
python ../../scripts/check_xlsx.py out/import-window.xlsx --case data/case.json
python ../../scripts/qa_render.py out/import-window.html --case data/case.json
```

## 模板里刻意留空的东西

| 项 | 值 | 为什么 |
|---|---|---|
| `freight.usd_per_ton` | `null` | 模板不知道你的航线运价，不替你猜 |
| `insurance.rate` | `null` | 同上 |
| `params.inland_cost_cny` | `null` | 港杂费用因港口/品类差异大 |
| `sources[].excerpt` | "占位：请粘贴…" | 强制你去原文里找到含数字的那句 |
| `events` | `[]` | 没有事件就留空，页面会显示"暂无" |

## 常见第一次就踩的坑

1. **规格字符串两边写得不一样** → `validate.js` 直接报错。复制粘贴同一个字符串最稳妥。
2. **只填了基准日汇率，没填 `fx.rows`** → 历史点全部 `NO_FX`，画不出曲线。历史序列必须逐日。
3. **FOB 报价没填运费** → 引擎拒绝折算。这是**设计如此**，请补运价而不是把运费写成 0。
4. **把境内费用写成 0** → 价差会虚高 50–120 元/吨。应该写 `null` 并登记缺口。
5. **在正文里写"建议买入"** → `validate.js` 的禁用词扫描会拦下来。
