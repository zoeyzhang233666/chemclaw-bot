# 换机器 / 换 agent / 换品类

## 1. 依赖

| 用途 | 依赖 | 说明 |
|---|---|---|
| `extract.py` `build_quote.py` `build_workbench.py` `selfcheck.py` | Python 3.9+ 标准库 | 无第三方依赖 |
| `build_xlsx.py` | `xlsxwriter` | 出 Excel；缺失时其余功能不受影响 |
| `selfcheck.py --xlsx` | `openpyxl` | 只用于校验 Excel |
| `make_example_inputs.py` | `Pillow` + `openpyxl` | 仅复现示例素材时需要 |
| `selftest_workbench.mjs` / `selftest_case.mjs` | Node 18+（需全局 `fetch`/`WebSocket`）+ Edge/Chrome | 可选，用于功能自测 |
| 报价草稿 → PDF | 浏览器打印，或 Excel COM/LibreOffice | 不强制 |

脚本全部按"相对自身位置"找 `_common.py` 与 `templates/`，整个目录拷走即可用：

```bash
cp -r inquiry-to-quotation /目标机器/skills/
```

## 2. 目录结构

```
inquiry-to-quotation/
├── SKILL.md                     ← 主流程（agent 读这个）
├── README.md / INSTALL.md / AGENTS.md
├── products/                    ← 产品画像：纯碱示例 + 空白模板
├── schemas/                     ← fields.json / quote.json 的 JSON Schema
├── references/                  ← 字段口径、抽取规则、报价写法、价格红线、研究手册、QA
├── scripts/
│   ├── _common.py               ← 字段契约与报价渲染（唯一真源）
│   ├── extract.py               ← 询盘原文 → fields.json
│   ├── build_workbench.py       ← fields.json → 交互式 HTML
│   ├── build_xlsx.py            ← fields.json → 7 表工作簿
│   ├── build_quote.py           ← 确认价格后 → 报价草稿 md/xlsx
│   ├── build_case_html.py       ← 纯碱案例的静态研究页
│   ├── make_example_inputs.py   ← 生成微信截图/邮件/需求表素材
│   ├── prepare_case.py          ← 校正纯碱案例字段 + 演示版
│   ├── selfcheck.py             ← 交付前自检
│   ├── selftest_workbench.mjs   ← 工作台功能自测（无头浏览器）
│   └── selftest_case.mjs        ← 案例页布局自测
├── templates/
│   ├── workbench.template.html   ← 工作台骨架（占位符 __DATA__ 等）
│   └── 报价模板_默认.md          ← 公司模板改这个即可
└── examples/
    ├── example-1-soda-ash-glass/ ← 纯碱完整案例（输入+输出）
    └── _skeleton/                ← 换品类空白骨架
```

## 3. 换品类（纯碱 → SBS / 甲醇 / 钛白粉 …）

只改 `scripts/extract.py` 顶部三张词表，别动结构：

1. `PRODUCTS`：加品名与别名，**长词在前**（"重质纯碱" 先于 "纯碱"）；
2. `GRADE_PATTERNS`：加该类产品的常见指标（`白度`、`熔指`、`软化点`、`苯乙烯含量`…）；
3. `PACK_PATTERNS`：加包装形态（`吨包`、`编织袋`、`槽车`、`IBC 桶`…）。

字段、两类分桶、四道锁、报价七要素、HTML/Excel 版式全部不变。
指标写法差异大的品类（如 SBS 的充油牌号），在 `references/field-schema.md` 的"易混案例"里补两行即可。

## 4. 换 agent / 换模型

本 skill 不假设你用什么模型：

- 有脚本执行能力 → 走 `extract.py` + `build_workbench.py` + `build_xlsx.py` 全自动；
  注意 `extract.py` 只吃文字：微信截图/扫描 PDF 要先 OCR 或人工转写，脚本本身不做 OCR；
- 只能读文本（无 shell）→ 直接读 `SKILL.md` + `references/`，或把 `PORTABLE_PROMPT.md`
  整段作为系统提示词；用 `templates/workbench.template.html` 手工替换 `__DATA__` 为 JSON
  也能出同一个工作台；
- 只要一份 Markdown 报价 → 读 `references/quotation-template.md` 手工按七要素写，
  `build_quote.py` 只是把这件事脚本化。

不管哪种方式，**四道锁的语义必须保留**：没有销售确认的单价，不得生成带价格的文本。

## 5. 接到已有系统

| 场景 | 接法 |
|---|---|
| 有自己的 CRM | 把 `fields.json` 映射成 CRM 询盘对象；`price` 段不落库，落到报价单时再带 |
| 有自己的报价模板 | 改 `templates/报价模板_默认.md`，或 `build_quote.py --template` |
| 要走审批流 | 用 Excel 05 表作为审批附件，04 表留空由销售填；审批通过后再生成 md |
| 要接合同审阅 | 工作台"下一步：合同审阅"复制的是交接文本：报价全文 + 审阅要点清单 |
| 要做历史价库 | 只归档**已发出**的报价（含 `quote_no` + `confirmed_at`），不得反向用历史价自动填新报价 |

## 6. 常见适配坑

- Windows 控制台 GBK 会让中文输出报 `UnicodeEncodeError`：脚本已 `reconfigure(encoding="utf-8")`，
  仍建议 `set PYTHONIOENCODING=utf-8`；
- 路径含中文时，Node 侧使用 `pathToFileURL` 转成 `file:///…` 再交给浏览器；
- 无头浏览器自测需要本地已装 Edge/Chrome，找不到会自动跳过（不报失败）；
- Excel 里引用带空格的工作表名必须加单引号：`'04 价格与口径'!$C$6`。

## 7. 演示价与正式价

`examples/example-1-soda-ash-glass/fields_demo.json` 和 `demo/` 里的 1,180 元/吨，
是演示者为了展示版式手动填入的，**不是默认价、建议价、行情价或成交价**。

移植到新客户时：

1. 不要复制 `fields_demo.json` 当正式字段；
2. 正式报价从 `fields.json` 出发，`price.unit_price` 保持 `null`；
3. 只有销售给出价格并写 `--ack`，才生成带价格的草稿；
4. 如果要做演示，文件名、页面、工作簿都要标 `DEMO`。
