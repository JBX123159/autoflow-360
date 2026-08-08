# AutoFlow 360 验收报告

软件验收日期：2026-08-08。数据边界：全部为合成演示/性能数据，默认币种 CNY；结果不代表真实企业采用、用户规模、营收或经营成效。

## 结论

核心业务代码、权限、AI 安全边界、角色工作台、三条演示数据和浏览器流程已经在本地真实 Frappe/ERPNext/CRM 环境及全新 GitHub 托管环境验证。静态契约 171/171、完整 Frappe 业务回归 148/148、三条 Playwright 流程 3/3；公开仓库 [完整集成验收](https://github.com/JBX123159/autoflow-360/actions/runs/31247387142) 已通过。数据库、公有附件、私有附件和站点配置完成 SHA-256 校验，并成功恢复到一次性隔离站点，取得 `RESTORE_CHECK_PASSED`。9 张桌面/移动端业务截图已从本机真实站点自动采集并逐张验收；演示视频包含 14 个动画分镜、14 段配音、62 组字幕和 13 个转场，运行、布局、动画、字幕安全区、图片越界与文字对比度门禁均为 0 错误。完整预览获人工确认后已渲染 162.633 秒高质量 MP4，并通过完整解码、黑帧、长静音、响度、抽帧总览和尾帧检查。多架构镜像、GitHub Release 附件和长期公网业务站点仍待独立验收，因此当前是公开发布候选，不描述为已上线生产系统。

## 需求证据矩阵

| 需求 | 实现证据 | 测试证据 | 状态 | 说明 |
| --- | --- | --- | --- | --- |
| CRM 商机转客户项目 | `services/deal_conversion.py` | `test_deal_conversion.py` | 通过 | 锁、唯一来源、映射和权限 |
| 项目阶段与里程碑 | `services/project_status.py` | `test_customer_project.py` | 通过 | 只允许合法主阶段转换 |
| 样品、检验、反馈、重新打样 | `services/sample_workflow.py` | `test_sample_workflow.py`、E2E | 通过 | 反馈唯一、轮次可追溯 |
| 报价门槛、额度审批、销售订单 | `services/sales_conversion.py` | `test_sales_conversion.py` | 通过 | 申请人不可自批，快照变化失效 |
| 物料缺口与采购需求 | `services/material_planning.py` | `test_material_planning.py` | 通过 | 需求/库存/预留/净缺口可解释 |
| RFQ、供应商报价、采购单、ETA | `services/procurement.py` | `test_procurement.py`、E2E | 通过 | 供应商隔离与交期审计 |
| 库存、交付和客户签收 | `services/delivery.py` | `test_delivery.py` | 通过 | 来源、超交、库存、身份、回执 |
| 开票、回款和严格结项 | `services/project_closure.py` | `test_project_closure.py` | 通过 | 缺口、审批快照和结项后保护 |
| 八类确定性风险 | `risk_engine/` | `test_risk_engine.py` | 通过 | 来源快照、去重、失效与重开 |
| 异常根因、整改、独立验证 | `services/exception_workflow.py` | `test_exception_workflow.py`、E2E | 通过 | 私有证据和相邻状态转换 |
| 七类内部角色、两类门户、多公司 | `permissions/`、`setup/permissions.py` | `test_permissions.py` | 通过 | 列表与对象两层控制 |
| AI 摘要、引用、审计和降级 | `ai/` | `test_ai_service.py` | 通过 | AI 不修改业务单据，默认关闭 |
| 工作台、全景与管理驾驶舱 | `api/analytics.py`、`page/` | `test_analytics_api.py`、页面验收 | 通过 | 桌面与 390px 手机宽度验收 |
| CNY 三场景合成演示 | `demo/seed.py` | `test_demo_seed.py`、3 条 E2E | 通过 | normal/delay/resample 幂等种子 |
| CI、多架构镜像、免费部署 | `.github/workflows/`、`deploy/oracle/` | 171 项静态契约、远端完整集成、Bash/Compose 解析 | 部分通过 | 静态与完整集成已远端通过；多架构镜像等待发布标签触发 |
| 备份与独立恢复 | `backup.sh`、`restore-check.sh`、`verify-backup.*` | `RESTORE_CHECK_PASSED` | 通过 | 数据库、公私附件和站点配置校验后恢复到隔离站点并清理 |

## 测试结果

| 测试层 | 实际结果 | 说明 |
| --- | --- | --- |
| 静态契约 | 171/171 | 本地与公开 `main` 均通过，包含元数据、业务、安全、性能与交付物合同 |
| 完整 Frappe 集成回归 | 148/148 | GitHub 全新锁定环境重建后全量通过 |
| 演示种子定向回归 | 7/7 | 包含重复生成后重新置顶的可见性测试 |
| 浏览器闭环 | 3/3 | 正常交付、供应商延期、重新打样；登录竞态修复后远端复测 |
| npm audit | 0 个已知漏洞 | Playwright 锁定安装时的结果 |
| 恢复演练 | 通过 | SHA-256 校验、隔离站点恢复、迁移、应用和 DocType 读取 |

## 性能基线

环境：GitHub Actions Ubuntu 托管运行器、4 CPU、15989 MB 内存、Python 3.14.2、Frappe 16.29.0、ERPNext 16.30.0、CRM 1.80.0、MariaDB 11.8.8。每项先预热 1 次，再记录 10 次，P95 使用 nearest-rank。原始记录见 `performance.json`。

| 操作 | 数据规模/结果 | P50 | P95 |
| --- | --- | ---: | ---: |
| 工作台项目列表 | 返回 50 条 | 27.776 ms | 38.229 ms |
| 项目全景详情 | 单项目聚合 | 14.242 ms | 18.098 ms |
| 每日风险扫描 | 扫描 200 个合成项目及演示数据 | 3818.708 ms | 3904.756 ms |
| 每周 AI 草稿调度 | AI 关闭，返回 0 | 0.264 ms | 0.406 ms |

性能数据集包含 200 项目、1000 样品、1000 反馈、500 销售订单、500 采购订单，以及合计 5000 条风险/异常/版本记录。它仅代表本次 GitHub 托管容器环境；没有并发压测、云网络延迟或生产 SLA 结论。

## 发布门禁

静态与完整集成 GitHub Actions 已通过。标记 `v1.0.0-rc1` 后仍须独立确认多架构镜像成功和演示视频 Release 附件可下载；临时或 Oracle 演示地址仍未部署。远端应用可达性未满足前保持“发布候选”而不是正式生产发布。
