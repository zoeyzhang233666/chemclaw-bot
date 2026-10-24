# 交付规格：HTML 报告与 Excel 工作簿

## 一、HTML 报告

### 技术要求

- **单文件自包含**：CSS/JS/数据全部内联，双击即可打开，无需联网、无需服务器。
- 数据通过 `<script>const DATA = {...}</script>` 注入，图表用原生 SVG 绘制（不依赖 CDN 图表库，保证离线可用）。
- 视口宽 1280px 居中，深色专业风格；所有文字使用系统中文字体栈 `"Segoe UI","Microsoft YaHei","PingFang SC"`。

### 必备章节（共 10 节）

| # | 章节 | 必备内容 |
|---|---|---|
| 0 | 页首结论区 | 一句话结论 + 结论等级徽标 + 6 个 KPI 卡（样本区间、检验 Lag 数、最小未校正 p、最小 FDR q、同期相关 r、最大 \|r\| 所在 Lag） |
| 1 | 指标定义 | A/B 的定义、频率、覆盖、**实际发布日期**、可得性含义；明确「统计日=发布日」的校验结论 |
| 2 | 数据变换 | 变换表（名称/定义/用途）+ ADF 单位根结论 + 为何差分 |
| 3 | **完整 Lag 曲线** | ±K 全部 Lag；可切换视图（r / −log10 p / −log10 q / n）；95% 置信带；点可点击；下方完整表格（Lag、n、r、CI、p、t_nw、p_nw、q_BH、q_Bonf、n_eff） |
| 4 | 领先滞后矩阵 | ±K 排列成矩阵，左半=B领先A、右半=A领先B，色深=|r|，标明 Lag=0 分界 |
| 5 | Lag 明细查看器 | 选定 Lag 后显示：时间对齐明细表（前 14 对）、散点+拟合线、26 期滚动相关、同 Lag 的逐年/分阶段结果、判定提示 |
| 6 | 稳定性 | 各年度/各阶段最强 Lag 汇总表、阶段定义依据表、Lag×时期热力图 |
| 7 | 稳健性与安慰剂 | 6 种变换切换曲线、伪造时点安慰剂表 |
| 8 | 多重比较与样本量 | 3 个警示卡（多重比较、自相关、分区样本量）+ 朴素 t vs NW t 对比图 |
| 9 | 预测回归 | 库存因子 vs 库存+需求侧的 R²、系数、t 值 |
| 10 | 结论 | 发现清单、有效/失效时期、产业解释、局限声明 |
| 附 | 数据来源 | 来源、口径、计算内核、时区 |

### 交互要求

1. 点击 Lag 曲线上的点、矩阵格子、表格行 → 全部同步更新明细区。
2. Lag 下拉选择器与曲线上选中的 Lag 保持一致。
3. 每个图表切换按钮只重绘对应图表，不刷新页面。
4. 明细区必须显示「该 Lag 未通过多重检验校正（q=…）」类判定文案。

### 质量校验（交付前必做）

用无头浏览器跑一遍，确认：

```
- 无 pageerror / console error
- 所有 SVG 均已绘制：path/circle/rect 数量 > 0
- 表格行数正确：Lag 表 = 2K+1；逐年表 = 年数；阶段表 = 阶段数
- 无文字溢出容器：scrollWidth <= clientWidth
- 无 SVG 文字碰撞：任意两个 text 的 bbox 不重叠
- 中文字体可渲染：canvas measureText('领先滞后') 宽度在 40~80px
```

碰撞检测示例（Playwright）：

```python
collisions = page.evaluate("""() => {
  const out = [];
  document.querySelectorAll('svg.chart').forEach(s => {
    const ts = [...s.querySelectorAll('text')].map(t => {
      const b = t.getBBox(); return {t: t.textContent, x:b.x, y:b.y, w:b.width, h:b.height};
    });
    for (let i=0;i<ts.length;i++) for (let j=i+1;j<ts.length;j++) {
      const a=ts[i], b=ts[j];
      const ox = Math.min(a.x+a.w,b.x+b.w) - Math.max(a.x,b.x);
      const oy = Math.min(a.y+a.h,b.y+b.h) - Math.max(a.y,b.y);
      if (ox>1.5 && oy>1.5) out.push(s.id+': '+a.t+' ^ '+b.t);
    }
  });
  return out;
}""")
```

### 常见渲染缺陷（来自实战）

