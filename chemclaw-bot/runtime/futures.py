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
    return {'source': 'AKShare / Sina daily history', 'sourceUrl': 'https://akshare.akfamily.xyz/data/futures/futures.html', 'interface': 'futures_main_sina' if domestic else 'futures_foreign_hist', 'symbol': symbol, 'seriesType': 'main-continuous' if domestic else 'provider-contract-series', 'timezone': 'Asia/Shanghai' if domestic else 'provider-local-trading-day', 'frequency': 'daily', 'retrievedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'asOf': str(last_day), 'stale': stale, 'exchange': exchange, 'currency': currency, 'unit': unit, 'gaps': gaps, 'data': json.loads(frame.tail(10000).to_json(orient='records', force_ascii=False, date_format='iso'))}


try:
    print(json.dumps(history(json.loads(sys.argv[1])), ensure_ascii=True, allow_nan=False))
except Exception:
    print(json.dumps({'error': 'Market source unavailable, unsupported symbol, invalid dates or changed schema. Retry or import exchange data; no substitute figures generated.'}))
