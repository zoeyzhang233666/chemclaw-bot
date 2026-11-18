# 产业研究晨报生成器

把某个交易日的新增变化，整理成一份可以直接发出去的**多品种产业晨报**：
一份离线互动 HTML + 一份逐格可追溯的 Excel。

适用于期现研究、产业基本面跟踪、晨会材料。

---

## 先看效果

打开 `examples/01-ma-pp-pvc-2026-10-20/output/` 里的两个文件，这是用真实数据跑出来的完整案例（甲醇 / PP / PVC，2026-10-20）：

- `甲醇-PP-PVC_产业研究晨报_2026-10-20.html` —— 双击打开，单文件、可断网
- `甲醇-PP-PVC_产业研究晨报_2026-10-20.xlsx` —— 12 张表

页面里能做的事：

| 操作 | 得到什么 |
|---|---|
| 看首屏 | 三个品种各一张摘要卡：主力收盘、基差、1-5 价差、本期最关键的变化 |
| 点摘要卡 | 跳到该品种的全部模块 |
| 展开模块 | 价格与价差 / 基差与月差 / 装置与产能 / 库存与需求 / 政策与事件 |
| 点任意一行 | 右侧抽屉：上期值→本期值→变动、基线来源、算法、历史轨迹、为什么重要、今天继续验证什么、原始来源链接 |
| 顶部筛选 | 按品种、按重要性（A 必看 / B 记录 / C 噪声）、只看有变化 |
| 看底部 | 被排除的资讯（为什么没进晨报）、数据缺口（缺什么怎么补）、数据来源 |

---

## 这个工具特别在意三件事

### 1. 不许把旧闻当新闻

搜索引擎会把去年同日的稿件端上来。案例里真实遇到过：搜「10月20日甲醇价格汇总」，命中的页面写着「发布时间：2025-10-20」，价格 2,275 元/吨——和 2026 年的量级完全不同。

工具的做法：
- 事件发生日早于上一期基线 → 标「旧闻·仅进展更新」，级别最高只到 B；
- 转载合并：同主体 + 量化数字指纹有交集 → 合并为一条（纯文本相似度对中文改写稿无效，实测只有 0.06）；
- 无量化、无影响路径的观点 → C 级噪声，不进正文，但列出「为什么被排除」。

### 2. 不许把未更新数据说成当天变化

数据发布日期 ≠ 报告日。库存「截至 10-15」在 10-20 的晨报里只能写「截至 10-15」，页面会自动打「未更新」标签并降级。

### 3. 拿不到就写缺口，不写估算

所有未取得的数据进「数据缺口」表：缺什么 / 为什么缺 / 怎么补。禁止用估算值、同比反推、上月数据顶替。

**全文禁止方向性预测**，且这条有自动检查——`check_html.py` 会拦下「预计下跌 / 看涨 / 抄底 / 底部已现」，但放行「若进口恢复，港口将集中到港」这样的条件句。

---

## 最快上手

```bash
# 1 复制案例当骨架
cp -r examples/01-ma-pp-pvc-2026-10-20 mybrief
cd mybrief

# 2 改 research.json —— 这是唯一需要你做判断的文件
#    报告日、本期数值、上期数值、来源，以及每条指标的 what/why/verify

# 3 一条命令跑完
python ../../scripts/assemble.py research.json --out build/data.json \
       --baseline baseline_2026-10-16.json
python ../../scripts/build_html.py build/data.json --out out/晨报.html
python ../../scripts/build_xlsx.py build/data.json --out out/晨报.xlsx

# 4 校验
python ../../scripts/selftest.py
python ../../scripts/check_html.py out/晨报.html build/data.json
python ../../scripts/check_xlsx.py out/晨报.xlsx build/data.json
```

换品种、换组合、换数据源，见 `references/adapters.md`。完整方法论见 `SKILL.md` 与 `references/`。

---

## 依赖

- Python 3.10+，`openpyxl`（生成 Excel）
- 抓行情：仅需标准库（`urllib`），无需 key
- 可选：`playwright`（真浏览器渲染检查；没有会自动跳过）
- 前端：ECharts 已内联在 `scripts/assets/echarts.min.js`，页面零外链

```bash
pip install openpyxl
# 可选
pip install playwright && playwright install chromium
```

---

## 目录

```
industrial-morning-brief/
├── SKILL.md                  给 AI 助手看的执行说明
├── README.md                 本文件
├── references/
│   ├── data-contract.md      两个 JSON 的字段契约
│   ├── change-detection.md   变动判定、去重、分级、换月、禁用词的全部规则
│   ├── research-playbook.md  每类数据去哪拿、有什么坑、怎么交叉核对
│   ├── adapters.md           换品种 / 换组合 / 换数据源 / 换版面
│   └── qa-checklist.md       交付前逐项检查表
├── scripts/
│   ├── common.py             公共工具
│   ├── fetch_futures.py      行情抓取
│   ├── assemble.py           变化检测与组装
│   ├── dedupe.py             事件去重与分级
│   ├── build_html.py         HTML 渲染
│   ├── build_xlsx.py         Excel 渲染
│   ├── check_html.py         HTML 校验
│   ├── check_xlsx.py         Excel 校验
│   ├── qa_render.py          浏览器渲染实测（可选）
│   ├── selftest.py           判定逻辑单测
│   ├── simulate_render.js    无浏览器时的渲染测试
│   ├── peek_render.js        打印渲染片段供人工过目
│   ├── templates/brief.html  页面模板
│   └── assets/echarts.min.js 图表库（内联用）
└── examples/
    └── 01-ma-pp-pvc-2026-10-20/   完整实战案例
```

---

## 一句话总结

> 晨报的价值不在于「今天有多少条」，而在于**每一条都是新的、都能核对、都不会误导人**。
