# 按需加载的对话图表

关联 #73。用户已授权在保留现有体验的前提下扩展图表。

## 接入边界

参考 dsh-genui 公开的组件、嵌入和按需加载方式，继续使用 ChemClaw 的
show_view 协议与权限、群聊交付、历史回放。此次不安装整个 GenUI 插件，
不复制其代码或界面，不接入其 action、panel 或系统提示，避免两套视图协议
争用回复及会话。DSH 固定 rc.3，仅使用公开 connection.fetch.register。

## 图表与数据

现有 bar/hbar/line/area/donut 仍由原 SVG 组件绘制。新增 scatter、radar、
heatmap、funnel、treemap、sankey、gauge，使用已依赖的 Apache ECharts 6。
不接受模型生成的 ECharts option、formatter、脚本或 URL。

chart 仍以 categories、series[{name?,values}]、unit、caption 表达数据：
scatter 另含 xValues、xUnit；radar 必须给各轴 maxima，至少三轴；gauge
为一个值并给 max；funnel/treemap 只接受一个非负序列；heatmap 每序列
是一行。sankey 不含 series，以 categories 为节点名，links[{source,target,value}]
为索引边，拒绝环、自连、负数及不存在的节点。高级图表上限 80 类、12 序列、
480 数据点、120 边，仍受整张视图 8 KiB 上限约束。缺失值保留 null；
radar 不能忠实呈现缺口时退回数据表，绝不补零。

## 加载、主题与退回

引擎单独构建至 runtime/chart-engine.js，通过经过 DSH 身份验证的同源
Fetch 路由交付。普通消息与 SVG 图表不请求引擎；多图共享一次加载。
不使用 CDN。加载失败可重试，默认仍展示完整数据表。

设置中的 Advanced charts 默认开启，关闭时高级图表以完整表格呈现，旧图表
继续原样显示。偏好使用现有 team prefs，启动缓存沿用现有主题缓存。

高级图表解析 --bt-* 主题颜色及字体，跟随明暗、强调色、动效偏好与容器宽度。
所有图表保留表格切换、复制 CSV、下载图片。高级引擎使用 SVG renderer，
tooltip 使用绘图层而非 HTML。交互仅发生在本地，不产生模型调用。

## 验证

校验契约覆盖非法字段、环、缺口、公式和超限；浏览器检查默认/暗色/窄屏、
主题切换、卸载、开关、加载失败与重试、复制和导出。mock bench 跑完整 smoke。
记录引擎体积、普通 SVG 路径零引擎请求及高级图表首次/缓存加载耗时；
mock 延迟只能验证调用次数与渲染开销，不能代表真实模型首字时间。

## 验收记录（2026-10-29）

- Windows / Chrome，DSH 0.2.1-rc.3，全部使用隔离数据与 mock 模型。
- 全量单测 1277 项：1276 通过，1 项按已有 Windows 文件名限制跳过；
  构建产物一致性检查与 lint 通过（仅有原有 lint 警告）。
- 既有 mock smoke 全部 51 步通过，覆盖私聊、群聊、视图回复、记忆、
  历史分段、压缩、工作目录与能力隔离。
- `node dev/chart-browser-check.mjs` 使用实际生产视图组件、ECharts 和主题，
  覆盖七种图、默认/暗色/强调色/390px 窄屏、表格、CSV、PNG、关闭、
  加载失败、重试和卸载。图集只用合成数据，Markdown 原语以空桩代替。
- 图集这次本机测得首次引擎加载并出图 498ms，复用引擎出图 111ms；
  引擎约 646KB（gzip 约 217KB）。原有 SVG 图表零次引擎请求，
  多个高级图表共享一次加载。这些是浏览器加载与渲染耗时，不是模型响应时间。
- `node dev/bench-windows.mjs chart-check-NAME --chart-check` 在真实 DSH 页面
  检查 mock → show_view → 回复区、七种图刷新后回放、群聊交付、身份验证、
  打包资产一致性与本地交互不调用模型。首次测试发现资产路由缺少公开契约
  必填项 requestBody，已补全并加断言，未修改 DSH。

图集：[默认主题](assets/advanced-inline-charts/paper.png)、
[暗色](assets/advanced-inline-charts/dark.png)、
[手机窄屏](assets/advanced-inline-charts/mobile.png)、
[真实 DSH 私聊回复区](assets/advanced-inline-charts/private-chat.png)、
[真实 DSH 群聊回复区](assets/advanced-inline-charts/group-chat.png)。

此次提供七类结构化图表，没有接入 GenUI 的任意界面生成、action 或 panel。
未用真实 API key 做模型耗时对比，未制作或发布桌面安装包。
