# region-industry-map

看一个区域某品种的产业格局：谁在生产、装置在哪、产能多少、上下游怎么走、有没有新项目、各地价格为什么不一样。

产出一份**离线可开的交互地图 HTML** 和一本**14 表 Excel 数据包**，所有数字都带来源编号，所有缺失都标成缺口而不是估算。

---

## 30 秒上手

```bash
cd scripts

# 1) 校验数据（error 阻断）
python validate.py ../examples/01-shandong-soda-ash/regions.json

# 2) 生成 HTML + Excel + 截图体检
python build_all.py ../examples/01-shandong-soda-ash/regions.json \
  --out ../out --name 山东纯碱 --qa --shot ../out/qa/shot.png

# 3) 改过脚本模板后，先跑自检再交付
python selftest.py
```

产物：

```
out/山东纯碱产业格局地图.html   ~1.4 MB，双击即开，断网可用
out/山东纯碱产业格局数据包.xlsx  14 张表
out/qa/shot.png                 真浏览器截图
```

---

## 目录

```
region-industry-map/
├── SKILL.md                                    技能入口（八问 → 字段 → 脚本）
├── README.md                                   本文件
├── references/
│   ├── geo-verification-and-aggregation.md     地理数据核验与聚合规则（必读）
│   ├── data-contract.md                        regions.json 字段全表
│   ├── source-playbook.md                      取证通道与口径陷阱
│   ├── evidence-grading.md                     A/B/C/D 分级与五道门禁
│   ├── design-system.md                        HTML/Excel 视觉与交互规范
│   └── qa-checklist.md                         交付前检查清单
├── scripts/
│   ├── common.py          枚举、归一化、聚合（CR/HHI/覆盖率/净增量）
│   ├── validate.py        五道门禁
│   ├── build_html.py      regions.json → 单文件 HTML
│   ├── build_xlsx.py      regions.json → 14 表工作簿
│   ├── build_all.py       一条命令跑完
│   ├── qa.py              真浏览器渲染 + Excel 交叉核对
│   ├── selftest.py        自检（含两条负向门禁测试）
│   ├── package.py         打 ZIP 分发
│   ├── templates/report.html
│   └── assets/            echarts.min.js、china_prov.json（离线内联）
└── examples/
    └── 01-shandong-soda-ash/                  山东纯碱完整工作示例（含成品）
```

---

## 数据流

```
研究（取证）  →  regions.json  →  ┌→ HTML
                                └→ Excel
                        （同一份数据，qa.py 交叉核对两边数字一致）
```

`regions.json` 是**唯一真源**。改数字只改 JSON，然后重新构建——HTML 与 Excel 里从不手改。

---

## 四条硬规则

1. **注册地址 ≠ 装置位置。** 注册地只用于确认法人，装置位置只认生产地址/园区位置。
2. **企业 ≠ 厂区。** 一个集团多厂区分行列示；集团总部不是一个厂。
3. **产能 ≠ 产量 ≠ 可售量。** 数字必带口径；两个口径冲突时并列，不取平均。
4. **缺就写缺。** 没查到的明确标"未取得"并写进缺口表（附补齐路径），绝不假设填补。

这四条由 `validate.py` 的地址门 / 口径门 / 缺口门 / 来源门机械把关。

---

## 换品种 / 换区域

只换 `regions.json`。脚本、模板、样式、图例、聚合规则都不用动。

两个注意点：

- `scripts/common.py` 的 `PROCESSES` 是纯碱的工艺枚举（氨碱/联碱/天然碱/其他/未知），换品种先改这一行；
- 价格单位、产能单位写在 `meta` 里，模板会跟着变。

---

## 为什么是这两个交付物

| 文件 | 谁用 | 干什么 |
|---|---|---|
| HTML | 决策者 / 汇报 | 一眼看出产业落在哪、点开看是谁、切换度量看结构 |
| Excel | 分析师 / 复核 | 一行一厂区地核数、按列筛选、把来源一条条点开 |

HTML 负责"看懂"，Excel 负责"可核"。两个都要，缺一个就会有人不信。

---

## 许可

MIT。`assets/` 内的 ECharts（Apache-2.0）与省界 GeoJSON（源自公开行政区划数据）随技能分发，供离线使用。
