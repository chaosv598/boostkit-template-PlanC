# RaBitQ介绍

## 最新消息

- [2026.03.30]：RaBitQ优化补丁发布于Gitcode平台，实现等价索引优化和非等价索引优化。

## 项目介绍

RaBitQ是由NTU团队提出的面向高维向量近似最近邻搜索（ANN）的随机二值量化方法（SIGMOD 2024），能将D维向量量化为D位二进制字符串，并提供理论误差界。原始实现基于x8664 AVX2指令集。鲲鹏优化基于开源RaBitQ代码做侵入式修改，将其扩展至ARM64（AArch64）架构，引入FP16精度优化、NEON SIMD向量化、汇编级LUT加速、SOAR溢出向量分配、ML自适应nprobe等多项性能优化和功能增强。

## 目录结构

```
rabitq/
├── docs/      # schemas.md (schema 权威定义) + usage.md (脚本使用说明)
├── tools/     # apply_patch.sh (★ 单入口) + _patches.py + lint.py
└── src/<V>/   # 一个上游版本一个子目录 (自包含: manifest.yaml + series/ + extras/<id>/)
```

## Patch 治理单入口

```bash
bash tools/apply_patch.sh verify      # CI 默认: lint + 双跑 dry-run + status
bash tools/apply_patch.sh lint        # 只 lint manifest
bash tools/apply_patch.sh apply       # 真 apply 到 /tmp/rabitq-build
bash tools/apply_patch.sh apply-layer <id>   # 单层: series<id> 或 extra<extra_id>

DISABLED_EXTRAS=neq bash tools/apply_patch.sh apply   # 运行时禁用某 extra
```

完整 schema 见 [docs/schemas.md](docs/schemas.md)，脚本细节见 [docs/usage.md](docs/usage.md)。

样板只管 patch 元数据 + 可重放，**不掺合编译**。真编译请用上游 [VectorDB-NTU/RaBitQ-Library](https://github.com/VectorDB-NTU/RaBitQ-Library) 自带构建方式。

## 版本说明

关于RaBitQ的版本更新情况请参见《[版本说明书](docs/zh/release_notes.md)》。

## 学习文档

| 学习资源名称 | 学习资源简介 |
| ---- | ------- |
| [版本说明书](docs/zh/release_notes.md) | 介绍等价索引优化和非等价索引优化补丁的版本信息。 |
| [特性指南](docs/zh/feature_introduction.md) | 详细说明等价索引优化和非等价索引优化的技术内容，包括SOAR算法、ML自适应nprobe机制及技术架构。 |
| [快速入门](docs/zh/quick_start.md) | 提供概述、前置条件、补丁应用方法和基本使用指导。 |
| [API参考](docs/zh/api_reference.md) | 对比原始RaBitQ开源代码，详细列出Python脚本、C++命令行、IVFRN类和Shell脚本的全部接口变动。 |
| [用户指南](docs/zh/user_guide.md) | 提供run.sh测试脚本的详细使用方法，包括参数说明、数据集配置、搜索参数、环境配置和使用示例。 |

## 免责声明

此代码仓计划参与RaBitQ开源组件，编码风格遵照原生开源软件，继承原生开源软件安全设计，不破坏原生开源软件设计及编码风格和方式，软件的任何漏洞与安全问题，均由相应的上游社区根据其漏洞和安全响应机制解决。请密切关注上游社区发布的通知和版本更新。鲲鹏计算社区对软件的漏洞及安全问题不承担任何责任。

## License

- 本项目采用Apache License 2.0许可证授权，详见[LICENSE](LICENSE)文件。

- 本项目的文档适用CC-BY 4.0许可证，具体请参见文件[LICENSE](docs/zh/LICENSE)文件。

## 贡献声明

欢迎大家为社区做贡献，如果使用过程中有任何问题/建议，或者需要反馈特性需求和bug报告，可以提交[Issues](https://gitcode.com/boostkit/community/blob/master/docs/contributor/issue-submit.md)联系我们，具体贡献方法可参考[这里](https://gitcode.com/boostkit/community/blob/master/docs/contributor/contributing.md)。同时也欢迎大家在[讨论专区](https://gitcode.com/boostkit/community/discussions)展开讨论交流。感谢您的支持。

## 致谢

RaBitQ由华为公司的下列部门联合贡献：

- 鲲鹏计算Boostkit开发部

感谢来自社区的每一个PR，欢迎贡献RaBitQ！