#!/usr/bin/env python3
"""Resolve ordered Patch APPLY/SKIP decisions from manifest.yaml."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from lint import load_manifest, text, validate_manifest


def enabled_features() -> set[str]:
    return {
        item.strip()
        for item in os.environ.get("ENABLED_FEATURES", "").split(",")
        if item.strip()
    }


def resolve(manifest: dict, selected_id: str | None = None) -> list[tuple[str, str, str, str]]:
    enabled = enabled_features()
    candidates: list[tuple[dict, str, str, list[str]]] = []
    for entry in manifest.get("patches", []):
        patch_id = text(entry.get("id"))
        if selected_id and patch_id != selected_id:
            continue
        file_name = text(entry.get("file"))
        required = [text(item) for item in entry.get("depend_on", [])]
        missing = [feature for feature in required if feature not in enabled]
        candidates.append((entry, patch_id, file_name, missing))

    active_ids = {
        patch_id
        for _, patch_id, _, missing in candidates
        if not missing
    }
    rows: list[tuple[str, str, str, str]] = []
    for entry, patch_id, file_name, missing in candidates:
        if missing:
            rows.append((patch_id, file_name, "SKIP", f"missing={','.join(missing)}"))
            continue
        active_conflicts = [
            conflict
            for conflict in entry.get("conflicts_with", []) or []
            if conflict in active_ids
        ]
        if active_conflicts:
            rows.append(
                (patch_id, file_name, "FAIL", f"conflict={','.join(active_conflicts)}")
            )
            continue
        rows.append((patch_id, file_name, "APPLY", "ready"))
    return rows


def load_validated(path: Path) -> dict | None:
    errors = validate_manifest(path)
    if errors:
        for error in errors:
            print(f"✗ {error}", file=sys.stderr)
        return None
    return load_manifest(path)


def command_list(path: Path, selected_id: str | None = None) -> int:
    manifest = load_validated(path)
    if manifest is None:
        return 1
    rows = resolve(manifest, selected_id)
    if selected_id and not rows:
        print(f"✗ Patch id 不存在: {selected_id}", file=sys.stderr)
        return 1
    for row in rows:
        print("\t".join(row))
    return 0


def command_summary(path: Path) -> int:
    manifest = load_validated(path)
    if manifest is None:
        return 1
    rows = resolve(manifest)
    apply_count = sum(1 for row in rows if row[2] == "APPLY")
    skip_count = sum(1 for row in rows if row[2] == "SKIP")
    fail_count = sum(1 for row in rows if row[2] == "FAIL")
    for patch_id, file_name, decision, reason in rows:
        print(f"[{decision}] {patch_id} {file_name} {reason}")
    print(
        f"APPLY={apply_count} SKIP={skip_count} "
        f"FAIL={fail_count} TOTAL={len(rows)}"
    )
    return 1 if fail_count else 0


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "usage: _patches.py {list|summary|one} <manifest.yaml> [id]",
            file=sys.stderr,
        )
        return 2
    command = sys.argv[1]
    path = Path(sys.argv[2])
    if command == "list" and len(sys.argv) == 3:
        return command_list(path)
    if command == "summary" and len(sys.argv) == 3:
        return command_summary(path)
    if command == "one" and len(sys.argv) == 4:
        return command_list(path, sys.argv[3])
    print(
        "usage: _patches.py {list|summary|one} <manifest.yaml> [id]",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
