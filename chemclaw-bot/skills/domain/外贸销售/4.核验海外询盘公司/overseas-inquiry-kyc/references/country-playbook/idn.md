# 印度尼西亚（IDN）核验手册

## 一、三个必须区分的东西

很多人把这三样混为一谈，导致结论全错：

| 东西 | 是什么 | 在哪查 | 能证明什么 |
|---|---|---|---|
| **AHU 登记**（Akta + SK） | 公司**法律设立**的登记，含名称、登记号、成立日、董事、注册资本 | Ditjen AHU Online | 主体存在、名称准确、谁是董事 |
| **NIB**（Nomor Induk Berusaha） | 通过 OSS 系统取得的**营业识别号**，13 位，内含 KBLI 与许可状态 | OSS-RBA (oss.go.id) | 企业已注册营业、业务分类、许可层级 |
| **NPWP** | 税务登记号（NPWP 已与新 NIK 体系衔接） | DJP (pajak.go.id) | 税务主体身份 |

**三者不能互相替代。** 有 NIB 不代表 AHU 名称一致；名称一致不代表 NIB 有效。

## 二、公司类型

| 类型 | 含义 | 备注 |
|---|---|---|
| **PT** | Perseroan Terbatas，有限责任公司 | 最常见；外资为 PT PMA |
| **CV** | Commanditaire Vennootschap，两合/合伙 | 规模小，不能做某些受监管业务 |
| **Perum / Persero** | 国企 | 罕见出现在普通询盘里 |
| **Koperasi** | 合作社 | — |
| **Perwakilan** | 外国公司代表处 | **不能直接签合同收款**，常见疑点来源 |

> 询盘里写 "PT X" 但检索显示是 CV 或代表处 → 明确的 `discrepancy`。

## 三、KBLI 业务分类（业务相关性的硬证据）

KBLI 是印尼标准行业分类。纯碱 / 玻璃 / 化工贸易相关的几个码：

| KBLI | 名称 | 含义 |
|---|---|---|
| **23111** | Industri Kaca Lembaran | 平板（浮法）玻璃制造 |
| **23112** | Industri Kaca Pengaman | 安全/钢化玻璃 |
| 23119 | Industri Kaca Lainnya | 其它玻璃制品 |
| **46651** | Perdagangan Besar Bahan dan Barang Kimia | 化工原料批发 |
| **46632** | Perdagangan Besar Kaca | 玻璃批发 |
| **52101** | Pergudangan | 仓储 |
| 46100 | Perdagangan Besar atas Dasar Balas Jasa (Fee) | 佣金代理/贸易代理 |

判读规则：

- 自称**制造商** → 应有 `23111`（或对应制造类 KBLI）。只有 `46651` → 是贸易商，**不是假，但要纠正身份**。
- 自称**有自己的仓库** → 应有 `52101`。
- 自称**official importer** → 需要 API-U（进口商识别号）与海关 ID。

> KBLI 是分类，不是许可。有 `23111` 不等于工厂在运转；但没有 `23111` 却自称玻璃厂，就是必须解释的矛盾。

## 四、进口管制（Lartas）与纯碱

- 纯碱 HS 编码：**2836.20.00**（Disodium carbonate）。
- 印尼对部分商品实行 **lartas**（larangan/pembatasan，禁止与限制）管理，进口需 API-U 与相关许可；
  具体品类与要求随 **Permendag**（贸易部条例）调整，**必须按基准日核对现行版本**。
- 化工品进口常涉及 SNI 强制认证、危险品运输与仓储要求。

写报告时不要断言"需要 X 许可"，而写："该品类受 lartas 管理，具体许可要求以基准日现行 Permendag 为准，需对方确认其 API-U 状态。"

## 五、检索步骤

