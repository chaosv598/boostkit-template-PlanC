# Plan C 扁平版本目录 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除版本目录的 `patches/` 中间层，并将远端仓库重命名为 `boostkit-template-PlanC`。

**Architecture:** Manifest 的 `file` 改为同级纯文件名，lint 负责禁止嵌套路径；解析和应用仍以 Manifest 目录为根。五个示例 Patch 使用 Git move 提升一级，不改变内容和执行结果。

**Tech Stack:** Python、PyYAML、Bash、Git、GitHub Actions

## Global Constraints

- Patch 文件必须与 `manifest.yaml` 同级。
- `file` 不能包含目录分隔符或 `..`。
- 编号、字典序、`exNN`、`depend_on` 和冲突语义不变。
- 三组真实验证结果必须保持 3/2、4/1、5/0。
- 远端最终名称必须是 `chaosv598/boostkit-template-PlanC`。

---

### Task 1: 用失败测试定义扁平路径

**Files:**
- Modify: `tests/test_patch_tools.py`
- Modify: `.ci/patch-tools/lint.py`

- [ ] 添加嵌套路径被拒绝的测试。
- [ ] 运行该测试并确认当前实现错误地接受 `patches/001-*.patch`。
- [ ] 将测试 fixture 改为 Patch 与 Manifest 同级。
- [ ] 修改 lint，要求 `file` 为纯文件名。
- [ ] 运行全部单元测试并要求通过。

### Task 2: 迁移示例与文档

**Files:**
- Move: `src/RaBitQ-Library/patches/*.patch` → `src/RaBitQ-Library/*.patch`
- Modify: `src/RaBitQ-Library/manifest.yaml`
- Modify: `src/RaBitQ-Library/README.md`
- Modify: `README.md`
- Modify: `README_en.md`
- Modify: `docs/schemas.md`
- Modify: `docs/usage.md`
- Modify: design and plan documentation

- [ ] 提升五个 Patch 文件并更新 Manifest。
- [ ] 删除所有面向用户的 `patches/` 目录描述。
- [ ] 运行旧术语和旧路径扫描。
- [ ] 运行 Python、Shell 和 YAML 静态检查。

### Task 3: 验证并发布

**Files:**
- Verify: entire repository
- Remote: `chaosv598/boostkit-template-PlanC`

- [ ] 运行 10 个单元测试。
- [ ] 运行 Manifest lint。
- [ ] 运行三组真实 verify。
- [ ] 提交并推送当前 HEAD 到远端 main。
- [ ] 使用 GitHub CLI 重命名仓库。
- [ ] 验证新 URL、默认分支、远端 SHA 和 GitHub Actions。
