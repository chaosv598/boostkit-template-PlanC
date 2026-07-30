# 工具使用说明

单入口：

```bash
bash .ci/patch-tools/apply_patch.sh <command>
```

## 命令

| 命令 | 作用 |
|---|---|
| `verify` | lint、checkout 固定上游、在临时工作区累计应用、输出汇总 |
| `lint` | 只校验所有 `src/*/manifest.yaml` |
| `apply` | 将所有 APPLY 项累计应用到 `PATCH_WORKDIR` |
| `apply-one <id>` | 只对指定 Patch 做依赖判定并尝试应用 |
| `help` | 输出帮助 |

## 环境变量

| 变量 | 作用 |
|---|---|
| `ENABLED_FEATURES` | 逗号分隔的业务特性，例如 `arm64-neon,kunpeng-runtime` |
| `PATCH_MANIFEST` | 指定单个 Manifest，主要用于测试和调试 |
| `PATCH_WORKDIR` | 工作目录，默认 `/tmp/boostkit-patch-build` |

## 常用场景

默认验证：

```bash
bash .ci/patch-tools/apply_patch.sh verify
```

启用部分特性：

```bash
ENABLED_FEATURES=arm64-neon \
  bash .ci/patch-tools/apply_patch.sh verify
```

启用全部示例特性：

```bash
ENABLED_FEATURES=arm64-neon,kunpeng-runtime \
  bash .ci/patch-tools/apply_patch.sh verify
```

单独检查特殊 Patch：

```bash
ENABLED_FEATURES=arm64-neon \
  bash .ci/patch-tools/apply_patch.sh apply-one ex01
```

## Python 工具

```bash
python3 .ci/patch-tools/lint.py manifest src/<V>/manifest.yaml
python3 .ci/patch-tools/lint.py status src/<V>/manifest.yaml
python3 .ci/patch-tools/_patches.py list src/<V>/manifest.yaml
python3 .ci/patch-tools/_patches.py summary src/<V>/manifest.yaml
python3 .ci/patch-tools/_patches.py one src/<V>/manifest.yaml ex01
```

`_patches.py list` 输出：

```text
001  patches/001-example-bootstrap.patch  APPLY  ready
ex01 patches/ex01-example-neon.patch       SKIP   missing=arm64-neon
```

实际字段使用 Tab 分隔，便于 Shell 稳定解析。

## Fail closed

下列情况均返回非零：

- Manifest Schema 错误
- Patch 文件缺失或乱序
- `depend_on` 或 `conflicts_with` 声明错误
- 上游 clone 或 checkout 失败
- 任一 APPLY Patch 无法应用

SKIP 只表示缺少业务特性，不表示验证通过。汇总始终分别输出 APPLY、SKIP 和 FAIL。
