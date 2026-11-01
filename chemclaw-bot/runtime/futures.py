import datetime
import json
import re
import sys
import urllib.parse
import urllib.request

import pandas as pd
import akshare as ak

CONTRACTS = {
    'M0': ('DCE', 'CNY', 'metric tonne'), 'V0': ('DCE', 'CNY', 'metric tonne'),
    'PP0': ('DCE', 'CNY', 'metric tonne'), 'L0': ('DCE', 'CNY', 'metric tonne'),
    'SA0': ('CZCE', 'CNY', 'metric tonne'), 'MA0': ('CZCE', 'CNY', 'metric tonne'),
    'TA0': ('CZCE', 'CNY', 'metric tonne'), 'UR0': ('CZCE', 'CNY', 'metric tonne'),
    'RB0': ('SHFE', 'CNY', 'metric tonne'), 'SC0': ('INE', 'CNY', 'barrel'),
    'CL': ('NYMEX', 'USD', 'barrel'), 'NG': ('NYMEX', 'USD', 'MMBtu'),
    'GC': ('COMEX', 'USD', 'troy ounce'), 'SI': ('COMEX', 'USD', 'troy ounce'),
}



def _tencent_stock_daily(symbol, adjust):
    """Bounded public HTTPS fallback; only parses provider-returned OHLC, never guesses."""
    ticker = ('sh' if symbol.startswith('6') else 'sz') + symbol
    param = '{},day,,,90,{}'.format(ticker, '' if adjust == 'none' else adjust)
    url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?' + urllib.parse.urlencode({'param': param})
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com/',
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(request, timeout=9) as response:
        payload = response.read(450000).decode('utf-8')
    data = json.loads(payload)
    node = data.get('data', {}).get(ticker, {})
    kind = {'none': 'day', 'qfq': 'qfqday', 'hfq': 'hfqday'}[adjust]
    rows = node.get(kind)
    if not isinstance(rows, list) or not rows:
        raise ValueError('Tencent did not supply the requested adjustment series')
    values = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 5:
            raise ValueError('Tencent OHLC row format is invalid')
        # Tencent: date, open, close, high, low, optional volume.
        record = {'date': row[0], 'open': row[1], 'close': row[2], 'high': row[3], 'low': row[4]}
        if len(row) > 5 and row[5] not in ('', None):
            record['volume'] = row[5]
        values.append(record)
    return pd.DataFrame(values)


def _stock_source_frame(symbol, adjust, start_date, end_date):
    start = start_date.strftime('%Y%m%d')
    end = end_date.strftime('%Y%m%d')
    failures = []
    sources = [
        ('AKShare / EastMoney', 'stock_zh_a_hist',
         lambda: ak.stock_zh_a_hist(symbol=symbol, period='daily', start_date=start,
                                    end_date=end, adjust='' if adjust == 'none' else adjust)),
        ('AKShare / Sina', 'stock_zh_a_daily',
         lambda: ak.stock_zh_a_daily(symbol=('sh' if symbol.startswith('6') else 'sz') + symbol,
                                     start_date=start_date.strftime('%Y-%m-%d'),
                                     end_date=end_date.strftime('%Y-%m-%d'),
                                     adjust='' if adjust == 'none' else adjust)),
        ('Tencent public daily K-line', 'tencent_fqkline',
         lambda: _tencent_stock_daily(symbol, adjust)),
    ]
    for source, interface, obtain in sources:
        try:
            frame = obtain()
            if frame is None or frame.empty:
                raise ValueError('empty response')
            frame = frame.rename(columns={
                '日期': 'date', '开盘': 'open', '最高': 'high',
                '最低': 'low', '收盘': 'close', '成交量': 'volume',
            })
            needed = ['date', 'open', 'high', 'low', 'close']
            if any(key not in frame.columns for key in needed):
                raise ValueError('required OHLC fields missing')
            frame = frame.copy()
            frame['date'] = frame['date'].astype(str).str.slice(0, 10)
            for key in ['open', 'high', 'low', 'close']:
                frame[key] = pd.to_numeric(frame[key], errors='raise')
            if 'volume' in frame.columns:
                frame['volume'] = pd.to_numeric(frame['volume'], errors='coerce')
            frame = frame[(frame['date'] >= str(start_date)) & (frame['date'] <= str(end_date))]
            if len(frame) < 2:
                raise ValueError('fewer than two dated bars')
            frame = frame.sort_values('date').drop_duplicates('date', keep='last')
            if len(frame) < 2:
                raise ValueError('fewer than two unique dated bars')
            return frame, source, interface, failures
        except Exception as exc:
            # Expose which provider failed, not raw network errors / local paths.
            failures.append({'provider': source, 'reason': type(exc).__name__})
    raise ValueError('A-share daily OHLC unavailable from EastMoney, Sina and Tencent (three bounded provider attempts). Use verifiable public web OHLC or explain the data gap.')

