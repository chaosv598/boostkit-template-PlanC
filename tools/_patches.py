#!/usr/bin/env python3
"""
_patches.py — BoostKit 单仓 patch 列表 helper (v6.5 · 极简)
==========================================================

唯一职责: 解析 manifest, 输出 patch 列表 (label\\tfile 行).

支持:
  - v6.5 双层 (series + extras)
  - v6.0 flat patches[] (向后兼容)
  - PHASE_FLAG=series|extras|all (默认 all)
  - DISABLED_EXTRAS env (逗号分隔)

不做:
  - apply (那是 apply_patch.sh)
  - clone (那是 apply_patch.sh)
  - lint (那是 lint.py)

用法:
  python3 tools/_patches.py list <manifest.yaml>
  python3 tools/_patches.py summary <manifest.yaml>
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml


def _load(manifest_path: Path) -> dict:
    """Load and validate manifest. Returns empty dict if schema unrecognized."""
    if not manifest_path.is_file():
        print(f"ERR: manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)
    m = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(m, dict):
        print("ERR: manifest top-level not a dict", file=sys.stderr)
        sys.exit(1)
    return m


def _disabled_extras() -> set[str]:
    """Parse DISABLED_EXTRAS env (comma-separated, lowercase)."""
    raw = os.environ.get("DISABLED_EXTRAS", "")
    return {x.strip() for x in raw.split(",") if x.strip()}


def _phase_flag() -> str:
    """PHASE_FLAG: 'series' | 'extras' | '' (all)."""
    return os.environ.get("PHASE_FLAG", "").strip().lower()


def _iter_patches(manifest: dict):
    """
    Yield (label, file_path) tuples in apply order.

    Apply order (两路独立, 不叠加):
      1. series[] in declaration order (lex by `id`)
      2. extras[] in declaration order; within each extra, files in declaration order

    Honors:
      - PHASE_FLAG: filters to series only / extras only
      - DISABLED_EXTRAS: skips disabled extras
      - self_contained (v6.5 extras): 默认 apply 只跑 self_contained=true 的 extra
        (依赖 CI / 下游服务 / 自编译环境的 extra 标 self_contained=false,
         apply/dry-run 自动跳过, 避免 dry-run 误报失败)
        override: BOOTSTRAP_NON_BUILDABLE=1 (强制包含 self_contained=false)
    """
    phase = _phase_flag()
    disabled = _disabled_extras()
    bootstrap = os.environ.get("BOOTSTRAP_NON_BUILDABLE", "").strip() == "1"

    is_v65 = "series" in manifest or "extras" in manifest
    is_v60 = "patches" in manifest and not is_v65

    if is_v65:
        series = manifest.get("series") or []
        if phase in ("", "series"):
            for entry in series:
                yield (f"series:{entry['id']}", entry["file"])

        extras = manifest.get("extras") or []
        if phase in ("", "extras"):
            for extra in extras:
                extra_id = extra.get("extra_id", "")
                if extra_id in disabled:
                    continue
                if not extra.get("enabled", True):
                    continue
                # self_contained gate (v6.5)
                if not bootstrap and not extra.get("self_contained", False):
                    continue  # 跳过非自主构建 extra (默认 dry-run/apply 行为)
                for f in extra.get("files") or []:
                    yield (f"extra:{extra_id}:{f['file']}", f["file"])

    elif is_v60:
        for p in manifest.get("patches") or []:
            yield (f"flat:{p['name']}", p["path"])
    else:
        print("ERR: manifest has neither series[]/extras[] (v6.5) nor patches[] (v6.0)",
              file=sys.stderr)
        sys.exit(1)


def cmd_list(manifest_path: Path) -> int:
    """Print 'label\\tfile' rows, one per patch."""
    m = _load(manifest_path)
    for label, file_path in _iter_patches(m):
        print(f"{label}\t{file_path}")
    return 0


def cmd_summary(manifest_path: Path) -> int:
    """Print human-readable summary table."""
    m = _load(manifest_path)
    series = m.get("series") or []
    extras = m.get("extras") or []
    is_v65 = bool(series) or bool(extras)

    print(f"== {manifest_path.name} ==")
    print(f"upstream_url: {m.get('upstream_url', m.get('repo', '?'))}")
    print(f"release:      {m.get('release', m.get('version', '?'))}")
    print(f"pin_commit:   {m.get('pin_commit', m.get('commit', '?'))}")
    print()

    if not is_v65:
        flat = m.get("patches") or []
        print(f"[flat] {len(flat)} patches (v6.0 compat)")
        for p in flat:
            print(f"  - {p.get('name', '?')}: {p.get('status', '?')}")
        return 0

    print(f"[series] {len(series)} entries")
    for s in series:
        print(f"  - {s.get('id', '?')}: {s.get('upstream_status', s.get('status', '?'))} "
              f"({s.get('file', s.get('path', '?'))})")

    print()
    disabled = _disabled_extras()
    enabled_count = sum(1 for e in extras if e.get("enabled", True) and e.get("extra_id") not in disabled)
    print(f"[extras] {len(extras)} total, {enabled_count} enabled, {len(extras) - enabled_count} disabled")
    bootstrap = os.environ.get("BOOTSTRAP_NON_BUILDABLE", "").strip() == "1"
    n_buildable = 0
    for e in extras:
        extra_id = e.get("extra_id", "?")
        is_disabled = extra_id in disabled
        is_off = not e.get("enabled", True)
        sc = e.get("self_contained", False)
        if not is_disabled and not is_off and sc and not bootstrap:
            n_buildable += 1
        files = e.get("files") or []
        # 状态标记: OFF (禁用) / SKIP (非 self_contained) / BOOT (force include) / ON (正常)
        if is_off or is_disabled:
            marker = "OFF"
        elif not sc:
            marker = "BOOT" if bootstrap else "SKIP"
        else:
            marker = "ON "
        sc_label = "self_contained" if sc else "non-self_contained"
        print(f"  - [{marker}] {extra_id}: {sc_label} / "
              f"{e.get('upstream', {}).get('upstream_status', '?')} ({len(files)} files)")
    print(f"  -> 默认 apply 目标: {n_buildable} 个 self_contained extra "
          f"(BOOTSTRAP_NON_BUILDABLE=1 可含其余)")
    return 0


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] not in ("list", "summary"):
        print("usage: _patches.py {list|summary} <manifest.yaml>", file=sys.stderr)
        return 2
    cmd, manifest_path = sys.argv[1], Path(sys.argv[2])
    if cmd == "list":
        return cmd_list(manifest_path)
    if cmd == "summary":
        return cmd_summary(manifest_path)
    return 2


if __name__ == "__main__":
    sys.exit(main())