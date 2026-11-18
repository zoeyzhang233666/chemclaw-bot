"""Audit bundled example reports offline; never executes their build scripts."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright


CHART_CHECK = """() => {
  const charts = [];
  if (!window.echarts) return charts;
  for (const el of document.querySelectorAll('[_echarts_instance_]')) {
    const chart = echarts.getInstanceByDom(el);
    if (!chart || !el.getBoundingClientRect().width) continue;
    chart.getModel().eachSeries(series => {
      if (series.subType !== 'candlestick') return;
      const data = series.getData();
      let valid = 0;
      for (let i = 0; i < data.count(); i++) {
        const layout = data.getItemLayout(i);
        if (data.hasValue(i) && layout && layout.ends &&
            layout.ends.flat().every(Number.isFinite)) valid++;
      }
      charts.push({id: el.id, count: data.count(), valid});
    });
  }
  return charts;
}"""


def audit(paths, channel=None):
    findings = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=channel, headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        context.route('http://**/*', lambda route: route.abort())
        context.route('https://**/*', lambda route: route.abort())
        page = context.new_page()
        for index, path in enumerate(paths):
            if index % 25 == 0:
                print(f'Checking {index + 1}/{len(paths)}: {path.name}', flush=True)
            errors = []
            listener = lambda error: errors.append(str(error))
            page.on('pageerror', listener)
            try:
                page.goto(path.resolve().as_uri(), wait_until='load', timeout=15000)
                page.wait_for_timeout(150)
                charts = page.evaluate(CHART_CHECK)
                bad = [chart for chart in charts if chart['count'] and not chart['valid']]
                for tab in page.locator('#chartTabs .pbtn[data-c], .tab[data-v], .tab[data-r]').all():
                    if not tab.is_visible() or not tab.is_enabled():
                        continue
                    tab.click(timeout=3000)
                    page.wait_for_timeout(150)
                    bad.extend(chart for chart in page.evaluate(CHART_CHECK)
                               if chart['count'] and not chart['valid'])
                if errors or bad:
                    findings.append({'path': str(path), 'errors': errors, 'candles': bad})
            except Exception as error:
                findings.append({'path': str(path), 'errors': [str(error)]})
            finally:
                page.remove_listener('pageerror', listener)
        browser.close()
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--browser', default=None, help='Installed Playwright channel, e.g. chrome')
    args = parser.parse_args()
    paths = []
    for path in sorted(args.root.rglob('*.html')):
        # Templates require the corresponding builder and data before rendering.
        if any(part in ('templates', 'template', 'node_modules', 'raw') for part in path.parts):
            continue
        if 'template' in path.stem or path.name == 'dashboard.html':
            continue
        if path.name == 'weekly_report.html' and '{{DATA_JSON}}' in path.read_text(encoding='utf-8'):
            continue
        paths.append(path)
    findings = audit(paths, channel=args.browser)
    args.out.write_text(json.dumps({'checked': len(paths), 'findings': findings},
                                   ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(paths)} reports checked; {len(findings)} findings. Details: {args.out}')
    return bool(findings)


if __name__ == '__main__':
    raise SystemExit(main())
