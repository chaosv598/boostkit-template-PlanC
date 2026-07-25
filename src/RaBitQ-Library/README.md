# RaBitQ-Library · BoostKit 鲲鹏适配

本目录管理 **RaBitQ (NTU SIGMOD 2024)** 的 2 个鲲鹏特定 patch，自包含（manifest + patch 在本目录）。

schema 字段定义见仓根 [docs/schemas.md](../../docs/schemas.md)。本 README 只记本版本的具体清单 + 演进步骤。

## 本版本 patch 清单

| layer | id | file | upstream_status | self_contained |
|-------|----|------|-----------------|:---:|
| extras | `neq` | `extras/neq/0001-neon-simd.patch` (NEON + FP16 + LUT) | Inappropriate | false |
| extras | `eqv` | `extras/eqv/0001-soar.patch` (SOAR + ML nprobe) | Inappropriate | false |
| series | `0001-series-fake` | `series/0001-series-fake.patch` (demo) | Pending | — |

2 extras 是 `diff -uNr` 快照式 patch，需配合 RabitQ 完整 build 链使用 —— 故 `self_contained: false`，CI 默认跳过。

## 加新版本（cp-r 整目录）

```bash
cp -r src/RaBitQ-Library src/RaBitQ-Library-v2
# 改 src/RaBitQ-Library-v2/manifest.yaml 的 upstream_url / release / pin_commit
```

## 加新 extra / series patch

按 [schemas.md §2/§3](../../docs/schemas.md) 在 manifest.yaml 追加条目，再 `bash tools/apply_patch.sh verify` 校验。