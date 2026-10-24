# UN Comtrade 调用手册

## 接口

公共预览版（无需 key，有配额）：

```
https://comtradeapi.un.org/public/v1/preview/C/A/HS
    ?reporterCode={ISO数字码}
    &period={单个年份}
    &cmdCode={HS六位}
    &flowCode={M|X}
```

完整版（需订阅 key）：`https://comtradeapi.un.org/data/v1/get/C/A/HS`

## 硬性规则

1. **一次一个年份**。`period=2023,2024` 会返回 `Maximum number of periods for preview is 1`。
2. **不传 partnerCode** 即返回全部伙伴国。传 `*` 或 `all` 会返回 `400 Invalid parameter value`。
3. **限速约 1 请求 / 1.5 秒**。超限返回：
   ```json
   {"statusCode":403,"message":"Out of call volume quota. Quota will be replenished in 00:34:29."}
   ```
   此时应等待或减少请求数，不要重试轰炸。
4. 响应中 `data` 为空数组表示该年该国无记录（可能是真无贸易，也可能未报告）。

## 参考数据（必须先取）

```python
# 伙伴国代码表
https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json
# 报告国代码表
https://comtradeapi.un.org/files/v1/app/reference/Reporters.json
```

字段：`id`（数字码）、`text`（英文名）、`PartnerCodeIsoAlpha3`（ISO3）。

**必须用这张表做映射，不要凭记忆。** 典型坑：

| id | text | ISO3 | 备注 |
|---|---|---|---|
| 490 | Other Asia, nes | S19 | 含中国台湾，**不可直接写成"中国台湾"** |
| 344 | Hong Kong SAR | HKG | 转口枢纽 |
| 699 | India | IND | |
| 757 | Switzerland | CHE | |
| 251 | France | FRA | |

## 关键字段

| 字段 | 含义 | 用法 |
|---|---|---|
| `primaryValue` | 贸易额（美元） | 金额 |
| `netWgt` | 净重（kg） | 数量，需 /1000 → 千吨 |
| `qty` | 数量（报告国单位） | 慎用，单位不一致 |
| `qtyUnitAbbr` | 单位 | 用于判断 qty 可否使用 |
| `partnerCode` / `partnerDesc` | 伙伴国 | 映射到 ISO3 |
| `reporterCode` / `reporterDesc` | 报告国 | |

**数量口径经验**：化工品优先用 `netWgt`（单位统一为 kg）。`qty` 常出现桶/升/千克混用，跨年不可比。

## 抓取策略

```
for reporter in [中国, 出口国...]:
    for year in range(2016, 2026):
        for flow in ["M", "X"]:
            fetch()  # 落盘 raw/{reporter}_{flow}.json
            sleep(1.6)
```

- **必须落盘缓存**，同一文件不重复请求
- 403 时把该年标记为 gap，继续下一项
- 结束后统计"成功/缺失"清单，写进数据缺口表

## 镜像核对（核心质检）

进口方与出口方对同一笔贸易的申报必然有差，正常范围 ±20%（CIF vs FOB）。

```python
# 中国自报进口（M）→ 各国对华出口额
cn_imports[partner]
# 出口国自报（X）→ 对中国出口额
exporter_exports[china]

divergence = (cn_imports - exporter_exports) / exporter_exports
```

判读：

| 偏差 | 可能原因 |
|---|---|
| +5% ~ +20% | 正常（CIF 高于 FOB） |
| > +50% | 有转口/转运，或对方统计滞后 |
| < -20% | 中国进口被低报（低报价值/走第三方） |
| 数量偏差 >100% | 对方 netWgt 报告有问题，或转口 |

**每条超限都要进 `checks` 表并写明解释，不能只写"不一致"。**

## 常见数据质量问题

1. **netWgt 为 null**：某年整年缺失（不是零）。必须标注为 gap。
2. **netWgt 为 0 但金额非零**：报告国未报数量。不要当成 0 吨算单价（会除零/无穷大）。
3. **"Rep. of Korea" vs "Other Asia, nes"**：不要合并。
4. **欧盟成员国单独报告**，不是"欧盟"整体；需要整体时必须自己求和并声明。
5. **最近年度为初步数**，会被修订。报告必须写"2025 为初步数"。

## 复用代码骨架

```python
import json, os, time, urllib.request

BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
CACHE = "raw"

def fetch(reporter, year, flow, cmd):
    fn = f"{CACHE}/{reporter}_{flow}.json"
    if os.path.exists(fn):
        return json.load(open(fn, encoding="utf-8"))
    url = f"{BASE}?reporterCode={reporter}&period={year}&cmdCode={cmd}&flowCode={flow}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                d = json.loads(r.read())
            # 追加到缓存文件
            old = json.load(open(fn, encoding="utf-8")) if os.path.exists(fn) else []
            old.extend(d.get("data", []))
            json.dump(old, open(fn, "w", encoding="utf-8"), ensure_ascii=False)
            return d
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if "quota" in body.lower():
                raise RuntimeError(f"quota: {body}")
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed {reporter} {year} {flow}")
```

注意：上面的缓存是"按 reporter+flow 一个文件存多年"，实际实现要按年去重，避免重复追加。
