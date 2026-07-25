#!/usr/bin/env bash
# apply_patch.sh — BoostKit RaBitQ 单入口 (v6.5 · Buildroot 风 · ~200 行)
#
# 用法 (Linux 服务器 / CI runner 主入口):
#   bash tools/apply_patch.sh help                # 帮助 (默认)
#   bash tools/apply_patch.sh verify              # CI 默认: lint + 双跑 dry-run + status
#   bash tools/apply_patch.sh lint                # 只 lint manifest
#   bash tools/apply_patch.sh apply               # 真 apply series + enabled extras 到 /tmp/rabitq-build
#   bash tools/apply_patch.sh apply-layer <id>    # 单层: series<id> 或 extra<extra_id>
#
# env:
#   DISABLED_EXTRAS=neq,eqv           运行时禁用某 extra (覆盖 enabled: true)
#   BOOTSTRAP_NON_BUILDABLE=1         强制 include self_contained=false 的 extra
#                                      (默认 dry-run/apply 会自动跳过非 self_contained extra,
#                                       它们依赖下游编译环境 / 上游 build 链 / CI 服务)
#
# 退出码:
#   0  全部成功
#   1  patch / lint / verify 失败
#   2  upstream clone / fetch 缺失
#
# 业界依据:
#   - Buildroot support/scripts/apply-patches.sh (~50 行基础 apply + 命令聚合)
#   - Yocto do_patch + patchreview.py (lint ⊥ apply)
#   - OpenWrt patches/series (字典序 apply)
#
# 注: 样板只管 patch 元数据 + patch 可重放, 不掺合编译.
# 真编译由各上游仓库 (VectorDB-NTU/RaBitQ-Library) 自带 build.sh 负责
# (见 docs/schemas.md §10 治理边界).

set -e
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

