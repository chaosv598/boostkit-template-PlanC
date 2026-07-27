# Schema

> **manifest 是 patch 元数据单一权威**。`series[]`（总是 on）+ `extras[]`（按 self_contained 单开关决定是否裸跑）。CI 双跑验可重放。编译由各仓自带脚本负责。

## 目录

```
boostkit-rabitq/
├── tools/                 # apply_patch.sh (单入口) + _patches.py + lint.py
├── docs/                  # schemas.md + usage.md
└── src/<V>/               # 一个上游版本一个子目录（自包含）
    ├── manifest.yaml      # ★ 唯一权威
    ├── series/            # 普通 patches (总是 on, 字典序 apply)
    └── extras/<id>/       # 鲲鹏特定 extras (可单独开关, 每 extra 一个子目录)
```

## 1. 顶层

| 字段 | 必填 | 语义 |
|------|:--:|------|
| `upstream_url` | 是 | 上游 git URL |
| `release` | 是 | 上游 tag 或 `snapshot-YYYY-MM-DD`；**禁止**写 `main`/`develop`/`master` |
| `pin_commit` | 是 | 40-char SHA，与 release 对应的固定 commit |

> ~~`install`~~ 已废弃（编译由各仓自带脚本负责）。

## 2. series[] + extras[] 字段对照

> **设计原则**：extras 是 series 的**超集**。同名字段 = 同语义、同必填规则、同校验。extras 多出来的 4 个字段是 `extra_id` / `self_contained` / `title` / `files[]`，没有 series 独占字段。

| 字段 | series | extras | 必填 | 备注 |
|------|:------:|:------:|:--:|------|
| `id` ¹ | ✓ | 改名为 `extra_id` | 是 | kebab-case |
| `file` ² | `file` | 改名为 `files[]` | 是 | 详见下方 |
| `author` | `author` | **同 series** | 是 | email |
| `date` | `date` | **同 series** | 是 | YYYY-MM-DD |
| `upstream_status` ³ | `upstream_status` | **同 series** | 是 | 6 态 enum（见 §4） |
| `notes` | `notes` | **同 series** | 条件 | Inappropriate/Denied/Backport 必填，≥10 字符 |
| `upstream_pr` | `upstream_pr` | **同 series** | 条件 | Pending/Submitted 必填（URL） |
| `merged_commit` | `merged_commit` | **同 series** | 条件 | Accepted 必填（40-char SHA） |
| `depends_on` ⁴ | `depends_on` | — | 否 | 仅 series；extras 禁止 |
| `title` ¹ | — | `title` | 是（extras） | 人类可读描述 |
| `self_contained` ¹ | — | `self_contained` | 是（extras） | 详见下方 |

**注释**：

- **¹ extras 独有字段**：`extra_id`（同时是子目录名）、`title`、`self_contained` 是 extras 必填；series 没有。
- **² patch files 形态不同**：
  - series：`file: series/0001-x.patch`（单文件 string）
  - extras：`files: [{file: extras/neq/0001-x.patch}, ...]`（多文件 list，字典序 apply）
- **³ extras 字段在 `upstream.` 嵌套块下**：extras 的 `upstream_status` / `notes` / `upstream_pr` / `merged_commit` 字段写在 `upstream:` 子块里（语义和 series 完全相同）。**extras patch 无独立 status**——继承所属 extra 的 `upstream.upstream_status`。
- **⁴ 依赖关系**：series 允许 `depends_on`（仅引用其他 series `id`，lint 校验完整性 + DFS 环检测）。**extras 禁止任何依赖**（extras 之间互不影响，也不引用 series）。**apply 顺序仍由 manifest 声明顺序决定**——`depends_on` 是 lint-time 防线，不做拓扑排序。
  - 业务约束：如果 patch B 逻辑上必须先 apply patch A，**必须在 manifest 里把 A 排在 B 前面**（用 `0001-` `0002-` 编号控制）。
  - 写错顺序 / 写错编号 → `bash tools/apply_patch.sh lint` 早期发现。
  - 反例（仅 lint-time 拦截）：声明 `0003-c: depends_on: [0001-a]` 但 manifest 里 0003-c 排在 0001-a 之前 → lint 不会报错（DFS 只查环，不查顺序），但 apply 会按声明顺序先跑 0003-c。这是**故意的取舍**——不做拓扑排序 = 保留 Buildroot 风字典序 = `0001-` 编号语义不被破坏。

