# BoostKit 单序列 Patch 模板 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将双层 Patch 模板改造成单一 `patches[]`、文件名字典序、`exNN + depend_on` 特性门控的可测试通用模板。

**Architecture:** Python 规则引擎负责 Schema、顺序、生命周期和依赖判定；极简 Shell 负责 clone、checkout 和同一工作区累计 apply。示例 Manifest 固定 RaBitQ 上游基线，普通和特殊假 Patch 展示 APPLY / SKIP 三种特性组合。

**Tech Stack:** Python 3.9+、PyYAML、Bash、Git、Python unittest、GitHub Actions

## Global Constraints

- 每个版本目录只有一个 `patches/` 目录。
- 普通 Patch 使用 `001`、`002`、`003`；特殊 Patch 使用 `ex01`、`ex02`。
- 文件名字典序是唯一执行顺序。
- `depend_on` 只允许出现在 `exNN` Patch，值为非空业务特性列表。
- 特性通过 `ENABLED_FEATURES` 逗号分隔环境变量提供。
- 工具位于 `.ci/patch-tools/`。
- 不兼容 `series[]`、`extras[]`、`self_contained`。
- SKIP 单独统计，不能当作 PASS。
- 任何 Schema、文件、冲突、clone、checkout 或 apply 错误均 fail closed。

---

### Task 1: 用失败测试定义单层 Schema 和特性门控

**Files:**
- Create: `tests/test_patch_tools.py`
- Replace: `.ci/patch-tools/lint.py`
- Replace: `.ci/patch-tools/_patches.py`

**Interfaces:**
- `lint.py manifest <path>`：退出码 0/1，错误写 stdout。
- `_patches.py list <manifest>`：输出 `id<TAB>file<TAB>APPLY|SKIP<TAB>reason`。
- `_patches.py summary <manifest>`：输出 APPLY / SKIP / FAIL 统计。

- [ ] 写测试 `test_valid_manifest_passes`，使用临时 Manifest 验证单层 `patches[]`。
- [ ] 写测试 `test_rejects_out_of_order_files`，把 `002` 放在 `001` 前并断言 lint 失败。
- [ ] 写测试 `test_rejects_normal_patch_depend_on`，断言普通 Patch 不能声明特性依赖。
- [ ] 写测试 `test_rejects_ex_patch_without_depend_on`，断言 `exNN` 必须声明依赖。
- [ ] 写测试 `test_feature_resolution`，分别用空特性、`arm64-neon`、两个特性断言 APPLY / SKIP。
- [ ] 写测试 `test_rejects_invalid_conflict_reference`，断言不存在和自身冲突都失败。
- [ ] 运行 `python3 -m unittest tests.test_patch_tools -v`，确认测试因新脚本接口不存在而失败。
- [ ] 实现最小 `lint.py` 和 `_patches.py` 使上述测试通过。
- [ ] 重新运行测试，要求全部通过。
- [ ] 提交 `test: define single-sequence manifest behavior`。

### Task 2: 用失败测试定义累计 apply

**Files:**
- Modify: `tests/test_patch_tools.py`
- Create: `.ci/patch-tools/apply_patch.sh`

**Interfaces:**
- `apply_patch.sh lint`：发现并校验所有 `src/*/manifest.yaml`。
- `apply_patch.sh verify`：临时 checkout 固定基线，累计应用 APPLY 项，结束后清理。
- `apply_patch.sh apply`：应用到 `PATCH_WORKDIR` 或默认 `/tmp/boostkit-patch-build`。
- `apply_patch.sh apply-one <id>`：仅应用指定 Patch。

- [ ] 在测试中创建本地临时 Git 上游仓和两个可独立应用的 Patch。
- [ ] 写 `test_verify_applies_selected_patches_cumulatively`，断言普通 Patch和满足依赖的 `ex01` 被应用。
- [ ] 写 `test_verify_skips_missing_features`，断言缺特性时 `ex01` 输出 SKIP 且退出码为 0。
- [ ] 写 `test_apply_failure_is_nonzero`，加入不可应用 Patch并断言 fail closed。
- [ ] 运行测试，确认因 `apply_patch.sh` 不存在而失败。
- [ ] 实现最小 Shell 入口和临时工作区生命周期。
- [ ] 重新运行测试，要求全部通过。
- [ ] 提交 `feat: add cumulative patch application`。

