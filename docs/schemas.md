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

## 2. series[]（普通 patches · 总是 on · 字典序 apply）

| 字段 | 必填 | 备注 |
|------|:--:|------|
| `id` | 是 | kebab-case |
| `file` | 是 | 相对 manifest 所在目录 |
| `author` | 是 | email |
| `date` | 是 | YYYY-MM-DD |
| `upstream_status` | 是 | 6 态 enum（见 §4） |
| `notes` | 条件 | Inappropriate/Denied/Backport 必填，≥10 字符 |
| `upstream_pr` | 条件 | Pending/Submitted 必填 |
| `merged_commit` | 条件 | Accepted 必填（40-char SHA） |
| `depends_on` | 否 | `series:<id>` 或 `<id>`；DFS 环检测；**不允许引用 extras** |
| `conflicts_with` | 否 | list[string] |

## 3. extras[]（鲲鹏性能优化 · 每 extra 一个子目录）

| 字段 | 必填 | 备注 |
|------|:--:|------|
| `extra_id` | 是 | kebab-case；子目录名 = extra_id |
| `title` | 是 | |
| `self_contained` | 是 | `true`=纯 upstream 可重放（CI 默认 apply）；`false`=依赖下游 build（CI 默认跳过，`BOOTSTRAP_NON_BUILDABLE=1` 强制包含） |
| `author` / `date` | 是 | |
| `upstream.upstream_status` | 是 | 6 态 enum；**patch 级不独立 status** |
| `upstream.notes` / `upstream_pr` / `upstream.merged_commit` | 条件 | 同 series |
| `files[]` | 是 | `[ {file: extras/<id>/0001-*.patch}, ... ]`，字典序 apply |

**运行时禁用某 extra**：`DISABLED_EXTRAS=neq,eqv` env 覆盖（无视 self_contained）。

**extras 之间禁止相互依赖**。

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