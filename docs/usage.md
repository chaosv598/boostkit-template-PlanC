# 脚本使用说明

单入口：`bash tools/apply_patch.sh <command>`

## 命令

| 命令 | 作用 |
|------|------|
| `verify` | CI 默认：lint + 双跑 dry-run + status |
| `lint` | 只校验 manifest |
| `apply` | 真 apply series + self_contained extras 到 `/tmp/rabitq-build` |
| `apply-layer <id>` | 单层命中：`series<id>` 或 `extra<extra_id>` |
| `help` | 帮助（默认行为） |

## 环境变量

| 变量 | 作用 |
|------|------|
| `DISABLED_EXTRAS=neq,eqv` | 运行时禁用某 extra（覆盖 `self_contained: true`） |
| `BOOTSTRAP_NON_BUILDABLE=1` | 强制 include `self_contained: false` 的 extra |
| `DRY_RUN=1` | apply 时只 `--check` / `--dry-run` |

## 退出码

| 码 | 含义 |
|:--:|------|
| `0` | 全部成功 |
| `1` | lint / patch / verify 失败 |
| `2` | upstream clone / fetch 缺失 |

## Python helper

```bash
python3 tools/_patches.py list    src/<V>/manifest.yaml   # label\tfile 行
python3 tools/_patches.py summary src/<V>/manifest.yaml   # 双层 human-readable 摘要
```

`list` 接受 env：`PHASE_FLAG=series|extras`、`DISABLED_EXTRAS=...`、`BOOTSTRAP_NON_BUILDABLE=1`。

## 排查

| 现象 | 排查 |
|------|------|
| verify 路 A 失败 | series 与 `pin_commit` 对不上，看哪行 ✗ |
| verify 路 B 失败 | extras 与 `pin_commit` 对不上；`self_contained=false` 是预期（默认 skip） |
| apply 输出"(无 patch)" | 全是 `self_contained=false`，加 `BOOTSTRAP_NON_BUILDABLE=1` 或改 `self_contained: true` |
| upstream 拉不到 | 网络 / 私有仓，挂 SSH key 或换镜像 |