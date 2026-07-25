#!/usr/bin/env python3
"""
lint —— BoostKit RaBitQ patch 仓统一 lint (v6.5 · 双层形态 · manifest-only)

形态说明:
  - 本仓为 boostkit/* 系列简单仓代表:
      * series=0 (rabitq 无通用 patch), extras=2 (鲲鹏性能优化)
      * 单一上游版本 (RaBitQ-Library @ snapshot-2026-07-25)
      * manifest.yaml 在 src/RaBitQ-Library/
  - master = manifest-only: lint 只读 manifest.yaml, 不读 patch 头
  - 业务约束: patch 文件不被改, 不被 CI/lint 读取

校验矩阵 (v6.5):
  ✓ manifest 顶层: upstream_url / release (非分支名) / pin_commit (40-char SHA)
  ✓ series[].id / file / author / date / upstream_status / notes
  ✓ extras[].extra_id (kebab-case) / title / enabled / upstream.status
  ✓ extras[].files[].file 存在性
  ✓ series 字典序 + extras[].files 字典序
  ✓ depends_on 完整性 (仅引用 series id) + 环检测
  ✗ patch 头 DEP-3 / Upstream-Status — master 下禁用, 切到备选分支

向后兼容:
  v6.0 flat patches[] 自动 fallback (本仓已迁移到 v6.5)

用法:
  python3 tools/lint.py manifest <manifest.yaml|repo-root>...
  python3 tools/lint.py all <repo-root>...
  python3 tools/lint.py headers <patch>...   # master = no-op
  python3 tools/lint.py status [<manifest.yaml>]   # 双层 status 分布
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml


# ─── YAML loader (禁用 timestamp 构造, 防止 2026-13-99 这种坏 date 让 PyYAML 直接抛 ValueError) ───
class _SafeLoaderNoDate(yaml.SafeLoader):
    """不构造 datetime/date — 全部当字符串. 让 lint 自己用正则检 YYYY-MM-DD."""


_SafeLoaderNoDate.add_constructor(
    "tag:yaml.org,2002:timestamp",
    lambda loader, node: loader.construct_scalar(node),
)


def _yaml_load(path: Path) -> dict:
    """鲁棒加载 — 坏 date 也只是字符串, 不抛."""
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=_SafeLoaderNoDate)
    return data if isinstance(data, dict) else {}


# ─── Yocto Upstream-Status 6 态 (对齐 Yocto dev-manual/common-tasks) ───
VALID_MANIFEST_STATUSES = frozenset({
    "Pending",       # 已发上游 PR/邮件, 等回复
    "Submitted",     # 上游复核中
    "Backport",      # 从更高版本反向移植
    "Denied",        # 上游明确拒绝
    "Inappropriate", # 不适合上游 (本仓全量使用)
    "Accepted",      # 上游已合并
})

# status → 联动必填字段
MANIFEST_STATUS_REQUIRES_NOTES = frozenset({
    "Inappropriate",  # 必填: 不适合上游原因
    "Denied",         # 必填: 上游拒绝原因
    "Backport",       # 必填: 源头 commit 或新版本号
})
MANIFEST_STATUS_REQUIRES_COMMIT = frozenset({"Accepted"})
MANIFEST_STATUS_REQUIRES_PR = frozenset({"Pending", "Submitted"})

MIN_NOTES_LEN = 10  # notes 至少 10 字符, 防止占位

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
# patch 文件名: 至少 4 位数字 + - + 描述 + .patch (Buildroot 风格)
PATCH_NAME_RE = re.compile(r"^(\d{4,})-.*\.patch$")


def _s(v) -> str:
    """Normalize value to stripped string (PyYAML parses YYYY-MM-DD as date)."""
    if v is None:
        return ""
    return str(v).strip()


def lint_manifest(manifest_path: Path) -> list[str]:
    """校验单个 manifest.yaml — 自动检测 schema 形态 (v6.5 优先, v6.0 flat fallback).

    位置约定 (业界 Buildroot / OpenWrt):
      仓根/src/<Upstream>-<Version>/manifest.yaml  (推荐, 多版本演进)
      仓根/manifest.yaml                           (兼容旧单版本仓)
    """
    if not manifest_path.is_file():
        return [f"{manifest_path}: 不存在"]
    try:
        data = _yaml_load(manifest_path)
    except yaml.YAMLError as e:
        return [f"{manifest_path}: YAML 解析失败: {e}"]
    if not isinstance(data, dict):
        return [f"{manifest_path}: 顶层不是 dict"]

    # v6.5 双层 (有 series 或 extras 键) — series/extras 双形态支持其中一个为空
    if "series" in data or "extras" in data:
        return _lint_dual_layer(manifest_path, data)

    # v6.0 flat patches[] 兼容
    return _lint_v60_flat(manifest_path, data)


def _lint_v60_flat(mf: Path, data: dict) -> list[str]:
    """v6.0 flat patches[] 校验 (旧仓兼容, 自动 fallback)."""
    errs: list[str] = []
    mf_dir = mf.parent

    # ── 顶层 (总): repo / version / commit ──
    for f in ("repo", "version", "commit"):
        if not data.get(f):
            errs.append(f"{mf}: 缺顶层字段 {f}:")

    commit = _s(data.get("commit"))
    if commit and not SHA_RE.fullmatch(commit):
        errs.append(f"{mf}: commit={commit!r} 不是 40-char SHA")

    repo_url = _s(data.get("repo"))
    if repo_url and not (repo_url.startswith("http://") or repo_url.startswith("https://") or repo_url.startswith("git://")):
        errs.append(f"{mf}: repo={repo_url!r} 不是 URL")

    # ── 分: patches[] ──
    patches = data.get("patches")
    if not isinstance(patches, list) or not patches:
        errs.append(f"{mf}: 缺 patches: 列表")
        return errs

    seen_names: set[str] = set()
    seen_paths: set[str] = set()
    for i, p in enumerate(patches):
        if not isinstance(p, dict):
            errs.append(f"{mf}: patches[{i}] 不是 dict")
            continue
        errs.extend(_lint_patch_entry(p, i, mf))

        name = _s(p.get("name"))
        path = _s(p.get("path"))
        if name:
            if name in seen_names:
                errs.append(f"{mf}: patches[{i}].name={name!r} 重复")
            seen_names.add(name)
        if path:
            if path in seen_paths:
                errs.append(f"{mf}: patches[{i}].path={path!r} 重复")
            seen_paths.add(path)

    errs.extend(_check_depends(patches, mf))
    errs.extend(_check_patch_order(patches, mf))
    errs.extend(_check_patch_files_exist(patches, mf, mf_dir))
    return errs


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# v6.5 dual-layer (series[] + extras[]) — 新形态校验
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# release 字段黑名单 — 禁止写分支名 (业务约束: pin commit 与 release 不能漂移)
RELEASE_BLACKLIST = frozenset({"main", "develop", "master", "HEAD", "trunk", "latest"})

# extra_id 命名约束 — kebab-case (Buildroot <pkg> + OpenWrt <package> 风格)
EXTRA_ID_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def _lint_dual_layer(mf: Path, data: dict) -> list[str]:
    """v6.5 双层形态校验 — series + extras + 字段 rename 后."""
    errs: list[str] = []
    mf_dir = mf.parent

    # ─── 顶层 ───
    for f in ("upstream_url", "release", "pin_commit"):
        if not data.get(f):
            errs.append(f"{mf}: 缺顶层字段 {f}:")

    url = _s(data.get("upstream_url"))
    if url and not (url.startswith("http://") or url.startswith("https://") or url.startswith("git://")):
        errs.append(f"{mf}: upstream_url={url!r} 不是 URL")

    commit = _s(data.get("pin_commit"))
    if commit and not SHA_RE.fullmatch(commit):
        errs.append(f"{mf}: pin_commit={commit!r} 不是 40-char SHA")

    release = _s(data.get("release"))
    if release and release in RELEASE_BLACKLIST:
        errs.append(
            f"{mf}: release={release!r} 是分支名, 应是上游真实 tag 或 snapshot ID (YYYY-MM-DD)\n"
            f"    业务约束: release 写 main / develop / master 会导致 pin_commit 与 release 漂移"
        )

    # ─── series[] ───
    series = data.get("series") or []
    if not isinstance(series, list):
        errs.append(f"{mf}: series 不是 list")
        series = []

    seen_series_ids: set[str] = set()
    seen_series_files: set[str] = set()
    series_id_set: set[str] = set()
    for i, s in enumerate(series):
        if not isinstance(s, dict):
            errs.append(f"{mf}: series[{i}] 不是 dict")
            continue
        errs.extend(_lint_series_entry(s, i, mf, mf_dir))

        sid = _s(s.get("id"))
        sfile = _s(s.get("file"))
        if sid:
            if sid in seen_series_ids:
                errs.append(f"{mf}: series[{i}].id={sid!r} 重复")
            seen_series_ids.add(sid)
            series_id_set.add(sid)
        if sfile:
            if sfile in seen_series_files:
                errs.append(f"{mf}: series[{i}].file={sfile!r} 重复")
            seen_series_files.add(sfile)

    # ─── extras[] ───
    extras = data.get("extras") or []
    if not isinstance(extras, list):
        errs.append(f"{mf}: extras 不是 list")
        extras = []

    seen_extra_ids: set[str] = set()
    for i, e in enumerate(extras):
        if not isinstance(e, dict):
            errs.append(f"{mf}: extras[{i}] 不是 dict")
            continue
        errs.extend(_lint_extra_block(e, i, mf, mf_dir))

        eid = _s(e.get("extra_id"))
        if eid:
            if eid in seen_extra_ids:
                errs.append(f"{mf}: extras[{i}].extra_id={eid!r} 重复")
            seen_extra_ids.add(eid)

    # ─── 跨层依赖 + 环检测 (二次扫描) ───
    errs.extend(_check_dual_depends(series, extras, series_id_set, mf))

    # ─── 字典序检查 ───
    errs.extend(_check_series_order(series, mf))
    for e in extras:
        if not isinstance(e, dict):
            continue
        files = e.get("files") or []
        ordered = sorted([_s(f.get("file")) for f in files if isinstance(f, dict)])
        actual = [_s(f.get("file")) for f in files if isinstance(f, dict)]
        if actual != ordered:
            eid = _s(e.get("extra_id")) or f"extras[?]"
            errs.append(
                f"{mf}: extra={eid}: files 顺序应字典序\n"
                f"    实际: {actual}\n"
                f"    应为: {ordered}"
            )

    return errs


def _lint_series_entry(s: dict, idx: int, mf: Path, mf_dir: Path) -> list[str]:
    """校验 series[idx] 单条 (v6.5 字段 rename 后)."""
    errs: list[str] = []
    sid = _s(s.get("id")) or f"series[{idx}]"
    prefix = f"{mf}: series.{sid}"

    # id 必填
    if not _s(s.get("id")):
        errs.append(f"{prefix}: 缺 id 字段")

    # file 必填 + 文件存在性
    sfile = _s(s.get("file"))
    if not sfile:
        errs.append(f"{prefix}: 缺 file 字段 (相对 manifest 所在目录)")
    else:
        full = mf_dir / sfile
        if not full.is_file():
            errs.append(f"{prefix}: file={sfile!r} 不存在 ({full})")

    # author: email (renamed from owner)
    author = _s(s.get("author"))
    if not author:
        errs.append(f"{prefix}: 缺 author 字段")
    elif not EMAIL_RE.match(author):
        errs.append(f"{prefix}: author={author!r} 不是 email 格式")

    # date: YYYY-MM-DD
    date = _s(s.get("date"))
    if not date:
        errs.append(f"{prefix}: 缺 date 字段")
    elif not DATE_RE.match(date):
        errs.append(f"{prefix}: date={date!r} 不是 YYYY-MM-DD")

    # upstream_status: 6 选 1 (renamed from status)
    status = _s(s.get("upstream_status"))
    if not status:
        errs.append(f"{prefix}: 缺 upstream_status 字段 (Yocto 6 态)")
    elif status not in VALID_MANIFEST_STATUSES:
        errs.append(
            f"{prefix}: upstream_status={status!r} 非法; "
            f"允许: {', '.join(sorted(VALID_MANIFEST_STATUSES))}"
        )

    # notes: 必填/选填依 status
    notes = _s(s.get("notes"))
    if status in MANIFEST_STATUS_REQUIRES_NOTES and len(notes) < MIN_NOTES_LEN:
        errs.append(
            f"{prefix}: upstream_status={status} → notes 必填且 ≥{MIN_NOTES_LEN} 字符 "
            f"(当前 {len(notes)} 字符)"
        )

    # upstream_pr / merged_commit 联动必填
    upstream_pr = _s(s.get("upstream_pr"))
    merged_commit = _s(s.get("merged_commit"))

    if status in MANIFEST_STATUS_REQUIRES_PR:
        if not upstream_pr:
            errs.append(f"{prefix}: upstream_status={status} → upstream_pr 必填")
        elif not (upstream_pr.startswith("http://") or upstream_pr.startswith("https://") or upstream_pr.startswith("git://")):
            errs.append(f"{prefix}: upstream_pr={upstream_pr!r} 不是 URL")

    if status in MANIFEST_STATUS_REQUIRES_COMMIT:
        if not merged_commit:
            errs.append(f"{prefix}: upstream_status={status} → merged_commit 必填")
        elif not SHA_RE.fullmatch(merged_commit):
            errs.append(f"{prefix}: merged_commit={merged_commit!r} 不是 40-char SHA")

    return errs


def _lint_extra_block(e: dict, idx: int, mf: Path, mf_dir: Path) -> list[str]:
    """校验 extras[idx] 单条块 (extra_id + upstream + files[]).

    v6.5 设计: extra 级 metadata 覆盖 patch 级 metadata (patch 级无 status 字段).
    """
    errs: list[str] = []
    eid = _s(e.get("extra_id")) or f"extras[{idx}]"
    prefix = f"{mf}: extra.{eid}"

    # extra_id: kebab-case 必填
    if not _s(e.get("extra_id")):
        errs.append(f"{prefix}: 缺 extra_id 字段")
    elif not EXTRA_ID_RE.fullmatch(eid):
        errs.append(
            f"{prefix}: extra_id={eid!r} 不符合 kebab-case (例如 neq / fp16-lut / rabitq-eqv)"
        )

    # title: 描述必填
    if not _s(e.get("title")):
        errs.append(f"{prefix}: 缺 title 字段")

    # enabled: 必填 (bool)
    enabled = e.get("enabled")
    if enabled is None:
        errs.append(f"{prefix}: 缺 enabled 字段 (true / false)")
    elif not isinstance(enabled, bool):
        errs.append(f"{prefix}: enabled={enabled!r} 不是 bool")

    # self_contained: 必填 (bool) — v6.5
    # true  = 此 extra 是纯 upstream 上可重放的独立补丁 (CI 默认 apply/dry-run)
    # false = 此 extra 依赖下游编译环境 / 上游 build 工具链 / CI 服务等,
    #         apply_patch.sh 默认跳过它, 避免 dry-run 误报失败;
    #         如需强制包含, 用 BOOTSTRAP_NON_BUILDABLE=1 env 或
    #         apply_patch.sh apply --bootstrap-non-buildable
    sc = e.get("self_contained")
    if sc is None:
        errs.append(
            f"{prefix}: 缺 self_contained 字段 (true = 纯 upstream 可重放; "
            f"false = 依赖下游环境, apply/dry-run 默认跳过)"
        )
    elif not isinstance(sc, bool):
        errs.append(f"{prefix}: self_contained={sc!r} 不是 bool")

    # author: email
    if not _s(e.get("author")):
        errs.append(f"{prefix}: 缺 author 字段")
    else:
        author = _s(e.get("author"))
        if not EMAIL_RE.match(author):
            errs.append(f"{prefix}: author={author!r} 不是 email 格式")

    # date: YYYY-MM-DD
    date = _s(e.get("date"))
    if not date:
        errs.append(f"{prefix}: 缺 date 字段")
    elif not DATE_RE.match(date):
        errs.append(f"{prefix}: date={date!r} 不是 YYYY-MM-DD")

    # upstream.{upstream_status, notes, upstream_pr, merged_commit}
    upstream = e.get("upstream") or {}
    if not isinstance(upstream, dict):
        errs.append(f"{prefix}: upstream 必须是 dict, 当前 {type(upstream).__name__}")
        upstream = {}
    status = _s(upstream.get("upstream_status"))
    if not status:
        errs.append(f"{prefix}: upstream.upstream_status 必填 (Yocto 6 态)")
    elif status not in VALID_MANIFEST_STATUSES:
        errs.append(
            f"{prefix}: upstream.upstream_status={status!r} 非法; "
            f"允许: {', '.join(sorted(VALID_MANIFEST_STATUSES))}"
        )

    notes = _s(upstream.get("notes"))
    if status in MANIFEST_STATUS_REQUIRES_NOTES and len(notes) < MIN_NOTES_LEN:
        errs.append(
            f"{prefix}: upstream.upstream_status={status} → upstream.notes 必填且 ≥{MIN_NOTES_LEN} 字符 "
            f"(当前 {len(notes)} 字符)"
        )

    upstream_pr = _s(upstream.get("upstream_pr"))
    merged_commit = _s(upstream.get("merged_commit"))
    if status in MANIFEST_STATUS_REQUIRES_PR:
        if not upstream_pr:
            errs.append(f"{prefix}: upstream.upstream_status={status} → upstream.upstream_pr 必填")
        elif not (upstream_pr.startswith("http://") or upstream_pr.startswith("https://") or upstream_pr.startswith("git://")):
            errs.append(f"{prefix}: upstream.upstream_pr={upstream_pr!r} 不是 URL")

    if status in MANIFEST_STATUS_REQUIRES_COMMIT:
        if not merged_commit:
            errs.append(f"{prefix}: upstream.upstream_status={status} → upstream.merged_commit 必填")
        elif not SHA_RE.fullmatch(merged_commit):
            errs.append(f"{prefix}: upstream.merged_commit={merged_commit!r} 不是 40-char SHA")

    # files[]
    files = e.get("files") or []
    if not isinstance(files, list):
        errs.append(f"{prefix}: files 不是 list")
        return errs
    seen_files: set[str] = set()
    for j, f in enumerate(files):
        if not isinstance(f, dict):
            errs.append(f"{prefix}: files[{j}] 不是 dict")
            continue
        fpath = _s(f.get("file"))
        if not fpath:
            errs.append(f"{prefix}: files[{j}].file 必填")
            continue
        if fpath in seen_files:
            errs.append(f"{prefix}: files[{j}].file={fpath!r} 重复")
        seen_files.add(fpath)
        full = mf_dir / fpath
        if not full.is_file():
            errs.append(f"{prefix}: files[{j}].file={fpath!r} 不存在 ({full})")

    if not files:
        errs.append(f"{prefix}: files 列表为空 (extra 至少要有一个 patch)")

    return errs


def _check_series_order(series: list, mf: Path) -> list[str]:
    """校验 series 顺序与文件名顺序一致 (字典序 0001 < 0002 < ...)."""
    errs: list[str] = []
    ids = [_s(s.get("id")) for s in series if isinstance(s, dict)]
    sorted_ids = sorted(ids)
    if ids != sorted_ids:
        errs.append(
            f"{mf}: series 顺序应字典序 (Buildroot 模式)\n"
            f"    实际: {ids}\n"
            f"    应为: {sorted_ids}"
        )
    return errs


def _check_dual_depends(series: list, extras: list,
                        series_id_set: set[str], mf: Path) -> list[str]:
    """跨层依赖 + 环检测 (v6.5):
        series<id>.depends_on = 其他 series id (optional 'series:' 前缀)
        extra patch 无 status 字段, 也不接受 depends_on (extra 级 metadata 覆盖)
    """
    errs: list[str] = []
    name_to_idx = {(_s(s.get("id"))): i for i, s in enumerate(series) if isinstance(s, dict) and _s(s.get("id"))}

    # 完整性: 所有 series.depends_on 必须指向存在的 series id
    for s in series:
        if not isinstance(s, dict):
            continue
        sid = _s(s.get("id"))
        raw_deps = s.get("depends_on")
        if raw_deps is None:
            deps: list[str] = []
        elif isinstance(raw_deps, list):
            deps = [_s(x) for x in raw_deps]
        elif isinstance(raw_deps, str):
            deps = [raw_deps]  # 单字符串包装 (但通常应写列表, 记下 lint)
            errs.append(f"{mf}: series.{sid}: depends_on={raw_deps!r} 应是 list, 当前是字符串")
        else:
            deps = []
            errs.append(f"{mf}: series.{sid}: depends_on 类型非法: {type(raw_deps).__name__}")
        for d in deps:
            d_clean = d[len("series:"):] if d.startswith("series:") else d
            if d_clean not in name_to_idx:
                errs.append(f"{mf}: series.{sid}: depends_on={d!r} 引用了不存在的 series id")

    # 环检测 (DFS)
    def has_cycle(start: str) -> bool:
        seen: set[str] = set()
        stack = [start]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            cur = next((x for x in series if _s(x.get("id")) == n), None)
            if cur is None:
                continue
            raw_deps = cur.get("depends_on")
            if isinstance(raw_deps, list):
                deps_local = [_s(x) for x in raw_deps]
            elif isinstance(raw_deps, str):
                deps_local = [raw_deps]
            else:
                deps_local = []
            for d in deps_local:
                d_clean = d[len("series:"):] if d.startswith("series:") else d
                if d_clean == start:
                    return True
                if d_clean not in seen:
                    stack.append(d_clean)
        return False

    for sid in name_to_idx:
        if has_cycle(sid):
            errs.append(f"{mf}: series.{sid}: 检测到环依赖")
    return errs


def _lint_patch_entry(p: dict, idx: int, mf: Path) -> list[str]:
    """校验 patches[idx] 单条 (总分形态分项)."""
    errs: list[str] = []
    name = _s(p.get("name")) or f"patches[{idx}]"
    prefix = f"{mf}: {name}"

    # ── 必填: name / path ──
    if not _s(p.get("name")):
        errs.append(f"{prefix}: 缺 name 字段")
    if not _s(p.get("path")):
        errs.append(f"{prefix}: 缺 path 字段 (相对仓根的 patch 文件路径)")

    # ── owner: email ──
    owner = _s(p.get("owner"))
    if not owner:
        errs.append(f"{prefix}: 缺 owner 字段")
    elif not EMAIL_RE.match(owner):
        errs.append(f"{prefix}: owner={owner!r} 不是 email 格式")

    # ── date: YYYY-MM-DD 或 'unknown' ──
    date = _s(p.get("date"))
    if not date:
        errs.append(f"{prefix}: 缺 date 字段 (YYYY-MM-DD 或 'unknown')")
    elif date != "unknown" and not DATE_RE.match(date):
        errs.append(f"{prefix}: date={date!r} 不是 YYYY-MM-DD")

    # ── status: 6 选 1 ──
    status = _s(p.get("status"))
    if not status:
        errs.append(f"{prefix}: 缺 status 字段 (Yocto 6 态)")
    elif status not in VALID_MANIFEST_STATUSES:
        errs.append(
            f"{prefix}: status={status!r} 非法; "
            f"允许: {', '.join(sorted(VALID_MANIFEST_STATUSES))}"
        )

    # ── notes: 必填/选填依 status ──
    notes = _s(p.get("notes"))
    if status in MANIFEST_STATUS_REQUIRES_NOTES and len(notes) < MIN_NOTES_LEN:
        errs.append(
            f"{prefix}: status={status} → notes 必填且 ≥{MIN_NOTES_LEN} 字符 "
            f"(当前 {len(notes)} 字符)"
        )

    # ── upstream_commit / upstream_pr 联动必填 ──
    upstream_commit = _s(p.get("upstream_commit"))
    upstream_pr = _s(p.get("upstream_pr"))

    if status in MANIFEST_STATUS_REQUIRES_COMMIT:
        if not upstream_commit:
            errs.append(f"{prefix}: status={status} → upstream_commit 必填")
        elif not SHA_RE.fullmatch(upstream_commit):
            errs.append(f"{prefix}: upstream_commit={upstream_commit!r} 不是 40-char SHA")

    if status in MANIFEST_STATUS_REQUIRES_PR:
        if not upstream_pr:
            errs.append(f"{prefix}: status={status} → upstream_pr 必填")
        elif not (upstream_pr.startswith("http://") or upstream_pr.startswith("https://") or upstream_pr.startswith("git://")):
            errs.append(f"{prefix}: upstream_pr={upstream_pr!r} 不是 URL")

    return errs


def _check_depends(patches: list, mf: Path) -> list[str]:
    errs: list[str] = []
    name_to_idx = {_s(p.get("name")): i for i, p in enumerate(patches) if _s(p.get("name"))}

    # 完整性: 所有 depends 必须指向存在的 patch name
    for p in patches:
        name = _s(p.get("name"))
        for d in (p.get("depends") or []):
            if d not in name_to_idx:
                errs.append(f"{mf}: {name}: depends={d!r} 引用了不存在的 patch")

    # 环检测 (DFS)
    def has_cycle(start: str) -> bool:
        seen: set[str] = set()
        stack = [start]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            cur = next((x for x in patches if _s(x.get("name")) == n), None)
            if cur is None:
                continue
            for d in (cur.get("depends") or []):
                if d == start:
                    return True
                if d not in seen:
                    stack.append(d)
        return False

    for name in name_to_idx:
        if has_cycle(name):
            errs.append(f"{mf}: {name}: 检测到环依赖")

    return errs


def _check_patch_order(patches: list, mf: Path) -> list[str]:
    """校验 manifest 顺序与文件名顺序一致 (字典序 0001 < 0002 < ...)."""
    errs: list[str] = []
    names = [_s(p.get("name")) for p in patches]
    sorted_names = sorted(names)
    if names != sorted_names:
        errs.append(
            f"{mf}: patches 顺序应字典序 (Buildroot 模式)\n"
            f"    实际: {names}\n"
            f"    应为: {sorted_names}"
        )
    return errs


def _check_patch_files_exist(patches: list, mf: Path, mf_dir: Path) -> list[str]:
    """校验 manifest.patches[].path 指向真实文件 (相对 manifest 所在目录)."""
    errs: list[str] = []
    for p in patches:
        name = _s(p.get("name"))
        rel_path = _s(p.get("path"))
        if not rel_path:
            continue
        full = mf_dir / rel_path
        if not full.is_file():
            errs.append(f"{mf}: {name}: path={rel_path} 不存在 ({full})")
    return errs


# === subcommand: headers (master = no-op) ===

def cmd_headers(paths: list[Path]) -> int:
    print(
        "⚠ master 分支 = manifest-only 形态, patch 头不被 lint 校验。\n"
        "  切换到 v6.0-patchheader-status 分支恢复 DEP-3 校验。"
    )
    return 0


# === subcommand: manifest ===

def cmd_manifest(targets: list[Path]) -> int:
    all_errs: list[str] = []
    for t in targets:
        # 既接受 manifest.yaml 文件, 也接受 src/<Version>/
        if t.is_dir():
            mf = t / "manifest.yaml"
            if not mf.is_file():
                print(f"✗ {t}/manifest.yaml 不存在", file=sys.stderr)
                return 2
        elif t.name == "manifest.yaml":
            mf = t
        else:
            print(f"✗ {t}: 不是 manifest.yaml 也不是 src/<Version>/", file=sys.stderr)
            return 2

        errs = lint_manifest(mf)
        if errs:
            for e in errs:
                print(f"  ✗ {e}", file=sys.stderr)
            all_errs.extend(errs)
        else:
            # 按 schema 形态给不同 OK 文案
            try:
                sd = _yaml_load(mf)
                if "series" in sd or "extras" in sd:
                    msg = "v6.5 双层 (series + extras)"
                else:
                    msg = "v6.0 flat patches (兼容)"
            except Exception:
                msg = "(schema 探测失败)"
            print(f"  ✓ {mf}: manifest OK ({msg}, patch 头不校验)")

    print(f"\n--- manifest: {len(targets)} 个, {len(all_errs)} 个错误 ---")
    return 0 if not all_errs else 1


# === subcommand: status (patch 状态分布报表) ===

def cmd_status(manifest_path: Path) -> int:
    if not manifest_path.is_file():
        print(f"✗ {manifest_path} 不存在", file=sys.stderr)
        return 1
    try:
        data = _yaml_load(manifest_path)
    except yaml.YAMLError as e:
        print(f"✗ YAML 解析失败: {e}", file=sys.stderr)
        return 1

    is_v65 = "series" in data or "extras" in data

    if is_v65:
        return _status_v65(manifest_path, data)
    return _status_v60(manifest_path, data)


def _status_v65(mf: Path, data: dict) -> int:
    """v6.5 双层 status 报表 — series 表 + extras 表."""
    series = data.get("series") or []
    extras = data.get("extras") or []
    print(f"=== patch 状态分布 (v6.5 双层, {mf}) ===\n")

    # series 表
    by_status: dict[str, list[str]] = {}
    for s in series:
        if not isinstance(s, dict):
            continue
        st = _s(s.get("upstream_status")) or "(空)"
        by_status.setdefault(st, []).append(_s(s.get("id")) or "?")
    print(f"[series] {len(series)} entries")
    if by_status:
        print(f"{'status':<15} {'count':>5}  ids")
        print(f"{'-'*15} {'-'*5}  {'-'*40}")
        for st in sorted(by_status.keys()):
            ids = by_status[st]
            print(f"{st:<15} {len(ids):>5}  {', '.join(ids)}")
    else:
        print("  (空)")

    print()

    # extras 表 — 按 upstream_status 归因
    by_status_e: dict[str, list[str]] = {}
    seen_extra_ids: set[str] = set()
    for e in extras:
        if not isinstance(e, dict):
            continue
        eid = _s(e.get("extra_id")) or "?"
        if eid in seen_extra_ids:
            continue
        seen_extra_ids.add(eid)
        st = _s((e.get("upstream") or {}).get("upstream_status")) or "(空)"
        by_status_e.setdefault(st, []).append(eid)
    print(f"[extras] {len(extras)} extra blocks")
    if by_status_e:
        print(f"{'status':<15} {'count':>5}  extra_ids")
        print(f"{'-'*15} {'-'*5}  {'-'*40}")
        for st in sorted(by_status_e.keys()):
            ids = by_status_e[st]
            print(f"{st:<15} {len(ids):>5}  {', '.join(ids)}")
    else:
        print("  (空)")

    # 汇总
    total = len(series) + sum(len(e.get("files") or []) for e in extras if isinstance(e, dict))
    enabled = sum(1 for e in extras if isinstance(e, dict) and e.get("enabled", True))
    print(f"\n汇总: {len(series)} series entries + {len(extras)} extras "
          f"({enabled} enabled) = {total} patch, {len(by_status) + len(by_status_e)} 种 upstream_status")
    return 0


def _status_v60(mf: Path, data: dict) -> int:
    """v6.0 flat patches[] status 报表 (兼容)."""
    patches = data.get("patches") or []
    by_status: dict[str, list[str]] = {}
    for p in patches:
        st = _s(p.get("status")) or "(空)"
        by_status.setdefault(st, []).append(_s(p.get("name")))

    print(f"=== patch 状态分布 ({mf}) ===\n")
    print(f"{'status':<15} {'count':>5}  patches")
    print(f"{'-'*15} {'-'*5}  {'-'*40}")
    for st in sorted(by_status.keys()):
        names = by_status[st]
        print(f"{st:<15} {len(names):>5}  {', '.join(names)}")
    print(f"\n总计: {len(patches)} patch, {len(by_status)} 种 status")
    return 0


# === subcommand: all ===

def cmd_all(targets: list[Path]) -> int:
    """master = manifest-only: 只跑 manifest 校验, 跳过 patch 头."""
    return cmd_manifest(targets)


# === arg helpers ===

def collect_manifest_targets(args: list[str]) -> list[Path]:
    targets: list[Path] = []
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            targets.append(p)
        elif p.is_file() and p.name == "manifest.yaml":
            targets.append(p)
        else:
            print(f"✗ {arg}: 不是 manifest.yaml 也不是仓根", file=sys.stderr)
            sys.exit(1)
    if not targets:
        print("✗ 未提供 manifest.yaml 或仓根路径", file=sys.stderr)
        sys.exit(1)
    return targets


USAGE = """\
用法 (master = manifest-only):
  python3 tools/lint.py manifest <manifest.yaml|repo-root>...
  python3 tools/lint.py all <repo-root>...
  python3 tools/lint.py headers <patch>...    # no-op
  python3 tools/lint.py status [<manifest.yaml>]

示例:
  python3 tools/lint.py manifest manifest.yaml
  python3 tools/lint.py status
  python3 tools/lint.py all ."""


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(USAGE, file=sys.stderr)
        return 2

    subcmd = argv[1]
    rest = argv[2:]

    if subcmd == "headers":
        paths = [Path(a) for a in rest]
        return cmd_headers(paths)
    elif subcmd == "manifest":
        return cmd_manifest([Path(a) for a in rest])
    elif subcmd == "all":
        return cmd_all([Path(a) for a in rest])
    elif subcmd == "status":
        if rest:
            mf = Path(rest[0])
        else:
            # 默认: 自动找一个 src/<V>/manifest.yaml
            candidates = list(Path("src").glob("*/manifest.yaml")) if Path("src").is_dir() else []
            if not candidates:
                mf = Path("manifest.yaml")
            elif len(candidates) == 1:
                mf = candidates[0]
            else:
                print(f"✗ 多个版本, 请指定: {', '.join(str(c) for c in candidates)}", file=sys.stderr)
                return 1
        return cmd_status(mf)
    else:
        print(f"✗ 未知子命令: {subcmd}\n\n{USAGE}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))