import datetime
import json
import re
import sys

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
    frame = ak.stock_zh_a_hist(
        symbol=symbol, period='daily', start_date=start_date.strftime('%Y%m%d'),
        end_date=end_date.strftime('%Y%m%d'),
        adjust={'none': '', 'qfq': 'qfq', 'hfq': 'hfq'}[adjust],
    )
    required = ['日期', '开盘', '最高', '最低', '收盘']
    if frame.empty or any(name not in frame.columns for name in required):
        raise ValueError('A-share daily OHLC data is unavailable from AKShare/EastMoney')
    frame = frame.rename(columns={
        '日期': 'date', '开盘': 'open', '最高': 'high',
        '最低': 'low', '收盘': 'close', '成交量': 'volume',
    }).sort_values('date')
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
        'source': 'AKShare / EastMoney A-share historical daily OHLC',
        'sourceUrl': 'https://akshare.akfamily.xyz/data/stock/stock.html',
        'interface': 'stock_zh_a_hist', 'symbol': symbol,
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


try:
    args = json.loads(sys.argv[1])
    print(json.dumps(stock_history(args) if args.get('market') == 'stock' else history(args), ensure_ascii=True, allow_nan=False))
except Exception:
    print(json.dumps({'error': 'Market source unavailable, unsupported symbol, invalid dates or changed schema. Retry or import exchange data; no substitute figures generated.'}))
