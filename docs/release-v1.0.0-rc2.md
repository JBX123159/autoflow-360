# AutoFlow 360 v1.0.0-rc2

这是首个完成公开工程验收的发布候选版本。项目基于 Frappe CRM、ERPNext 与 frappe_docker，新增汽车零部件客户项目和供应链协同闭环；所有演示与性能数据均为 CNY 合成数据，不代表真实企业采用或生产效果。

## 已验证

- [完整集成验收](https://github.com/JBX123159/autoflow-360/actions/runs/31247387142)：Frappe 148/148、Playwright 3/3，并生成 200 个合成项目规模的性能证据。
- [静态质量门禁](https://github.com/JBX123159/autoflow-360/actions/runs/31248369952)：171/171。
- [多架构镜像构建](https://github.com/JBX123159/autoflow-360/actions/runs/31248409381)：`linux/amd64`、`linux/arm64`、SBOM 和构建来源证明均已发布。
- 公开镜像：`ghcr.io/jbx123159/autoflow-360:v1.0.0-rc2`
- 镜像索引摘要：`sha256:95e19322ca31aa03fdc85b35f7d8ce342075a5049a73bbc356f39d395f9651a0`
- 演示视频：162.633 秒，1920×1080，30fps，大小 65,534,062 字节。
- 视频 SHA-256：`2EBF2BE882A0DCC5FA54675DE0D8229CBEEEB6D399B2DD322856048183851F58`

## 说明

`v1.0.0-rc1` 在首次镜像构建时暴露了发行包名与 Frappe 应用名不一致的问题；`rc2` 已修复并通过双架构远端构建。项目当前没有长期公网业务站点，Oracle 免费层脚本尚未在真实云主机验收，因此本版本仍是发布候选，不描述为已上线生产系统。
