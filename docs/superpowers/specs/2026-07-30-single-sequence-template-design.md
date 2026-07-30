# BoostKit 单序列 Patch 模板设计

## 目标

将现有 `series[] + extras[]` 双层模板改造成可复制的通用模板：

- 一个版本目录只有一个 `patches/` 目录。
- 普通 Patch 使用 `001-*.patch`、`002-*.patch`、`003-*.patch`。
- 特殊 Patch 使用 `ex01-*.patch`、`ex02-*.patch`。
- 文件名字典序是唯一应用顺序。
- 特殊 Patch 使用 `depend_on` 声明所需业务特性。
- CI 通过 `ENABLED_FEATURES` 提供当前环境具备的特性。
- 依赖满足时 APPLY；依赖不满足时明确 SKIP，并列出缺失特性。

## 仓库结构

```text
boostkit-template/
├── .ci/
│   └── patch-tools/
│       ├── apply_patch.sh
│       ├── _patches.py
│       └── lint.py
├── .github/
│   └── workflows/
│       └── patch-verify.yml
├── docs/
│   ├── schemas.md
│   └── usage.md
├── src/
│   └── RaBitQ-Library/
│       ├── README.md
│       ├── manifest.yaml
│       └── patches/
│           ├── 001-example-bootstrap.patch
│           ├── 002-example-compat.patch
│           ├── 003-example-observability.patch
│           ├── ex01-example-neon.patch
│           └── ex02-example-runtime.patch
└── tests/
    └── test_patch_tools.py
```

`.git/` 不能被 Git 跟踪，也不会出现在 CI 的全新 checkout 中，因此工具使用 `.ci/patch-tools/`。GitHub Actions 工作流只负责调用该稳定入口。

## Manifest

```yaml
upstream_url: https://github.com/VectorDB-NTU/RaBitQ-Library
release: snapshot-2026-07-25
pin_commit: 540242ea0a68926f1b827bf1f9add844f07a427b

patches:
  - id: "001"
    file: patches/001-example-bootstrap.patch
    author: template@boostkit.example
    date: 2026-07-30
    upstream_status: Inappropriate
    notes: Template-only patch used to demonstrate deterministic replay.

  - id: ex01
    file: patches/ex01-example-neon.patch
    author: template@boostkit.example
    date: 2026-07-30
    upstream_status: Inappropriate
    notes: Template-only ARM64 feature patch.
    depend_on:
      - arm64-neon
```

通用字段：

- `id`
- `file`
- `author`
- `date`
- `upstream_status`
- `notes`
- `upstream_pr`
- `merged_commit`
- `conflicts_with`

特殊 Patch 额外字段：

- `depend_on`: 非空业务特性列表；仅允许在 `exNN` Patch 中出现。

## 顺序与依赖

1. `lint.py` 校验 Manifest、文件存在、文件名与 ID 对齐。
2. `lint.py` 校验 `patches[]` 已按 `file` 字典序声明。
3. `_patches.py` 按该顺序输出每个 Patch 的 APPLY / SKIP 判定。
4. 普通编号 Patch 默认 APPLY。
5. `exNN` Patch 的 `depend_on` 全部包含在 `ENABLED_FEATURES` 时 APPLY。
6. 有任一特性缺失时 SKIP，并输出缺失特性。
7. `apply_patch.sh` 在同一临时工作区累计应用所有 APPLY 项。
8. 任一缺文件、冲突、Schema、clone、checkout 或 apply 错误均返回非零。

`depend_on` 只表达业务运行前置条件，不表达 Patch 之间的执行顺序；执行顺序始终由文件名决定。

## 命令

```bash
bash .ci/patch-tools/apply_patch.sh verify
bash .ci/patch-tools/apply_patch.sh lint
bash .ci/patch-tools/apply_patch.sh apply
bash .ci/patch-tools/apply_patch.sh apply-one ex01
```

示例：

```bash
ENABLED_FEATURES=arm64-neon bash .ci/patch-tools/apply_patch.sh verify
ENABLED_FEATURES=arm64-neon,kunpeng-runtime bash .ci/patch-tools/apply_patch.sh verify
```

`apply-one <id>` 只对指定 Patch 做依赖判定并尝试应用，用于定位单个 Patch 是否能够独立应用到固定上游基线。

## 假 Patch 设计

- `001`、`002`、`003` 分别修改上游 `example.sh` 的不同独立位置，既能单独应用，也能累计应用。
- `ex01` 依赖 `arm64-neon`。
- `ex02` 依赖 `arm64-neon` 和 `kunpeng-runtime`。
- 不设置 `ENABLED_FEATURES` 时，三个普通 Patch APPLY，两个特殊 Patch SKIP。
- 只启用 `arm64-neon` 时，`ex01` APPLY，`ex02` SKIP。
- 同时启用两个特性时，五个 Patch 全部 APPLY。

## 测试

使用 Python `unittest` 覆盖：

- 有效 Manifest 通过。
- 乱序文件被拒绝。
- 普通 Patch 使用 `depend_on` 被拒绝。
- `exNN` 缺少 `depend_on` 被拒绝。
- 不同 `ENABLED_FEATURES` 产生正确 APPLY / SKIP 集合。
- `conflicts_with` 引用不存在或自身时被拒绝。
- 本地临时上游仓能够完成累计 verify，不依赖公网。

GitHub Actions 运行：

1. 安装 PyYAML。
2. 执行单元测试。
3. 执行模板 Manifest lint。
4. 执行真实 `verify`，验证固定 RaBitQ 上游基线。

## 兼容性边界

- 不兼容旧 `series[]`、`extras[]`、`self_contained`。
- 不支持通过 Manifest 字段覆盖文件名顺序。
- 不负责业务编译、功能测试和性能验证。
- SKIP 不是 PASS，CI 摘要必须单独统计。
