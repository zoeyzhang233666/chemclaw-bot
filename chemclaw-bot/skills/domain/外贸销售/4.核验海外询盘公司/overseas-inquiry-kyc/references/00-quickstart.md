# 00 · 快速开始（30 分钟从一封邮件到两份附件）

## 0. 检查环境（1 分钟）

```bash
python -c "import openpyxl; print(openpyxl.__version__)"   # 需要 >= 3.1
python scripts/validate.py examples/id-soda-ash-demo/inquiry.json   # 应当 0 error
```

没有 openpyxl：`python -m pip install -r requirements.txt`。
不要用 CSV 或空文件冒充 xlsx。

## 1. 复制骨架（1 分钟）

```bash
cp -r examples/_skeleton work/my-inquiry
# 或直接复制印尼案例，把主体改成你的询盘方
cp -r examples/id-soda-ash-demo work/my-inquiry
```

## 2. 填六个必填块（15 分钟）

只填这六块就能出报告，其余块留空也不报错：

| 块 | 最少要填什么 |
|---|---|
| `meta` | `title` / `as_of` / `synthetic` / `synthetic_note`（模拟时）/ `product` |
| `inquiry` | `subject` / `from` / `body_lines` |
| `extraction` | 公司名、地址、网站、域名、邮箱、联系人、产品、数量 8 条起 |
| `checks` | A/B/C/D 区块各 3 条以上，状态分开写 |
| `sources` | 至少 1 条 A 级（官方）+ 1 条 D 级（对方自述） |
| `requests` | 至少 3 条 P0 |

> 秘诀：**先把 `checks` 写满，再回头补 `sources`。**
> 校验器会逼你给每条"已核实"挂来源——这正是我们想要的效果。

## 3. 生成（3 分钟）

```bash
python scripts/build_all.py work/my-inquiry/inquiry.json work/my-inquiry/out --name 印尼客户A
```

产出：

```
out/印尼客户A_核验报告.html     # 双击即可看
out/印尼客户A_核验工作簿.xlsx
out/build_report.json
```

## 4. 自检（2 分钟）

```bash
python scripts/selfcheck.py work/my-inquiry/inquiry.json --outdir work/my-inquiry/out
```

全部通过后，打开 HTML 手工看三件事：

1. 顶部横幅是否正确（模拟样例会显示"模拟样例"）；
2. 点任一来源标签能否弹出抽屉、里面有没有链接；
3. `待补充资料` 区的英文话术能否复制（点"复制全文"）。

## 5. 交付前最后一个动作

把 `build_report.json` 里的 `warnings` 读一遍。通常会有两类：

- `Kxx 没有关联来源` → 那条大概率还没做完检索，属于正常；
- `B 区块没有已核实项` → 业务相关性判断还没落地，需要补一条。

## 常见卡点

| 症状 | 处方 |
|---|---|
| `validate` 报 `已核实但没有 source_ids` | 给那条挂来源，或把它改成 `unverified` |
| 报 `疑点但没有 boundary` | 补一句"为什么它还不算致命" |
| `xlsx` 打开一片空白 | 检查是否装了 openpyxl、是否用了 CSV |
| HTML 打开是源码 | 文件名后缀必须是 `.html`，且用浏览器打开而不是编辑器 |
| 想改成西班牙语/印尼语 | 只改 `messages[].body_en` 字段内容，其余不用动 |

## 想换国家？

只动三处：`subject.*.portal`、`sources[]` 的官方链接、`requests[]` 要的证照名称。
框架不动。读 `references/country-playbook/generic.md` 的五步法。
