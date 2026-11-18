# 安装与使用（Install）

本 Skill 是**纯文本 + 脚本**的目录包，无二进制依赖、无网络服务、不需要安装数据库。

---

## 一、放到哪里

把整个 `overseas-buyer-discovery/` 目录放进 DSH 的 skills 根目录即可：

```
<skills 根目录>/
└─ 外贸销售/
   └─ 3.找海外候选买家/          ← 把包内文件直接放在这里（或放 overseas-buyer-discovery/ 子目录）
      ├─ SKILL.md
      ├─ README.md
      ├─ references/
      ├─ templates/
      ├─ examples/
      ├─ scripts/
      └─ assets/
```

DSH 通过 `SKILL.md` 顶部的 frontmatter（`name` / `description`）发现技能，`description` 里的中文触发词决定它何时被自动加载。**不要修改 `name` 字段**，否则调用会失败。

---

## 二、依赖

| 依赖 | 是否必需 | 说明 |
|---|---|---|
| Python 3.9+ | 生成 HTML / XLSX 时必需 | 只用标准库 + `openpyxl` |
| `openpyxl` | 生成 XLSX 时必需 | `pip install openpyxl` |
| PowerShell 5.1+ | 用自带抓取脚本时必需 | Windows 自带 |
| `pypdf` | 解析年报 PDF 时必需 | `pip install pypdf` |
| Playwright + Chromium | **仅**做视觉验收时需要 | 可选，见下 |

只做研究和出报告，不跑自带脚本的话，真正必需的只有 Python + openpyxl。

---

## 三、自带脚本怎么用

```bash
# 1) 抓一个页面（Windows）
scripts\web_cmd.cmd -Mode fetch -Url https://example.co.id -Max 3000

# 2) 批量抓（把一个 URL 一行写进 urls.txt）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\fetch_many.ps1 ^
    -InFile urls.txt -Max 3000 -OutDir fetchout

# 3) 合并各 lane 的 JSON 成统一线索文件
python scripts\merge_leads.py

# 4) 一键生成报告 + 工作簿（含数据校验）
python scripts\run_all.py <工作目录>
```

`run_all.py` 会先校验 `leads_merged.json`（必填字段、等级合法性、证据是否有链接、有无个人手机号），有硬伤直接中止而不是生成半成品。

---

## 四、Windows 下的三个必须注意

1. **中文编码**：写含中文的脚本时不要用 `Out-File` / `Set-Content`，会按 GBK 编码把中文毁掉。用 Python 或编辑工具写。控制台先执行 `$env:PYTHONIOENCODING="utf-8"`。
2. **执行策略**：`.ps1` 可能被策略阻止，所以包里配了 `web_cmd.cmd` 包装器（内部用 `-ExecutionPolicy Bypass`）。
3. **模板格式化**：HTML 模板别用 `%` 或 f-string，用 `{{占位符}}` + `str.replace`，否则正文里的 `99.2%` 会触发格式化错误。

---

## 五、视觉验收（可选）

```powershell
pip install playwright
python -m playwright install chromium
```

然后用 `assets/qa_report.py` 检查：

- 四种宽度（1440/1024/768/390）无横向溢出
- 无 JS 报错
- 卡片数 = 线索数
- 筛选、展开、保存线索、生成邮件四个交互可用

---

## 六、快速自检

装好后问一句：

> 帮我找印尼的重质纯碱买家

如果 Skill 被正确加载，它应当先**反问任务契约**（产品规格、目标客户类型、优先产业、交付形式），而不是直接开始搜公司名。
