#!/usr/bin/env python3
"""Validate the BoostKit single-sequence patch manifest."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml


VALID_STATUSES = frozenset(
    {"Pending", "Submitted", "Backport", "Denied", "Inappropriate", "Accepted"}
)
REQUIRES_NOTES = frozenset({"Backport", "Denied", "Inappropriate"})
REQUIRES_PR = frozenset({"Pending", "Submitted"})
REQUIRES_COMMIT = frozenset({"Accepted"})
RELEASE_BLACKLIST = frozenset(
    {"main", "master", "develop", "head", "trunk", "latest"}
)
NORMAL_ID_RE = re.compile(r"^\d{3,}$")
EX_ID_RE = re.compile(r"^ex\d{2,}$")
FEATURE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class LoaderWithoutDates(yaml.SafeLoader):
    """Keep YAML dates as strings so validation owns the date rules."""


LoaderWithoutDates.add_constructor(
    "tag:yaml.org,2002:timestamp",
    lambda loader, node: loader.construct_scalar(node),
)


def text(value: object) -> str:
    return "" if value is None else str(value).strip()


def load_manifest(path: Path) -> dict:
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=LoaderWithoutDates)
    return data if isinstance(data, dict) else {}


def validate_manifest(path: Path) -> list[str]:
    if not path.is_file():
        return [f"{path}: manifest 不存在"]
    try:
        data = load_manifest(path)
    except (OSError, yaml.YAMLError) as exc:
        return [f"{path}: YAML 解析失败: {exc}"]
    if not data:
        return [f"{path}: 顶层必须是非空 mapping"]

    errors: list[str] = []
    for legacy in ("series", "extras", "self_contained"):
        if legacy in data:
            errors.append(f"{path}: 不支持旧字段 {legacy}")

    for field in ("upstream_url", "release", "pin_commit"):
        if not text(data.get(field)):
            errors.append(f"{path}: 缺顶层字段 {field}")

    release = text(data.get("release"))
    if release.lower() in RELEASE_BLACKLIST:
        errors.append(f"{path}: release 不能使用漂移分支名 {release!r}")

    pin_commit = text(data.get("pin_commit"))
    if pin_commit and not SHA_RE.fullmatch(pin_commit):
        errors.append(f"{path}: pin_commit 必须是 40 字符小写 SHA")

    patches = data.get("patches")
    if not isinstance(patches, list) or not patches:
        errors.append(f"{path}: patches 必须是非空列表")
        return errors

    entries = [entry for entry in patches if isinstance(entry, dict)]
    if len(entries) != len(patches):
        errors.append(f"{path}: patches[] 每项必须是 mapping")

    ids: list[str] = []
    files: list[str] = []
    for index, entry in enumerate(entries):
        prefix = f"{path}: patches[{index}]"
        patch_id = text(entry.get("id"))
        file_name = text(entry.get("file"))
        ids.append(patch_id)
        files.append(file_name)

        if not (NORMAL_ID_RE.fullmatch(patch_id) or EX_ID_RE.fullmatch(patch_id)):
            errors.append(f"{prefix}: id 必须为 001 或 ex01 形态")
        if (
            not file_name
            or Path(file_name).name != file_name
            or "/" in file_name
            or "\\" in file_name
            or file_name in (".", "..")
        ):
            errors.append(f"{prefix}: file 必须是 manifest 同级纯文件名")
        elif Path(file_name).name and not Path(file_name).name.startswith(
            f"{patch_id}-"
        ):
            errors.append(f"{prefix}: 文件名必须以 {patch_id}- 开头")
        elif not (path.parent / file_name).is_file():
            errors.append(f"{prefix}: Patch 文件不存在: {file_name}")

        author = text(entry.get("author"))
        if not EMAIL_RE.fullmatch(author):
            errors.append(f"{prefix}: author 必须是 email")
        if not DATE_RE.fullmatch(text(entry.get("date"))):
            errors.append(f"{prefix}: date 必须是 YYYY-MM-DD")

        status = text(entry.get("upstream_status"))
        if status not in VALID_STATUSES:
            errors.append(f"{prefix}: upstream_status 非法")
        if status in REQUIRES_NOTES and len(text(entry.get("notes"))) < 10:
            errors.append(f"{prefix}: {status} 要求 notes 至少 10 字符")
        if status in REQUIRES_PR and not text(entry.get("upstream_pr")).startswith(
            ("http://", "https://")
        ):
            errors.append(f"{prefix}: {status} 要求 upstream_pr URL")
        if status in REQUIRES_COMMIT and not SHA_RE.fullmatch(
            text(entry.get("merged_commit"))
        ):
            errors.append(f"{prefix}: Accepted 要求 merged_commit 40 字符 SHA")

        depend_on = entry.get("depend_on")
        if EX_ID_RE.fullmatch(patch_id):
            if not isinstance(depend_on, list) or not depend_on:
                errors.append(f"{prefix}: 特殊 Patch 必须声明 depend_on")
            elif any(not FEATURE_RE.fullmatch(text(item)) for item in depend_on):
                errors.append(f"{prefix}: depend_on 包含非法特性名")
        elif depend_on is not None:
            errors.append(f"{prefix}: 普通 Patch 不允许 depend_on")

        conflicts = entry.get("conflicts_with", [])
        if not isinstance(conflicts, list) or any(
            not isinstance(item, str) for item in conflicts
        ):
            errors.append(f"{prefix}: conflicts_with 必须是字符串列表")

    if len(ids) != len(set(ids)):
        errors.append(f"{path}: Patch id 不能重复")
    if len(files) != len(set(files)):
        errors.append(f"{path}: Patch file 不能重复")
    if files != sorted(files):
        errors.append(f"{path}: patches[] 必须按 file 字典序声明")

    known_ids = set(ids)
    for index, entry in enumerate(entries):
        patch_id = text(entry.get("id"))
        for conflict in entry.get("conflicts_with", []) or []:
            if conflict == patch_id:
                errors.append(
                    f"{path}: patches[{index}] 不能与自身冲突: {conflict}"
                )
            elif conflict not in known_ids:
                errors.append(
                    f"{path}: patches[{index}] conflicts_with 引用不存在: {conflict}"
                )
    return errors


def discover_manifests(root: Path) -> list[Path]:
    manifests = sorted(root.glob("src/*/manifest.yaml"))
    if (root / "manifest.yaml").is_file():
        manifests.append(root / "manifest.yaml")
    return manifests


def command_manifest(paths: list[str]) -> int:
    failures = 0
    for raw_path in paths:
        path = Path(raw_path)
        errors = validate_manifest(path)
        if errors:
            failures += 1
            for error in errors:
                print(f"✗ {error}")
        else:
            print(f"✓ {path}")
    return 1 if failures else 0


def command_all(roots: list[str]) -> int:
    manifests: list[Path] = []
    for raw_root in roots:
        manifests.extend(discover_manifests(Path(raw_root)))
    if not manifests:
        print("✗ 未找到 manifest.yaml")
        return 1
    return command_manifest([str(path) for path in manifests])


def command_status(path: str) -> int:
    manifest = Path(path)
    errors = validate_manifest(manifest)
    if errors:
        for error in errors:
            print(f"✗ {error}")
        return 1
    counts: dict[str, int] = {}
    for entry in load_manifest(manifest)["patches"]:
        status = text(entry.get("upstream_status"))
        counts[status] = counts.get(status, 0) + 1
    print(" ".join(f"{status}={counts[status]}" for status in sorted(counts)))
    return 0


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: lint.py {manifest|all|status} <path>...", file=sys.stderr)
        return 2
    command = sys.argv[1]
    if command == "manifest":
        return command_manifest(sys.argv[2:])
    if command == "all":
        return command_all(sys.argv[2:])
    if command == "status" and len(sys.argv) == 3:
        return command_status(sys.argv[2])
    print("usage: lint.py {manifest|all|status} <path>...", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
