# 对话内 K 线图试验（2026-10-31）

## 目标和隔离边界

在不修改 main、既有 `show_view` 渲染器、DSH/GenUI 内部代码及生成的 `client.js` 前提下，优先尝试让 ChemClaw 自动把可靠的股票/期货 OHLC(V) 数据呈现为对话内真正的蜡烛图。当前为**验证性第一阶段**，不声称已通过桌面真实渲染。独立分支：`feat/inline-candlestick-chart`。

## 采用现有图表能力

- `show_view` 当前 chart kind 不包含蜡烛图，不能把普通 line 伪装为 K 线。
- ChemClaw 依赖的 GenUI 已声明支持 `dsh-ui` 的 `echart` **full option**；尝试 `series.type = "candlestick"`，配合成交量柱图、均线和 `dataZoom`。引擎能否识别 candle 类型，必须在已打包版本 0.15.0 的真实环境确认，不能只根据通用 ECharts 文档判断。
- `src/shared/candlestick.js` 是纯数据转换/验证的**试验辅助模块**：可把 AKShare 常见中文字段映射成只含 JSON 的 GenUI 规格。它目前**尚未接入模型工具流**；实际自动选择依赖 `view-policy`，未来如果需要高度确定性，再考虑在 Host 增加窄接口或完整的原生组件。
- 不扩大应用安装包的图表引擎、不引入任何新的第三方依赖。

## 数据安全和质量条件

1. 至少两根日线，每根同时具有真实 `date/open/high/low/close`；无完整 OHLC 退回折线或表格，绝不合成 K 线。
2. 严格验证 `low <= min(open,close) <= max(open,close) <= high`、价格正数、成交量非负、日期真实有效、日期无重复。支持 AKShare 的 `日期/开盘/最高/最低/收盘/成交量`。
3. ECharts 蜡烛图数组的顺序是 **[open, close, low, high]**，不是原始 OHLC 顺序；同轴按日期升序。
4. 国内市场红涨绿跌，成交量颜色与对应蜡烛图一致；只在所有展示记录均有真实成交量时绘制量柱。
5. MA5/10/20 只在有足量历史观察值时计算，并先在全部已知历史上计算，再裁切窗口；对缺乏历史的最初几期保持空值。
6. 为避免 GenUI 规格过大，辅助模块最多绘制最近 80 根，不默默隐藏历史：返回 `meta.total/shown/omitted/firstDate/lastDate` 供交付文本说明。真实任务大数据保存在单独文件；不能把整个文件重新塞进消息。
7. 附价格单位、来源、采样周期、合同/标的标识、复权或连续合约口径。行情缺失则显式写明，不猜测。支持纯文字优先。

## 验收流程

**自动检查**（在独立分支 CI 或干净工作区）：
- `cd chemclaw-bot && npm test`
- `cd chemclaw-bot && node scripts/build-client.mjs --check`
- `cd chemclaw-bot && npm run lint`
- 辅助模块测试涵盖 AKShare 列名映射、排序/均线、成交量缺失、数值/日期边界、80 根窗口与纯收盘价退回规则。

**人工桌面验收**（合并前必做）：
1. ChemClaw Bot 私聊：`请用 AKShare 查询万华化学（600309）最近三个月的真实日线开高低收和成交量，直接在对话里自动画 K 线，加 MA5、MA10、MA20 和成交量，允许缩放及悬浮查看，说明数据截至时间、来源和复权口径。不要单独生成网页。`
2. 群聊问期货研究 Bot：`请查询螺纹钢期货的真实日 K 数据并直接在对话显示 K 线。清楚标出是哪个合约，不要自行拼接主力连续数据。`
3. Agent 模式：复测第 1 条，确认 GenUI `echart` 实际出现而非 JSON 代码块。
4. 反例：`请画近一个月华东甲醇现货日价趋势（只有每日一个价格）`，应使用折线，不得臆造 OHLC。
5. 偏好：`只要文字，分析一下 600309 最近的走势`，不可强行插图。
6. 数据多于 80 根、缺失成交量、重复日期、无效 OHLC：界面可用且说明截断/错误；其他旧 SVG/ECharts 图正常；切换主题、窄屏、会话重开不丢视图。

