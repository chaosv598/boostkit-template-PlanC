# Manifest Schema

`manifest.yaml` 是每个上游版本 Patch 元数据的单一权威。

## 目录

```text
src/<Upstream>-<Version>/
├── manifest.yaml
├── README.md
├── 001-<name>.patch
├── 002-<name>.patch
├── 003-<name>.patch
├── ex01-<feature>.patch
└── ex02-<feature>.patch
```

文件名按字典序排列，也按该顺序累计应用。Manifest 中 `patches[]` 的声明顺序必须与文件名字典序一致。

## 顶层字段

| 字段 | 必填 | 说明 |
|---|:---:|---|
| `upstream_url` | 是 | 上游 Git 地址；本地测试可使用本地仓路径 |
| `release` | 是 | 上游 tag 或 `snapshot-YYYY-MM-DD`；禁止漂移分支名 |
| `pin_commit` | 是 | 40 字符小写 commit SHA |
| `patches` | 是 | 非空 Patch 列表 |

## Patch 通用字段

| 字段 | 必填 | 说明 |
|---|:---:|---|
| `id` | 是 | 普通 Patch 为 `001`；特殊 Patch 为 `ex01` |
| `file` | 是 | 与 Manifest 同级的 `<id>-<name>.patch` 纯文件名 |
| `author` | 是 | 责任人 email |
| `date` | 是 | `YYYY-MM-DD` |
| `upstream_status` | 是 | Yocto 6 态 |
| `notes` | 条件 | Backport、Denied、Inappropriate 必填，至少 10 字符 |
| `upstream_pr` | 条件 | Pending、Submitted 必填 URL |
| `merged_commit` | 条件 | Accepted 必填 40 字符 SHA |
| `conflicts_with` | 否 | 已知冲突 Patch ID 列表 |

## 特殊 Patch 字段

`exNN` Patch 必须增加：

```yaml
depend_on:
  - arm64-neon
  - kunpeng-runtime
```

`depend_on` 表达业务运行前置特性，不表达 Patch 顺序：

- 特性由 `ENABLED_FEATURES` 逗号分隔环境变量提供。
- 依赖全部满足：APPLY。
- 任一依赖缺失：SKIP，并输出 `missing=<feature>`。
- 普通数字 Patch 不允许声明 `depend_on`。

## 完整示例

```yaml
upstream_url: https://github.com/VectorDB-NTU/RaBitQ-Library
release: snapshot-2026-07-25
pin_commit: 540242ea0a68926f1b827bf1f9add844f07a427b

patches:
  - id: "001"
    file: 001-example-bootstrap.patch
    author: template@boostkit.example
    date: 2026-07-30
    upstream_status: Inappropriate
    notes: Template-only Patch used to demonstrate deterministic replay.

  - id: ex01
    file: ex01-example-neon.patch
    author: template@boostkit.example
    date: 2026-07-30
    upstream_status: Inappropriate
    notes: Template-only ARM64 Patch used to demonstrate feature gating.
    depend_on:
      - arm64-neon
```

## Upstream 状态

| 状态 | 联动必填 |
|---|---|
| `Pending`、`Submitted` | `upstream_pr` |
| `Backport`、`Denied`、`Inappropriate` | `notes` |
| `Accepted` | `merged_commit` |

## 冲突规则

- `conflicts_with` 只能引用当前 Manifest 中存在的 Patch ID。
- Patch 不能与自身冲突。
- 冲突声明错误属于 Schema 错误，CI 立即失败。

## 退出语义

- `APPLY`：依赖满足且 Patch 成功应用。
- `SKIP`：特殊 Patch 缺少业务特性；不计为 PASS。
- `FAIL`：Schema、文件、clone、checkout、冲突或 apply 失败。

旧 `series[]`、`extras[]` 和 `self_contained` 不再兼容。
