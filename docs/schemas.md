# Schema

> **manifest 是 patch 元数据单一权威**。`series[]`（总是 on）+ `extras[]`（按 self_contained 单开关决定是否裸跑）。CI 双跑验可重放。编译由各仓自带脚本负责。

## 目录

```
boostkit-rabitq/
├── tools/                 # apply_patch.sh (单入口) + _patches.py + lint.py
├── docs/                  # schemas.md + usage.md
└── src/<V>/               # 一个上游版本一个子目录（自包含）
    ├── manifest.yaml      # ★ 唯一权威
    ├── series/            # 普通 patches (总是 on, 字典序 apply)
    └── extras/<id>/       # 鲲鹏特定 extras (可单独开关, 每 extra 一个子目录)
```

## 1. 顶层

| 字段 | 必填 | 语义 |
|------|:--:|------|
| `upstream_url` | 是 | 上游 git URL |
| `release` | 是 | 上游 tag 或 `snapshot-YYYY-MM-DD`；**禁止**写 `main`/`develop`/`master` |
| `pin_commit` | 是 | 40-char SHA，与 release 对应的固定 commit |

> ~~`install`~~ 已废弃（编译由各仓自带脚本负责）。

## 2. series[] + extras[] 字段对照

| 字段 | series | extras | 必填 | 备注 |
|------|:------:|:------:|:--:|------|
| **entry 标识**¹ | `id` | `extra_id` | 是 | kebab-case；extras 用 `extra_id` 区分 |
| **开关字段**² | — | `self_contained` | 是 | series 总是 on（无开关）；extras 必填，详见下方 |
| `file` / `files[]`³ | `file` | `files[]` | 是 | 相对 manifest 目录；series 单文件 string，extras 多文件 list |
| `title` | — | `title` | 否（extras） | series 无；extras 人类可读描述 |
| `author` | `author` | `author` | 是 | email |
| `date` | `date` | `date` | 是 | YYYY-MM-DD |
| `upstream_status`⁴ | `upstream_status` | `upstream.upstream_status` | 是 | 6 态 enum（见 §4）；**extras 字段位于 `upstream.` 嵌套块** |
| `notes` | `notes` | `upstream.notes` | 条件 | Inappropriate/Denied/Backport 必填，≥10 字符 |
| `upstream_pr` | `upstream_pr` | `upstream.upstream_pr` | 条件 | Pending/Submitted 必填（URL） |
| `merged_commit` | `merged_commit` | `upstream.merged_commit` | 条件 | Accepted 必填（40-char SHA） |
| `depends_on`⁵ | `depends_on` | — | 否 | `series:<id>` 或 `<id>`；DFS 环检测；**extras 禁止** |
| `conflicts_with` | `conflicts_with` | — | 否 | list[string]；extras 禁止 |

**注释**：

- **¹ entry 标识**：series 用 `id`，extras 用 `extra_id`（命名区分）。**`extra_id` 即子目录名**（`extras/<extra_id>/...`）。
- **² 开关字段**：series 总是 on，无开关字段。extras **唯一开关**是 `self_contained`：
  - `true` = 纯 upstream 可重放（CI 默认 apply）
  - `false` = 依赖下游 build（CI 默认跳过，`BOOTSTRAP_NON_BUILDABLE=1` 强制包含）
  - 运行时覆盖：`DISABLED_EXTRAS=neq,eqv` env（无视 `self_contained: true`）
- **³ patch files**：series 是单个 string `file: series/0001-x.patch`；extras 是 list `files: [{file: extras/neq/0001-x.patch}, ...]`，字典序 apply。
- **⁴ upstream_status 位置**：series 平铺在 entry 顶层；extras 在 `upstream.` 嵌套块（`upstream.upstream_status`）。**extras patch 无独立 status**，继承所属 extra 的 `upstream.upstream_status`。
- **⁵ 依赖**：series 允许 `depends_on` / `conflicts_with`（仅引用其他 series `id`，DFS 环检测）。**extras 禁止任何依赖**（extras 之间互不影响）。

## 4. upstream_status 6 态

| status | 联动必填 |
|--------|----------|
| `Pending` / `Submitted` | `upstream_pr` |
| `Backport` / `Denied` / `Inappropriate` | `notes` |
| `Accepted` | `merged_commit` |

## 5. 校验

| 命令 | 作用 |
|------|------|
| `bash tools/apply_patch.sh verify` | lint + series dry-run + extras dry-run + status（CI 默认） |
| `bash tools/apply_patch.sh lint` | 只校验 manifest 字段 |
| `bash tools/apply_patch.sh apply` | 真 apply 到 `/tmp/rabitq-build` |
| `bash tools/apply_patch.sh apply-layer <id>` | 单层：`series<id>` 或 `extra<extra_id>` |

退出码：`0` 成功 / `1` 失败 / `2` upstream 缺失。

## 6. 治理边界

样板只管 patch 元数据 + patch 可重放。**不掺合编译**（autotools/cmake/bazel/python/AOSP 都不在样板范围）。真编译用上游自带入口（`build.sh`/`make`/`bazel build`/...）。

**业务约束**：patch 文件不被 lint/CI/任何脚本读取。