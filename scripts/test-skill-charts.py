"""Offline regression checks for the shipped sales and procurement price reports."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1] / 'chemclaw-bot/skills/domain'
SALES = ROOT / '内贸销售/15.看产品近期行情/chem-market-brief'
BUYING = ROOT / '内贸采购/12.看原料近期行情/chem-procure-brief'


def run_script(skill, name, *args, expect_failure=False):
    result = subprocess.run([sys.executable, str(skill / 'scripts' / name), *map(str, args)],
                            capture_output=True, encoding='utf-8', errors='replace',
                            env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1'})
    if expect_failure and result.returncode == 0:
        raise AssertionError('Checker accepted an intentionally invalid report')
    if result.returncode and not expect_failure:
        raise AssertionError(result.stdout + result.stderr)
    return result.stdout + result.stderr


def main():
    global SALES, BUYING
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', default=None, help='Installed Playwright channel, e.g. chrome')
    parser.add_argument('--skill-root', type=Path, default=ROOT,
                        help='Verify an installed/linked skill tree instead of this checkout')
    parser.add_argument('--sales-skill', type=Path, help='Exact standalone sales skill directory')
    parser.add_argument('--buying-skill', type=Path, help='Exact standalone procurement skill directory')
    parser.add_argument('--artifacts', type=Path, help='Save the synthetic oil regression report and screenshots')
    args = parser.parse_args()
    SALES = args.skill_root.resolve() / '内贸销售/15.看产品近期行情/chem-market-brief'
    BUYING = args.skill_root.resolve() / '内贸采购/12.看原料近期行情/chem-procure-brief'
    SALES = args.sales_skill.resolve() if args.sales_skill else SALES
    BUYING = args.buying_skill.resolve() if args.buying_skill else BUYING
    spec = importlib.util.spec_from_file_location('chart_qa', SALES / 'scripts/chart_qa.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix='chemclaw-chart-tests-') as directory, sync_playwright() as pw:
        temp = Path(directory)
        browser = pw.chromium.launch(channel=args.browser)
        page = browser.new_page(viewport={'width': 1280, 'height': 1000})
        page.route('https://**/*', lambda route: route.abort())
        page.route('http://**/*', lambda route: route.abort())
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        for skill, example in [(SALES, '01-soda-ash-national'), (SALES, '02-glass-shahe'),
                               (BUYING, '01-meoh-huadong')]:
            data_path = temp / 'data.json'
            run_script(skill, 'assemble.py', skill / 'examples' / example / 'research.json', '--out', data_path)
            original = json.loads(data_path.read_text(encoding='utf-8'))
            variants = [('original', original)]
            if skill == SALES:
                for label, routes in [('missing', {}), ('null', {'路线': None}), ('zero', {'路线': 0})]:
                    data = json.loads(json.dumps(original))
                    data['margins'] = [{'date': '2026-10-19', 'routes': routes, 'src': '回归测试'}]
                    data['meta']['unit'] = '元/桶'
                    if data.get('anchor'):
                        data['anchor']['unit'] = '元/桶'
                    variants.append((label, data))
            else:
                data = json.loads(json.dumps(original))
                data['cost_lines'] = []
                data['route_costs'] = []
                variants.append(('missing-cost', data))
            for label, data in variants:
                data_path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
                html = temp / 'report.html'
                run_script(skill, 'build_html.py', data_path, '--out', html)
                page.goto(html.as_uri())
                page.wait_for_timeout(500)
                modes = ('candle', 'line', 'monthly') if skill == SALES else ('candle', 'line', 'allpts')
                for mode in modes:
                    page.click(f'#chartTabs .pbtn[data-c="{mode}"]')
                    page.wait_for_timeout(500)
                    assert not module.check_price_chart(page), (example, label, mode, module.check_price_chart(page))
                if label == 'original':
                    for button in page.locator('#winSel .pbtn').all():
                        if button.is_enabled():
                            button.click()
                            page.wait_for_timeout(500)
                            assert not module.check_price_chart(page), (example, 'time window', module.check_price_chart(page))
                    if skill == SALES:
                        page.locator('#winSel .pbtn').filter(has_text='1年').click()
                if label == 'missing-cost':
                    assert not page.is_visible('#costSection')
                if skill == SALES:
                    assert page.is_visible('#marginPanel') == (label in ('original', 'zero'))
                    assert page.locator('#limitations').get_attribute('open') is None
                    assert page.locator('meta[name="chemclaw-skill"]').get_attribute('content') == 'chem-market-brief:price-charts-v4-daily'
                    if label != 'original':
                        assert '元/桶' in page.inner_text('#quoteLabel')
                        page.fill('#msgQuote', '734')
                        page.click('#btnGen')
                        assert '734 元/桶' in page.input_value('#msgout')
                        assert '734 元/吨' not in page.input_value('#msgout')
                    page.click('#chartTabs .pbtn[data-c="monthly"]')
                    assert page.evaluate("chart.getOption().series[0].data.length") == len(data['monthly']['1y'])
                    # Axes and annotations remain visible in the original failure.
                    # The checker must reject it based on the price data itself.
                    page.click('#chartTabs .pbtn[data-c="candle"]')
                    page.evaluate("chart.setOption({series:[{type:'candlestick',data:D.series['1y']}]}, false)")
                    page.wait_for_timeout(500)
                    assert module.check_price_chart(page), 'Checker accepted malformed candles'
                print(f'PASS {example}: {label}', flush=True)
        # A different product with deliberately different daily and monthly shapes.
        # All values are synthetic regression fixtures, never market evidence.
        dates = ['2026-08-28', '2026-08-31', '2026-09-01', '2026-09-30', '2026-10-01', '2026-10-02']
        closes = [100, 102, 200, 204, 300, 306]
        raw = temp / 'oil-fixture.json'
        raw.write_text(json.dumps([{'d': day, 'o': close-1, 'c': close, 'l': close-2, 'h': close+2}
                                   for day, close in zip(dates, closes)]), encoding='utf-8')
        research = temp / 'research-oil-fixture.json'
        research.write_text(json.dumps({
            'meta': {'product': '原油（合成回归数据）', 'spec': '测试', 'region': '山东',
                     'asof': '2026-10-29', 'unit': '元/桶'},
            'futures': {'series': str(raw), 'code': 'SC', 'exchange': 'INE'},
            'spot': [{'region': '山东', 'product': '回归原油', 'lo': 7430, 'hi': 7430,
                      'date': '2026-10-27', 'tax': '含税', 'basis': '自提', 'src': '合成测试'}],
            'margins': [], 'balance': [], 'downstream': [],
            'upstream': [{'name': '未取得原料', 'value': None}],
            'gaps': [{'item': '区域价差', 'status': '缺口', 'detail': '只有一个地区，不展示价差模块'}]
        }, ensure_ascii=False), encoding='utf-8')
        data_path = temp / 'oil-data.json'
        run_script(SALES, 'assemble.py', research, '--out', data_path)
        html = temp / 'oil-report.html'
        run_script(SALES, 'build_html.py', data_path, '--out', html)
        run_script(SALES, 'check_html.py', html, data_path)
        report = html.read_text(encoding='utf-8')
        invalid = temp / 'invalid.html'
        invalid.write_text(report.replace('chem-market-brief:price-charts-v4-daily', 'chem-market-brief:price-charts-v1'), encoding='utf-8')
        assert '版本不匹配' in run_script(SALES, 'check_html.py', invalid, data_path, expect_failure=True)
        broken = report.replace('data:src.map(x=>x.slice(1,5))', 'data:src')
        assert broken != report
        invalid.write_text(broken, encoding='utf-8')
        assert '渲染脚本' in run_script(SALES, 'check_html.py', invalid, data_path, expect_failure=True)
        bad_data = json.loads(data_path.read_text(encoding='utf-8'))
        bad_data['monthly']['1y'][0][2] = 999
        invalid_data = temp / 'invalid-data.json'
        invalid_data.write_text(json.dumps(bad_data, ensure_ascii=False), encoding='utf-8')
        run_script(SALES, 'build_html.py', invalid_data, '--out', invalid)
        assert '月均数据' in run_script(SALES, 'check_html.py', invalid, invalid_data, expect_failure=True)
        if args.artifacts:
            args.artifacts.mkdir(parents=True, exist_ok=True)
            (args.artifacts / 'synthetic-oil-regression.html').write_bytes(html.read_bytes())
        page.goto(html.as_uri())
        page.wait_for_timeout(500)
        assert not module.check_price_chart(page), module.check_price_chart(page)
        if args.artifacts:
            page.locator('.chartcard').screenshot(path=str(args.artifacts / 'candles.png'))
        assert not page.is_visible('#spreadSection')
        assert not page.is_visible('#marginPanel')
        assert not page.is_visible('#chainSection')
        assert '同日多地区缺失' not in page.inner_text('#kpiGrid')
        page.click('#winSel .pbtn[data-w="all"]')
        for mode in ('candle', 'line'):
            page.click('#chartTabs .pbtn[data-c="%s"]' % mode)
            page.wait_for_timeout(500)
            assert page.evaluate('chart.getOption().xAxis[0].data') == dates
            assert len(page.evaluate('chart.getOption().series[0].data')) == len(dates)
            assert not module.check_price_chart(page), module.check_price_chart(page)
        page.click('#winSel .pbtn[data-w="1y"]')
        page.click('#chartTabs .pbtn[data-c="line"]')
        assert len(page.evaluate('chart.getOption().series[0].data')) == 6
        if args.artifacts:
            page.wait_for_timeout(500)
            page.locator('.chartcard').screenshot(path=str(args.artifacts / 'daily-close.png'))
        page.click('#chartTabs .pbtn[data-c="monthly"]')
        page.wait_for_timeout(500)
        assert page.evaluate('chart.getOption().series[0].data') == [101, 202, 303]
        assert page.evaluate('chart.getOption().xAxis[0].data') == ['2026-08', '2026-09', '2026-10']
        assert not module.check_price_chart(page), module.check_price_chart(page)
        if args.artifacts:
            page.locator('.chartcard').screenshot(path=str(args.artifacts / 'monthly-mean.png'))
        page.evaluate("chart.setOption({series:[{data:D.series['1y'].map(row=>row[2])}], xAxis:{data:D.series['1y'].map(row=>row[0])}})")
        assert module.check_price_chart(page), 'Checker accepted daily data recolored as monthly averages'
        print('PASS synthetic oil: daily candles and close in every window, separate monthly means, hidden empty sections', flush=True)
        assert not errors, errors
        browser.close()


if __name__ == '__main__':
    main()
