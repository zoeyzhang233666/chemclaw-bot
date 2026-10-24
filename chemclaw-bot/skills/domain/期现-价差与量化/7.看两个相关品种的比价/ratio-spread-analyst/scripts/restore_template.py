# -*- coding: utf-8 -*-
"""
restore_template.py — 把已填充的 report.html 还原成带 /*__DATA__*/ 占位符的模板
================================================================================
build_html.py 会把数据注入模板。如果直接用填充后的文件当模板，
下次 build 就会在一个已经含数据的文件上再替换一次（占位符已不存在，替换无效，
但文件会带着旧数据）。

这个脚本把 `const DATA = {...};` 换回占位符，得到一个干净的可复用模板。
"""
import re
import sys


def restore(src, dst):
    with open(src, encoding="utf-8") as f:
        html = f.read()
    # 匹配 const DATA = {...};  并替换回占位符
    pat = re.compile(r"const DATA = \{[\s\S]*?\};\s*\n</script>")
    new, n = pat.subn("const DATA = /*__DATA__*/null;\n</script>", html)
    if n != 1:
        print("WARN: 匹配到 %d 处 const DATA（期望 1 处）" % n)
        if n == 0:
            return False
    with open(dst, "w", encoding="utf-8") as f:
        f.write(new)
    print("restored template: %s  (%.0f KB)" % (dst, len(new.encode("utf-8")) / 1024))
    # 自检：必须不含真实数据、必须含占位符
    ok_ph = "/*__DATA__*/" in new
    ok_clean = "1.0744900" not in new
    print("  has placeholder:", ok_ph, " no stale data:", ok_clean)
    return ok_ph and ok_clean


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "build/report.html"
    dst = sys.argv[2] if len(sys.argv) > 2 else "assets/templates/ratio-report-template.html"
    sys.exit(0 if restore(src, dst) else 3)
