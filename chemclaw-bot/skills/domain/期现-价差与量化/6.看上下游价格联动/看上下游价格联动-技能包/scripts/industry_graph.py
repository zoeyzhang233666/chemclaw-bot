# -*- coding: utf-8 -*-
"""
industry_graph.py —— 生成 PX→PTA 产业关系图（内联 SVG，无外部依赖）

图形表达（自上而下，宽度表示流量）：
  原油 → 石脑油 → 重整/MX → PX ──0.655 t/t──> PTA ──> 聚酯(PET) ──> 涤纶/瓶片/薄膜
                                  │              │
                     其他方向(约 X%)         其他方向(约 Y%)
标注：
  - 每条流股的「单耗/占比」都必须有出处，无出处的用「未核实」而非填数。
  - 原料侧：PX 是 PTA 的唯一主要原料（另有醋酸 0.03-0.04 t/t 为辅料/溶剂）；
    不存在第二条主要原料路线（对比：丙烯酸、乙二醇等品种有煤基/油基多路线）。
"""
import os
import sys


def svg_industry(w=980, h=430):
    """返回 SVG 字符串。颜色与 HTML 主题一致。"""
    G = [
        # 阶段块
        ('原油', 20, 60, 60, '#3a4658', '#cfe6ff'),
        ('石脑油 / 重整', 110, 60, 96, '#3a4658', '#cfe6ff'),
        ('MX 混合二甲苯\n吸附分离/结晶', 236, 60, 110, '#3a4658', '#cfe6ff'),
        ('PX 对二甲苯', 376, 50, 112, '#1f6feb', '#eaf3ff'),
        ('PTA 精对苯二甲酸', 376, 190, 112, '#1f6feb', '#eaf3ff'),
        ('聚酯 PET', 376, 330, 90, '#2f7d5a', '#e6fff2'),
        ('涤纶长丝/短纤\n瓶片/薄膜', 520, 330, 96, '#2f7d5a', '#e6fff2'),
    ]
    out = [f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img" '
           f'aria-label="PX-PTA 产业关系图" style="width:100%;height:auto">',
           '<defs>'
           '<marker id="ar" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">'
           '<path d="M0,0 L0,6 L9,3 z" fill="#5b7288"/></marker>'
           '</defs>']
    # 连接线（先画线，后画块，避免遮挡）
    # 原油→石脑油→MX→PX 横向
    out.append('<line x1="80" y1="90" x2="110" y2="90" stroke="#5b7288" stroke-width="2" marker-end="url(#ar)"/>')
    out.append('<line x1="206" y1="90" x2="236" y2="90" stroke="#5b7288" stroke-width="2" marker-end="url(#ar)"/>')
    out.append('<line x1="346" y1="90" x2="376" y2="90" stroke="#5b7288" stroke-width="2" marker-end="url(#ar)"/>')
    # PX→PTA（主链路，粗线 + 单耗标签）
    out.append('<line x1="432" y1="162" x2="432" y2="190" stroke="#1f6feb" stroke-width="5" marker-end="url(#ar)"/>')
    out.append('<text x="444" y="182" font-size="13" fill="#8fd3ff">PX 0.655 t/t PTA</text>')
    out.append('<text x="444" y="200" font-size="11.5" fill="#93a1b5">＋醋酸 0.030~0.039 t/t（溶剂/辅料）</text>')
    # PTA→聚酯
    out.append('<line x1="432" y1="302" x2="432" y2="330" stroke="#2f7d5a" stroke-width="5" marker-end="url(#ar)"/>')
    out.append('<text x="444" y="322" font-size="13" fill="#8fe0b8">PTA ＋乙二醇(MEG) 缩聚</text>')
    # 聚酯→下游
    out.append('<line x1="472" y1="375" x2="520" y2="375" stroke="#5b7288" stroke-width="2" marker-end="url(#ar)"/>')
    # 侧支：PX 其他用途
    out.append('<line x1="432" y1="162" x2="620" y2="90" stroke="#5b7288" stroke-width="1.6" stroke-dasharray="5 4" marker-end="url(#ar)"/>')
    out.append('<text x="628" y="86" font-size="12" fill="#93a1b5">PX 其他下游：DMT/PT酸、涂料、医药中间体（占比较小）</text>')
    # 侧支：PTA 其他用途
    out.append('<line x1="488" y1="246" x2="620" y2="230" stroke="#5b7288" stroke-width="1.6" stroke-dasharray="5 4" marker-end="url(#ar)"/>')
    out.append('<text x="628" y="226" font-size="12" fill="#93a1b5">PTA 其他：约 90% 以上用于聚酯（PET）</text>')
    out.append('<text x="628" y="244" font-size="12" fill="#93a1b5">其中聚酯纤维约 75%，瓶片约 20%（国内口径）</text>')

    for txt, x, y, bh, fill, fc in G:
        lines = txt.split('\n')
        bw = 150 if max(len(l) for l in lines) > 8 else 120
        out.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="10" fill="{fill}" '
                   f'stroke="rgba(255,255,255,.18)"/>')
        for k, ln in enumerate(lines):
            fs = 13 if k == 0 else 11.5
            out.append(f'<text x="{x + bw/2}" y="{y + 24 + k * 16}" font-size="{fs}" fill="{fc}" '
                       f'text-anchor="middle" font-weight="600">{ln}</text>')

    # 图例
    out.append(f'<text x="20" y="{h-28}" font-size="12" fill="#93a1b5">实线＝主工艺链；虚线＝次要流股；'
               f'蓝色块＝本研究标的；单耗数字均标注来源（见 references/02-工艺与单耗台账.md）</text>')
    out.append(f'<text x="20" y="{h-10}" font-size="12" fill="#93a1b5">注：PX 是 PTA 唯一主要原料；'
               f'不存在第二条主要原料替代路线，故 PX 单耗可靠、可计算理论加工价差。</text>')
    out.append('</svg>')
    return '\n'.join(out)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) > 1:
        open(sys.argv[1], 'w', encoding='utf-8').write(svg_industry())
        print('written', sys.argv[1])
    else:
        print(svg_industry()[:400])
