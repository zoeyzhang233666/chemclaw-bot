# -*- coding: utf-8 -*-
"""新链条脚手架：把一个新产品/工艺快速接入本框架。

用法：
    python new_chain.py <链条名> <输出目录>
例：
    python new_chain.py 纯碱-氨碱法  ../../纯碱测算

生成：
    <输出目录>/chain_config.json    ← 只改这个文件即可定义新链条
    <输出目录>/README.md            ← 接入步骤

chain_config.json 的作用：
    把"工艺、单耗、价格、收率"这些与品种相关的部分，从引擎代码里剥出来。
    引擎（engine.py）不需要改，只要换配置。
"""
import io
import os
import sys
import json
import shutil

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

TEMPLATE = {
    "meta": {
        "chain_name": "<待填：链条名>",
        "product": "<待填：产品名与规格>",
        "process": "<待填：工艺路线及产能占比>",
        "region_basis": "全国基准（未含区域价差）",
        "tax_basis": "含税（增值税13%）",
        "as_of": "<待填：数据冻结日 YYYY-MM-DD>",
        "window": "<待填：起 至 止>"
    },
    "product": {
        "name": "<产品名>",
        "price": 0,
        "unit": "元/吨（含税）",
        "source": "<来源>"
    },
    "yield": 1.0,
    "inputs": [
        {
            "id": "main_raw",
            "name": "<主导原料>",
            "kind": "raw",
            "cons": 0,
            "unit": "吨/吨",
            "price": 0,
            "source": "<单耗来源与适用范围；若多来源请注明取哪一个>",
            "note": "<口径说明、易错点>"
        },
        {
            "id": "energy_ele",
            "name": "电",
            "kind": "energy",
            "cons": 0,
            "unit": "kWh/吨",
            "price": 0.55,
            "source": "<装置本级电耗；注意区别于全链综合电耗>",
            "note": "能源不除收率"
        }
    ],
    "byproduct": {
        "id": "byp",
        "name": "<联产/副产>",
        "kind": "byproduct",
        "cons": 0,
        "unit": "吨/吨",
        "price": 0,
        "enabled": False,
        "source": "<说明>",
        "note": "是否抵减需用第三方数据验证，不可默认开启"
    },
    "manufacturing": {
        "labor": 0,
        "depreciation": 0,
        "packaging": 0,
        "other": 0,
        "enabled": True,
        "source": "<折算依据：人数×薪酬、投资额÷折旧年限>"
    },
    "checks": {
        "dominant_share_range": [65, 78],
        "dominant_share_note": "主导原料占总成本的合理区间，来自文献",
        "aux_max_yuan": 100,
        "expected_sign_cases": []
    }
}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    name, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    cfg = json.loads(json.dumps(TEMPLATE))
    cfg['meta']['chain_name'] = name
    p = os.path.join(outdir, 'chain_config.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    readme = os.path.join(outdir, 'README.md')
    with open(readme, 'w', encoding='utf-8') as f:
        f.write("""# %s · 测算工作区

## 接入步骤

1. **改 `chain_config.json`** —— 填工艺、单耗、价格、收率、制造费用。
   - 单耗务必标注来源与**适用口径**（装置本级 / 全链、外购 / 自产、折百 / 实物）。
   - 多个来源冲突时全部写进 `source`，不要私自平均。
2. **拷贝脚本** —— 把 `scripts/` 下的 engine.py / build_html.py / build_xlsx.py / verify_*.py 复制过来。
3. **接价格数据** —— 参照 `references/02-价格匹配与口径统一.md` 做好五要素登记；
   缺数据就留空，不要外推。
4. **跑校验** —— 三个 verify 脚本必须全绿后再出报告。
5. **写报告** —— 用 `references/03-指标定义与命名规范.md` 里的输出模板。

## 口径红线（复述）

- 理论加工价差 ≠ 利润
- 理论制造利润 ≠ 企业净利润
- 企业实际利润：无内部数据就不输出
- 不同工艺的原料数据不得混用
- 缺数据留空，不编造
""" % name)
    print('[OK] %s' % p)
    print('[OK] %s' % readme)
    return 0


if __name__ == '__main__':
    sys.exit(main())