**`self_contained` 语义**：

- `true` = 纯 upstream 可重放（CI 默认 apply）
- `false` = 依赖下游 build（CI 默认跳过，`BOOTSTRAP_NON_BUILDABLE=1` 强制包含）
- 运行时覆盖：`DISABLED_EXTRAS=neq,eqv` env（无视 `self_contained: true`）

## 3. 完整 schema 示例

**顶层**：

```yaml
upstream_url: https://github.com/VectorDB-NTU/RaBitQ-Library
release: snapshot-2026-07-25                # 上游 tag 或 snapshot-YYYY-MM-DD
pin_commit: 540242ea0a68926f1b827bf1f9add844f07a427b
```

**series[] entry**（普通 patch · 总是 on）：

```yaml
series:
  - id: 0001-series-fake                     # kebab-case
    file: series/0001-series-fake.patch      # 相对 manifest 目录
    author: chaosv598@users.noreply.github.com
    date: 2026-07-25
    upstream_status: Pending                 # 6 态 enum
    upstream_pr: https://github.com/VectorDB-NTU/RaBitQ-Library/pull/TBD
    notes: |                                  # Pending 不要求 notes；这里演示多行写法
      演示用 series patch — 给 example.sh 加一行注释, 验证 dry-run 路 A。
      上游 NTU 真实 PR 链接待填。
    # depends_on: [0002-other-series]        # 可选; list of series id; lint-time 检查 (apply 仍字典序)
```

**extras[] entry**（鲲鹏特定 extra · 每 extra 一个子目录）：

```yaml
extras:
  - extra_id: neq                            # 子目录名 = extras/neq/
    title: 鲲鹏非等价索引优化
    self_contained: false                    # 鲲鹏特定 NEON 优化, 依赖下游 build
    author: codesheepchen@huawei.com
    date: 2026-02-06
    upstream:                                # ← series 的字段在这里
      upstream_status: Inappropriate
      notes: |
        鲲鹏非等价索引优化 (neq): 引入 FP16 精度 + NEON SIMD 向量化
        + 汇编级 LUT 加速, 提升 ARM64 上非等价索引场景性能。
        上游 NTU 仅支持 x86_64 AVX2, 鲲鹏特定 NEON 优化上游不收。
    files:                                   # ← series 的 file 在这里是 list
      - file: extras/neq/0001-neon-simd.patch
```

## 4. upstream_status 6 态

| status | 联动必填 |
|--------|----------|
| `Pending` / `Submitted` | `upstream_pr` |
| `Backport` / `Denied` / `Inappropriate` | `notes` |
| `Accepted` | `merged_commit` |

## 5. 校验

| 命令 | 作用 |
|------|------|
| `bash tools/apply_patch.sh verify` | lint + series dry-run + extras dry-run + status（CI 默认） |
| `bash tools/apply_patch.sh lint` | 只校验 manifest 字段 |
| `bash tools/apply_patch.sh apply` | 真 apply 到 `/tmp/rabitq-build` |
| `bash tools/apply_patch.sh apply-layer <id>` | 单层：`series<id>` 或 `extra<extra_id>` |

退出码：`0` 成功 / `1` 失败 / `2` upstream 缺失。

## 6. 治理边界

样板只管 patch 元数据 + patch 可重放。**不掺合编译**（autotools/cmake/bazel/python/AOSP 都不在样板范围）。真编译用上游自带入口（`build.sh`/`make`/`bazel build`/...）。

**业务约束**：patch 文件不被 lint/CI/任何脚本读取。