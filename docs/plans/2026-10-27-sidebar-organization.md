# 侧栏分类折叠、拖拽与关注排序

Issue #38。宽侧栏已有按种子分类分区，但分类不能折叠、行不能拖拽重排，也没有把业务关注分类提前的偏好。

## 行为

| 能力 | 行为 |
| --- | --- |
| 分类折叠 | 宽侧栏分类标题可点；折叠状态写入 `prefs.sidebar.collapsed`（稳定 id，非译文） |
| 拖拽 | 拖分类标题改分类顺序；拖行改分类内顺序；Main Bot 固定最上；顺序写入 `prefs.sidebar.categoryOrder` / `itemOrder` |
| 排序模式 | `recent`（默认）/ `manual` / `focus`（关注分类置顶，组内仍按最近或手动） |
| 业务偏好 | 设置 → 外观「侧栏关注分类」多选；写入 `prefs.sidebar.focus` |
| 窄轨 | 无折叠与拖拽 chrome，保持现有密度 |

稳定分类 id：`rooms`、`agents`、种子 `templateInfo.category`（缺省时用角色名，再缺省用 `specialists`）。

## 视觉约束

- 延续 `.bt-side` / `.bt-list` / `.bt-directory-label` / `.bt-row` 的字号、行高与边距。
- 折叠箭头与计数同排；把手默认低对比，hover/焦点才明显；拖拽用细线插入指示，无厚阴影或彩色描边。
- 设置页用现有 `SetRow` / `Choice` / chip 节奏，不另起管理面板。

## 非目标

不重做侧栏信息架构；不在窄轨上做折叠/拖拽。
