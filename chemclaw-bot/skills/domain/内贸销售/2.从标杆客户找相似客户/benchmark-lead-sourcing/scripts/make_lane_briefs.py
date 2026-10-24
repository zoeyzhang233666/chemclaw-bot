#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_lane_briefs.py —— 按 project.json 批量生成 lane 作业书（六件套）

产出：
  <项目>/briefs/_common.md      所有 lane 共用：环境、通道命令、JSON schema、纪律、同行名单
  <项目>/briefs/NN_<lane>.md    每条 lane 的细分范围、候选企业、检索式、落盘路径

子代理 prompt 只需：
  「你是市场情报研究员。第一步：read <项目>/briefs/_common.md 与 <项目>/briefs/NN_x.md 全文，
    严格按其执行。完成后只回一句概况，不要贴 JSON。」

用法： python make_lane_briefs.py --dir <项目目录>
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import load_project, setup_console  # noqa: E402

setup_console()

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)


def common_md(cfg, d):
    p = cfg["product"]
    reg = cfg.get("region", {})
    bm = cfg.get("benchmark", {})
    peers = cfg.get("peer_keywords") or []
    dims = cfg.get("similarity_dimensions") or []
    dim_lines = "\n".join(
        f"- **{x.get('name')}**：{x.get('guide') or '（见 references/similarity-framework.md）'}"
        for x in dims) or "- （未配置，按 references/similarity-framework.md 的五维骨架判定）"
    fetched = os.path.join(HERE, "fetch.py")
    return f"""# lane 共用作业纪律（所有 lane 必读，逐条遵守）

## 0. 任务性质
你在为一家**{p['name']}**（{p['grades'] or '工业级'}）供应商梳理**{reg.get('label') or '目标区域'}**
的下游用料工厂线索。标杆客户是**{bm.get('name') or '（见画像文件）'}**。
你要找的是**业务特征与标杆相似、因而会产生同类{p['name']}需求**的工厂，
**不是**按工商行业门类匹配。

产品用途总述：{p.get('use_summary') or '（见 project.json）'}

## 1. 相似性判据（每家都要判定命中哪几项）
{dim_lines}

## 2. 取证通道（按优先级，每级只试一次）
1. **你自己的联网搜索/抓取工具**（宿主提供则优先——发现企业主要靠它）。
2. **结构化取证脚本**（仅需 Python 标准库；工作目录任意）：
```bash
python "{fetched}" cninfo -k "<公司名> {p['name']}" -n 8 --snippet 240
python "{fetched}" cninfo -k "{p['name']} <行业词>" -n 8
python "{fetched}" html "https://<官网>/" --grep "{p['name']}"
python "{fetched}" sina -c <6位A股代码>
```
   注意：公告检索的 `pageSize` 必须 ≤10；产品**别名/学名**索引很差，要用正式名；短公司名会被模糊匹配污染，必须逐条判读高亮片段。
3. shell 直连（curl / iwr）兜底。三条通道各试一次即可，**不要反复重试搜索引擎**。

## 3. 硬性纪律（同类代理曾因违反而零产出崩溃）
1) 目标产出 12–20 条，绝不贪多。
2) 每家公司最多抓 1–2 个页面；抓取失败**直接跳过，不重试、不换域名反复试**。
3) 总网络调用 ≤30 次；**禁止创建任何中间转储文件**。
4) **每完成 5 条就用 write 增量落盘**（读回已有数组 → 追加 → 覆盖写），崩溃也要有产出。
5) 严禁编造公司名、产能数字或 URL；核不到就写 `未核实` + `置信度 低`。
6) 写入来源前确认页面**确实属于该公司**（点开是反诈页/影视站/博彩站/出售页的域名一律弃用）。
7) 只收**{reg.get('label') or '目标区域'}**（{'/'.join(reg.get('provinces') or []) or '省份见配置'}）
   有**自有生产实体**的工厂；不含经销商/贸易商。但把{p['name']}当原料**深加工/复配再转售**的厂属于合格客户。
8) **peer gate（同行不是客户）**：自己也生产{p['name']}的企业必须剔除，并在回复里说明剔除了谁。
   本产品同行线索关键词：{('、'.join(peers)) or '（见 project.json 的 peer_keywords）'}

## 4. 必须回答的两个问题（每家都要写清楚）
- `相似维度`：从 产品结构/工艺路线/下游市场/规模/产业链位置 中选 1–2 项，写成「维度（具体落点）」。
- `相似逻辑`：**这种相似为什么带来相似的原料需求**——点到工序、投料身份、为何不可替代。
  ⚠️ 禁止写「同属XX行业、相似度高」这类工商门类式表述。

## 5. 落盘格式（严格照抄字段名，UTF-8，JSON 数组，路径见各 lane 文件）
```json
[
  {{
    "公司": "某某股份有限公司（简称，代码）",
    "细分行业": "光伏玻璃",
    "省市": "浙江/嘉兴",
    "需求点": "在哪个工序、起什么作用、投料形态/计量方式",
    "规模线索": "产线数/日熔量/产能（没有证据就不要写数字）",
    "相似维度": "产品结构（超白原片）+ 工艺路线（熔窑助熔）",
    "相似逻辑": "与标杆同为……据……故需求同源。",
    "来源": "可点开的 URL（多个用空格分隔；核不到写 未核实）",
    "置信度": "高"
  }}
]
```
- `细分行业`：10 字内短标签（用于统计），不要写长句。
- `省市`：`省份/城市`，省份必须命中：{' / '.join(reg.get('provinces') or []) or '见配置'}。
- `置信度`：只有 `高`（原文写明该原料/工序）、`中`（主体与工序可确认，用途属工艺必然）、`低`（主体都没核到）。

## 6. 回复方式
**只回一句概况**：条数、置信度分布（高中低）、剔除的同行名单、放弃原因。
**不要把 JSON 贴进回复。**
"""