| 缺陷 | 表现 | 修法 |
|---|---|---|
| 固定 y 轴范围用于 p/q 视图 | −log10(q) 最大仅 0.22，所有点挤在底部 7% | y 轴上限按数据自适应：`max(1, ceil((max+0.25)*2)/2)` |
| SVG 内多空格被折叠 | 「← Lag 递减　　Lag=0」挤成一句 | 用全角空格 `\u3000` 或拆成两个 text |
| 行标签字号大于行高 | 热力图 25 行 × 15px 行高，10.5px 字号必重叠 | 行高 ≥ 18px 或字号 ≤ 9.5px |
| 注释文字未夹紧边界 | 「最强 \|r\|」标注在正 Lag 侧被裁切 | `if (ax + textWidth > W - pad) ax = x - textWidth` |
| 文案与渲染不一致 | 说「上排/下排」，实际是「左半/右半」 | 交付前逐句核对图例与代码 |

## 二、Excel 工作簿

### 必备工作表（≥12 个）

| 工作表 | 内容 | 关键列 |
|---|---|---|
| `00_说明` | 研究设定、结论、工作表导航 | 指标定义、Lag 符号、对齐基准、结论、局限 |
| `01_指标A原始` | A 的逐期原始记录 | 期序、统计日、发布时间、数值、变化、标题、摘要、原文链接 |
| `02_指标B原始` | B 的逐日/逐期记录 | 日期、收盘、成交量、持仓、涨跌、涨跌幅 |
| `03_发布日期与可得时点` | **逐条校验** | 统计日、星期、发布时刻、是否盘中、最早可得时点、统计日=发布日、可得性判定 |
| `04_研究样本` | 统一频率后的样本 | 期序、统计日、A 值、ΔA（**Excel 公式**）、ΔA%、P_before、P_after、收益（**公式**）、分位、对照指标 |
| `05_Lag对齐明细` ×3 | 选定 Lag 的逐期配对（如 +2 / 0 / −2） | 配对序、A 期日期/发布时间/值、B 期日期/值、Lag 说明；表尾带 CORREL/COUNT/T.DIST 公式 |
| `06_Lag扫描结果` | 完整扫描 | Lag、含义、n、r、CI 上下限、t、p、t_NW、p_NW、NW阶数、q_BH、q_Bonf、n_eff、判定 |
| `07_分段与逐年` | 分年度/分阶段/分半年 | 分组、区间、n、Lag−12…+12 的 r 矩阵 |
| `08_滚动相关` | 滚动窗口序列 | 窗口末端、各 Lag 的滚动 r、两个 Lag 的 n |
| `09_回归与稳健性` | 4 个区块 | A 变换稳健性、B 伪造时点、C 预测回归、D 诊断统计 |
| `10_公式与口径` | 全部公式 | 编号、名称、公式/方法、出处 |

### 格式要求

- 表头：深色底、白字、加粗、居中、自动换行、冻结首行。
- 数字列用 `Consolas` 等宽 + `0.000` 格式；日期用 `yyyy-mm-dd`。
- 显著/不显著用条件格式或底色区分（绿=通过 FDR，红=伪回归反例，黄=仅未校正显著）。
- 原始数据表开启自动筛选。
- 关键计算保留**可复核的 Excel 公式**，并写入缓存值以便不重算也能看到结果。

### XlsxWriter 踩坑

```python
# 带格式的空单元格：必须用 write_blank，且不能传值
ws.write_blank(r, c, None, fmt)      # ✓

# 以下三种都会写坏文件或写出字面量 'None'
ws.write_blank(r, c, "", fmt)        # ✗ 类型不符
ws.write_string(r, c, "", fmt)       # ✗ 写出空字符串，数据类型标记为字符串
ws.write_string(r, c, None, fmt)     # ✗ TypeError: object of type 'NoneType' has no len()
```

- 数值列中出现 `None` 时先判断再写，不要直接 `write_number`（`TypeError: must be real number, not NoneType`）。
- `merge_range` 合并单个单元格会告警，单列文本直接 `write`。
- 交付前校验 XML 完整性：

```python
import zipfile
from xml.etree import ElementTree as ET
z = zipfile.ZipFile(path)
bad = [n for n in z.namelist() if n.endswith(('.xml', '.rels')) and
       (lambda: (ET.fromstring(z.read(n)), False)[1] if True else True)()]
```
