from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / ".ci" / "patch-tools" / "lint.py"
PATCHES = ROOT / ".ci" / "patch-tools" / "_patches.py"
APPLY = ROOT / ".ci" / "patch-tools" / "apply_patch.sh"


def patch_entry(
    patch_id: str,
    file_name: str,
    *,
    depend_on: list[str] | None = None,
    conflicts_with: list[str] | None = None,
) -> dict:
    entry = {
        "id": patch_id,
        "file": file_name,
        "author": "template@boostkit.example",
        "date": "2026-07-30",
        "upstream_status": "Inappropriate",
        "notes": "Template fixture with an explicit upstream rationale.",
    }
    if depend_on is not None:
        entry["depend_on"] = depend_on
    if conflicts_with is not None:
        entry["conflicts_with"] = conflicts_with
    return entry


class ManifestFixture:
    def __init__(self, patches: list[dict]):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for entry in patches:
            patch_file = self.root / entry["file"]
            patch_file.parent.mkdir(parents=True, exist_ok=True)
            patch_file.write_text(
                "diff --git a/a b/a\n", encoding="utf-8"
            )
        self.manifest = self.root / "manifest.yaml"
        self.manifest.write_text(
            yaml.safe_dump(
                {
                    "upstream_url": "https://example.com/upstream.git",
                    "release": "snapshot-2026-07-30",
                    "pin_commit": "a" * 40,
                    "patches": patches,
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

    def close(self) -> None:
        self.temp.cleanup()


class PatchToolTests(unittest.TestCase):
    def run_lint(self, fixture: ManifestFixture) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(LINT), "manifest", str(fixture.manifest)],
            text=True,
            capture_output=True,
            check=False,
        )

    def run_list(
        self, fixture: ManifestFixture, enabled_features: str = ""
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["ENABLED_FEATURES"] = enabled_features
        return subprocess.run(
            [sys.executable, str(PATCHES), "list", str(fixture.manifest)],
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    def test_valid_manifest_passes(self) -> None:
        fixture = ManifestFixture(
            [
                patch_entry("001", "001-normal.patch"),
                patch_entry(
                    "ex01",
                    "ex01-neon.patch",
                    depend_on=["arm64-neon"],
                ),
            ]
        )
        self.addCleanup(fixture.close)

        result = self.run_lint(fixture)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_out_of_order_files(self) -> None:
        fixture = ManifestFixture(
            [
                patch_entry("002", "002-second.patch"),
                patch_entry("001", "001-first.patch"),
            ]
        )
        self.addCleanup(fixture.close)

        result = self.run_lint(fixture)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("字典序", result.stdout)

    def test_rejects_nested_patch_directory(self) -> None:
        nested = patch_entry("001", "001-normal.patch")
        nested["file"] = "patches/001-normal.patch"
        fixture = ManifestFixture([nested])
        self.addCleanup(fixture.close)

        result = self.run_lint(fixture)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("同级纯文件名", result.stdout)

    def test_rejects_normal_patch_depend_on(self) -> None:
        fixture = ManifestFixture(
            [patch_entry("001", "001-normal.patch", depend_on=["arm64-neon"])]
        )
        self.addCleanup(fixture.close)

        result = self.run_lint(fixture)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("普通 Patch 不允许 depend_on", result.stdout)

    def test_rejects_ex_patch_without_depend_on(self) -> None:
        fixture = ManifestFixture(
            [patch_entry("ex01", "ex01-neon.patch")]
        )
        self.addCleanup(fixture.close)

        result = self.run_lint(fixture)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("特殊 Patch 必须声明 depend_on", result.stdout)

    def test_feature_resolution(self) -> None:
        fixture = ManifestFixture(
            [
                patch_entry("001", "001-normal.patch"),
                patch_entry(
                    "ex01",
                    "ex01-neon.patch",
                    depend_on=["arm64-neon"],
                ),
                patch_entry(
                    "ex02",
                    "ex02-runtime.patch",
                    depend_on=["arm64-neon", "kunpeng-runtime"],
                ),
            ]
        )
        self.addCleanup(fixture.close)

        no_features = self.run_list(fixture)
        neon_only = self.run_list(fixture, "arm64-neon")
        all_features = self.run_list(
            fixture, "arm64-neon,kunpeng-runtime"
        )

        self.assertEqual(no_features.returncode, 0, no_features.stderr)
        self.assertIn("001\t001-normal.patch\tAPPLY", no_features.stdout)
        self.assertIn("ex01\tex01-neon.patch\tSKIP\tmissing=arm64-neon", no_features.stdout)
        self.assertIn(
            "ex02\tex02-runtime.patch\tSKIP\tmissing=arm64-neon,kunpeng-runtime",
            no_features.stdout,
        )
        self.assertIn("ex01\tex01-neon.patch\tAPPLY", neon_only.stdout)
        self.assertIn(
            "ex02\tex02-runtime.patch\tSKIP\tmissing=kunpeng-runtime",
            neon_only.stdout,
        )
        self.assertIn("ex02\tex02-runtime.patch\tAPPLY", all_features.stdout)

    def test_rejects_invalid_conflict_reference(self) -> None:
        missing = ManifestFixture(
            [
                patch_entry(
                    "001",
                    "001-normal.patch",
                    conflicts_with=["404"],
                )
            ]
        )
        self.addCleanup(missing.close)
        own = ManifestFixture(
            [
                patch_entry(
                    "001",
                    "001-normal.patch",
                    conflicts_with=["001"],
                )
            ]
        )
        self.addCleanup(own.close)

        missing_result = self.run_lint(missing)
        own_result = self.run_lint(own)

        self.assertNotEqual(missing_result.returncode, 0)
        self.assertIn("不存在", missing_result.stdout)
        self.assertNotEqual(own_result.returncode, 0)
        self.assertIn("不能与自身冲突", own_result.stdout)

    def test_active_conflict_is_fail(self) -> None:
        fixture = ManifestFixture(
            [
                patch_entry("001", "001-normal.patch"),
                patch_entry(
                    "ex01",
                    "ex01-neon.patch",
                    depend_on=["arm64-neon"],
                    conflicts_with=["001"],
                ),
            ]
        )
        self.addCleanup(fixture.close)

        skipped = self.run_list(fixture)
        active = self.run_list(fixture, "arm64-neon")

        self.assertIn("ex01\tex01-neon.patch\tSKIP", skipped.stdout)
        self.assertIn(
            "ex01\tex01-neon.patch\tFAIL\tconflict=001",
            active.stdout,
        )


class ApplyToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.upstream = self.root / "upstream"
        self.upstream.mkdir()
        self.run_git("init", "-b", "main")
        self.run_git("config", "user.name", "BoostKit Test")
        self.run_git("config", "user.email", "test@boostkit.example")
        (self.upstream / "data.txt").write_text("base\n", encoding="utf-8")
        self.run_git("add", "data.txt")
        self.run_git("commit", "-m", "base")
        self.pin_commit = self.run_git("rev-parse", "HEAD").stdout.strip()

        self.version = self.root / "version"
        self.patch_dir = self.version
        self.patch_dir.mkdir(parents=True)
        self.make_patch(
            self.patch_dir / "001-normal.patch",
            {"data.txt": "base\nnormal\n"},
        )
        self.make_patch(
            self.patch_dir / "ex01-feature.patch",
            {"feature.txt": "feature enabled\n"},
        )
        self.manifest = self.version / "manifest.yaml"
        self.write_manifest(
            [
                patch_entry("001", "001-normal.patch"),
                patch_entry(
                    "ex01",
                    "ex01-feature.patch",
                    depend_on=["arm64-neon"],
                ),
            ]
        )

    def run_git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.upstream,
            text=True,
            capture_output=True,
            check=True,
        )

    def make_patch(self, output: Path, files: dict[str, str]) -> None:
        for relative, content in files.items():
            path = self.upstream / relative
            path.write_text(content, encoding="utf-8")
            tracked = subprocess.run(
                ["git", "ls-files", "--error-unmatch", relative],
                cwd=self.upstream,
                text=True,
                capture_output=True,
                check=False,
            )
            if tracked.returncode != 0:
                self.run_git("add", "-N", relative)
        diff = self.run_git("diff", "--binary").stdout
        output.write_text(diff, encoding="utf-8")
        self.run_git("reset", "--hard", "HEAD")
        for relative in files:
            path = self.upstream / relative
            if not self.run_git("ls-files", relative).stdout.strip() and path.exists():
                path.unlink()

    def write_manifest(self, entries: list[dict]) -> None:
        self.manifest.write_text(
            yaml.safe_dump(
                {
                    "upstream_url": str(self.upstream),
                    "release": "snapshot-2026-07-30",
                    "pin_commit": self.pin_commit,
                    "patches": entries,
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

    def run_apply(
        self, *args: str, enabled_features: str = ""
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PATCH_MANIFEST"] = str(self.manifest)
        env["PATCH_WORKDIR"] = str(self.root / "work")
        env["ENABLED_FEATURES"] = enabled_features
        return subprocess.run(
            ["bash", str(APPLY), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    def test_verify_applies_selected_patches_cumulatively(self) -> None:
        result = self.run_apply("verify", enabled_features="arm64-neon")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("APPLY 001", result.stdout)
        self.assertIn("APPLY ex01", result.stdout)
        self.assertIn("APPLY=2 SKIP=0 FAIL=0", result.stdout)

    def test_verify_skips_missing_features(self) -> None:
        result = self.run_apply("verify")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SKIP ex01 missing=arm64-neon", result.stdout)
        self.assertIn("APPLY=1 SKIP=1 FAIL=0", result.stdout)

    def test_apply_failure_is_nonzero(self) -> None:
        bad_patch = self.patch_dir / "002-broken.patch"
        bad_patch.write_text(
            "diff --git a/missing.txt b/missing.txt\n"
            "--- a/missing.txt\n"
            "+++ b/missing.txt\n"
            "@@ -1 +1 @@\n"
            "-missing\n"
            "+broken\n",
            encoding="utf-8",
        )
        self.write_manifest(
            [
                patch_entry("001", "001-normal.patch"),
                patch_entry("002", "002-broken.patch"),
                patch_entry(
                    "ex01",
                    "ex01-feature.patch",
                    depend_on=["arm64-neon"],
                ),
            ]
        )

        result = self.run_apply("verify", enabled_features="arm64-neon")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL 002", result.stdout)


if __name__ == "__main__":
    unittest.main()
