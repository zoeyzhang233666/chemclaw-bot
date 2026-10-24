# HTML 报告模板说明

模板文件：`make_html.py`（生成器，内含完整 HTML/CSS/JS 模板字符串）

## 设计原则

1. **完全自包含**：数据以 JSON 内嵌在 `<script id="DATA">` 中，无 CDN、无外部 JS/CSS、无网络请求。
   双击即可离线打开，适合发给不装环境的业务同事。
2. **纯 Canvas 绘图**：不用 ECharts/Chart.js/D3，避免 CDN 依赖与版本问题。
3. **深色专业风**：金融研究报告惯例，长时间阅读不刺眼。

## 必需的八个章节

| 章节 | 必须回答的问题 |
|---|---|
| 顶部口径声明 | 现货是什么口径、为什么是这个口径、结论因此受限在哪 |
| 一、首屏结论 | 当前基差多少、历史分位多少、偏离均值几个标准差、季节性区间在哪 |
| 二、逐项核实 | 品种/规格/地区/单位/税基/时点/交割规则/频率，逐行给"是否可比" |
| 三、映射与换月 | 三种映射规则、每次换月记录、换月跳空的条形图 |
| 四、季节性统计 | 月度/周度切换、p10/p25/中位/p75/p90 区间带、明细表 |
| 五、逐年原始曲线 | **每一年一条线**，不是只给均值线 |
| 六、典型阶段 | 走强/走弱月份区间及幅度 |
| 七、可比性检查 | 障碍清单 + 换月污染量化 + 稳定性 CV |
| 八、稳定性结论 | 季节性方差占比、最稳/最不稳月份 |
| 底部使用边界 | "不是预测"的明确声明 |

## 配色变量

```css
--bg:     #0e1117   /* 页面背景 */
--panel:  #151a23   /* 卡片背景 */
--line:   #26303f   /* 边框 */
--fg:     #e6edf3   /* 主文字 */
--dim:    #8b98a9   /* 次要文字 */
--accent: #4cc2ff   /* 当前年曲线（蓝） */
--long:   #e5484d   /* 上涨/升水（红） */
--short:  #30a46c   /* 下跌/贴水（绿） */
--warn:   #f5a524   /* 往年均值/警示（橙） */
--violet: #a78bfa   /* 均值点（紫） */
```

**中国金融惯例：红涨绿跌**，与欧美相反。

## 关键交互组件

### 1. 分位带图（ribbon）

绘制顺序（从下到上）：
```
p10-p90 灰蓝色带 (#3b4a5e)
p25-p75 深蓝色带 (#2b6f91)
中位数   灰白线  (#8b98a9)
往年均值 橙色虚线 (#f5a524)
当前年   蓝色实线 (#4cc2ff) + 数据点
当前点   红点 + 白描边
```

hover 显示该月全部统计。

### 2. 逐年曲线图

- X 轴：1–12 月，每月一个刻度
- 每年一种颜色（`YEAR_COLORS` 循环）
- **年度独立**：不跨年连线，避免误导
- hover 垂直扫描：同时显示所有年份在该时点的值

### 3. 换月跳空条形图

以 0 为中轴，向上红色（跳空为正）、向下绿色（跳空为负）。
标注最大值。

### 4. 口径切换按钮组

```html
<button class="on" data-map="near">近月连续</button>
<button data-map="main">主力连续</button>
```

点击切换时重绘，`.on` 类表示当前选中。

## Canvas 绘制工具函数

```javascript
function setup(canvas, h){
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth || canvas.parentNode.clientWidth;
  canvas.width = w * dpr; canvas.height = h * dpr;
  canvas.style.height = h + 'px';
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr,0,0,dpr,0,0);   // 高分屏清晰
  ctx.clearRect(0,0,w,h);
  return {ctx, w, h};
}
```

**必须处理 devicePixelRatio**，否则 Retina 屏上文字模糊。

```javascript
function axes(ctx, w, h, pad, ymin, ymax){
  // 画水平网格线 + Y 轴刻度
  // 返回 {y: 值→像素, x: (索引,总数)→像素}
}
```

## 数据内嵌格式

```python
data = json.dumps(DATA, ensure_ascii=False, separators=(',', ':'))
html = TPL.replace('__DATA__', data)
```

`ensure_ascii=False` 保证中文不转义（体积更小、可读）。
`separators` 去掉多余空格（甲醇实测从 480KB 降到 426KB）。

## 验证方法（不要只靠"看起来对"）

生成后必须做三重验证：

### 1. JS 语法与数据解析

```javascript
// Node 校验
const s = fs.readFileSync(p,'utf8');
const m = s.match(/<script>([\s\S]*?)<\/script>/g);
const last = m[m.length-1].replace(/^<script>/,'').replace(/<\/script>$/,'');
new Function(last);   // 抛错即语法有问题
JSON.parse(dataBlock);
```

### 2. 无头渲染 + 像素分析

```powershell
chrome --headless=new --window-size=1400,4200 --screenshot=shot.png --virtual-time-budget=6000 file:///...
```

然后用 Pillow 检查：
- 各横向分带非背景像素比例（确认没有空白区）
- 目标配色是否出现在预期 y 区间（确认图表真画出来了）

甲醇实测：accent 653 px、warn 1055 px、band75 11022 px、band90 12789 px，全部落在对应章节。

### 3. DOM 提取确认数值注入

```powershell
chrome --headless=new --dump-dom --virtual-time-budget=5000 file:///... 
```

正则提取 `id="k-basis"` 等元素的文本，确认是真实数值而非 `—`。

甲醇实测：
```
k-basis = 631.67 元/吨
k-pctl  = 100%
k-z     = +5.49 σ
k-ss    = 19.0%
```

## 常见问题

| 问题 | 原因 | 解决 |
|---|---|---|
| 图表空白 | Canvas 宽度算成 0 | 用 `clientWidth \|\| parentNode.clientWidth` |
| 文字模糊 | 未处理 dpr | `setTransform(dpr,0,0,dpr,0,0)` |
| 数据里的 `</script>` 截断 | JSON 未转义 | 用 `<script type="application/json">` 承载 |
| 中文乱码 | `ensure_ascii=True` 后又被错误解码 | `ensure_ascii=False` + 文件 UTF-8 写入 |
| 打开是空白 | `__DATA__` 未替换 | 检查 `TPL.replace()` 被调用，`placeholder left: 0` |
