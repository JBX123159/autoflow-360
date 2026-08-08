# 上游技术基线

## 目的

AutoFlow 360 以独立 Frappe 自定义应用的方式集成上游项目，不直接修改上游核心源码。本文件记录来源、稳定线与许可证，避免把上游能力误写为个人实现。

## 固定范围

| 上游项目 | 当前采用线 | 官方来源 | 许可证 | 精确提交哈希 |
| --- | --- | --- | --- | --- |
| Frappe Framework | `version-16` | https://github.com/frappe/frappe | MIT | `06613fc60b44d5736007ae3107cdab029b2ae045`（获取日期：2026-07-30） |
| Frappe Payments | `version-16` | https://github.com/frappe/payments | MIT | `cca07d9f9392e2ea0e521c5975151db9e4b6c321`（获取日期：2026-08-08） |
| ERPNext | `version-16` | https://github.com/frappe/erpnext | GPL-3.0 | `8378b6e203841c056925420cc44e6d631c915cf1`（获取日期：2026-07-30） |
| Frappe CRM | `main` | https://github.com/frappe/crm | AGPL-3.0 | `966705a95dbc6e66a8c3342bec6e78a3b397b402`（获取日期：2026-07-30） |
| frappe_docker | `main` | https://github.com/frappe/frappe_docker | MIT | `f137f05d799a6a00d203b4c0d316a8f475e51778`（获取日期：2026-07-30） |

## 固定策略

- Frappe Framework、Frappe Payments 与 ERPNext 只跟随 `version-16` 稳定线，禁止在未评估兼容性的情况下切换主版本。
- Frappe CRM 当前使用 `main`，因为项目确认的 v1 兼容矩阵以该线为准；它属于可移动分支，实际构建必须检出锁定提交，不能直接使用分支的新 HEAD。
- `frappe_docker` 仅作为容器构建、开发和部署来源，不复制或私自修改其核心文件；启动脚本同样检出锁定提交。
- 分支名不能替代不可变版本证据。五个精确提交同时记录在本表和机器可读的 `deploy/upstream-lock.json` 中；本地启动脚本会逐项检出并验证，二者变更必须同步。
- 上游升级必须先验证应用安装、迁移、静态测试、Frappe 业务测试和浏览器主流程，不在未验证时声明兼容。

## 已核验的本地开发契约

2026-07-30 核验官方 `frappe_docker/main` 当前文件后，本地开发脚本遵守以下契约；该核验日期不替代首次拉取后的不可变提交哈希：

- `devcontainer-example/docker-compose.yml` 使用 MariaDB 11.8，并把本地 MariaDB root 密码固定为 `123`。
- `development/installer.py` 默认 Frappe 分支为 `version-16`，支持 `--apps-json`、`--py-version`、`--node-version` 和 `--admin-password`，但创建 MariaDB 站点时同样固定使用 root 密码 `123`。
- 因此 `deploy/env.example` 不提供虚假的数据库 root 密码配置项。该固定口令仅限本机隔离开发，生产环境禁止复用开发 Compose 或固定口令。
- AutoFlow 360 通过只在本机生成的 Compose 覆盖文件挂载当前仓库，再在 Bench 的 `apps` 目录建立符号链接；不复制自定义应用，也不修改上游核心源码。
- 干净安装先把锁定提交获取到本地上游缓存，并用本地 `autoflow-lock` 分支调用官方安装器；建站和安装应用之前已经固定源码，完成后再把 Bench 内各仓库 origin 恢复为官方地址并复核提交。
- `deploy/container-lock.json` 固定实际验证过的 Frappe Bench、MariaDB 与 Redis 镜像摘要；镜像升级和上游源码升级一样需要重新完成安装、迁移与测试验证。
- 开发脚本优先使用可用的 Windows Docker；否则使用指定 WSL2 Ubuntu 内的 Docker 与 Git，并在调用 `wslpath` 前把 Windows 路径的反斜杠转换为正斜杠，以支持中文和空格路径。

## 能力边界

上游承担框架、CRM 基础对象及 ERP 标准单据。规划中的自主新增范围由 AutoFlow 360 计划自主实现，包括客户项目、样品闭环、跨单据编排、风险与异常、门户扩展、AI 审计、合成演示数据和招聘验收材料；完成状态以实际代码和测试为准。详细第三方声明见仓库根目录 `NOTICE.md`。