```
1. AHU Online → 用公司全称检索 → 记录登记号、成立日、地址、董事
2. OSS → 用 NIB 或名称查 → 记录 KBLI 清单、许可状态、营业地点
3. DJP → 核 NPWP（通常需对方提供）
4. 官网 → About / Contact / Products；抓取日期
5. 本地新闻（印尼语）→ 搜索 "PT xxx" + "pabrik / kapasitas / gugatan / pailit"
6. 制裁与法律 → OFAC / 世行 / 印尼法院公告
```

中文检索基本无效。**必须用印尼语关键词**：

```
"{nama}" gugatan
"{nama}" pailit
"{nama}" pabrik kapasitas produksi
"{nama}" NIB KBLI
importir soda ash Indonesia
produsen kaca lembaran Indonesia
```

## 六、地址与行政区

印尼地址层级：`Jalan (Jl.) → Kelurahan/Desa → Kecamatan → Kota/Kabupaten → Provinsi → Kode Pos`

- **Cakung** 是雅加达东部（Jakarta Timur）的一个 kecamatan，工业区集中。
- **Bekasi** 是雅加达东侧独立的 kabupaten/kota，有大量工业园（如 Jababeka、MM2100、EJIP）。
- 这两个地方**相邻但不同行政区**。办公室在 Cakung、工厂在 Bekasi 是完全正常的制造业布局。
  → 所以"地址不一致"要判 `partial`，而不是 `different`。
- 邮编需核对是否属于该 kecamatan。

## 七、典型疑点清单（印尼专项）

| 疑点 | 严重度 | 说明 |
|---|---|---|
| 自称 PT，实为 CV / 代表处 | high | 合同主体资格不同 |
| 有 NIB 但 KBLI 无制造类，却自称工厂 | medium | 事实是贸易商，影响报价与条款 |
| 自称 importer 但无 API-U | high | 无法合法进口 |
| 名称中 `Nusantara` 等词被省略 | low | 常见缩写，要求书面确认 |
| 域名与名称不对应（少一个字母） | medium | 需确认官方域名 |
| 只给手机、无总机（万吨级采购） | medium | 要求索取 |
| 工厂在 Bekasi、办公在 Cakung 且未说明 | low | 正常布局，写 `partial` |
| 自称外资（PMA）但 AHU 显示本地 PT | medium | 影响付款路径与合规 |

## 八、官方入口（写进 `sources[]`）

| 用途 | 名称 | URL |
|---|---|---|
| 公司登记检索 | Ditjen AHU Online | https://ahu.go.id/ |
| 营业许可 / NIB | OSS-RBA | https://oss.go.id/ |
| 税务 | Direktorat Jenderal Pajak | https://www.pajak.go.id/ |
| 标准与认证 | BSN / SNI | https://bsn.go.id/ |
| 贸易部条例 | Kemendag | https://kemendag.go.id/ |
| 统计 | BPS | https://www.bps.go.id/ |

> 政府站点常改版。每次使用都要在 `retrieved` 里记录日期，并在报告里说明"入口有效、按基准日核验"。

## 九、印尼语话术要点

- 抬头用 `Kepada Yth. Bapak/Ibu ...`（尊敬的先生/女士）。
- 索取资料用 `Mohon kesediaan Bapak/Ibu untuk melampirkan ...`（烦请附上）。
- 说明用途用 `untuk keperluan pendaftaran vendor`（用于供应商登记）。
- 强调不用于其他目的：`data hanya digunakan untuk proses verifikasi internal`。
- 英文版本同样可行——印尼商务英文普及度较高，但附一句印尼语会显著提升回复率。

## 十、边界

- AHU 完整档案（Akta、SK）需付费或需当事人授权 → 通常只能索取，不能自取。
- OSS 的部分信息对公众不开放 → 只能靠对方提供 NIB 后核验。
- 因此"印尼公司的身份核验"**绝大多数情况下要落到"索取 + 核验"两步**，
  不能指望一次性查全。报告里把这一点写清楚，比硬凑一个"已核实"有价值得多。
