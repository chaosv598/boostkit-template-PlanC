# Introduction to RaBitQ

## Latest Updates

- 2026.03.30: The RaBitQ optimization patches were released on the Gitcode platform, implementing both equivalence and non-equivalence index optimizations.

## Project Introduction

RaBitQ is a randomized binary quantization method (SIGMOD 2024) proposed by the NTU team for high-dimensional vector approximate nearest neighbor (ANN) search. It quantizes a D-dimensional vector into a D-bit binary string and provides a theoretical error bound. The original implementation relies on the x86_64 AVX2 instruction set. Kunpeng optimizations are based on deep, architecture-specific intrusive modifications to the open-source RaBitQ codebase. This extends its support to the AArch64 architecture, introducing performance optimizations and functional enhancements. These include FP16 precision optimization, NEON SIMD vectorization, assembly-level Lookup Table (LUT) acceleration, Spilling with Orthogonality-Amplified Residuals (SOAR) spilled vector assignment, and ML-based adaptive nprobe.

## Directory Structure

```
rabitq/
├── docs/      // schemas.md (schema authority) + usage.md (script usage)
├── tools/     // apply_patch.sh (★ single entry) + _patches.py + lint.py
└── src/<V>/   // one upstream version per subdir (self-contained: manifest.yaml + series/ + extras/<id>/)
```

## Patch Governance Single Entry

```bash
bash tools/apply_patch.sh verify      # CI default: lint + dual-run dry-run + status
bash tools/apply_patch.sh lint        # manifest lint only
bash tools/apply_patch.sh apply       # apply to /tmp/rabitq-build
bash tools/apply_patch.sh apply-layer <id>   # single layer: series<id> or extra<extra_id>

DISABLED_EXTRAS=neq bash tools/apply_patch.sh apply   # runtime-disable extras
```

Full schema: [docs/schemas.md](docs/schemas.md). Script details: [docs/usage.md](docs/usage.md).

This template only governs patch metadata + replay, not compile. For the actual build, use the upstream [VectorDB-NTU/RaBitQ-Library](https://github.com/VectorDB-NTU/RaBitQ-Library) build flow.

## Release Notes

For details about the version updates of RaBitQ, see [Release Notes](docs/en/release_notes.md).

## Documents

| Resource Type| Resource Name | Resource Description |
| ------ | ------------- | ------------ |
| Document    | [Release Notes](docs/en/release_notes.md)        | Provides version information for both equivalence and non-equivalence index optimization patches.                          |
| Document    | [Quick Start](docs/en/quick_start.md)        | Provides the overview, prerequisites, patch application methods, and basic usage guide.                          |
| Document    | [Feature Introduction](docs/en/feature_introduction.md)    | Details the technical components of equivalence and non-equivalence index optimizations, including the SOAR algorithm, the ML-based adaptive nprobe mechanism, and the overall technical architecture.     |
| Document    | [API Reference](docs/en/api_reference.md)    | Details all API modifications across Python scripts, C++ command lines, the IVFRN class, and Shell scripts, relative to the original open-source RaBitQ code.|
| Document    | [User Guide](docs/en/user_guide.md)| Provides detailed instructions for the `run.sh` test script, including parameter descriptions, dataset configurations, search parameters, environment setups, and usage examples.         |

## Disclaimer

This code repository contributes to the RaBitQ open-source components. It strictly adheres to the coding style and methods, as well as security design of the native open-source software. Any vulnerability and security issues of the software shall be resolved by the corresponding upstream communities according to their response mechanisms. Please pay attention to the notifications and version updates released by the upstream communities. The Kunpeng computing community does not assume any responsibility for software vulnerabilities and security issues.

## License

This project is licensed under the Apache License 2.0. For details, see [LICENSE](docs/en/LICENSE).

The documents of this project are licensed under CC-BY 4.0. For details, see [LICENSE](docs/en/LICENSE).

## Contribution Statement

We welcome your contributions to the community. If you have any questions/suggestions or want to provide feedback on feature requirements and bug reports, you can submit [issues](https://gitcode.com/boostkit/community/blob/master/docs/contributor/issue-submit.md). For details, see [Contribution Guideline](https://gitcode.com/boostkit/community/blob/master/docs/contributor/contributing.md). You are also welcome to share insights in the [Discussions](https://gitcode.com/boostkit/community/discussions). Thank you for your support.

## Acknowledgments

RaBitQ is jointly developed by the following Huawei department:

- Kunpeng Computing BoostKit Development Dept

Thank you to everyone in the community for your PRs. We warmly welcome contributions to RaBitQ!