### Task 3: 迁移示例 Manifest 和五个假 Patch

**Files:**
- Replace: `src/RaBitQ-Library/manifest.yaml`
- Move: `src/RaBitQ-Library/series/0001-series-fake.patch` → `src/RaBitQ-Library/patches/001-example-bootstrap.patch`
- Create: `src/RaBitQ-Library/patches/002-example-compat.patch`
- Create: `src/RaBitQ-Library/patches/003-example-observability.patch`
- Create: `src/RaBitQ-Library/patches/ex01-example-neon.patch`
- Create: `src/RaBitQ-Library/patches/ex02-example-runtime.patch`
- Modify: `src/RaBitQ-Library/README.md`

**Interfaces:**
- 示例普通 Patch 必须可独立和累计应用到 `pin_commit`。
- `ex01` 依赖 `arm64-neon`。
- `ex02` 依赖 `arm64-neon`、`kunpeng-runtime`。

- [ ] 克隆固定 RaBitQ commit 并选择五个互不冲突的上下文位置。
- [ ] 生成五个独立可应用的统一 diff Patch。
- [ ] 写单层 Manifest，按文件名字典序列出五项。
- [ ] 运行 `.ci/patch-tools/apply_patch.sh lint`。
- [ ] 运行无特性 `verify`，要求 3 APPLY / 2 SKIP。
- [ ] 运行 `ENABLED_FEATURES=arm64-neon verify`，要求 4 APPLY / 1 SKIP。
- [ ] 运行两个特性 `verify`，要求 5 APPLY / 0 SKIP。
- [ ] 提交 `feat: add ordered patch examples`。

### Task 4: 同步文档和 CI

**Files:**
- Replace: `README.md`
- Replace: `README_en.md`
- Replace: `docs/schemas.md`
- Replace: `docs/usage.md`
- Create: `.github/workflows/patch-verify.yml`
- Modify: `.gitignore`
- Delete: `tools/apply_patch.sh`
- Delete: `tools/_patches.py`
- Delete: `tools/lint.py`

**Interfaces:**
- CI 调用 `.ci/patch-tools/apply_patch.sh`，不复制内部逻辑。
- 中文和英文 README 使用相同命令及目录。

- [ ] 更新中文和英文入口文档。
- [ ] 完整记录字段、命名、`depend_on`、`ENABLED_FEATURES`、SKIP 语义和退出码。
- [ ] 创建 GitHub Actions 工作流，安装 PyYAML，运行 unittest、lint 和三组 verify。
- [ ] 删除旧 `tools/`。
- [ ] 搜索旧术语，除迁移说明外不得出现。
- [ ] 运行 YAML 解析、Shell 语法和 Python 编译检查。
- [ ] 提交 `docs: publish single-sequence template workflow`。

### Task 5: 最终验证和发布新仓库

**Files:**
- Verify: entire repository
- Remote: `https://github.com/chaosv598/boostkit-template`

**Interfaces:**
- 新仓库默认分支为 `main`。
- 新仓库为 public。

- [ ] 运行 `python3 -m unittest discover -s tests -v`。
- [ ] 运行 `bash .ci/patch-tools/apply_patch.sh lint`。
- [ ] 运行三组 `verify`。
- [ ] 运行 `python3 -m py_compile .ci/patch-tools/lint.py .ci/patch-tools/_patches.py tests/test_patch_tools.py`。
- [ ] 运行 `bash -n .ci/patch-tools/apply_patch.sh`。
- [ ] 检查 `git status`、`git diff --check` 和提交历史。
- [ ] 使用 Windows `gh repo create chaosv598/boostkit-template --public` 创建空仓。
- [ ] 将当前 HEAD 推送为新仓库 `main`。
- [ ] 读取远端默认分支和最新 commit，确认推送成功。
