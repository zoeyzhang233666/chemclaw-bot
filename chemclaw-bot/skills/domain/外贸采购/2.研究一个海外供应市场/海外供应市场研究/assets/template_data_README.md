# 数据模板：`template_data.json` 使用说明

`template_data.json` 是**空白骨架**：所有必填字段都在，数值用 `0 / "" / []` 占位，并带 `_comment` 提示。
适合开始一个全新国家/产品时，直接拷进 `examples/<国家>-<产品>/data.json` 再逐块填。

## 使用顺序（建议）

1. `meta` —— 先定国家、产品、HS、基准日
2. `sources` —— 边查边记，每条都写 `note`（摘录 + 口径）
3. `sites` —— 工业城/园区 + 经纬度 + `coast`
4. `companies` —— 先分三类（集团/生产法人/无该产品）
5. `plants` —— **逐套装置**，产能口径与证据等级必填
6. `trade` —— WITS 抓取后填 `by_year`，再填 `partners_*`
7. `logistics` / `policy` / `events` / `risks`
8. `unverified` / `next_steps` —— 最后写，把"不能填的数"在这里交代清楚

## 校验

```bash
python scripts/build_html.py examples/<实例>/data.json assets/report_template.html out/报告.html
```

脚本会检查：必填顶层字段、装置必填字段、`site` 是否存在于 `sites`、来源引用是否有效。

## 占位符约定

| 写法 | 含义 |
|---|---|
| `0` | 数值待填（会被脚本当作真实值，**填完再生成**） |
| `""` | 文本待填 |
| `[]` | 列表待填 |
| `"_comment"` | 提示字段，生成前可保留（HTML 不渲染它） |
