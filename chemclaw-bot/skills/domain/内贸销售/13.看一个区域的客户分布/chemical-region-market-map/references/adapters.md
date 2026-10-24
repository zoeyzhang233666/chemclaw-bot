# 在各 agent / 各机器上落地

整个 `chemical-region-market-map/` 目录是一个**自包含单元**：`SKILL.md` 是入口说明，`scripts/` 是生成器，`assets/` 自带离线资源，`examples/` 是范本。

## 一、依赖

| 需要 | 说明 |
|---|---|
| Python 3.8+ | 生成器与校验器 |
| `openpyxl` | 生成 Excel。`pip install openpyxl` |
| 浏览器（可选） | `qa.py` 用 headless Chrome/Edge 做渲染核对；没有则退化为静态检查 |
| 网络 | **仅**首次补资源时需要（`scripts/assets/` 已内置，通常不需要） |

不需要 Node、不需要 pandas、不需要联网 CDN——ECharts 与省界 GeoJSON 已内联进 HTML。

## 二、安装位置

| 环境 | 放哪里 | 怎么触发 |
|---|---|---|
| Claude Code / Claude 桌面 | `~/.claude/skills/chemical-region-market-map/` | 说"做一张纯碱华东的区域市场地图"即自动匹配 |
| 项目级（任意 agent） | 仓库内 `skills/chemical-region-market-map/` | 在该项目里工作时读取 |
| Codex / 通用 CLI agent | 同上，或把 `SKILL.md` 全文粘进系统指令，目录挂到工作区 | 显式说"按 SKILL.md 的流程做" |
| DeepSeek Harness | `~/.agents/skills/chemical-region-market-map/` | 技能目录自动加载 |
| chemclaw / workbuddy 等业务侧 agent | 上传为"知识包/自定义指令"，或把脚本目录放进其工作区 | 一般支持 `SKILL.md` 约定的都能直接用 |

> 判定标准：只要该 agent 能读工作区文件、能执行 Python，就能用；`SKILL.md` 是给模型看的，`scripts/` 是给机器跑的。

## 三、三种使用姿势

**A. 全自动（模型自己研究）**
```
用 chemical-region-market-map 这个 skill，做 钛白粉 × 华南 的区域市场地图。
研究完写 data.json，跑 build_all.py 和 qa.py，交付 HTML + Excel。
```
模型会按 SKILL.md 的六问去取证、写 JSON、生成并自检。需要它具备 web 搜索/抓取能力。

**B. 半自动（人给数据，机器出图）**
```bash
python scripts/validate.py my.json
python scripts/build_all.py my.json --out out --name 钛白粉-华南
python scripts/qa.py my.json "out/钛白粉-华南区域市场地图.html" "out/钛白粉-华南客户分布与走访优先级.xlsx"
```
适合已有 CRM/名录数据的团队，JSON 可以从 Excel 用脚本转。

**C. 只要模板**
把 `examples/02-skeleton-toy-region/data.json` 复制成自己的，替换 `cities/lanes/companies/projects/prices/route/narrative`，删掉所有「占位」字样。

## 四、能力缺失时的降级

| 缺少 | 降级方案 |
|---|---|
| 不能用 headless 浏览器 | `qa.py` 自动跳过渲染检查，仍做占位符/数据注入/Excel 结构检查 |
| 不能执行 Python | 直接交付 `examples/01` 的 `data.json` 让对面的 agent 自己生成；或要求对方提供 Python 环境 |
| 不能联网 | 用 `examples/01/data.json` 的结构 + 本地已有资料填；价格与项目字段标注为"未更新至最新" |
| 没有中文输入 | 全部字段支持英文值；`demand_label` 可写 `consumption`，页面会照常渲染 |

## 五、给 agent 的最小提示词

```
读取 chemical-region-market-map/SKILL.md，按其中「三步走」执行。
产品：<产品>  区域：<区域>  截止日：<YYYY-MM-DD>
要求：数据不足的字段标注估算/未核实，不要编企业名；
最终交付 HTML + Excel，并跑 qa.py 通过。
```

## 六、版本与兼容

- `data.json` 是唯一契约；旧数据只需补 `meta.demand_label`、`narrative` 等字段即可升级。
- 图表依赖 ECharts 5.5.1（已内联）；若要换新版，替换 `scripts/assets/echarts.min.js` 后重跑即可。
- 省界 GeoJSON 约 570 KB；若目标区域含港澳台，注意 `china_prov.json` 的行政区名映射（页面里会去掉"省/市"后缀再匹配）。
