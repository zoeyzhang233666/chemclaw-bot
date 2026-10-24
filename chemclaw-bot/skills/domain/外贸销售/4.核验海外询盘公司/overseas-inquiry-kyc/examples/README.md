# 案例索引（Examples）

每个案例都是一个完整、可一键重建的工作目录：

```
<case>/
├── inquiry.json        ← 唯一数据源（改这个）
├── output/             ← 产物（由 build_all.py 生成，不要手改）
│   ├── *_核验报告.html
│   ├── *_核验工作簿.xlsx
│   └── build_report.json
└── README.md           ← 这个案例演示了什么
```

## 案例列表

| 目录 | 国家 / 产品 | 演示重点 |
|---|---|---|
| [`id-soda-ash-demo/`](id-soda-ash-demo/) | 🇮🇩 印度尼西亚 / 重质纯碱 | 完整五区块 24 条核验；模拟询盘邮件与名片；AHU + NIB + KBLI 口径；两处口径矛盾（地址、规模）；NDA 前置的处置；四段英文话术；4 已核实 / 2 疑点 / 18 未核实 |

## 重建任一案例

```bash
cd <case>
python ../../scripts/validate.py   inquiry.json
python ../../scripts/build_all.py  inquiry.json output --name 前缀
python ../../scripts/selfcheck.py  inquiry.json --outdir output
```

## 复制成你自己的

```bash
cp ../templates/inquiry.skeleton.json  my-case/inquiry.json
# 或直接复制最接近的案例，然后替换主体信息
cp -r id-soda-ash-demo my-case
```

替换清单（漏掉任何一个都会让报告"串味"）：

- [ ] `meta.title` / `meta.subtitle` / `meta.as_of` / `meta.inquiry_id` / `meta.client_slug`
- [ ] `meta.product` / `product_spec` / `quantity` / `incoterm` / `packaging` / `hs_code`
- [ ] `meta.synthetic` —— **你的数据是真实的，就改成 `false` 并删掉 `synthetic_note`**
- [ ] `inquiry` 整块（原文邮件）
- [ ] `extraction` 全部
- [ ] `subject` 的检索入口与结果
- [ ] `sources` 里的官方链接（换成目标国家的）
- [ ] `requests` 里的证照名称（每国不同）
- [ ] `business_fit.keywords` 的业务分类码（KBLI / NIC / CNAE …）
- [ ] `messages` 里的产品名与占位符

## 关于模拟数据

`id-soda-ash-demo` 中的 `PT Sinar Kaca Nusantara`、`sinarkacanusa.co.id`、
联系人 `Andi Pratama Wibowo`、地址与电话**均为虚构**，仅用于演示核验方法。

- 页面顶部有"模拟样例"横幅；
- 询盘原件区有斜向水印"模拟询盘 · 非真实企业"；
- HTML 标题带 `[模拟]` 前缀；
- `meta.synthetic_note` 说明了虚构范围。

报告中出现的真实机构（AHU、OSS、DJP、BSN 等）**只作为官方检索入口被引用**，
不被表述为任何询盘的发送方。
