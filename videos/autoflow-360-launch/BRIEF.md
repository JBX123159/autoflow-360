---
workflow: product-launch-video
flow: autonomous
language: zh-CN
format: landscape
canvas: 1920x1080
target_duration_seconds: 165
voice_provider: kokoro
voice_id: zf_xiaobei
captions: true
music: none
---

# AutoFlow 360 秋招项目演示视频

## Intent

展示产品本身，使用实际本地站点画面和仓库验证证据，面向秋招招聘者说明这是一个基于 Frappe CRM、ERPNext 和 Frappe Framework 扩展出的完整汽车零部件客户项目与供应链协同平台。

## Core message

AutoFlow 360 不是换皮页面，而是把商机、客户项目、样品、报价审批、销售订单、物料缺口、采购、库存、交付签收、开票回款、风险异常和严格结项串成可审计闭环，并通过权限、幂等、恢复演练和自动化测试证明工程可信度。

## Audience

2027 秋招中的供应链、客户项目、商业运营、项目型 ToB 及数字化相关岗位招聘者和面试官。

## Angle

从真实业务问题切入，先展示端到端主线，再展示三个可复现场景，最后用权限、安全、性能和恢复证据收束。所有数据均为人民币合成数据，不声称真实企业采用、真实营收或真实用户规模。

## Must show

1. AutoFlow 工作台与项目全景。
2. `DEMO-NORMAL-001` 正常交付、开票、回款和结项。
3. `DEMO-DELAY-001` 供应商延期、风险、整改和独立验证。
4. `DEMO-RESAMPLE-001` 第一轮反馈、重新打样和第二轮认可。
5. 管理驾驶舱、项目/公司/门户权限边界与 AI 默认关闭。
6. 170/170 静态测试、148/148 Frappe 集成测试、3/3 Playwright 和 `RESTORE_CHECK_PASSED`。

## Visual direction

优先使用产品自己的实际截图，辅以少量流程图、数据卡片和代码证据。整体克制、清晰、可信，避免虚构客户 Logo、夸大规模、霓虹科技感和无依据指标。

## Offline render requirement

确认分镜后的配音、字幕、画面合成和最终渲染必须只使用本机 Kokoro、Chrome、FFmpeg、已登记素材与本地脚本。成片运行时不得依赖 CDN、在线字体、远程图片或临时站点请求；外部 URL 只能作为不会在渲染阶段读取的配置说明。
