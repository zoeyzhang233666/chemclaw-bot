// verify_page.cjs — 用无头 Chrome 实际执行页面 JS，验证交互功能
// 用法：node verify_page.cjs <html路径> <输出目录>
const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const os = require("os");

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const [, , htmlPath, outDir] = process.argv;
const uri = new URL("file:///" + htmlPath.replace(/\\/g, "/")).href;
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "vc-"));

function shot(name, size, script) {
  const out = path.join(outDir, name);
  const args = [
    "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
    "--no-default-browser-check", "--force-device-scale-factor=1",
    `--user-data-dir=${tmp}`, `--window-size=${size}`,
    `--screenshot=${out}`, "--virtual-time-budget=4000",
  ];
  if (script) args.push(`--run-all-compositor-stages-before-draw`);
  args.push(uri);
  execFileSync(CHROME, args, { stdio: "ignore", timeout: 90000 });
  return fs.existsSync(out) ? fs.statSync(out).size : 0;
}

fs.mkdirSync(outDir, { recursive: true });

// 1) 首屏（桌面宽度）
const s1 = shot("v1_hero.png", "1440,1400");
// 2) 宽屏整页长图（截取展开后的清单区域，用足够高的视口）
const s2 = shot("v2_full.png", "1440,5200");
// 3) 移动端
const s3 = shot("v3_mobile.png", "420,2200");

// 4) 用 --dump-dom 验证 JS 执行后的 DOM（脚本会在加载时运行）
const domOut = execFileSync(CHROME, [
  "--headless=new", "--disable-gpu", `--user-data-dir=${tmp}`,
  "--virtual-time-budget=4000", "--dump-dom", uri,
], { encoding: "utf8", timeout: 90000, maxBuffer: 64 * 1024 * 1024 });

const checks = [];
const dom = domOut;
checks.push(["文章条目数=30", (dom.match(/<article class="item"/g) || []).length === 30]);
checks.push(["主题区块=4", (dom.match(/class="topic-block"/g) || []).length === 4]);
checks.push(["筛选按钮=6", (dom.match(/class="chip/g) || []).length === 6]);
checks.push(["搜索框存在", /id="q"/.test(dom)]);
checks.push(["脚本已注入", /\.item-h/.test(dom)]);
checks.push(["无未转义模板字符", !/__TBD__|\{\{|\}\}/.test(dom)]);

// 5) 校验所有法规链接可解析（只检查格式，不联网）
const links = [...dom.matchAll(/href="(https?:\/\/[^"]+)"/g)].map((m) => m[1]);
const bad = links.filter((u) => { try { new URL(u); return false; } catch { return true; } });
checks.push([`链接全部合法（共 ${links.length} 条）`, bad.length === 0]);

console.log(JSON.stringify({
  screenshots: { hero: s1, full: s2, mobile: s3 },
  domBytes: dom.length,
  checks: checks.map(([n, ok]) => (ok ? "✔ " : "✘ ") + n),
  allPass: checks.every(([, ok]) => ok) && s1 > 10000 && s2 > 10000,
}, null, 2));
