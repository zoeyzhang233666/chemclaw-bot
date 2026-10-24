# 在各 agent / 各机器上落地

整个 `chem-market-brief/` 目录是一个**自包含单元**：
`SKILL.md` 是给模型看的流程，`references/` 是判断依据，`scripts/` 是生成器，
`examples/` 是可运行的范本。**没有任何 CDN、Node、pandas 依赖**，ECharts 已内联进 HTML。

---

## 一、依赖

| 需要 | 用途 | 没有会怎样 |
|---|---|---|
| Python 3.8+ | 全部脚本 | 只能手工照 `examples/` 抄结构 |
| `openpyxl` | 生成 Excel | `build_xlsx.py` 报错；可 `--html-only` 只出 HTML |
| 网络 | 抓期货序列与现货报价 | 用 `examples/` 已有数据出样品，价格标“未更新至最新” |
| `playwright`（可选） | `qa_render.py` 浏览器实测 | 自动跳过，静态检查仍执行 |

```bash
pip install openpyxl             # 必需
pip install playwright && playwright install chromium   # 可选，做渲染自检
```

ECharts 5.x 已内联在 `scripts/assets/echarts.min.js`，**不需要联网也不需要 CDN**。

---

## 二、安装位置

| 环境 | 放哪里 | 怎么触发 |
|---|---|---|
| DeepSeek Harness / DSH | `~/.agents/skills/chem-market-brief/` | 技能目录自动加载，说“做一份纯碱行情简报”即匹配 |
| Claude Code / Claude 桌面 | `~/.claude/skills/chem-market-brief/` | 同上 |
| Codex / 通用 CLI agent | 仓库内 `skills/chem-market-brief/`，或把 `SKILL.md` 全文贴进系统指令 | 显式说“按 SKILL.md 的六步做” |
| chemclaw / workbuddy 等业务侧 agent | 上传为“知识包 / 自定义指令”，并把 `scripts/` 放进其可执行工作区 | 只要支持 `SKILL.md` 约定就能用 |
| 纯人工使用 | 直接 `cd scripts && python build_all.py …` | 不需要任何 agent |

> 判定标准：**能读工作区文件 + 能跑 Python** 就够了。
> `SKILL.md` 是给模型看的，`scripts/` 是给机器跑的，`references/` 是判断标准。

Windows / macOS / Linux 均可，脚本只用标准库 + openpyxl，路径全部走 `os.path`，
中文文件名已处理（运行时建议 `PYTHONIOENCODING=utf-8`）。

---

## 三、三种用法

### A. 全自动（模型自己研究并生成）

```
用 chem-market-brief 这个 skill，做一份「纯碱 × 华东」的行情简报，基准日今天。
研究完写 research.json，跑 build_all.py，交付 HTML + Excel，并保证 check_html 与 qa_render 全过。
```

模型会按六步走：定口径 → `fetch_futures.py` 抓序列 → 找现货六项口径 → 写 `research.json`
→ `build_all.py` → 自检。**需要它具备 web 搜索/抓取能力**。

### B. 半自动（人给数据，机器出版）

已有 CRM / 日报 / iFinD 导出的团队，把数据填成 `research.json` 后一条命令出版：

```bash
python scripts/validate.py my.json
python scripts/build_all.py my.json --out out --name 烧碱-华东
```

也可以从 Excel 用脚本转成 `research.json`（参考 `soda-ash-quote/to_research.py` 的思路：
一行现货 = 一个 dict，事件/缺口同理）。

### C. 只要结构

复制 `examples/01-soda-ash-national/research.json`，替换全部事实内容；
或复制 `research.template.json`（带注释的空骨架）从零填。

---

## 四、能力缺失时的降级

| 缺少 | 降级方案 |
|---|---|
| 无 `openpyxl` | `build_all.py ... --html-only`，交付单 HTML 并说明 Excel 缺依赖 |
| 无 `playwright` | `--no-render`，静态检查（占位符/外链/禁用词/数字一致）仍全跑 |
| 不能联网 | 用 `examples/02-glass-shahe/` 作模板（它演示了只有部分数据时的完整输出），价格字段标“未更新至最新” |
| 该品种无场内期货 | `research.json` 不填 `futures`，走势/分位/异常三块自动降级为缺口提示 |
| 只有 1 条现货 | 区域价差留空，首屏改显现货点价，摘要只陈述这一条 |
| 三条现货都没有 | 首屏 KPI 明确显示“无现货报价”，全部结论改用期货，并在 `caveats` 声明口径 |
| 数据单位不统一 | 统一折到 `meta.unit`，折算系数写进 `spot.basis` 与 `caveats`（玻璃三种单位就是范例） |
| 不能执行 Python | 直接交付 `examples/` 里的成品让对面参考，或要求对方提供 Python 环境 |

---

## 五、给 agent 的最小提示词

```
读取 chem-market-brief/SKILL.md，按其中「六步」执行。
品种：<品种>   规格：<规格>   重点市场：<地区>   基准日：<YYYY-MM-DD>
硬要求：
1) 不预测涨跌，只陈述已发生的事实；
2) 每个价格数字必须带 规格/地区/含税/日期/来源，缺一项就写进 gaps；
3) 拿不到就写缺口，不要用近似值或行业均值顶替；
4) 最终交付 HTML + Excel，并保证 validate.py、check_html.py、qa_render.py 全部通过。
```

---

## 六、版本与兼容

- `research.json` 是唯一契约；`build/data.json` 是派生物，**不要手改**（下次生成会被覆盖）。
- ECharts 版本 5.x，内联在 `scripts/assets/echarts.min.js`；换版本只需替换该文件后重跑。
- `margins` 支持新写法 `routes:{路线名:毛利}` 与旧写法 `ammonia/hou/natural`，两者可混用。
- 产物文件名由 `--name` 决定，默认 `<品种>-<地区>`；中文文件名在 Windows/macOS/Linux 均可。
- 13 张表的顺序与名称是稳定的，外部脚本可以按表名索引。
