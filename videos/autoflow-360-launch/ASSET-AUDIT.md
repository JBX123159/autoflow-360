# 素材审计

## 使用

- `assets/brand/autoflow-360-logo.svg`：项目自有品牌标识，用于片头和片尾。
- `assets/product/01-workbench-overview.png`：展示角色工作台、待审批、七日节点和高风险区域。
- `assets/product/07-project-portfolio.png`：展示三个演示项目在项目组合中的位置与金额、阶段、风险。
- `assets/product/02-normal-project.png`：展示从商机、样品、报价、订单到交付签收的正常闭环。
- `assets/product/03-supplier-delay.png`：展示供应商延期、风险升级与整改关闭场景。
- `assets/product/04-resample.png`：展示客户退样、重新打样与第二轮认可证据链。
- `assets/product/05-management-cockpit.png`：展示项目规模、金额、风险、异常与下钻入口。
- `assets/product/06-mobile-workbench.png`：展示窄屏响应式布局，用于结尾前的多端适配镜头。
- `assets/product/08-normal-finance-closure.png`：展示已付款发票、收付款记录、零异常和操作审计，补足正常闭环的财务证据。
- `assets/product/09-delay-remediation.png`：展示供应商延期异常已关闭、高风险标识和操作审计，补足整改闭环证据。
- `assets/fonts/NotoSansSC-VF.ttf`：视频离线中文字体；字体内嵌许可证元数据声明 SIL Open Font License 1.1。SHA-256：`763146584CF0710223441356B4395E279021B0806C196614377A7A0174AE074A`。
- `assets/vendor/gsap.min.js`：GSAP 3.15.0 官方浏览器构建，只用于离线时间线动画；保留原版权、版本和 GSAP Standard License 链接。SHA-256：`92BB9A96476F983D212A2BC4F54C889039C1696DD4461D40A736860938570FBB`。
- `assets/voice/01.wav` 至 `14.wav`：使用本机 Kokoro `zf_xiaobei` 合成的中文旁白，不是真人录音或真人声音克隆；总时长 162.624 秒，无背景音乐。

## 跳过

- `capture/screenshots/full-page.png`、`capture/screenshots/scroll-000.png`：仅为登录页，不能体现业务价值。
- `capture/assets/svgs/svg-*.svg`：均为登录表单通用小图标，联系表无法辨认，且不是 AutoFlow 360 品牌资产。
- `capture/assets/svgs/contact-sheet.jpg`、`capture/screenshots/contact-sheet.jpg`：仅用于内部素材核验，不进入成片。

## 合规边界

- 所有业务截图来自本机站点，数据均为合成演示数据。
- 不展示 `.env`、口令、访问令牌或第三方真实客户信息。
- 视频只陈述已经通过测试和验收的能力，不宣称真实企业采用、营收或用户规模。
- 项目自有标识、产品截图和脚本由本项目生成；第三方字体与动画库不因仓库采用 AGPL 而被重新许可，仍分别适用其原许可证。