def lane_md(cfg, lane, out_path, idx, total):
    p = cfg["product"]
    reg = cfg.get("region", {})
    cands = lane.get("candidates") or []
    cand_block = "\n".join(f"- {c}" for c in cands) or "- （候选企业待补，请自行按产业常识+检索发现）"
    kws = lane.get("keywords") or []
    kw_block = "、".join(f"`{k}`" for k in kws) or f"`{p['name']}`、`{lane.get('name')} {p['name']}`"
    return f"""# lane {lane.get('id')} · {lane.get('name')}（{idx}/{total}）

> 先读同目录 `_common.md`（工具命令、纪律、JSON schema、同行名单全在那里），再读本文件。

## ① 本 lane 细分范围
{lane.get('scope') or '（待补）'}

## ② 用料逻辑（写「需求点」时要落到这个工序上）
{lane.get('use_logic') or '（待补）'}

用量强度参考：{'★' * int(lane.get('strength') or 3)}（5 星=单客户千吨级/年，4 星=百吨级，3 星=数十吨级）

## ③ 候选企业（核验后取用，不要局限于此，也不要编造）
{cand_block}

产业集聚地：{lane.get('clusters') or '（待补）'}

## ④ 建议检索式
{kw_block}

## ⑤ 落盘路径（增量落盘，每 5 条覆盖写一次）
`{out_path}`

## ⑥ 目标条数
12–20 条，全部限 **{reg.get('label') or '目标区域'}（{'/'.join(reg.get('provinces') or [])}）**。
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    args = ap.parse_args()
    d = os.path.abspath(args.dir)
    cfg = load_project(d)
    lanes = cfg.get("lanes") or []
    if not lanes:
        print("!! project.json 里没有 lanes，先设计 lane 再生成 brief")
        return 1
    briefs = os.path.join(d, "briefs")
    os.makedirs(briefs, exist_ok=True)
    with open(os.path.join(briefs, "_common.md"), "w", encoding="utf-8") as fh:
        fh.write(common_md(cfg, d))
    made = []
    for i, lane in enumerate(lanes, 1):
        lid = str(lane.get("id") or f"{i:02d}")
        name = str(lane.get("name") or f"lane{i}").replace("/", "_")
        out_json = os.path.join(d, "leads_raw", f"{lid}_{name}.json")
        path = os.path.join(briefs, f"{lid}_{name}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(lane_md(cfg, lane, out_json, i, len(lanes)))
        made.append(path)
    print(f"OK 生成 {len(made)} 条 lane brief -> {briefs}")
    for m in made:
        print("  " + os.path.basename(m))
    print(f"  共用纪律 -> {os.path.join(briefs, '_common.md')}")
    print("子代理 prompt 模板：")
    print(f"  你是市场情报研究员。第一步：read {os.path.join(briefs, '_common.md')} 与 "
          f"{made[0]} 全文，严格按其执行；完成后只回一句概况，不要贴 JSON。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
