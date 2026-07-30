# BoostKit Patch Template

A reusable BoostKit Patch governance template based on one directory, one
ordered sequence, and feature-gated special patches.

## Rules

- Patch files live directly beside the version's `manifest.yaml`.
- Normal patches use `001-*.patch`, `002-*.patch`, and `003-*.patch`.
- Special patches use `ex01-*.patch`, `ex02-*.patch`, and so on.
- Filename lexicographic order is the only application order.
- A special patch declares required business features in `depend_on`.
- A business exception that cannot replay on the pinned source uses
  `ci_skip: true` with an explicit `skip_reason`.
- CI provides available features through `ENABLED_FEATURES`.
- A special patch is applied when every dependency is available; otherwise it
  is reported as SKIP with the missing features.

## Layout

```text
boostkit-template/
├── .ci/patch-tools/
│   ├── apply_patch.sh
│   ├── _patches.py
│   └── lint.py
├── .github/workflows/patch-verify.yml
├── docs/
├── src/<Upstream>-<Version>/
│   ├── manifest.yaml
│   ├── README.md
│   ├── 001-<name>.patch
│   └── ex01-<feature>.patch
└── tests/test_patch_tools.py
```

The tools live under `.ci/patch-tools/`, not `.git/`. Git does not track
`.git/`, so scripts stored there are unavailable in a fresh CI checkout.

## Quick start

```bash
python3 -m pip install PyYAML
bash .ci/patch-tools/apply_patch.sh lint
bash .ci/patch-tools/apply_patch.sh verify

ENABLED_FEATURES=neq \
  bash .ci/patch-tools/apply_patch.sh verify

ENABLED_FEATURES=eqv \
  bash .ci/patch-tools/apply_patch.sh verify
```

The included RaBitQ example contains three normal patches plus two mutually
exclusive special variants: `ex01` for NeQ and `ex02` for EQV. The business
patches target a separate source snapshot, so this template records both as
`ci_skip`. CI therefore reports 3 APPLY / 2 SKIP for the sample. After a
business repository adapts the patches to its pinned source and removes
`ci_skip`, the `conflicts_with` declarations prevent both variants from
becoming active together.

See [docs/schemas.md](docs/schemas.md) and
[docs/usage.md](docs/usage.md) for the complete contract.

## Scope

The template validates metadata, lifecycle evidence, ordering, feature
dependencies, and replay against a pinned upstream commit. Business builds,
functional tests, performance tests, and releases remain owned by the
downstream repository.

## License

Apache License 2.0. See [LICENSE](LICENSE).
