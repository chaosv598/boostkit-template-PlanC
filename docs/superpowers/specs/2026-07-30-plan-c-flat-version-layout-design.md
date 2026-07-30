# Plan C 扁平版本目录设计

## 目标

取消版本目录中的 `patches/` 和 `extras/` 中间层。所有 Patch 文件与
`manifest.yaml`、`README.md` 同级，编号和特性门控语义保持不变。

## 最终结构

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

## Schema 变化

- `file` 必须是纯文件名，不能包含 `/`、`\` 或 `..`。
- `file` 相对 `manifest.yaml` 所在目录解析。
- 普通 Patch 仍使用 `001`、`002`、`003`。
- 特殊 Patch 仍使用 `ex01`、`ex02`。
- `depend_on`、`conflicts_with`、生命周期 6 态保持不变。
- 文件名字典序仍是唯一执行顺序。

## 工具和测试

- `lint.py` 拒绝任何嵌套 Patch 路径。
- `_patches.py` 输出纯文件名。
- `apply_patch.sh` 继续使用 Manifest 目录拼接 `file`，无需改变应用顺序。
- 测试 fixture 和真实 RaBitQ 示例都迁移为同级 Patch 文件。
- 三组验证结果仍为 3/2、4/1、5/0，且 FAIL 均为 0。

## 发布

- 将公开仓库 `chaosv598/boostkit-template` 重命名为
  `chaosv598/boostkit-template-PlanC`。
- 推送更新到远端 `main`。
- 验证默认分支、远端 SHA 和 GitHub Actions。
