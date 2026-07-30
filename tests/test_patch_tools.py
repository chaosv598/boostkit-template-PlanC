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


def patch_entry(
    patch_id: str,
    file_name: str,
    *,
    depend_on: list[str] | None = None,
    conflicts_with: list[str] | None = None,
) -> dict:
    entry = {
        "id": patch_id,
        "file": f"patches/{file_name}",
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
        patch_dir = self.root / "patches"
        patch_dir.mkdir()
        for entry in patches:
            (self.root / entry["file"]).write_text(
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
        self.assertIn("001\tpatches/001-normal.patch\tAPPLY", no_features.stdout)
        self.assertIn("ex01\tpatches/ex01-neon.patch\tSKIP\tmissing=arm64-neon", no_features.stdout)
        self.assertIn(
            "ex02\tpatches/ex02-runtime.patch\tSKIP\tmissing=arm64-neon,kunpeng-runtime",
            no_features.stdout,
        )
        self.assertIn("ex01\tpatches/ex01-neon.patch\tAPPLY", neon_only.stdout)
        self.assertIn(
            "ex02\tpatches/ex02-runtime.patch\tSKIP\tmissing=kunpeng-runtime",
            neon_only.stdout,
        )
        self.assertIn("ex02\tpatches/ex02-runtime.patch\tAPPLY", all_features.stdout)

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


if __name__ == "__main__":
    unittest.main()
