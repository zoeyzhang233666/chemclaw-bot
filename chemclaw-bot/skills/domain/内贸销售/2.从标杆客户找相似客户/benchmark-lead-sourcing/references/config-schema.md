# `project.json` 字段说明（唯一事实来源）

项目目录下的 `project.json` 驱动全部脚本（取证除外）。所有产品特定内容都写在这里，脚本不含任何产品硬编码。

```jsonc
{
  "project_id": "soda-ash-huadong",
  "product": {
    "name": "纯碱",                          // 必填：产品正式名（用于检索与文案）
    "formula": "Na₂CO₃",                     // 选填：化学式
    "grades": "重质纯碱 / 轻质纯碱 / 食品级 / 药用级",  // 必填：规格级别（销售话术与需求点要用）
    "aliases": ["碳酸钠", "苏打", "soda ash"],  // 选填：别名（检索时避免依赖别名）
    "use_summary": "玻璃助熔、锂盐沉淀、洗涤助洗、脱硫钠碱……"  // 必填：一句话用途总述
  },
  "region": {
    "label": "华东",                          // 必填：区域名（写进报告标题与文案）
    "provinces": ["山东","江苏","浙江","安徽","上海"]  // 必填：过滤白名单，省市字段必须命中其一
  },
  "benchmark": {
    "name": "旗滨集团（601636.SH）",           // 必填：标杆客户
    "stock_code": "601636",                  // 选填
    "profile_file": "benchmark_profile.json" // 画像文件（步骤 2 产出）
  },
  "similarity_dimensions": [                 // 必填：五维判据（换产品时重写 guide）
    {"name": "产品结构", "keywords": ["产品结构","配方","产品"], "guide": "最终产品是否同属钠钙硅/硅酸盐体系"},
    {"name": "工艺路线", "keywords": ["工艺路线","熔窑","窑炉","助熔","工序","反应","中和"], "guide": "纯碱是否以助熔剂/反应物身份进入主流程"},
    {"name": "下游市场", "keywords": ["下游"], "guide": "下游行业对纯碱是否无替代"},
    {"name": "规模", "keywords": ["规模"], "guide": "是否有自有窑炉、单厂年用量量级"},
    {"name": "产业链位置", "keywords": ["产业链"], "guide": "是否中游加工厂、对该原料为纯采购方"}
  ],
  "lanes": [                                 // 必填：8–12 条
    {
      "id": "01",                            // 两位序号，决定 leads_raw/01_*.json 命名
      "name": "光伏玻璃",                     // lane 名
      "block": "玻璃原片（光伏/浮法）",          // 归入 Excel 的「行业板块」
      "scope": "超白压延/超白浮法光伏玻璃原片厂",   // brief 里的细分范围
      "use_logic": "熔窑配合料中纯碱作助熔剂提供 Na₂O……",  // brief 的用料逻辑
      "strength": 5,                         // 1–5 星（写进 brief，供 lane 判断优先级）
      "candidates": ["福莱特玻璃集团（601865，浙江嘉兴/安徽凤阳）", "..."],  // 5–8 家
      "clusters": "安徽凤阳、浙江嘉兴",          // 产业集聚地
      "keywords": ["福莱特 纯碱", "亚玛顿 纯碱"] // cninfo 检索式
    }
  ],
  "strength_rules": [                        // 必填：细分行业关键词 → 用量强度（取第一个命中）
    [5, ["光伏玻璃","浮法","泡花碱","碳酸锂","氧化铝","洗涤","脱硫"]],
    [4, ["印染","皮革","味精","造纸","电子玻璃","冶炼"]],
    [3, ["医药","原料药","陶瓷","耐火","食品"]],
    [2, ["试剂","特种","卷烟"]]
  ],
  "default_strength": 3,                     // 未命中时给几星
  "priority_thresholds": {"high": 11, "mid": 9},   // score = 星级×2 + 置信度分
  "confidence_scores": {"高": 3, "中": 2, "低": 0},
  "peer_keywords": ["氨碱","联碱","天然碱","纯碱生产"],   // 细分行业命中即判同行并剔除
  "buckets": {                               // 必填：细分行业 → 统计品类（只匹配「细分行业」字段）
    "玻璃原片（光伏/浮法/建筑）": ["光伏玻璃","浮法","超白","原片"],
    "日用与药用玻璃": ["日用玻璃","药用玻璃","瓶罐"],
    "无机硅与泡花碱": ["泡花碱","硅酸钠","白炭黑","分子筛"],
    "其他": ["其他"]
  },
  "industry_map": [                          // 必填：Excel 说明页与 HTML 第 3 节的行业地图
    ["玻璃原片（光伏/浮法）", "光伏玻璃、浮法/超白原片", "熔窑配合料：纯碱提供 Na₂O、助熔降粘", "★★★★★", "谈长协锁量+分月到货"]
  ],
  "report": {
    "title": "纯碱（Na₂CO₃）华东下游潜客开发地图 · 对标旗滨集团复制第二批",
    "workbook_output": "下游潜客池.xlsx",
    "html_output": "标杆客户复制与潜客池报告.html",
    "benchmark_name": "旗滨集团（601636）",      // 报告中反复出现的标杆简称
    "product_short": "纯碱",                  // 报告中反复出现的产品简称
    "headline_facts": [                       // 第 8 节 SOP 用的「三条硬事实」
      "日熔量 8,200 吨/日（2023 社会责任报告）",
      "纯碱套保公告写明实物为『重质纯碱』",
      "连续四年就重质纯碱做期货套保"
    ],
    "sales_script": "我方已为旗滨集团稳定供应纯碱：您的窑炉配合料同样是……",
    "sop_steps": [                            // 第 8 节动作清单（可 4–8 条）
      "外呼前先读画像页，记住标杆的三个硬事实",
      "优先打 5 星板块",
      "用同工序切入，先测算用量再谈价格"
    ],
    "evidence_note": "本次取证通道说明（写进报告第 5 节）",
    "boundary_note": "使用边界（写进报告第 5 节或 Excel 说明页）"
  }
}
```

## 最小可用配置

只跑通全流程所需的最少字段：`product.name`、`product.grades`、`product.use_summary`、`region.label`、`region.provinces`、`benchmark.name`、`lanes`、`strength_rules`、`peer_keywords`、`buckets`。
其余字段缺失时脚本用默认值（标题自动生成、industry_map 为空、SOP 用通用六步）。

## 与旧版配置的兼容

脚本同时接受旧文件名 `skill_config.json`（字段为 `file_blocks` / `strength_rules` / `buckets` / `industry_map` / `workbook_title` / `output`）。
新项目请用 `project.json`；`file_blocks`（文件名前缀 → 板块）已由 `lanes[].block` 取代。
