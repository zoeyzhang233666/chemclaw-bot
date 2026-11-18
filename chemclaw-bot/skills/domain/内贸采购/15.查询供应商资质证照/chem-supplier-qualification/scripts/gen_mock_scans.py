# -*- coding: utf-8 -*-
"""gen_mock_scans.py — 生成明确标注「模拟件」的演示扫描件（SVG，无第三方依赖）

纪律：
  * 每一页都有 45° 水印、页眉红条与页脚声明，明确写出「模拟演示件 · 非真实证照」；
  * 证照编号等字段一律使用 SAMPLE / MOCK 前缀，避免被误认为真实编号；
  * 不得用于任何对外提交、备案或凭证场景。

用法： python gen_mock_scans.py --out ../examples/hydrogen-peroxide-30/scans
"""

import argparse
import os
import sys

DPI = 96
W, H = 860, 1200


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def page(title, issuer, rows, footer, stamp_seal=True, table_head=None):
    """rows: [(label, value)] ；table_head=['许可范围', '...'] 时 rows 为 list 的 list"""
    head_h = 120
    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H))
    out.append('<defs>')
    out.append('<pattern id="wm" width="300" height="160" patternUnits="userSpaceOnUse" patternTransform="rotate(-28)">'
               '<text x="0" y="80" font-family="Microsoft YaHei,SimHei" font-size="26" fill="#b3402a" '
               'fill-opacity="0.16" letter-spacing="4">模拟演示件 · 非真实证照</text></pattern>')
    out.append('<linearGradient id="hd" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#12312a"/>'
               '<stop offset="1" stop-color="#1b4239"/></linearGradient>')
    out.append('</defs>')
    out.append('<rect width="%d" height="%d" fill="#fdfcf7"/>' % (W, H))
    out.append('<rect width="%d" height="%d" fill="url(#wm)"/>' % (W, H))
    # 边框
    out.append('<rect x="26" y="26" width="%d" height="%d" fill="none" stroke="#a8843c" stroke-width="2"/>' % (W - 52, H - 52))
    # 顶部警示条
    out.append('<rect x="0" y="0" width="%d" height="46" fill="#b3402a"/>' % W)
    out.append('<text x="30" y="30" font-family="Microsoft YaHei,SimHei" font-size="19" font-weight="bold" fill="#ffffff" '
               'letter-spacing="2">⚠ 模拟演示件 SAMPLE — 仅供技能模板演示，不得作为真实证照使用</text>')
    out.append('<text x="30" y="86" font-family="Microsoft YaHei,SimHei" font-size="15" fill="#8b1e1e">'
               'MOCK DOCUMENT · NOT A VALID CERTIFICATE · FOR TEMPLATE DEMONSTRATION ONLY</text>')
    # 标题
    out.append('<text x="%d" y="150" text-anchor="middle" font-family="SimSun,Microsoft YaHei" font-size="34" '
               'font-weight="bold" fill="#12312a" letter-spacing="6">%s</text>' % (W // 2, esc(title)))
    out.append('<line x1="150" y1="168" x2="%d" y2="168" stroke="#a8843c" stroke-width="1.5"/>' % (W - 150))
    out.append('<text x="%d" y="196" text-anchor="middle" font-family="Microsoft YaHei,SimHei" font-size="13" '
               'fill="#6d7a74">此页为结构示意，字段值均为样例，不代表任何真实企业</text>' % (W // 2))
    y = 240
    if table_head:
        out.append('<rect x="80" y="%d" width="%d" height="34" fill="#1b4239"/>' % (y, W - 160))
        cw = (W - 160) / float(len(table_head))
        for i, h in enumerate(table_head):
            out.append('<text x="%d" y="%d" font-family="Microsoft YaHei,SimHei" font-size="13" fill="#ffffff" '
                       'font-weight="bold">%s</text>' % (int(80 + cw * i + 10), y + 23, esc(h)))
        y += 34
        for i, row in enumerate(rows):
            f = "#fbfaf5" if i % 2 == 0 else "#f4f0e3"
            out.append('<rect x="80" y="%d" width="%d" height="30" fill="%s" stroke="#d9d3c3" stroke-width="0.6"/>'
                       % (y, W - 160, f))
            for j, cell in enumerate(row):
                out.append('<text x="%d" y="%d" font-family="Microsoft YaHei,SimHei" font-size="12" fill="#22302a">%s</text>'
                           % (int(80 + cw * j + 10), y + 20, esc(str(cell))))
            y += 30
        y += 20
    else:
        for label, value in rows:
            out.append('<text x="92" y="%d" font-family="Microsoft YaHei,SimHei" font-size="14.5" fill="#6d7a74">%s</text>'
                       % (y, esc(label)))
            # 值可能较长：按 26 字折行
            v = str(value)
            chunks = [v[i:i + 26] for i in range(0, len(v), 26)] or [""]
            for k, ck in enumerate(chunks):
                out.append('<text x="250" y="%d" font-family="Microsoft YaHei,SimHei" font-size="14.5" fill="#18231f">%s</text>'
                           % (y + k * 22, esc(ck)))
            y += 26 + 22 * (len(chunks) - 1)
            out.append('<line x1="92" y1="%d" x2="%d" y2="%d" stroke="#e2ded2" stroke-width="0.8"/>' % (y - 8, W - 92, y - 8))
            y += 8
    # 发证机关与日期
    y = max(y, H - 330)
    out.append('<text x="%d" y="%d" text-anchor="end" font-family="Microsoft YaHei,SimHei" font-size="15" fill="#18231f">%s</text>'
               % (W - 110, y, esc("发证机关：［样例占位］" + issuer)))
    out.append('<text x="%d" y="%d" text-anchor="end" font-family="Microsoft YaHei,SimHei" font-size="15" fill="#18231f">%s</text>'
               % (W - 110, y + 28, esc(footer)))
    # 印章（虚线、标注模拟）
    if stamp_seal:
        cx, cy, rr = W - 200, y + 130, 82
        out.append('<circle cx="%d" cy="%d" r="%d" fill="none" stroke="#b3402a" stroke-opacity="0.55" stroke-width="4" '
                   'stroke-dasharray="7 6"/>' % (cx, cy, rr))
        out.append('<text x="%d" y="%d" text-anchor="middle" font-family="Microsoft YaHei,SimHei" font-size="16" '
                   'fill="#b3402a" fill-opacity="0.7" font-weight="bold">模拟印章</text>' % (cx, cy - 4))
        out.append('<text x="%d" y="%d" text-anchor="middle" font-family="Microsoft YaHei,SimHei" font-size="11" '
                   'fill="#b3402a" fill-opacity="0.7">SAMPLE SEAL</text>' % (cx, cy + 18))
    # 页脚
    out.append('<rect x="0" y="%d" width="%d" height="60" fill="#f1ede1"/>' % (H - 70, W))
    out.append('<text x="%d" y="%d" text-anchor="middle" font-family="Microsoft YaHei,SimHei" font-size="11.5" fill="#6d7a74">'
               '由 chem-supplier-qualification 技能 generate_mock_scans.py 生成 · 仅用于演示"上传扫描件→OCR 字段提取→与公示比对"流程</text>'
               % (W // 2, H - 42))
    out.append('<text x="%d" y="%d" text-anchor="middle" font-family="Microsoft YaHei,SimHei" font-size="11.5" fill="#b3402a">'
               '任何情况下不得将该文件提交备案、作为凭证或对外宣称其为真实证照</text>' % (W // 2, H - 22))
    out.append('</svg>')
    return "\n".join(out)


def build_docs():
    docs = {}

    docs["01_营业执照_样例.svg"] = page(
        "营业执照（样例 · 副本）", "", [
            ("统一社会信用代码", "［样例］91330100MOCK0000000"),
            ("名称", "［样例］XX化工有限公司"),
            ("类型", "有限责任公司（自然人投资或控股）"),
            ("法定代表人", "［样例］张三"),
            ("注册资本", "3869 万人民币"),
            ("成立日期", "2007 年 11 月 07 日"),
            ("住所", "［样例］XX省XX市XX区XX路 000 号"),
            ("登记机关", "［样例］XX市市场监督管理局"),
        ], "登记日期：20XX 年 XX 月 XX 日（样例）",
        table_head=None)

    docs["02_危险化学品安全生产许可证_样例.svg"] = page(
        "危险化学品安全生产许可证（样例）", "样例省应急管理厅", [
            ["证照编号", "MOCK-WH安许-0000000（样例）", "有效期", "20XX-XX-XX 至 20XX-XX-XX（样例）"],
            ["企业名称", "［样例］XX化工有限公司", "许可范围", "［样例］过氧化氢溶液（含量＞8%）XXXX 吨/年"],
            ["生产地址", "［样例］XX园区", "发证机关", "样例省应急管理厅"],
        ], "发证日期：20XX 年 XX 月 XX 日（样例）",
        table_head=["字段", "样例内容", "字段", "样例内容"])

    docs["03_危险化学品经营许可证_样例.svg"] = page(
        "危险化学品经营许可证（样例 · 适用经营企业）", "样例市应急管理局", [
            ["证照编号", "MOCK-危化经字-0000000或非000000（样例）", "经营方式", "［样例］不带储存 / 带储存设施经营"],
            ["企业名称", "［样例］XX贸易有限公司", "许可范围", "［样例］易制爆化学品∶过氧化氢溶液〔含量＞8%〕"],
            ["经营地址", "［样例］XX市XX区", "有效期限", "20XX-XX-XX 至 20XX-XX-XX（样例）"],
        ], "发证日期：20XX 年 XX 月 XX 日（样例）",
        table_head=["字段", "样例内容", "字段", "样例内容"])

    docs["04_危险化学品登记证_样例.svg"] = page(
        "危险化学品登记证（样例）", "样例省危险化学品登记办公室", [
            ("证书编号", "［样例］MOCK-登记-000000"),
            ("企业名称", "［样例］XX化工有限公司"),
            ("企业性质", "［样例］危险化学品生产企业"),
            ("登记品种", "［样例］过氧化氢溶液（含量＞8%）"),
            ("有效期", "20XX 年 XX 月 XX 日 至 20XX 年 XX 月 XX 日（样例）"),
        ], "发证日期：20XX 年 XX 月 XX 日（样例）")

    docs["05_ISO9001质量体系认证_样例.svg"] = page(
        "质量管理体系认证证书（样例）", "样例认证机构", [
            ("证书编号", "［样例］MOCK-ISO9001-000000"),
            ("获证组织", "［样例］XX化工有限公司"),
            ("认证标准", "GB/T 19001-2016 / ISO 9001:2015"),
            ("覆盖范围", "［样例］过氧化氢溶液的生产"),
            ("有效期", "20XX 年 XX 月 XX 日 至 20XX 年 XX 月 XX 日（样例）"),
        ], "签发日期：20XX 年 XX 月 XX 日（样例）")

    docs["06_全国工业产品生产许可证_样例.svg"] = page(
        "全国工业产品生产许可证（样例）", "样例省市场监督管理局", [
            ("许可证编号", "［样例］MOCK-(X)-X-0000000"),
            ("企业名称", "［样例］XX化工有限公司"),
            ("产品名称", "［样例］危险化学品有机产品 \\\\ 无机产品"),
            ("有效期", "20XX 年 XX 月 XX 日 至 20XX 年 XX 月 XX 日（样例）"),
        ], "发证日期：20XX 年 XX 月 XX 日（样例）")

    docs["07_食品生产许可证_样例.svg"] = page(
        "食品生产许可证（样例 · 仅当采购食品添加剂级时相关）", "样例区市场监督管理局", [
            ("许可证编号", "［样例］SC00000000000000"),
            ("生产者名称", "［样例］XX化工有限公司"),
            ("食品类别", "［样例］食品添加剂（过氧化氢）"),
            ("有效期", "20XX 年 XX 月 XX 日 至 20XX 年 XX 月 XX 日（样例）"),
        ], "发证日期：20XX 年 XX 月 XX 日（样例）")

    docs["08_消毒产品生产企业卫生许可证_样例.svg"] = page(
        "消毒产品生产企业卫生许可证（样例 · 仅消毒剂类相关）", "样例省卫生健康委员会", [
            ("许可证编号", "［样例］X卫消证字（20XX）第 MOCK000 号"),
            ("单位名称", "［样例］XX化工有限公司"),
            ("生产类别", "［样例］液体消毒剂"),
            ("有效期", "20XX 年 XX 月 XX 日 至 20XX 年 XX 月 XX 日（样例）"),
        ], "发证日期：20XX 年 XX 月 XX 日（样例）")

    docs["09_易制爆购买备案_购买登记簿_样例.svg"] = page(
        "易制爆危险化学品购销台账 / 购买备案回执（样例）", "样例市公安局治安管理支队", [
            ["购买单位", "［样例］XX新材料有限公司", "销售单位", "［样例］XX化工有限公司"],
            ["品种", "过氧化氢溶液(含量＞8%)", "CAS", "7722-84-1"],
            ["数量", "［样例］30 t", "流向", "［样例］XX市XX区 XX 厂区"],
            ["备案编号", "MOCK-易制爆备-000000（样例）", "备案日期", "购买后 5 日内（样例）"],
        ], "经办人：［样例］李四　签名：________（样例）",
        table_head=["字段", "样例内容", "字段", "样例内容"])

    return docs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    docs = build_docs()
    for name, svg in docs.items():
        with open(os.path.join(a.out, name), "w", encoding="utf-8") as f:
            f.write(svg)
    print("mock scans -> %s (%d files)" % (a.out, len(docs)))


if __name__ == "__main__":
    main()
