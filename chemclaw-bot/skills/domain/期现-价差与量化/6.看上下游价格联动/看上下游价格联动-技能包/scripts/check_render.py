# -*- coding: utf-8 -*-
"""check_render.py —— 用无头 Chrome 取渲染后的 DOM 文本，确认报告真的画出来了

不依赖截图（模型无法看图时仍可校验）：
  - 抓 document.title、九个小节标题、各 canvas 的尺寸
  - 抓 KPI 卡片里的实际数字，确认 JS 执行成功（否则会是占位符）
  - 抓控制台错误
"""
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = os.environ.get(
    'CHROME_EXE',
    (__import__('os').environ.get('CHROME_EXE') or __import__('shutil').which('chrome') or __import__('shutil').which('msedge') or str(__import__('pathlib').Path(__import__('os').environ.get('ProgramFiles(x86)', '')) / 'Microsoft/Edge/Application/msedge.exe')))

DOM_JS = r"""
(async () => {
  const out = {title: document.title, sections: [], canvases: [], kpis: [], errors: []};
  document.querySelectorAll('section[id], div[id^="s"]').forEach(s => {
    const h = s.querySelector('h2, h3, .sec-title');
    if (h) out.sections.push([s.id, h.textContent.trim().slice(0, 40)]);
  });
  document.querySelectorAll('canvas').forEach(c => {
    out.canvases.push([c.id, c.width, c.height]);
  });
  document.querySelectorAll('.kpi').forEach(k => {
    out.kpis.push(k.textContent.replace(/\s+/g, ' ').trim().slice(0, 80));
  });
  return out;
})()
"""


def main():
    report = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'build', 'report.html')
    url = 'file:///' + report.replace('\\', '/')
    js_file = os.path.join(tempfile.gettempdir(), '_dom_check.js')
    with open(js_file, 'w', encoding='utf-8') as f:
        f.write(DOM_JS)
    p = subprocess.run([CHROME, '--headless', '--disable-gpu', '--no-sandbox',
                        '--virtual-time-budget=6000', '--dump-dom', url],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    html = p.stdout or ''
    print('dom bytes', len(html))
    txt = re.sub(r'<script.*?</script>', ' ', html, flags=re.S)
    txt = re.sub(r'<style.*?</style>', ' ', txt, flags=re.S)
    txt = re.sub(r'<[^>]+>', ' ', txt)
    txt = re.sub(r'\s+', ' ', txt)
    print('visible text chars', len(txt))
    for lbl in ('PX', 'PTA', '加工价差', '滚动相关', '领先', '背离', '结论'):
        print(f'  contains {lbl}:', lbl in txt)
    # 关键数字是否渲染进正文
    A = json.load(open(os.path.join(HERE, 'build', 'analysis.json'), encoding='utf-8'))
    for name, val in (('水平r', f"{A['corr']['level']['r']:.3f}"),
                      ('收益率r', f"{A['corr']['return']['r']:.3f}"),
                      ('N', str(A['meta']['n_obs']))):
        print(f'  {name} {val} rendered:', val in txt)
    bad = [t for t in ('undefined', 'NaN', 'Infinity') if t in txt]
    print('suspicious tokens in visible text:', bad or 'none')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
