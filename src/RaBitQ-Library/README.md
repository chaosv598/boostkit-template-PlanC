# RaBitQ-Library 示例版本

本目录用于演示单目录 Patch 治理。NeQ 与 EQV 作为两条互斥的特殊实现路线，统一纳入 `exNN` 序列。

## 文件顺序

```text
├── manifest.yaml
├── README.md
├── 001-example-bootstrap.patch
├── 002-example-compat.patch
├── 003-example-observability.patch
├── ex01-neq-neon-simd.patch
└── ex02-eqv-soar.patch
```

- `001`、`002`、`003` 默认按字典序累计应用。
- `ex01` 对应 NeQ，启用特性为 `neq`。
- `ex02` 对应 EQV，启用特性为 `eqv`。
- NeQ 与 EQV 修改同一批实现文件，Manifest 将 `ex01`、`ex02` 标记为互斥，禁止同时启用。
- 两份 Patch 针对独立业务源码快照，无法在本示例的 `pin_commit` 上重放，因此当前设置 `ci_skip: true`。

## 验证组合

```bash
# 3 APPLY / 2 SKIP
bash .ci/patch-tools/apply_patch.sh verify

# 3 APPLY / 2 SKIP：ex01/ex02 均按 ci_skip 跳过
ENABLED_FEATURES=neq \
  bash .ci/patch-tools/apply_patch.sh verify

# 3 APPLY / 2 SKIP：ex01/ex02 均按 ci_skip 跳过
ENABLED_FEATURES=eqv \
  bash .ci/patch-tools/apply_patch.sh verify

# 3 APPLY / 2 SKIP：ci_skip 优先于活动冲突判定
ENABLED_FEATURES=neq,eqv \
  bash .ci/patch-tools/apply_patch.sh verify
```

业务仓适配到正确源码基线后，应移除 `ci_skip` 和 `skip_reason`。届时
`depend_on` 决定选择 NeQ 或 EQV，`conflicts_with` 阻止两套实现同时应用。
