"""Offline contract tests for the packaged stock/futures market adapter.

No live finance HTTP call is made. The same pinned AKShare provider interfaces
are mocked to test failover and to ensure we never synthesize OHLC figures.
"""
import contextlib
import datetime
import importlib.util
import io
import json
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd


class Response:
    def __init__(self, data):
        self.data = json.dumps(data).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return self.data


class StockSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ak = types.ModuleType('akshare')
        cls.previous = sys.modules.get('akshare')
        sys.modules['akshare'] = cls.ak
        path = pathlib.Path(__file__).with_name('futures.py')
        spec = importlib.util.spec_from_file_location('chemclaw_market_adapter', path)
        cls.adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.adapter)

    @classmethod
    def tearDownClass(cls):
        if cls.previous is None:
            sys.modules.pop('akshare', None)
        else:
            sys.modules['akshare'] = cls.previous

    def params(self):
        return {'symbol': '601857', 'market': 'stock', 'start': '2026-10-01',
                'end': '2026-10-30', 'adjust': 'none'}

    @staticmethod
    def rows():
        return pd.DataFrame([
            {'date': '2026-10-28', 'open': 10.0, 'high': 13.0,
             'low': 9.0, 'close': 12.0, 'volume': 100},
            {'date': '2026-10-29', 'open': 12.0, 'high': 14.0,
             'low': 11.0, 'close': 13.0, 'volume': 110},
        ])

    @staticmethod
    def unavailable(*_args, **_kwargs):
        raise ConnectionError('provider network unavailable')

    def test_eastmoney_success_does_not_call_fallback(self):
        source = self.rows().rename(columns={
            'date': '日期', 'open': '开盘', 'high': '最高',
            'low': '最低', 'close': '收盘', 'volume': '成交量',
        })
        with patch.object(self.ak, 'stock_zh_a_hist', return_value=source, create=True), \
             patch.object(self.ak, 'stock_zh_a_daily', side_effect=AssertionError('unexpected'), create=True):
            result = self.adapter.stock_history(self.params())
        self.assertEqual(result['interface'], 'stock_zh_a_hist')
        self.assertEqual(result['data'][0]['open'], 10)
        self.assertEqual(result['data'][1]['high'], 14)

    def test_sina_success_after_eastmoney_failure(self):
        with patch.object(self.ak, 'stock_zh_a_hist', side_effect=self.unavailable, create=True), \
             patch.object(self.ak, 'stock_zh_a_daily', return_value=self.rows(), create=True):
            result = self.adapter.stock_history(self.params())
        self.assertEqual(result['interface'], 'stock_zh_a_daily')
        self.assertEqual(len(result['previousSourceFailures']), 1)
        self.assertEqual(result['data'][-1]['close'], 13)

    def test_tencent_OHLC_after_both_akshare_sources_fail(self):
        payload = {'data': {'sh601857': {'day': [
            ['2026-10-28', '10', '12', '13', '9', '100'],
            ['2026-10-29', '12', '13', '14', '11', '110'],
        ]}}}
        with patch.object(self.ak, 'stock_zh_a_hist', side_effect=self.unavailable, create=True), \
             patch.object(self.ak, 'stock_zh_a_daily', side_effect=self.unavailable, create=True), \
             patch.object(self.adapter.urllib.request, 'urlopen', return_value=Response(payload)) as urlopen:
            result = self.adapter.stock_history(self.params())
        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(result['interface'], 'tencent_fqkline')
        self.assertEqual(len(result['previousSourceFailures']), 2)
        self.assertEqual(result['data'][0]['low'], 9)
        self.assertEqual(result['data'][0]['high'], 13)
        self.assertEqual(result['data'][-1]['close'], 13)
        self.assertEqual(result['adjustment'], 'none')

    def test_all_sources_fail_explains_web_fallback_without_fake_bars(self):
        with patch.object(self.ak, 'stock_zh_a_hist', side_effect=self.unavailable, create=True), \
             patch.object(self.ak, 'stock_zh_a_daily', side_effect=self.unavailable, create=True), \
             patch.object(self.adapter.urllib.request, 'urlopen', side_effect=TimeoutError('offline')):
            argv = ['futures.py', json.dumps(self.params())]
            out = io.StringIO()
            with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(out):
                self.adapter.main()
        result = json.loads(out.getvalue())
        self.assertEqual(result['status'], 'unavailable')
        self.assertIn('EastMoney, Sina and Tencent', result['error'])
        self.assertIn('web_search/web_fetch', result['next'])
        self.assertNotIn('data', result)

    def test_invalid_stock_is_rejected_without_network(self):
        with self.assertRaisesRegex(ValueError, 'six digits'):
            self.adapter.stock_history({'symbol': '000000/../../'})
        with self.assertRaisesRegex(ValueError, 'Invalid stock date'):
            self.adapter.stock_history({
                'symbol': '601857', 'start': '2026-11-01', 'end': '2026-10-01',
            })


    def test_lpg_natural_language_resolves_PG0_and_renders_real_provider_ohlc(self):
        source = pd.DataFrame([
            {'日期': '2026-10-28', '开盘价': 4000, '最高价': 4100,
             '最低价': 3980, '收盘价': 4050, '成交量': 190},
            {'日期': '2026-10-29', '开盘价': 4050, '最高价': 4150,
             '最低价': 4010, '收盘价': 4120, '成交量': 220},
        ])
        with patch.object(self.ak, 'futures_main_sina', return_value=source, create=True) as fetch:
            result = self.adapter.history({'market': 'domestic', 'query': '液化气期货最近一个月价格'})
        fetch.assert_called_once_with(symbol='PG0')
        self.assertEqual(result['symbol'], 'PG0')
        self.assertEqual(result['exchange'], 'DCE')
        self.assertEqual(result['currency'], 'CNY')
        self.assertEqual(result['unit'], 'metric tonne')
        self.assertEqual(result['seriesType'], 'main-continuous')
        self.assertEqual(result['data'][-1]['close'], 4120)
        self.assertEqual(result['data'][-1]['high'], 4150)

    def test_common_continuous_futures_names_use_real_symbols(self):
        cases = {
            '液化石油气': 'PG0', 'LPG': 'PG0',
            '甲醇期货最近一个月价格': 'MA0',
            '螺纹钢': 'RB0', '纯碱': 'SA0',
            '碳酸锂': 'LC0', '国际铜': None,
        }
        for name, expected in cases.items():
            if expected is None:
                continue
            self.assertEqual(self.adapter.resolve_futures_symbol(
                {'market': 'domestic', 'query': name}), expected)
        self.assertEqual(self.adapter.resolve_futures_symbol(
            {'market': 'foreign', 'query': 'WTI'}), 'CL')

    def test_unknown_futures_name_uses_unique_provider_catalog_or_returns_unknown(self):
        frame = pd.DataFrame([{'symbol': 'XY0', 'name': '测试原料连续', 'exchange': 'dce'}])
        with patch.object(self.ak, 'futures_display_main_sina', return_value=frame, create=True):
            self.assertEqual(self.adapter.resolve_futures_symbol(
                {'market': 'domestic', 'query': '测试原料期货'}), 'XY0')
            with self.assertRaisesRegex(ValueError, 'Unrecognized or ambiguous'):
                self.adapter.resolve_futures_symbol({'market': 'domestic', 'query': '不存在品种'})


if __name__ == '__main__':
    unittest.main()
