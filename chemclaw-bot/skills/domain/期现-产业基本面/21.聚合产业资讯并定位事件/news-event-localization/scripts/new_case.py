#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Initialize a new case from templates.

Usage:
    python new_case.py --product 甲醇 --start 2026-10-13 --end 2026-10-19 \
        --scope "中国甲醇产业链" --out ./cases/methanol [--force]

Creates the src/ skeleton, raw/ directory and a README pointing at the workflow.
The generated files are valid JSON that already passes validate.py, so you can
start filling them in incrementally instead of writing everything at once.
"""
import argparse
import json
import os
import shutil
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(os.path.dirname(HERE), 'templates', 'case-skeleton')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--product', required=True)
    ap.add_argument('--start', required=True, help='YYYY-MM-DD')
    ap.add_argument('--end', required=True, help='YYYY-MM-DD')
    ap.add_argument('--scope', default='')
    ap.add_argument('--code', default='', help='品种英文代码，用于事件编号，如 MEOH')
    ap.add_argument('--out', required=True)
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()

    out = os.path.abspath(a.out)
    if os.path.exists(out) and os.listdir(out) and not a.force:
        print(f'目标目录非空：{out}\n如需覆盖请加 --force')
        return 2

    d0 = dt.date.fromisoformat(a.start)
    d1 = dt.date.fromisoformat(a.end)
    days = (d1 - d0).days + 1
    case_id = f"{a.code or a.product}-{d0:%Y%m%d}-{d1:%Y%m%d}"

    os.makedirs(os.path.join(out, 'src'), exist_ok=True)
    os.makedirs(os.path.join(out, 'raw'), exist_ok=True)
    os.makedirs(os.path.join(out, 'out'), exist_ok=True)
    if os.path.isdir(TPL):
        for fn in os.listdir(TPL):
            src = os.path.join(TPL, fn)
            dst = os.path.join(out, 'src', fn)
            if a.force or not os.path.exists(dst):
                shutil.copyfile(src, dst)

    sources_path = os.path.join(out, 'src', 'sources.json')
    doc = json.load(open(sources_path, encoding='utf-8'))
    doc['meta'].update({
        'case_id': case_id,
        'product': a.product,
        'scope': a.scope or f'{a.product}产业链',
        'window_start': a.start,
        'window_end': a.end,
        'window_label': f'{a.start} 至 {a.end}（{days}个自然日）',
        'collect_time': dt.datetime.now().astimezone().replace(microsecond=0).isoformat(),
        'window_selection_rationale': '【待填】用三个前置条件说明为什么选这个窗口：'
                                      '①窗口内是否有可读官方原文 ②关键事件能否被≥2家独立机构记录 '
                                      '③核心报道正文是否可读',
    })
    json.dump(doc, open(sources_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    readme = f"""# {a.product}资讯事件定位（{a.start} ~ {a.end}）

case_id: `{case_id}`
scope: {doc['meta']['scope']}

## 这个案例的进度

- [ ] 1. 选窗口：填写 `src/sources.json` 的 `window_selection_rationale`
- [ ] 2. 立源：填 `sources`
- [ ] 3. 采集：填 `news.json`，页面存到 `raw/`
- [ ] 4. 判重：填 `dedupe.json`（可先跑 `scripts/dedupe.py` 看候选）
- [ ] 5. 立事件：填 `events.json`
- [ ] 6. 提实体：填 `entities.json`
- [ ] 7. 定确认度：更新 `events[].verify_status` / `verify_basis`
- [ ] 8. 挂节点：填 `chain.json`
- [ ] 9. 列待验证：填 `toverify.json`

## 每次填完就校验

```bash
python scripts/validate.py ./src
python scripts/audit_quotes.py ./src ./raw
python scripts/build_xlsx.py .
python scripts/build_html.py .
python scripts/check_outputs.py .
```

## 提醒

- 保存每个来源页到 `raw/`，否则 `audit_quotes.py` 无法验证引文
- 产能取不到就留 `null`，不要填估计值
- 读不到正文就标 `title_only` / `summary_only`，并写进访问限制日志
- 不给价格涨跌结论
"""
    open(os.path.join(out, 'README.md'), 'w', encoding='utf-8').write(readme)

    print(f'已创建案例：{out}')
    print(f'  case_id = {case_id}（窗口 {days} 天）')
    print(f'  src/ 7 个 JSON 骨架 + raw/ + out/')
    print('下一步：python scripts/validate.py ' + os.path.join(out, 'src'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())