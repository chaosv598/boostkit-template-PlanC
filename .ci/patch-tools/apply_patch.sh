#!/usr/bin/env bash
# BoostKit Patch governance entrypoint.

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LINT="$SCRIPT_DIR/lint.py"
PATCHES="$SCRIPT_DIR/_patches.py"

discover_manifests() {
    if [ -n "${PATCH_MANIFEST:-}" ]; then
        printf '%s\n' "$PATCH_MANIFEST"
        return
    fi
    local found=0
    for manifest in "$ROOT"/src/*/manifest.yaml; do
        [ -f "$manifest" ] || continue
        printf '%s\n' "$manifest"
        found=1
    done
    if [ "$found" = "0" ] && [ -f "$ROOT/manifest.yaml" ]; then
        printf '%s\n' "$ROOT/manifest.yaml"
        found=1
    fi
    if [ "$found" = "0" ]; then
        echo "✗ 未找到 manifest.yaml" >&2
        return 1
    fi
}

lint_manifest() {
    python3 "$LINT" manifest "$1"
}

read_metadata() {
    python3 -c '
import sys, yaml
data = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
print("{}\t{}".format(data.get("upstream_url", ""), data.get("pin_commit", "")))
' "$1"
}

prepare_upstream() {
    local manifest="$1"
    local workdir="$2"
    local upstream_dir="$workdir/upstream"
    local upstream_url pin_commit
    IFS=$'\t' read -r upstream_url pin_commit < <(read_metadata "$manifest")

    rm -rf "$upstream_dir"
    mkdir -p "$workdir"
    echo "CLONE $upstream_url"
    git clone --quiet --no-checkout "$upstream_url" "$upstream_dir" || {
        echo "FAIL clone"
        return 2
    }
    git -C "$upstream_dir" checkout --quiet --detach "$pin_commit" || {
        echo "FAIL checkout $pin_commit"
        return 2
    }
    printf '%s\n' "$upstream_dir"
}

apply_manifest() {
    local manifest="$1"
    local selected_id="${2:-}"
    local cleanup="${3:-0}"
    local workdir="${PATCH_WORKDIR:-/tmp/boostkit-patch-build}"
    local upstream_dir

    lint_manifest "$manifest" || return 1
    upstream_dir=$(prepare_upstream "$manifest" "$workdir") || return $?
    upstream_dir=$(printf '%s\n' "$upstream_dir" | tail -n 1)

    local resolver=(python3 "$PATCHES" list "$manifest")
    if [ -n "$selected_id" ]; then
        resolver=(python3 "$PATCHES" one "$manifest" "$selected_id")
    fi

    local rows
    rows=$("${resolver[@]}") || return 1
    local patch_root
    patch_root="$(cd "$(dirname "$manifest")" && pwd)"
    local apply_count=0 skip_count=0 fail_count=0
    local patch_id file_name decision reason patch_file

    while IFS=$'\t' read -r patch_id file_name decision reason; do
        [ -n "$patch_id" ] || continue
        if [ "$decision" = "SKIP" ]; then
            echo "SKIP $patch_id $reason"
            skip_count=$((skip_count + 1))
            continue
        fi
        patch_file="$patch_root/$file_name"
        if git -C "$upstream_dir" apply --check "$patch_file" >/dev/null 2>&1 &&
           git -C "$upstream_dir" apply "$patch_file" >/dev/null 2>&1; then
            echo "APPLY $patch_id $file_name"
            apply_count=$((apply_count + 1))
        else
            echo "FAIL $patch_id $file_name"
            fail_count=$((fail_count + 1))
            break
        fi
    done <<< "$rows"

    echo "APPLY=$apply_count SKIP=$skip_count FAIL=$fail_count"
    if [ "$cleanup" = "1" ]; then
        rm -rf "$workdir/upstream"
    fi
    [ "$fail_count" = "0" ]
}

cmd_lint() {
    local failures=0
    local manifest
    while read -r manifest; do
        lint_manifest "$manifest" || failures=$((failures + 1))
    done < <(discover_manifests)
    [ "$failures" = "0" ]
}

cmd_verify() {
    local failures=0
    local manifest
    while read -r manifest; do
        echo "== VERIFY ${manifest#$ROOT/} =="
        apply_manifest "$manifest" "" 1 || failures=$((failures + 1))
        python3 "$PATCHES" summary "$manifest" || failures=$((failures + 1))
    done < <(discover_manifests)
    [ "$failures" = "0" ]
}

cmd_apply() {
    local manifest
    while read -r manifest; do
        apply_manifest "$manifest" "" 0 || return $?
    done < <(discover_manifests)
}

cmd_apply_one() {
    local selected_id="${1:?usage: apply-one <id>}"
    local manifest
    while read -r manifest; do
        apply_manifest "$manifest" "$selected_id" 0 || return $?
    done < <(discover_manifests)
}

print_help() {
    cat <<'EOF'
BoostKit Patch governance

Usage:
  bash .ci/patch-tools/apply_patch.sh verify
  bash .ci/patch-tools/apply_patch.sh lint
  bash .ci/patch-tools/apply_patch.sh apply
  bash .ci/patch-tools/apply_patch.sh apply-one <id>

Environment:
  ENABLED_FEATURES=arm64-neon,kunpeng-runtime
  PATCH_MANIFEST=/absolute/path/to/manifest.yaml
  PATCH_WORKDIR=/tmp/boostkit-patch-build
EOF
}

command="${1:-help}"
shift || true
case "$command" in
    verify) cmd_verify ;;
    lint) cmd_lint ;;
    apply) cmd_apply ;;
    apply-one) cmd_apply_one "$@" ;;
    help|--help|-h) print_help ;;
    *) echo "unknown command: $command" >&2; print_help; exit 2 ;;
esac