## 放行标准与后续

本 PR **保持 Draft**，直到真实环境证明：GenUI 0.15.0 的 full option 确实内置 `candlestick` 渲染模块，图表不会退化为代码或空白，Bot / Group / Agent 均可正常显示，CI 全绿，且不影响旧图表。若 GenUI 引擎缺少 candle，应先评估上游能力或改为单独按需加载组件；不能偷偷扩展 `show_view` 或直接改 main。

此阶段的 `src/shared/candlestick.js` 尚未绑定到真实 AKShare 调用链。真实的“每次遇到 OHLC 自动出图”仍需用真实模型任务验证，必要时在后续 PR 接入可追溯的工具数据传递，不能仅凭提示规则宣称 100% 自动。


## 2026-11-01 实测反馈与修订

用户在 PR #94 的 CMD 预览中对 WTI 提问：第一轮生成的是原始普通折线图；第二轮明确说“我想看 K 线图”，仍返回收盘/最低双折线，并错误表示终端不支持蜡烛图；第二次回答用时约两分钟。

**已证实的缺口：** 当前开发分支的 `buildCandlestickSpec` 纯函数还未连接 AKShare 工具返回值或对话渲染器；CI 单元测试只证明它能对测试数组生成合法配置，**不能证明产品具备端到端 K 线能力**。本次在不修改 DSH、GenUI 或 `main` 的前提下补了：
- 对 AKShare 日线实际字段 `开盘价/最高价/最低价/收盘价` 和 00:00:00 日频时间戳的解析。
- 对新一轮明确 K 线请求强调先取 `futures_foreign_hist`/国内等真实 OHLC 数据，再走 GenUI 完整 `echart option`，不再错误声称“终端不支持”。
- 将 `我想看K线图` 纳入已命名图表要求；如果模型只生成旧折线图，则至多进行一次有界纠正（无完整 OHLC 时只解释缺口，不再次检索，不凭空制造 K 线）。
- 默认优先最近 20–40 根真实 K 线，避免无谓抄录 88 行数据或重复生成图表。

**性能边界：** 截图并不能拆出 2 分钟里工具调用、模型执行和前端渲染各自的耗时，且截图没有真正调用 K 线模块，不能据此证明“新版 K 线加载慢”。后续验收应记录 AKShare 查询、模型输出、GenUI 首次绘制及二次绘制的四段时间；避免将性能原因先归给图表组件。

**尚未完成：** 让 AKShare 的真实 OHLC 数据自动以机器可读方式送到 `buildCandlestickSpec` 并由对话 UI 直接显示，而不依赖模型自行拼写完整 `dsh-ui` JSON。实现前不能将此 PR 标为 Ready，更不能合并 main。下一阶段如确需确定性，可设计独立数据引用与客户端图表接收协议，须另行评估 DSH 公共 API、打包和测试。


## 2026-11-01 第二轮现场问题：从提示词过渡到原生组件

新截图显示 WTI CL 实际取得 OHLC 23 条后，Bot 仍先画高/收/低三条折线，随后生成 HTML 绘图，并输出坐标轴存在但蜡烛实体缺失的另一张图。此前提示词路由/GenUI full option 未在现场稳定工作，因此在 **本 PR（不影响 main）** 做了真正的原生图表接入：

- `show_view` 新增 `kind:"candlestick"`，直接输入真实 `bars:[{date,open,high,low,close,volume?}]`，2–50 根。不得用虚假 OHLC、缺失价格或随意 ECharts option。
- `src/shared/advanced-charts.js` 和 `views.js` 在 Host 侧校验新协议并支持历史重放；原有图表不变。共享 `normalizeCandles` 严格验证不重复日期、开高低收关系和成交量。
- `chart-engine.js` 注册 ECharts 6 的 `CandlestickChart`、`BarChart`、`LineChart`、缩放组件；`chart-options.js` 产生原生蜡烛图/均线/真实成交量图；`widget-advanced-chart.js` 提供更高的画图区。
- `view-policy.js` 对历史股票/期货行情优先**一个**原生 K 线图，不附 HTML/GenUI/折线重复展示；当前单次报价可用指标卡，没有完整 OHLC 时仍允许诚实地画折线。
- `test/candlestick.test.js` 保护 K 线协议、字段完整性和图形配置；`test/candlestick-render.test.js` 使用 ECharts SVG SSR 检查是否绘出实心蜡烛而不仅是空轴。