def stock_history(args):
    """Use the same pinned AKShare runtime as chem_futures_history."""
    symbol = str(args.get('symbol', ''))
    if not re.fullmatch(r'[0-9]{6}', symbol) or symbol[0] not in '0236':
        raise ValueError('A-share code must be six digits on SSE/SZSE')
    adjust = args.get('adjust', 'none')
    if adjust not in ('none', 'qfq', 'hfq'):
        raise ValueError('Stock adjustment must be none, qfq or hfq')
    today = datetime.datetime.now(datetime.timezone.utc).date()
    end_date = datetime.date.fromisoformat(args['end']) if args.get('end') else today
    start_date = datetime.date.fromisoformat(args['start']) if args.get('start') else end_date - datetime.timedelta(days=65)
    if start_date > end_date or (end_date - start_date).days > 1000:
        raise ValueError('Invalid stock date window; use at most 1000 calendar days')
    frame, source, interface, previous_failures = _stock_source_frame(
        symbol, adjust, start_date, end_date
    )
    columns = ['date', 'open', 'high', 'low', 'close']
    if 'volume' in frame.columns:
        columns.append('volume')
    frame = frame[columns].tail(50)
    if len(frame) < 2:
        raise ValueError('Fewer than two verified stock trading days')
    records = json.loads(frame.to_json(orient='records', force_ascii=False, date_format='iso'))
    for row in records:
        row['date'] = str(row['date'])[:10]
        prices = [row.get(key) for key in ['open', 'high', 'low', 'close']]
        if any(not isinstance(value, (int, float)) or not 0 < value < float('inf') for value in prices):
            raise ValueError('Stock OHLC contains invalid prices')
        if row['low'] > min(row['open'], row['close']) or row['high'] < max(row['open'], row['close']):
            raise ValueError('Stock source OHLC inconsistency')
    last_day = records[-1]['date']
    stale = (today - datetime.date.fromisoformat(last_day)).days > 7
    return {
        'source': source, 'sourceUrl': (
            'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
            if interface == 'tencent_fqkline' else
            'https://akshare.akfamily.xyz/data/stock/stock.html'
        ),
        'interface': interface, 'previousSourceFailures': previous_failures, 'symbol': symbol,
        'exchange': 'SSE' if symbol.startswith('6') else 'SZSE',
        'currency': 'CNY', 'unit': 'share', 'frequency': 'daily',
        'adjustment': adjust, 'retrievedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'asOf': last_day, 'stale': stale, 'data': records,
        'gaps': (['Latest trading day is more than seven calendar days old.'] if stale else []) +
            ['Historical closing price is not an intraday live quote.'],
    }


def history(args):
    symbol = args['symbol']
    if not re.fullmatch(r'[A-Za-z0-9_]{1,24}', symbol):
        raise ValueError('Use a documented AKShare futures symbol')
    domestic = args['market'] == 'domestic'
    frame = ak.futures_main_sina(symbol=symbol) if domestic else ak.futures_foreign_hist(symbol=symbol)
    frame = frame.rename(columns={'日期': 'date', '开盘价': 'open', '最高价': 'high', '最低价': 'low', '收盘价': 'close', '成交量': 'volume', '持仓量': 'open_interest', '动态结算价': 'settlement'})
    if 'date' not in frame.columns:
        raise ValueError('Source schema changed: date column is missing')
    frame['date'] = frame['date'].astype(str)
    for key, op in [('start', 'ge'), ('end', 'le')]:
        if args.get(key):
            datetime.date.fromisoformat(args[key])
            frame = frame[getattr(frame['date'], op)(args[key])]
    if frame.empty:
        raise ValueError('No observations for this symbol and period; import a file or retry')
    exchange, currency, unit = CONTRACTS.get(symbol.upper(), (None, None, None))
    last_day = datetime.date.fromisoformat(frame['date'].max()[:10])
    stale = (datetime.datetime.now(datetime.timezone.utc).date() - last_day).days > 7
    gaps = ['Provider history has an unspecified roll rule. Verify against exchange specifications before comparing or backtesting.', 'Settlement is distinct from close; a missing settlement must remain missing.']
    if exchange is None:
        gaps.append('Exchange, currency and unit are unverified for this symbol; do not compare prices until supplied.')
    if stale:
        gaps.append('Latest observation is over seven calendar days old; this is historical data, not a current quote.')
    if len(frame) > 50:
        gaps.append('Only the latest 50 verified daily observations were returned for compact inline charts; longer history was omitted.')
    return {'source': 'AKShare / Sina daily history', 'sourceUrl': 'https://akshare.akfamily.xyz/data/futures/futures.html', 'interface': 'futures_main_sina' if domestic else 'futures_foreign_hist', 'symbol': symbol, 'seriesType': 'main-continuous' if domestic else 'provider-contract-series', 'timezone': 'Asia/Shanghai' if domestic else 'provider-local-trading-day', 'frequency': 'daily', 'retrievedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'asOf': str(last_day), 'stale': stale, 'exchange': exchange, 'currency': currency, 'unit': unit, 'gaps': gaps, 'totalObservations': len(frame), 'shownObservations': min(len(frame), 50), 'data': json.loads(frame.tail(50).to_json(orient='records', force_ascii=False, date_format='iso'))}


def main():
    try:
        args = json.loads(sys.argv[1])
        print(json.dumps(stock_history(args) if args.get('market') == 'stock' else history(args), ensure_ascii=True, allow_nan=False))
    except ValueError as error:
        # Known parameter/provider failures may be shown. Never reveal traceback paths.
        print(json.dumps({'status': 'unavailable', 'error': str(error)[:350],
                          'next': 'Try web_search/web_fetch for verified daily OHLC from another source before concluding data are missing. Do not repeat the failed same-provider query or fabricate bars.'}))
    except Exception:
        print(json.dumps({'status': 'unavailable', 'error': 'A market provider or runtime returned an unexpected error.',
                          'next': 'Try web_search/web_fetch for independently verifiable historical OHLC, or report the actual data gap without made-up numbers.'}))


if __name__ == '__main__':
    main()
