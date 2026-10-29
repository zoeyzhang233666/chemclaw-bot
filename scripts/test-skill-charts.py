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


def run_script(skill, name, *args):
    result = subprocess.run([sys.executable, str(skill / 'scripts' / name), *map(str, args)],
                            capture_output=True, encoding='utf-8', errors='replace',
                            env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1'})
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', default=None, help='Installed Playwright channel, e.g. chrome')
    args = parser.parse_args()
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
        assert not errors, errors
        browser.close()


if __name__ == '__main__':
    main()
