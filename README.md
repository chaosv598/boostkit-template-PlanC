# BoostKit Patch Template

BoostKit Patch 统一治理模板，采用“单目录、单序列、特性门控”模型。

## 核心约定

- 一个版本目录只有一个 `patches/`。
- 普通 Patch 使用 `001-*.patch`、`002-*.patch`、`003-*.patch`。
- 特殊 Patch 使用 `ex01-*.patch`、`ex02-*.patch`。
- 文件名字典序是唯一应用顺序。
- 特殊 Patch 使用 `depend_on` 声明所需业务特性。
- CI 通过 `ENABLED_FEATURES` 注入当前环境具备的特性。
- 依赖满足时 APPLY；依赖不满足时 SKIP，并输出缺失特性。

## 目录

```text
boostkit-template/
├── .ci/patch-tools/
│   ├── apply_patch.sh
│   ├── _patches.py
│   └── lint.py
├── .github/workflows/patch-verify.yml
├── docs/
│   ├── schemas.md
│   └── usage.md
├── src/<Upstream>-<Version>/
│   ├── manifest.yaml
│   ├── README.md
│   └── patches/
│       ├── 001-<name>.patch
│       ├── 002-<name>.patch
│       └── ex01-<feature>.patch
└── tests/test_patch_tools.py
```

工具放在 `.ci/patch-tools/`，而不是真正的 `.git/`。`.git/` 不能被版本控制，CI 全新 checkout 时无法获得其中脚本。

## 快速开始

安装依赖：

```bash
python3 -m pip install PyYAML
```

校验 Schema 和文件：

```bash
bash .ci/patch-tools/apply_patch.sh lint
```

验证默认 Patch：

```bash
bash .ci/patch-tools/apply_patch.sh verify
```

启用特殊 Patch：

```bash
ENABLED_FEATURES=arm64-neon \
  bash .ci/patch-tools/apply_patch.sh verify

ENABLED_FEATURES=arm64-neon,kunpeng-runtime \
  bash .ci/patch-tools/apply_patch.sh verify
```

只检查并应用一个 Patch：

```bash
ENABLED_FEATURES=arm64-neon \
  bash .ci/patch-tools/apply_patch.sh apply-one ex01
```

## 示例结果

仓库内置五个可重放的 RaBitQ 假 Patch：

| 特性集合 | APPLY | SKIP |
|---|:---:|:---:|
| 空 | `001`、`002`、`003` | `ex01`、`ex02` |
| `arm64-neon` | `001`、`002`、`003`、`ex01` | `ex02` |
| `arm64-neon,kunpeng-runtime` | 全部五个 | 无 |

SKIP 不等于 PASS。输出会单独列出缺失特性。

## 文档

- [Manifest Schema](docs/schemas.md)
- [工具使用说明](docs/usage.md)
- [RaBitQ 示例](src/RaBitQ-Library/README.md)

## 治理边界

模板负责：

- Manifest 元数据校验
- Patch 命名和顺序校验
- 上游生命周期 6 态及证据字段联动
- `depend_on` 特性判定
- 固定 `pin_commit` 上的累计 Patch 重放

模板不负责业务编译、功能测试、性能测试和发布。

## License

Apache License 2.0，见 [LICENSE](LICENSE)。
