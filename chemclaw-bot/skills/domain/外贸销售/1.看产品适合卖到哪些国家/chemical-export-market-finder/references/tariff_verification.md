# 关税与非关税措施核验（tariff verification）

关税是"能不能卖"的第一道硬门槛，也是最容易被编造的数据。本文件规定**哪个源、怎么取、怎么标状态**。

---

## 1. 核心原则

1. **只认行级税率**：必须对应该国 8/10 位本地编码，不能用 6 位、不能用国家平均税率。
2. **只认本次会话取到的**：从官方系统实时取得才算 `verified`；凭记忆、凭常识、凭"一般大约"一律记 `gap`。
3. **至少看三档**：普遍(MFN)税率 + 优惠(FTA/GSP)税率 + 附加税(反倾销/反补贴/保障措施)。
4. **优惠税率必须配原产地规则**：没有原产地证（如 Form E、FORM F、中韩 FTA 证书）时，优惠税率等于不存在。
5. **"未发现"也要写**：核查过后没有 AD/CVD，要明确写"本次核验未发现"，而不是留空。

---

## 2. 已实测可用的官方源

### 2.1 美国 — USITC HTS（推荐，最稳定）

```bash
curl "https://hts.usitc.gov/reststop/search?keyword=2836.20"
```
返回 JSON：`general`（普遍税率）、`special`（FTA 优惠，括号里是协定代码）、`other`（Column 2，非正常贸易关系）。

示例（实测）：
```json
{"htsno":"2836.20.00.00","description":"Disodium carbonate",
 "general":"1.2%","special":"Free (A,AU,BH,CL,CO,D,E,IL,JO,KR,MA,OM,P,PA,PE,S,SG)","other":"8.5%"}
```
注意：美国对中国**不适用** special 栏（中国不在任何美国 FTA 名单内），因此中国原产对应 **1.2%**。

### 2.2 欧盟 — EU TARIC（需要会话流程）

TARIC 的 `measures.jsp` 只是一个壳，真正数据在 `measures_details.jsp`，且必须带 `Sid` 参数和 cookie。可靠流程：

```
1) GET measures.jsp?Lang=en&SimDate=<yyyy-mm-dd>&Area=<ISO2>&Taric=<10位>&callbackuri=CBU-1
   —— 用 cookiejar 保存 JSESSIONID / client_nr
2) 在返回 HTML 中正则抓取 measures_details.jsp?...（含 Sid、FrameId）
3) GET 该 URL，Referer 设为第 1 步的 URL
4) 剥标签后解析："Third country duty ... : 5.50 %"
   "Anti-dumping duty" / "Countervailing duty" / "Import control" / "Export control"
```

实测（2836200000，Area=CN，SimDate=2025-01-01）：
- **Third country duty：5.50%**（法规 R2658/87）
- 另含：**Import control - Waste（R1013/06，CD572–CD577）**——这是非关税壁垒，不能忽略
- **未发现** 针对中国的反倾销/反补贴措施

> 注意：`Area` 填**原产国**（中国 CN），不是进口国。欧盟是统一关税区，成员国税率相同（故德/意/西/波/荷/比/法一致）。

### 2.3 其他国家 — trade.gov 国别指南（只给结构，不给行级）

`https://www.trade.gov/country-commercial-guides/<country>-import-tariffs`

实测结论：
| 国家 | 能拿到什么 | 拿不到什么 |
|---|---|---|
| 巴西 | 税种结构（II + IPI + PIS/COFINS + ICMS）、Mercosur CET 框架 | NCM 2836.20.00 的具体 II 税率 |
| 智利 | **非 FTA 原产统一 6%**；美国原产零关税 | 中智 FTA 优惠税率 |
| 印尼 | 平均 MFN 8.1%；**化学品被点名为更高或未约束** | 行级税率、SNI/进口许可细节 |
| 马来西亚 | 工业品简单平均 6.1%；**本地有生产则税率偏高** | 行级税率 |
| 土耳其 | 与欧盟关税同盟对齐；VAT 20%；有 FTA 与"暂停清单" | 行级税率 |

这些一律记 `status: "gap"`。

### 2.4 不可达或需额外条件（不要浪费时间硬闯）

| 源 | 状况 |
|---|---|
| WITS（World Bank） | API 返回 403；HTML 可读，但 API 被墙 |
| MacMap（ITC） | 403，需账号 |
| WTO Tariff & Trade Data / api.wto.org | 需 API key（401） |
| 印度 CBIC | JS 渲染，且旧域超时 |
| 中国商务部/海关查阅 | 需登录或验证码 |

→ 遇到这些，**正确做法是标 gap 并说明"需人工用 X 账号核验"**，而不是估一个数。

---

## 3. 必须一并核查的非关税措施（NTM）

关税只是入口成本的一部分。以下项目也应逐国记录（能取到就写，取不到就标缺口）：

| 类别 | 具体项 | 化工品常见情形 |
|---|---|---|
| 贸易救济 | 反倾销(AD)、反补贴(CVD)、保障措施 | **最关键**。一旦有 AD，价格再低也进不去 |
| 进口许可/登记 | 印尼 LS、印度 BIS、埃及 GOEIC | 注册周期可达数月 |
| 强制标准 | 印尼 SNI、沙特 SASO、欧盟 REACH | 合规成本可能高于关税 |
| 化学品管制 | 欧盟 REACH/CBAM、废物条例 | 纯碱在 EU 受废物条例进出口管制 |
| 原产地规则 | FTA 证书要求 | 决定优惠税率是否可用 |
| 单证与检验 | 装运前检验(PVOC)、SGS | 影响交货周期 |

---

## 4. 状态标注规范

```json
{
  "iso3": "DEU",
  "country": "Germany",
  "hs_local": "2836 20 00",
  "mfn": 5.5,
  "pref": null,
  "basis": "CIF",
  "source": "EU TARIC SimDate=2025-01-01, Area=CN, Taric=2836200000 (live pull 2026-10-19)",
  "restriction": "EU Waste Regulation R1013/06 import control. No AD/CVD found for China origin.",
  "status": "verified",
  "note": ""
}
```

```json
{
  "iso3": "IND",
  "country": "India",
  "hs_local": "2836.20.00",
  "mfn": null,
  "pref": null,
  "basis": "CIF + BCD + SWS + IGST",
  "source": "CBIC Customs Tariff - JS-gated, not retrievable this session",
  "restriction": "India raised tariffs extensively 2021-2024. Verify AD/safeguard before quoting. CRITICAL GAP.",
  "status": "gap",
  "note": ""
}
```

**硬规则**（`validate_outputs.py` 会强制检查）：
- `verified` 必须有数值 + 可识别来源；`gap` 必须为 `null` 且说明原因。
- 二者任一违反 → FATAL，不允许交付。

---

## 5. 报价前的最后一道人工确认

即使标了 `verified`，报价前仍建议：
1. 用**实际报关编码**（不是 6 位）再查一次；
2. 确认**生效日期**（税率会变，尤其贸易摩擦年份）；
3. 确认**附加税**是否叠加（如巴西的 IPI/ICMS 是累进的）；
4. 确认是否有**临时措施**（保障措施、反倾销调查中）；
5. 把核验日期写进报价单的备注。
