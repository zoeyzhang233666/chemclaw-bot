# 示例索引

| 目录 | 类型 | 用途 |
|---|---|---|
| `01-soda-ash-guangdong-jiangmen/` | 真实案例 | 看成品、看研究逻辑、看证据链；17 家/22 厂/3,070 万吨样本 |
| `02-minimal-template/` | 全虚构结构示例 | 复制字段、跑通流程、回归测试；3 家/3 厂/340 万吨 |

## 先看哪个

- 第一次用：先看 `01` 的 HTML 和 Excel，知道“交付长什么样”；
- 要动手：复制 `02/data.json`，按 `references/data-contract.md` 填；
- 改代码：两个都跑，确认通用性。

## 命令

```bash
python scripts/validate.py examples/01-soda-ash-guangdong-jiangmen/data.json
python scripts/build_all.py examples/01-soda-ash-guangdong-jiangmen/data.json examples/01-soda-ash-guangdong-jiangmen
python scripts/qa.py --data examples/01-soda-ash-guangdong-jiangmen/data.json \
  --html examples/01-soda-ash-guangdong-jiangmen/纯碱_广东江门_竞争供给地图.html \
  --xlsx examples/01-soda-ash-guangdong-jiangmen/纯碱_广东江门_竞争供给地图.xlsx
```

`02` 同理，替换路径即可。

> 示例 02 是结构示例，不是研究结论；示例 01 的数字也不能直接复用到别的产品/区域。
