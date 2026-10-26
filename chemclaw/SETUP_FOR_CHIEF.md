# ChemClaw 团队安装指令（给 Main Bot / ChemClaw）

工作区请使用本仓库，并确保能读取：`D:/cursor-chembot/chemclaw`。

## 0. 质量原则（转告每个 Bot）
- L1 domain skills from chemclaw/skills/domain define workflow, fields, and provenance.
- Follow process, not pixels: examples/ are reference-only; fix bad maps/occlusion.
- Stronger models may surpass Flash-era example layouts within L1 contracts.
- L2 community skills assist delivery/grilling/planning; never invent business facts.
- Never fabricate prices or company claims; mark gaps explicitly.

## 1. 凭据（请用户在 Settings → Connectors 配置，你不要索要明文写入文件）
- `CHEM_DATA_HUB` → MCP chem-data-hub
- `CHEM_BIZ_SCOPE` → MCP chem-biz-scope
- `QCC` → 企查查系列 MCP

若 Capabilities 里还没有 chem-* / qcc-* / pack-*，请用 `save_capability` 按 `D:/cursor-chembot/chemclaw/seed/capabilities-library.json` 重建（或让用户重新运行 install-seed）。

## 2. 创建或更新 Bots
按下列名单 `create_bot`（或 `update_bot`）。instructions = 对应 IDENTITY.md 全文 + ROUTING.md 摘要。
创建后 `attach_capability` 挂上 packs。

- **ChemClaw** role=`主控` (Main Bot — if Chief already exists, update its instructions instead of creating a duplicate)
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/chemclaw/IDENTITY.md`
  - Attach packs: pack-mcp-core, pack-process
- **潜客猎手** role=`潜客`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/lead-hunter/IDENTITY.md`
  - Attach packs: pack-sales-leads, pack-mcp-core
- **拜访顾问** role=`拜访`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/visit-advisor/IDENTITY.md`
  - Attach packs: pack-sales-visit, pack-mcp-core
- **外贸销售** role=`外贸销`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/export-sales/IDENTITY.md`
  - Attach packs: pack-export-sales, pack-mcp-core
- **供应商寻源** role=`寻源`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/supplier-source/IDENTITY.md`
  - Attach packs: pack-buy-source, pack-mcp-core
- **准入尽调** role=`尽调`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/due-diligence/IDENTITY.md`
  - Attach packs: pack-due-diligence, pack-mcp-core, pack-mcp-qcc
- **外贸采购** role=`外贸采`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/import-buy/IDENTITY.md`
  - Attach packs: pack-import-buy, pack-mcp-core
- **行情报价** role=`行情`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/price-quote/IDENTITY.md`
  - Attach packs: pack-price, pack-mcp-core
- **产业基本面** role=`基本面`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/fundamentals/IDENTITY.md`
  - Attach packs: pack-fundamentals, pack-mcp-core
- **价差量化** role=`价差`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/spreads-quant/IDENTITY.md`
  - Attach packs: pack-spreads, pack-mcp-core
- **产品情报** role=`产品`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/product-intel/IDENTITY.md`
  - Attach packs: pack-product, pack-mcp-core
- **PPT设计师** role=`PPT`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/ppt-designer/IDENTITY.md`
  - Attach packs: pack-ppt
- **表格专家** role=`表格`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/sheet-expert/IDENTITY.md`
  - Attach packs: pack-sheets
- **文档撰稿** role=`文档`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/doc-writer/IDENTITY.md`
  - Attach packs: pack-docs
- **PDF助手** role=`PDF`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/pdf-helper/IDENTITY.md`
  - Attach packs: pack-pdf
- **产业链制图** role=`制图`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/chain-mapper/IDENTITY.md`
  - Attach packs: pack-diagrams
- **深度研究员** role=`深研`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/deep-researcher/IDENTITY.md`
  - Attach packs: pack-research, pack-mcp-core
- **舆情雷达** role=`舆情`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/news-radar/IDENTITY.md`
  - Attach packs: pack-news
- **会议纪要** role=`纪要`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/meeting-notes/IDENTITY.md`
  - Attach packs: pack-meeting
- **中英译审** role=`译审`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/bilingual/IDENTITY.md`
  - Attach packs: pack-translate
- **市场研报** role=`研报`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/market-report/IDENTITY.md`
  - Attach packs: pack-market-report, pack-mcp-core
- **质询官** role=`质询`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/griller/IDENTITY.md`
  - Attach packs: pack-grill
- **流程参谋** role=`流程`
  - Read and use as instructions: `D:/cursor-chembot/chemclaw/bots/process-aide/IDENTITY.md`
  - Attach packs: pack-process

## 3. 创建群聊
- **客户开发作战室** admin=ChemClaw
  - members: ChemClaw、潜客猎手、拜访顾问、行情报价、准入尽调、产品情报、表格专家、文档撰稿、会议纪要、质询官
  - notice: 默认 ChemClaw 接话并拆单。线索找潜客猎手；拜访包找拜访顾问；背调找准入尽调；价找行情报价；名单表找表格专家。重要交付前可 @质询官。禁止编造无来源价格与企业事实。版式可优于 skill 示例，字段与溯源必须满足 domain skill 契约。
- **采购寻源台** admin=ChemClaw
  - members: ChemClaw、供应商寻源、准入尽调、行情报价、产品情报、表格专家、PDF助手、质询官
  - notice: 找真厂家→供应商寻源；准入/证照→准入尽调；比价→行情报价；PDF 抽取→PDF助手。事实不足标 gap。定稿前可 @质询官。
- **期现研究台** admin=ChemClaw
  - members: ChemClaw、产业基本面、价差量化、行情报价、产品情报、PPT设计师、表格专家、产业链制图、市场研报、质询官
  - notice: 归因/供需→产业基本面；基差价差→价差量化；现货价→行情报价；汇报→PPT设计师。不做买卖建议。价格必带日期规格税基来源。
- **进出口协作** admin=ChemClaw
  - members: ChemClaw、外贸销售、外贸采购、行情报价、准入尽调、中英译审、文档撰稿
  - notice: 出口询盘→外贸销售；进口窗口成本→外贸采购；英文润色→中英译审。
- **交付工坊** admin=ChemClaw
  - members: ChemClaw、PPT设计师、表格专家、文档撰稿、PDF助手、产业链制图、深度研究员、舆情雷达、市场研报、质询官、流程参谋
  - notice: 业务结论须来自上游业务岗或已核实材料。PPT 未指定格式默认可编辑 pptx 并确认。定稿前可 @质询官；大单先 @流程参谋。

## 4. 自检
- @潜客猎手 与 @供应商寻源 能区分场景
- @PPT设计师 未指定格式时确认 pptx vs HTML
- @质询官 一次一问且不编价格
- 价格类回答含溯源或 gap
