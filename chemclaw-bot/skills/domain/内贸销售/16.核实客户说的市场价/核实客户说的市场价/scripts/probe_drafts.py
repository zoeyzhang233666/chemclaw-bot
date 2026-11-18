# -*- coding: utf-8 -*-
"""probe_drafts.py — 把三个按钮生成的全文导出来看，检查措辞是否越界。"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

JS = r"""
setTimeout(function(){
  var o=[];
  function grab(id){var e=document.getElementById(id);return e?(e.value!=null?e.value:e.innerText):"";}
  ["btnBrief","btnWx","btnMail"].forEach(function(b){
    document.getElementById(b).click();
    o.push("====="+b+"=====\n"+grab("talkOut")+"\n[提示]"+grab("talkWarn"));
  });
  var d=document.createElement("pre");
  d.id="__drafts";
  d.textContent=o.join("\n");
  document.body.appendChild(d);
},2600);
"""


def main():
    html = sys.argv[1]
    outdir = os.path.dirname(os.path.abspath(html))
    src = io.open(html, encoding="utf-8").read()
    # 临时页写到系统临时目录，不能落在 out/ 里污染交付目录
    tmpdir = tempfile.mkdtemp(prefix="dsh_draft_")
    tmp = os.path.join(tmpdir, "__drafts_page.html")
    # 内联 ECharts 源码里含 "</body>" 字样，插入到最后一个之前
    k = src.rfind("</body>")
    patched = src[:k] + "<script>" + JS + "</script>" + src[k:] if k >= 0 else src + "<script>" + JS + "</script>"
    io.open(tmp, "w", encoding="utf-8").write(patched)
    p = subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-sandbox",
                        "--virtual-time-budget=12000", "--dump-dom",
                        "file:///" + tmp.replace("\\", "/")], capture_output=True)
    dom = p.stdout.decode("utf-8", "replace")
    # 页面里内联脚本自身就含 '__drafts' 字样，必须定位「真正的元素」：
    # 取最后一个 <pre id="__drafts">（我们追加的元素在 body 末尾）。
    marks = [m.start() for m in __import__("re").finditer(r'<pre[^>]*id="__drafts"', dom)]
    if not marks:
        print("[x] 未取到草稿")
        return 1
    i = marks[-1]
    start = dom.find(">", i) + 1
    end = dom.rfind("</pre>")
    if end <= start:
        print("[x] 草稿块解析失败")
        return 1
    import html as _h
    txt = _h.unescape(dom[start:end])
    print(txt)

    # 合规扫描：只扫草稿正文，去掉「[提示]」行（那是工具自己的免责声明，不是发给客户的文字）
    body = "\n".join(ln for ln in txt.splitlines() if not ln.strip().startswith("[提示]"))
    bad = ["底价", "让价", "优惠", "返点", "承诺", "保证", "一定", "最低", "独家",
           "下单即", "抄底", "建议报价", "可以降到", "打折", "包您"]
    hit = [w for w in bad if w in body]
    print("\n" + "=" * 50)
    print(f"草稿正文字数：{len(body)}")
    print("草稿正文中的禁用/承诺类措辞：", hit if hit else "无 ✓")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out-drafts-check.txt")
    io.open(os.path.normpath(out), "w", encoding="utf-8").write(txt)
    print("（草稿全文另存，便于逐字复核）")
    shutil.rmtree(tmpdir, ignore_errors=True)
    try:
        os.remove(out)          # 自检用，不留在技能包里
    except OSError:
        pass
    return 0 if not hit else 2


if __name__ == "__main__":
    sys.exit(main())