### 验收与明确限制

必须检查 GitHub CI 最终通过（含 SVG 绘制检查、客户端构建一致性）、Windows CMD 选择本 PR 最新 SHA 后，在 **Bot 私聊和群聊** 验证：普通历史市场行情询问直接显示一个原生 K 线且无 HTML/多条折线，纯现货单价按事实合理回退，重新打开仍可见。普通 DSH Agent 没有 `show_view` tool，仍需进一步确认 GenUI 路线的兼容性。**UI 中禁止模型输出第二图现在主要由交付策略约束，尚不是对所有任意模型输出的代码级强制去重。** 因此不能只靠 CI 声称 100% 端到端验收完成。

不要把本次未接入的 `buildCandlestickSpec` 辅助函数描述成确定性自动调用的工具。实际原生路径由 Bot 调用 `show_view(kind:"candlestick")`，ECharts 绘制不靠模型逐点写图形参数。AKShare 数据仍需由 Agent 通过可用工具取得，未添加新的私有数据源或自行拉取网络请求。


## 2026-11-01 第三轮：普通语言提问仍生成折线图

实际反馈：用户明确指定完整日 K 后，PR #94 已能画出原生带 MA 的蜡烛实体；但“WTI 原油期货最近一个月价格”“中石油最近一个月股价”仍选旧折线。Stock Analysis/FT 的中国石油 601857 历史行情页含逐日 Open/High/Low/Close/Volume，因此该案例不是市场没有 K 线数据，而是模型没选择获取/使用完整 OHLC 的路径。企业信息 MCP `search_enterprise` 仅适合企业背景核对，不能替代股票价格历史。

**本轮变更**：
- 解决 `view-policy` 最后一条残留的“OHLC -> GenUI candlestick”冲突，统一：Bot/Group 优先 `show_view(kind:"candlestick")`，普通 DSH Agent 仍需 GenUI。
- 明确 A 股日线接口 `stock_zh_a_hist(symbol="601857", period="daily", adjust="")`（需真正具备 Python AKShare 执行能力），否则使用能提供真实四价的历史网页数据。无工具就不能声称 AKShare 已调用，也不能捏造数值；同一公司 A 股和 H 股需区分市场。
- 对普通股价/期货**历史行情请求**增加轻量级识别；对于**第一个**图表工具试图交付的 line/area/html，给模型返回一次 OHLC-first 纠正。若行情历史确实只有 Close，**下次**允许一张真实折线，不能强制 K 线或陷入重试循环。纯文字、公司信息、化工现货、即时单点报价不进入此检查。
- 让 Bot 提示清晰区分股价历史和企业工商信息的工具优先级；防止用公司资料搜索替代历史市场行情。
- 增加针对自然语言 WTI/中国石油请求、单次纠正上限、已交付 K 线和纯文字豁免的回归测试。

**尚未解决和不可夸大**：这不是新建了 AKShare 工具，也不能保证每台新安装的 ChemClaw 都有 Python/AKShare。由于工具/模型对金融历史来源的可达性不同，不能承诺每次普通行情请求必定取到 OHLC 或零附加延迟。真正确定性的数据源适配层（可选 AKShare 后端或其他官方市场行情渠道）需要单独设计、打包、鉴权/网络测试；模型继续对工具进行选择，但显示端已经原生支持 K 线。

仍需在最新 PR #94 Windows CMD 预览验证一轮普通自然语言提问：一次行情数据获取，默认显示一张原生 K 线，无 HTML 或重复折线，数据溯源/市场/复权口径准确。不得仅凭 CI 单元测试宣称全面验收。
