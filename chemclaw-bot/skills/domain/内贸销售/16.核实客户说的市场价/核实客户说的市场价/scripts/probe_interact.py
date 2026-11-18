# -*- coding: utf-8 -*-
"""probe_interact.py — 在无头 Chrome 里真的点一遍报告，验证交互功能。

不是看截图，而是注入脚本执行：
  · 改客户价 → KPI 偏离金额与结论跟着变
  · 切换地区 → 市场区间跟着变
  · 点「事实要点 / 微信 / 邮件」→ 有输出文本
  · 合规提示出现

结果写到 DOM 里的 #__probe，再 dump 出来读。
"""
import io
import os
import subprocess
import sys

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

JS = r"""
setTimeout(function(){
  var out=[];
  function t(id){var e=document.getElementById(id);return e?e.innerText.replace(/\s+/g," ").trim():"<none>";}
  function val(id){var e=document.getElementById(id);return e?(e.value||""):"";}
  try{
    out.push("初始 | K1="+t("k1")+" | K3="+t("k3")+" | 结论="+t("verdictBox").slice(0,40));

    var c=document.getElementById("inCust");
    c.value=1150; c.dispatchEvent(new Event("input",{bubbles:true}));
    out.push("客户价1150 | K1="+t("k1")+" | K2="+t("k2")+" | 结论="+t("verdictBox").slice(0,40));

    c.value=900; c.dispatchEvent(new Event("input",{bubbles:true}));
    out.push("客户价900  | K1="+t("k1")+" | 结论="+t("verdictBox").slice(0,40));

    c.value=1400; c.dispatchEvent(new Event("input",{bubbles:true}));
    out.push("复原1400   | 结论="+t("verdictBox").slice(0,40));

    var r=document.getElementById("inRegion");
    if(r&&r.options.length>1){
      r.selectedIndex=1; r.dispatchEvent(new Event("change",{bubbles:true}));
      out.push("地区→"+r.value+" | K3="+t("k3"));
      r.selectedIndex=0; r.dispatchEvent(new Event("change",{bubbles:true}));
    }

    document.getElementById("btnBrief").click();
    out.push("事实要点 chars="+val("talkOut").length+" 首句="+val("talkOut").slice(0,60));

    document.getElementById("btnWx").click();
    out.push("微信 chars="+val("talkOut").length);

    document.getElementById("btnMail").click();
    out.push("邮件 chars="+val("talkOut").length);

    out.push("提示="+t("talkWarn").slice(0,80));
  }catch(e){ out.push("ERR: "+e.message); }
  var d=document.createElement("div");
  d.id="__probe";
  d.textContent=out.join(" ##@ ");
  document.body.appendChild(d);
},2600);
"""


def main():
    html = sys.argv[1]
    src = io.open(html, encoding="utf-8").read()
    # 临时页写到系统临时目录，不能落在 out/ 里污染交付目录
    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="dsh_probe_")
    tmp = os.path.join(tmpdir, "__probe_page.html")
    # 页面里内联的 ECharts 源码中可能含 "</body>" 字样，必须插入到最后一个之前
    k = src.rfind("</body>")
    patched = src[:k] + "<script>" + JS + "</script>" + src[k:] if k >= 0 else src + "<script>" + JS + "</script>"
    io.open(tmp, "w", encoding="utf-8").write(patched)
    url = "file:///" + tmp.replace("\\", "/")
    p = subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-sandbox",
                        "--virtual-time-budget=14000", "--dump-dom", url],
                       capture_output=True)
    dom = p.stdout.decode("utf-8", "replace")
    # 内联的 ECharts 源码里含 "</div>" 字样，regex 会错位，改用 div 嵌套计数
    idx = dom.find('id="__probe"')
    if idx < 0:
        print("[x] 探针未执行（页面脚本可能报错）")
        return 1
    start = dom.find(">", idx) + 1
    depth, i = 1, start
    while i < len(dom) and depth:
        if dom.startswith("<div", i):
            depth += 1
            i += 4
        elif dom.startswith("</div>", i):
            depth -= 1
            i += 6 if depth else i
            if depth == 0:
                break
        else:
            i += 1
    body = dom[start:i]
    import html as _h
    for line in _h.unescape(body).split("##@"):
        line = line.strip()
        if line:
            print("  " + line)
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
