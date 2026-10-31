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
