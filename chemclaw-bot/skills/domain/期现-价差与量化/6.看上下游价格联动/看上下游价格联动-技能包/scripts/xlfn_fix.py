# -*- coding: utf-8 -*-
"""
xlfn_fix.py —— 让新版 Excel 函数在 LibreOffice / 旧版 Excel 中也能算出值

背景（踩过的坑，固化为规则）
  - Excel 保存文件时，2010 年后新增的函数以 `_xlfn.PERCENTILE.INC(...)` 形式存储；
    openpyxl 不会自动加前缀，某些读取器因此返回 #NAME?。
  - 但 CORREL / STDEV / MEDIAN / RANK.AVG 属于 2007 版函数，**绝对不能**加前缀，
    否则同样变成 #NAME?（曾因误加导致相关性与标准差整列失效）。

做法：保存后直接改写 xlsx 内的 sheet XML，对 MODERN 列表中的函数补齐/去重 `_xlfn.` 前缀。
"""
import re
import shutil
import sys
import zipfile

MODERN = [
    'PERCENTILE.INC', 'PERCENTILE.EXC', 'PERCENTRANK.INC', 'PERCENTRANK.EXC',
    'QUARTILE.INC', 'QUARTILE.EXC', 'T.DIST.2T', 'T.DIST', 'T.INV.2T', 'T.INV',
    'NORM.S.INV', 'NORM.S.DIST', 'STDEV.S', 'STDEV.P', 'VAR.S', 'VAR.P', 'MODE.SNGL',
]
LEGACY_MUST_NOT_PREFIX = ['CORREL', 'STDEV', 'MEDIAN', 'RANK.AVG', 'RANK.EQ', 'SKEW', 'KURT']


def patch(path_in, path_out=None):
    path_out = path_out or path_in
    tmp = path_out + '.tmp'
    changed = 0
    with zipfile.ZipFile(path_in) as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.startswith('xl/worksheets/sheet') and item.filename.endswith('.xml'):
                txt = data.decode('utf-8')
                new = txt
                for fn in MODERN:
                    # 补齐前缀：前面不是 _xlfn. 也不是其他标识符字符
                    new = re.sub(r'(?<!_xlfn\.)(?<![A-Za-z0-9_.])' + re.escape(fn) + r'\(',
                                 '_xlfn.' + fn + '(', new)
                    # 去重：_xlfn._xlfn.X -> _xlfn.X
                    new = re.sub(r'_xlfn\.(?:_xlfn\.)+' + re.escape(fn), '_xlfn.' + fn, new)
                for fn in LEGACY_MUST_NOT_PREFIX:
                    new = re.sub(r'_xlfn\.(?:_xlfn\.)*' + re.escape(fn) + r'\(',
                                 fn + '(', new)
                if new != txt:
                    changed += 1
                data = new.encode('utf-8')
            zout.writestr(item, data)
    shutil.move(tmp, path_out)
    return changed


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    n = patch(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print('patched sheets:', n)
