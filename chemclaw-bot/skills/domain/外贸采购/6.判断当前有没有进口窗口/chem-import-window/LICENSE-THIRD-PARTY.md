# 第三方组件与许可

本 Skill 的代码与文档以「按现状提供、供内部使用」的方式交付。其中内联的第三方组件如下：

## ECharts 5.x

- 文件：`scripts/assets/echarts.min.js`（构建时内联进 HTML，使看板成为**完全离线的单文件**）
- 版权：Copyright 2017-2024 The Apache Software Foundation
- 许可：**Apache License 2.0**
- 许可原文：http://www.apache.org/licenses/LICENSE-2.0
- 说明：文件头部保留原始 Apache 许可声明，未作修改。分发本 Skill 时请一并保留该声明。

## 数据版权

`examples/01-meg-huadong` 中的价格数据来自公开渠道的**引用与摘录**（隆众资讯、ChemPriceHub、同花顺 iFinD、CFETS、ECB 等），
每条数据在 `case.json` 的 `sources[]` 与 `research/FACT-SHEET.md` 中标注了发布方、日期、URL 与原文摘录。

这些数据仅用于**说明计算方法**，不代表任何机构对本报告的授权、认可或背书。
如需在正式业务文件中使用行情数据，请取得相应数据源的正式订阅授权。
