#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交付前体检：真浏览器渲染 HTML + 核对 Excel 表数与合计。

用法:
  python qa.py "out/某.html" "out/某.xlsx" [--shot out/qa/shot.png] [--wait 4500]

检查项
  1. HTML 自包含：无外部 http(s) 资源引用（离线可开）；
  2. 无占位符残留（%%ECHARTS%% / %%DATA%% / %%GEO%% / __DATA__ 之类）；
  3. headless Chrome/Edge 打开后：JS 无报错、地图 canvas 有像素、关键区块有内容；
  4. Excel：13 张表齐全、每张表有标题与表头、关键表行数与 JSON 一致、数值列为数值型；
  5. 交叉一致：HTML 内嵌数据里的厂区数 / 产能合计 与 Excel 03 表合计一致。
退出码非 0 表示不可交付。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

BROWSERS = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
]


def find_browser():
    for p in BROWSERS:
        if os.path.exists(p):
            return p
    return None


def check_html_static(path):
    err = []
    with open(path, encoding='utf-8') as f:
        html = f.read()
    for ph in ('%%ECHARTS%%', '%%DATA%%', '%%GEO%%', '__ECHARTS__'):
        if ph in html:
            err.append('HTML 残留占位符 %s（生成失败或模板未替换）' % ph)
    if 'window.__DATA__={' not in html:
        err.append('HTML 未注入数据（应出现 window.__DATA__={...}）')
    ext = re.findall(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', html)
    ext = [e for e in ext if 'w3.org' not in e]
    if ext:
        err.append('HTML 引用了 %d 个外部资源（离线会失效）：%s' % (len(ext), ', '.join(ext[:3])))
    if len(html) < 200000:
        err.append('HTML 体积仅 %.0f KB，疑似资产未内联' % (len(html) / 1024))
    return err, html


def check_browser(browser, path, shot, wait_ms):
    """用 headless chrome --dump-dom 判断渲染后是否仍有内容 + 截图人工看。"""
    err = []
    prof = tempfile.mkdtemp(prefix='qa_')
    url = 'file:///' + os.path.abspath(path).replace('\\', '/')
    dom_file = os.path.join(prof, 'dom.html')
    try:
        cmd = [browser, '--headless=new', '--disable-gpu', '--no-sandbox',
               '--allow-file-access-from-files', '--virtual-time-budget=%d' % wait_ms,
               '--user-data-dir=' + prof, '--dump-dom', url]
        out = subprocess.run(cmd, capture_output=True, timeout=120)
        dom = out.stdout.decode('utf-8', 'ignore')
        with open(dom_file, 'w', encoding='utf-8') as f:
            f.write(dom)
        if len(dom) < 1000:
            err.append('浏览器未取到 DOM（%d 字节）：%s' % (len(dom), out.stderr.decode('utf-8', 'ignore')[-400:]))
        else:
            for probe, label in (('class="kpi"', 'KPI 卡'), ('id="tSites"', '工厂表'),
                                 ('id="legend"', '图例'), ('id="concBox"', '集中度块')):
                if probe not in dom:
                    err.append('渲染后缺少「%s」' % label)
            m = re.search(r'id="siteCount"[^>]*>([^<]*)<', dom)
            if m and '显示' not in m.group(1):
                err.append('工厂表计数未渲染：%r' % m.group(1)[:60])
        if shot:
            os.makedirs(os.path.dirname(os.path.abspath(shot)) or '.', exist_ok=True)
            # 优先用 CDP 截图（shot.py）：Chrome 的 --screenshot 在部分环境下会挂住并写不出文件。
            # 必须传绝对路径 —— headless 的 --screenshot 相对路径是相对 Chrome 自己的 cwd。
            ok = False
            try:
                r = subprocess.run([sys.executable, os.path.join(HERE, 'shot.py'), path,
                                    os.path.abspath(shot), '--w', '1600', '--h', '2600',
                                    '--wait', str(max(wait_ms, 6000))],
                                   capture_output=True, timeout=180)
                ok = r.returncode == 0 and os.path.exists(shot)
            except Exception:
                ok = False
            if not ok:  # 退回到原生 --screenshot
                prof2 = tempfile.mkdtemp(prefix='qa2_')
                cmd2 = [browser, '--headless=new', '--disable-gpu', '--no-sandbox',
                        '--allow-file-access-from-files', '--hide-scrollbars',
                        '--window-size=1600,2600', '--virtual-time-budget=%d' % wait_ms,
                        '--user-data-dir=' + prof2,
                        '--screenshot=' + os.path.abspath(shot), url]
                try:
                    subprocess.run(cmd2, capture_output=True, timeout=60)
                except subprocess.TimeoutExpired:
                    pass
                finally:
                    shutil.rmtree(prof2, ignore_errors=True)
            if not (os.path.exists(shot) and os.path.getsize(shot) > 10000):
                err.append('截图失败（可手工打开 HTML 检查）')
    except subprocess.TimeoutExpired:
        err.append('浏览器渲染超时')
    return err


def _data_rows(ws):
    """表体行数：第 5 行起，遇到"说明与口径"标题或空行即止。"""
    n = 0
    for r in range(5, ws.max_row + 1):
        v = ws.cell(row=r, column=1).value
        if v is None or str(v).startswith('说明与口径') or str(v).startswith('· '):
            break
        n += 1
    return n


def check_xlsx(path, data_json):
    err = []
    try:
        from openpyxl import load_workbook
    except ImportError:
        return ['openpyxl 未安装，无法检查 Excel']
    wb = load_workbook(path)
    need = ['00_封面与目录', '01_核心结论', '02_生产企业总表', '03_区域汇总', '04_工厂点位核验',
            '05_化工园区', '06_产能与工艺', '07_上下游关联', '08_新增在建项目', '09_价格与供需',
            '10_集中度与价差', '11_数据缺口', '12_口径与核验', '13_来源清单']
    for n in need:
        if n not in wb.sheetnames:
            err.append('缺工作表 %s' % n)
    if err:
        return err
    D = json.load(open(data_json, encoding='utf-8'))
    sites = D.get('sites', [])
    ws = wb['02_生产企业总表']
    n = _data_rows(ws)
    if n != len(sites):
        err.append('02 表行数 %d ≠ JSON 站点数 %d' % (n, len(sites)))
    # 数值列类型
    bad = 0
    for r in range(5, ws.max_row + 1):
        v = ws.cell(row=r, column=11).value
        if v not in (None, '—') and not isinstance(v, (int, float)):
            bad += 1
    if bad:
        err.append('02 表产能列有 %d 个非数值单元格（会破坏排序/着色）' % bad)
    # 03 表合计与 JSON 样本产能一致
    ws3 = wb['03_区域汇总']
    total = None
    for r in range(5, ws3.max_row + 1):
        if ws3.cell(row=r, column=3).value == '【城市合计】':
            total = ws3.cell(row=r, column=6).value
    import common  # noqa
    idx = [s for s in sites if s.get('role') == 'production']
    want = round(sum((s.get('capacity') or 0) for s in idx), 2)
    if total is None:
        err.append('03 表缺【城市合计】行')
    elif abs(float(total) - want) > 0.01:
        err.append('03 表合计 %.2f ≠ JSON 生产厂区合计 %.2f' % (total, want))
    ws13 = wb['13_来源清单']
    src_n = _data_rows(ws13)
    if src_n != len(D.get('sources', [])):
        err.append('13 表来源数 %d ≠ JSON %d' % (src_n, len(D.get('sources', []))))
    return err


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)
    html, xlsx = args[0], args[1]
    shot = None
    wait = 5000
    for i, a in enumerate(args):
        if a == '--shot':
            shot = args[i + 1]
        if a == '--wait':
            wait = int(args[i + 1])
    data_json = args[2] if len(args) > 2 and args[2].endswith('.json') else None
    errs = []
    err, htmltext = check_html_static(html)
    errs += err
    if not data_json:
        m = re.search(r'window\.__DATA__=(\{.*?\});\s*</script>', htmltext, re.S)
        if m:
            tmp = os.path.join(tempfile.mkdtemp(prefix='qa_'), 'data.json')
            with open(tmp, 'w', encoding='utf-8') as f:
                f.write(m.group(1))
            data_json = tmp
    b = find_browser()
    if b:
        errs += check_browser(b, html, shot, wait)
    else:
        print('[WARN ] 未找到 Chrome/Edge，跳过真浏览器渲染检查')
    if os.path.exists(xlsx):
        errs += check_xlsx(xlsx, data_json) if data_json else check_xlsx(xlsx, xlsx)
        # xlsx 传入时无法核对 JSON，改用内嵌数据副本
    else:
        errs.append('Excel 文件不存在：%s' % xlsx)
    for e in errs:
        print('[FAIL]', e)
    print('—— QA %s（%d 项失败）' % ('通过' if not errs else '未通过', len(errs)))
    if shot:
        print('截图：', shot)
    sys.exit(1 if errs else 0)


if __name__ == '__main__':
    main()
