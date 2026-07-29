# 上游技术基线

## 目的

AutoFlow 360 以独立 Frappe 自定义应用的方式集成上游项目，不直接修改上游核心源码。本文件记录来源、稳定线与许可证，避免把上游能力误写为个人实现。

## 固定范围

| 上游项目 | 当前采用线 | 官方来源 | 许可证 | 精确提交哈希 |
| --- | --- | --- | --- | --- |
| Frappe Framework | `version-16` | https://github.com/frappe/frappe | MIT | 待后续依赖拉取阶段写入 |
| ERPNext | `version-16` | https://github.com/frappe/erpnext | GPL-3.0 | 待后续依赖拉取阶段写入 |
| Frappe CRM | `main` | https://github.com/frappe/crm | AGPL-3.0 | 待后续依赖拉取阶段写入 |
| frappe_docker | 官方仓库稳定来源 | https://github.com/frappe/frappe_docker | MIT | 待后续容器基线拉取阶段写入 |

## 固定策略

- Frappe Framework 与 ERPNext 只跟随 `version-16` 稳定线，禁止在未评估兼容性的情况下切换主版本。
- Frappe CRM 当前使用 `main`，因为项目确认的 v1 兼容矩阵以该线为准；它属于可移动分支，构建可复现前必须记录实际提交。
- `frappe_docker` 仅作为容器构建、开发和部署来源，不复制或私自修改其核心文件；构建时记录实际提交。
- 分支名不能替代不可变版本证据。Task 3 拉取依赖后，应把四项“待后续写入精确提交哈希”替换为实际 40 位 Git 提交哈希，并保留获取日期。
- 上游升级必须先验证应用安装、迁移、静态测试、Frappe 业务测试和浏览器主流程，不在未验证时声明兼容。

## 能力边界

上游承担框架、CRM 基础对象及 ERP 标准单据。规划中的自主新增范围由 AutoFlow 360 计划自主实现，包括客户项目、样品闭环、跨单据编排、风险与异常、门户扩展、AI 审计、合成演示数据和招聘验收材料；完成状态以实际代码和测试为准。详细第三方声明见仓库根目录 `NOTICE.md`。
