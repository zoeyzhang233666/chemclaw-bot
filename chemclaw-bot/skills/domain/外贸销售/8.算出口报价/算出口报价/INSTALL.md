# 安装与放置

## 方式一：放进 DSH Skill 目录（推荐）

1. 解压 `算出口报价.zip`
2. 把整个 `算出口报价` 文件夹放入：

```
../../..\外贸销售\8.算出口报价\
```

最终结构应为：

```
../../..\外贸销售\8.算出口报价\
├── SKILL.md
├── README.md
├── references\
├── scripts\
└── ...
```

> 注意：是**文件夹本身**放进去，不要多套一层 `算出口报价\算出口报价\`。

## 方式二：任意位置使用

脚本全部使用相对自身路径，把文件夹放在任何位置都能直接运行：

```bash
python "任意路径\算出口报价\scripts\calc_engine.py" input.json -o result.json
```

## 方式三：只用 HTML

不需要装任何东西。直接双击 `examples\soda-ash-qingdao-jakarta\output\出口报价计算器_*.html`，
用浏览器打开即可完整使用（可改参数、看公式、做敏感性、生成草稿）。

---

## 依赖安装

```bash
pip install openpyxl      # 只有生成 Excel 才需要
```

Python 自带 `json` / `argparse` / `dataclasses`，无需其他包。

---

## 验证安装

```bash
python scripts/selfcheck.py
```

全绿输出表示：引擎、HTML 生成、Excel 生成、恒等式校验全部正常。

---

## Windows 中文显示

命令行如出现中文乱码，先执行：

```powershell
$env:PYTHONIOENCODING="utf-8"
```

不影响计算结果，只影响控制台显示。
