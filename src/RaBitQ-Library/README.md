# RaBitQ-Library 示例版本

本目录用于演示单目录 Patch 治理，不代表 RaBitQ 的正式业务补丁。

## 文件顺序

```text
patches/
├── 001-example-bootstrap.patch
├── 002-example-compat.patch
├── 003-example-observability.patch
├── ex01-example-neon.patch
└── ex02-example-runtime.patch
```

- `001`、`002`、`003` 默认按字典序累计应用。
- `ex01` 需要 `arm64-neon`。
- `ex02` 需要 `arm64-neon` 和 `kunpeng-runtime`。

## 验证组合

```bash
# 3 APPLY / 2 SKIP
bash .ci/patch-tools/apply_patch.sh verify

# 4 APPLY / 1 SKIP
ENABLED_FEATURES=arm64-neon \
  bash .ci/patch-tools/apply_patch.sh verify

# 5 APPLY / 0 SKIP
ENABLED_FEATURES=arm64-neon,kunpeng-runtime \
  bash .ci/patch-tools/apply_patch.sh verify
```