# 自动发现所有 manifest
discover_manifests() {
    local mfs=()
    if compgen -G "$ROOT/src/*/manifest.yaml" > /dev/null; then
        for f in "$ROOT"/src/*/manifest.yaml; do mfs+=("$f"); done
    elif [ -f "$ROOT/manifest.yaml" ]; then
        mfs+=("$ROOT/manifest.yaml")
    fi
    [ ${#mfs[@]} -gt 0 ] || { echo "✗ 未找到 manifest.yaml (期望 src/<V>/manifest.yaml)"; exit 1; }
    printf '%s\n' "${mfs[@]}"
}

# 核心: parse manifest + clone upstream + apply loop
# args: <manifest> [--series|--extras] [DRY_RUN=1]
cmd_apply() {
    local MANIFEST="$1"
    local PHASE_FLAG="${2:-}"   # series | extras | (空 = both)
    local DRY_RUN="${DRY_RUN:-0}"

    # ---- 1. 解析 manifest, 取 patch 列表 ----
    # _patches.py 已按 self_contained (v6.5 extras) 自动过滤:
    #   - 默认: 仅返回 self_contained=true 的 extra (依赖下游环境的标记 false 自动跳过)
    #   - override: BOOTSTRAP_NON_BUILDABLE=1 强制全量含 false 的
    local PATCHES
    PATCHES=$(PHASE_FLAG="$PHASE_FLAG" DISABLED_EXTRAS="${DISABLED_EXTRAS:-}" \
        BOOTSTRAP_NON_BUILDABLE="${BOOTSTRAP_NON_BUILDABLE:-}" \
        python3 "$ROOT/tools/_patches.py" list "$MANIFEST")
    if [ -z "$PATCHES" ]; then
        # 真空的原因可能是 self_contained 全 false — 给用户一个明确提示
        local sc_summary
        sc_summary=$(PHASE_FLAG=extras python3 "$ROOT/tools/_patches.py" summary "$MANIFEST" 2>&1) || true
        echo "(无 patch 可 apply)"
        echo "  提示: extras 可能因 self_contained=false 被自动跳过."
        echo "        (BOOTSTRAP_NON_BUILDABLE=1 可强制包含, 但 dry-run 通常会失败)"
        return 0
    fi

    # ---- 2. clone upstream (idempotent) ----
    local PIN_COMMIT UPSTREAM_URL
    PIN_COMMIT=$(python3 -c "import yaml; print(yaml.safe_load(open('$MANIFEST')).get('pin_commit') or yaml.safe_load(open('$MANIFEST')).get('commit') or '')")
    UPSTREAM_URL=$(python3 -c "import yaml; print(yaml.safe_load(open('$MANIFEST')).get('upstream_url') or yaml.safe_load(open('$MANIFEST')).get('repo') or '')")
    local UPSTREAM_DIR="/tmp/rabitq-build/upstream"

    if [ ! -d "$UPSTREAM_DIR/.git" ]; then
        mkdir -p "$(dirname "$UPSTREAM_DIR")"
        echo "→ clone upstream ..."
        git clone --quiet --no-checkout "$UPSTREAM_URL" "$UPSTREAM_DIR" || { echo "✗ clone failed"; return 2; }
    fi
    (cd "$UPSTREAM_DIR" && git fetch --quiet --depth 1 origin "$PIN_COMMIT") || \
        { echo "✗ fetch $PIN_COMMIT failed"; return 2; }
    # checkout 必须有 working tree (DRY_RUN 也跑 dry-run patch 测试需要)
    (cd "$UPSTREAM_DIR" && git checkout --quiet "$PIN_COMMIT") || \
        { echo "✗ checkout $PIN_COMMIT failed"; return 2; }

    # ---- 3. apply loop (Buildroot 风 — 一个 patch 一行) ----
    # 注意: bash 在 < $FILE 重定向时, 用 PARENT shell cwd (而非子 shell 的 cd),
    # 所以 PATCH_DIR / PATCH_FULL 必须先解析为绝对路径, 否则 "No such file".
    local PATCH_DIR
    PATCH_DIR="$(cd "$(dirname "$MANIFEST")" && pwd)"
    local APPLIED=0 FAILED=0
    local LABEL FILE PATCH_FULL FMT rc

    while IFS=$'\t' read -r LABEL FILE; do
        [ -z "$FILE" ] && continue
        PATCH_FULL="$PATCH_DIR/$FILE"
        if [ ! -f "$PATCH_FULL" ]; then
            echo "  ✗ $LABEL: 缺失 $PATCH_FULL"; FAILED=$((FAILED+1)); continue
        fi
        if head -1 "$PATCH_FULL" | grep -qE "^From [0-9a-f]{40}"; then FMT=git-format; else FMT=plain-diff; fi

        if [ "$DRY_RUN" = "1" ]; then
            if [ "$FMT" = "git-format" ]; then
                (cd "$UPSTREAM_DIR" && git apply --check < "$PATCH_FULL") >/dev/null 2>&1 || rc=$?
            else
                (cd "$UPSTREAM_DIR" && patch --dry-run -p1 < "$PATCH_FULL") >/dev/null 2>&1 || rc=$?
            fi
            rc="${rc:-0}"
            if [ "$rc" = "0" ]; then echo "  ✓ $LABEL [$FMT]"; APPLIED=$((APPLIED+1))
            else echo "  ✗ $LABEL [$FMT] (would fail)"; FAILED=$((FAILED+1)); fi
            unset rc
        else
            if [ "$FMT" = "git-format" ]; then
                (cd "$UPSTREAM_DIR" && git apply < "$PATCH_FULL") >/dev/null 2>&1 || rc=$?
            else
                (cd "$UPSTREAM_DIR" && patch -p1 < "$PATCH_FULL") >/dev/null 2>&1 || rc=$?
            fi
            rc="${rc:-0}"
            if [ "$rc" = "0" ]; then echo "  ✓ $LABEL [$FMT]"; APPLIED=$((APPLIED+1))
            else echo "  ✗ $LABEL [$FMT]: apply 失败"; FAILED=$((FAILED+1)); fi
            unset rc
        fi
    done <<< "$PATCHES"

    echo "=== 汇总: $APPLIED 个成功, $FAILED 个失败 ==="
    [ "$FAILED" = "0" ] && return 0 || return 1
}

# 子命令: lint (manifest schema 校验)
cmd_lint() {
    local errs=0
    while read -r mf; do
        [ -z "$mf" ] && continue
        python3 "$ROOT/tools/lint.py" manifest "$mf" || errs=$((errs+1))
    done < <(discover_manifests)
    echo "--- lint: $errs 个错误 ---"
    [ "$errs" = "0" ] && return 0 || return 1
}

# 子命令: verify (CI 默认 — lint + 双跑 dry-run + status)
cmd_verify() {
    local errs=0
    echo "=== boostkit-rabitq verify (v6.5 · CI 双跑) ==="
    while read -r mf; do
        [ -z "$mf" ] && continue
        local rel="${mf#$ROOT/}"
        echo ""
        echo "## 版本: $rel"

        # 1. lint
        echo "--- lint ---"
        python3 "$ROOT/tools/lint.py" manifest "$mf" || errs=$((errs+1))

        # 2. apply dry-run 双跑
        echo "--- apply dry-run 双跑 ---"
        echo "  路 A · series dry-run:"
        local series_ok=1
        if DRY_RUN=1 PHASE_FLAG=series cmd_apply "$mf"; then
            series_ok=1
        else
            echo "  ⚠ 路 A 失败, 跳路 B"
            errs=$((errs+1)); series_ok=0
        fi
        if [ "$series_ok" = "1" ]; then
            echo "  路 B · extras dry-run:"
            DRY_RUN=1 PHASE_FLAG=extras cmd_apply "$mf" || errs=$((errs+1))
        fi

        # 3. status
        echo "--- status ---"
        python3 "$ROOT/tools/lint.py" status "$mf" || true

        # 4. per-layer summary
        echo "--- per-layer summary ---"
        python3 "$ROOT/tools/_patches.py" summary "$mf" || true
    done < <(discover_manifests)

    echo ""
    echo "=== 汇总 ==="
    if [ "$errs" = "0" ]; then echo "✓ verify 全部通过"
    else echo "✗ verify 失败 ($errs 个错误)"; fi
    [ "$errs" = "0" ] && return 0 || return 1
}

# 子命令: apply-layer <id>  (单层: series<id> 或 extra<extra_id>)
cmd_apply_layer() {
    local target="${1:?usage: apply-layer <series-id-or-extra-id>}"
    while read -r mf; do
        [ -z "$mf" ] && continue
        echo "## 版本: ${mf#$ROOT/}"
        if python3 -c "import yaml,sys; m=yaml.safe_load(open('$mf')); sys.exit(0 if any(e.get('extra_id')=='$target' for e in m.get('extras',[])) else 1)"; then
            # 命中 extra: 反向 DISABLED_EXTRAS
            local others
            others=$(python3 -c "import yaml; m=yaml.safe_load(open('$mf')); print(','.join(e['extra_id'] for e in m.get('extras',[]) if e.get('extra_id')!='$target' and e.get('enabled',True)))")
            echo "→ apply-layer extra=$target, disable others: $others"
            DISABLED_EXTRAS="$others" cmd_apply "$mf" extras || return 1
        else
            # series<id>
            echo "→ apply-layer series=$target"
            PHASE_FLAG=series cmd_apply "$mf" || return 1
        fi
    done < <(discover_manifests)
}

# 子命令: apply (series + enabled extras)
cmd_apply_real() {
    while read -r mf; do
        [ -z "$mf" ] && continue
        echo "## 版本: ${mf#$ROOT/}"
        cmd_apply "$mf" || return 1
    done < <(discover_manifests)
}

print_help() {
    cat <<'EOF'

BoostKit RaBitQ · v6.5 (Buildroot 风 · 单入口)

  用法: bash tools/apply_patch.sh <command> [args]

Commands:
  help                帮助 (默认)
  verify              CI 默认: lint + 双跑 dry-run + status
  lint                只 lint src/*/manifest.yaml
  apply               apply series + enabled extras 到 /tmp/rabitq-build
  apply-layer <id>    单层: series<id> 或 extra<extra_id>

环境:
  DISABLED_EXTRAS=neq,eqv           运行时禁用某 extra (覆盖 enabled: true)
  BOOTSTRAP_NON_BUILDABLE=1         强制 apply self_contained=false 的 extra
                                    (默认跳过 — 它们依赖下游编译/上游 build 链/CI 服务)

上手 2 步:
  1. bash tools/apply_patch.sh verify       # 校验 manifest + 双跑 dry-run (CI 也跑这个)
  2. bash tools/apply_patch.sh apply        # 真 apply 到 /tmp/rabitq-build (编译由各仓自带脚本负责)

注: 样板只管 patch 元数据 + patch 可重放, 不掺合编译
   (业界依据: Buildroot / OpenWrt / Yocto 都分离 patch 治理与编译, 见 docs/schemas.md §10)
EOF
}

cmd="${1:-help}"; shift || true

case "$cmd" in
    help|--help|-h|"") print_help ;;
    verify)   cmd_verify ;;
    lint)     cmd_lint ;;
    apply)    cmd_apply_real ;;
    apply-layer) cmd_apply_layer "$@" ;;
    *) echo "✗ 未知 command: $cmd"; print_help; exit 1 ;;
esac
