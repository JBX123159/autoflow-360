---
format: 1920x1080
duration: 162.624s
message: "把商机到回款的汽车零部件客户项目，做成可审计、可复现、可恢复的完整闭环"
arc: "Demo Loop：业务追问 → 产品定位 → 三场景演示 → 管理与安全 → 工程证据 → CTA"
audience: "2027 秋招供应链、客户项目、商业运营、项目型 ToB 与数字化岗位招聘者"
mode: autonomous
music: none
---

## Video direction

- Palette: 画布使用 `#f7f9fc`，唯一强调色使用 `#2563b8`；主文字 `#20242b`，次级文字 `#667085`，弱提示 `#98a2b3`。截图与数据层不额外引入第二强调色。
- Type and hierarchy: 沿用 `frame.md` 的 display、body、mono 角色；每个镜头只保留一个明确主视觉，数字使用等宽数字排版，重要结论用字号、字重与位置共同拉开层级。
- Motion grammar: 所有揭示都跟随旁白语义落点，默认使用平滑长尾运动；每个镜头从一个主动作展开，最多一个持续运动，其余元素形成有因果的响应。画面不得在前 25% 一次性完成，也不得让多个元素无关联漂浮。
- Shot model: 主视觉覆盖上方约 83% 内容区，至少包含背景、主体、强调层三个深度；底部约 17% 永久留给字幕。真实产品截图以裁切、局部放大和高亮框引导阅读，不展示浏览器栏、鼠标或滚动条。
- Rhythm: Frame 3、7、9、13、14 在关键证据落地后安排短暂停顿；静止用于阅读，不使用呼吸缩放、无目的后半程平移或循环动画。
- Negative list: 不使用纯黑纯白、紫蓝 AI 渐变、漂浮光斑、无业务意义的装饰图形、弹跳缓动、幻灯片式前置堆叠或屏保式独立漂移；运行时不得依赖 CDN、在线字体、远程图片或临时站点。

## Frame 1 — 一环断开，证据就断开

- scene: 报价、样品、采购、交付、回款五个词依次落下，最后被一条断开的流程线截断
- voiceover: "一份客户需求，要穿过报价、样品、采购、交付、回款。只要一环断开，项目就失去证据。"
- duration: 10.283s
- transition_in: cut
- status: animated
- src: compositions/frames/01-hook.html
- type: hook
- persuasion: Pain validation
- beat: tension
- blueprint: kinetic-type-beats (Adapt)
- asset_candidates:
- focal: none（以“证据链”流程线为主视觉）
- roles: none（本镜头无外部素材）
- rules: discrete-text-sequence kinetic-beat-slam svg-path-draw

narrativeRole: 用招聘者熟悉的跨部门断点切入，不先讲技术栈。
keyMessage: 业务闭环的核心不是多一张表，而是证据不断链。

Adapt: 保留“文字按节拍落点、最后一次重击形成结论”的签名动作；把单词节拍改造成五个业务节点，并在末段加入断链证据。
Scene 1 (0.–1.828s): “一份客户需求”作为唯一 display 文字从上方三分之一落定，细流程基线仅显露起点；Centered，主视觉约占内容区 45%，三层纵深，kinetic-beat-slam。
Scene 2 (1.828–6.398s): 报价、样品、采购、交付、回款依旁白逐词出现并沿全宽流程线排开，每次落点只点亮当前节点；Full-width strip，上疏下密，discrete-text-sequence 与 svg-path-draw 同步推进。
Scene 3 (6.398–8.569s): 流程线首次完整连通，五个节点同时清晰，镜头轻微推进到“交付—回款”连接处；Layered-depth，主链保持唯一运动轴。
Scene 4 (8.569–10.283s): 连接线在重击处断开，“证据断开”短标签压住断点并保持静止；Asymmetric 70/30，结论位于上方黄金区，不做退出动画。

## Frame 2 — 信息散落，项目不可回答

- scene: 表格、聊天、单据、风险四类信息从画面四周压向中心，中央只留下三个问题
- voiceover: "表格记进度，聊天追异常，单据留在系统。客户一追问，团队仍回答不了：卡在哪，谁负责，下一步是什么。"
- duration: 12.032s
- transition_in: crossfade 0.4s
- status: animated
- src: compositions/frames/02-problem.html
- type: pain_point
- persuasion: Pain agitation
- beat: overwhelm
- blueprint: overwhelm-surround (Adapt)
- asset_candidates:
- focal: none（中央三个业务追问为主视觉）
- roles: none（本镜头无外部素材）
- rules: depth-scatter-assemble dynamic-content-sequencing

narrativeRole: 把分散记录带来的管理盲区具体化。
keyMessage: 没有统一证据链，就没有可执行的项目全景。

Adapt: 保留“碎片从四周围压中央焦点”的签名动作；将抽象噪点换成表格、聊天、单据、风险四类真实工作载体。
Scene 1 (0.–2.406s): “表格”卡片从左上进入，中央仍保持空白；Rule-of-thirds，主体占内容区 40%，depth-scatter-assemble。
Scene 2 (2.406–4.922s): “聊天”卡片从右上压入，与表格形成不对齐的双层信息面；Asymmetric 60/40，两个载体仅沿共同中心收紧。
Scene 3 (4.922–7.11s): “单据”和“风险”从下方两侧补齐包围圈，四类信息降低不透明度，把视觉焦点让给中央；Layered-depth，四周为前景、中央为负空间。
Scene 4 (7.11–10.282s): “卡在哪 / 谁负责 / 下一步”依旁白逐项在中央组装，外围卡片同步轻微收紧；Centered triptych，dynamic-content-sequencing，最后一个问题在后半段才落地。
Scene 5 (10.282–12.032s): 三个问题保持清晰，外围信息停在未连接状态；静止阅读，不做呼吸或循环。

## Frame 3 — AutoFlow 360

- scene: 品牌标识由流程节点组装完成，商机、项目、供应链和财务四个标签围绕锁定
- voiceover: "AutoFlow 360 连接商机、项目、样品、销售、采购、交付和财务，形成一条可审计链路。"
- duration: 10.624s
- transition_in: zoom-through 0.5s
- status: animated
- src: compositions/frames/03-product-intro.html
- type: product_intro
- persuasion: Friction reduction
- beat: relief + clarity
- blueprint: logo-assemble-lockup (Adapt)
- asset_candidates: assets/brand/autoflow-360-logo.svg — AutoFlow 360 自有品牌标识
- focal: assets/brand/autoflow-360-logo.svg
- roles: autoflow-360-logo = cutout
- rules: center-outward-expansion svg-path-draw

narrativeRole: 给出产品名称与唯一承诺，建立后续演示的判断标准。
keyMessage: AutoFlow 360 是连接真实业务对象的 Frappe 扩展，不是换皮页面。

Adapt: 保留“零件汇聚并锁定品牌标识”的签名动作；让七类业务对象先形成一条链，标识在链路闭合时落地。
Scene 1 (0.–1.912s): 一个蓝色流程起点与细环线在中央显现，背景只保留低对比网格；Centered，主视觉约占内容区 45%，svg-path-draw。
Scene 2 (1.912–7.224s): 商机、项目、样品、销售、采购、交付、财务按旁白分组从中心向外展开，又由连线逐步接回中央；Radial stations，三层纵深，center-outward-expansion，后半段继续补齐节点。
Scene 3 (7.224–9.349s): 七个节点向内汇聚，品牌标识由结构件组装并锁定，环线闭合成“可审计链路”；Centered lockup，标识成为绝对主视觉。
Scene 4 (9.349–10.624s): 标识与闭合链路静止保持，节点标签降为次级；不做退出动画。

## Frame 4 — 先看需要行动的事

- scene: 工作台截图置于窗口框内，镜头依次强调待审批、七日节点、高风险和 AI 默认关闭
- voiceover: "角色工作台先回答三件事：待我审批什么，七天内什么到期，哪些高风险必须升级处理。AI 默认关闭。"
- duration: 12.267s
- transition_in: blur-crossfade 0.45s
- status: animated
- src: compositions/frames/04-workbench.html
- type: feature_showcase
- persuasion: Show-don't-tell proof
- beat: control
- blueprint: device-surface-showcase (Adapt)
- asset_candidates: assets/product/01-workbench-overview.png — 角色工作台总览
- focal: assets/product/01-workbench-overview.png
- roles: 01-workbench-overview = background (dim ~15%)
- rules: multi-phase-camera coordinate-target-zoom ambient-glow-bloom

narrativeRole: 第一次展示真实产品界面，从行动入口而非功能菜单切入。
keyMessage: 工作台围绕审批、时限和风险组织，而不是堆叠模块。

Adapt: 保留“真实界面作为大画幅设备表面、镜头按功能区推进”的签名动作；用四次局部聚焦代替浏览器操作演示。
Scene 1 (0.–2.044s): 工作台截图在无浏览器栏的窗口表面内铺满上方内容区，标题区先清晰，其余区域轻微降对比；Full-width surface，三层纵深，主界面首秒内可见。
Scene 2 (2.044–5.111s): 镜头沿单一路径聚焦“待我审批”，蓝色细框与短标签同步出现；Asymmetric 70/30，coordinate-target-zoom，不模拟鼠标。
Scene 3 (5.111–7.667s): 沿同一方向移动到“七天内到期”，前一高亮自然降级，日期区域成为主焦点；multi-phase-camera，局部信息占主体约 55%。
Scene 4 (7.667–10.222s): 镜头继续到高风险区域，风险卡通过一次克制强调脉冲落定；Rule-of-thirds，ambient-glow-bloom 仅使用品牌蓝浅色扩散。
Scene 5 (10.222–12.267s): 画面停到“AI 默认关闭”提示，添加“只读 · 默认关闭”短注释并保持；截图仍为主视觉，结尾静止阅读。

## Frame 5 — 三个可复现场景

- scene: 项目组合截图中的三条演示项目逐条高亮，金额、阶段和风险标签同步出现
- voiceover: "三个演示项目全部使用人民币合成数据，分别复现正常交付、供应商延期和客户退样重打。"
- duration: 11.072s
- transition_in: push-slide LEFT 0.45s
- status: animated
- src: compositions/frames/05-scenarios.html
- type: feature_showcase
- persuasion: Risk reversal
- beat: confidence
- blueprint: grid-card-assemble (Adapt)
- asset_candidates: assets/product/07-project-portfolio.png — 三个演示项目的项目组合表
- focal: assets/product/07-project-portfolio.png
- roles: 07-project-portfolio = background (dim ~12%)
- rules: anchored-layout-expand card-morph-anchor dynamic-content-sequencing

narrativeRole: 明确演示数据性质，并预告三条可重复验证的链路。
keyMessage: 场景不是一次性截图，而是可以重新播种和下钻的合成数据。

Adapt: 保留“三张卡从统一网格组装”的签名动作；卡片内容取自项目组合截图中的三条演示记录，截图表格作为可核对底层证据。
Scene 1 (0.–1.661s): 项目组合表以全宽表面出现，“人民币合成数据”短标签在左上落定；Full-width surface，主表首秒可见，底部字幕带保持清空。
Scene 2 (1.661–4.65s): 正常交付记录从表格行锚点扩展为第一张证据卡，金额、阶段、低风险随旁白逐项显现；Asymmetric 60/40，card-morph-anchor。
Scene 3 (4.65–7.75s): 供应商延期记录从第二行扩展到中央卡，高风险标签最后压入；Triptych 开始成形，anchored-layout-expand。
Scene 4 (7.75–9.965s): 客户退样重打记录从第三行扩展成右侧卡，两轮样品提示在后半段才出现；Triptych 满宽，dynamic-content-sequencing。
Scene 5 (9.965–11.072s): 三张卡与原始表格行通过细线对应，标题变为“可播种 · 可下钻 · 可复现”并静止保持。

## Frame 6 — 正常交付主链路

- scene: 正常项目全景截图缓慢横移，六个端到端节点按旁白依次点亮
- voiceover: "正常场景从商机立项开始，依次经过样品认可、报价审批、订单履约和交付签收；每一步都有来源单据。"
- duration: 12.096s
- transition_in: push-slide LEFT 0.45s
- status: animated
- src: compositions/frames/06-normal-flow.html
- type: feature_showcase
- persuasion: Show-don't-tell proof
- beat: ease + trust
- blueprint: device-surface-showcase (Adapt)
- asset_candidates: assets/product/02-normal-project.png — 正常项目端到端全景
- focal: assets/product/02-normal-project.png
- roles: 02-normal-project = background (dim ~8%)
- rules: multi-phase-camera coordinate-target-zoom svg-path-draw

narrativeRole: 完成第一条核心 Demo Loop，证明主链路覆盖业务对象而非只展示状态。
keyMessage: 正常交付链上的每个节点都有可追溯来源。

Adapt: 保留“单一真实界面上的连续镜头旅程”签名动作；用一条蓝色证据线串起六个业务节点，避免拆成六张独立幻灯片。
Scene 1 (0.–1.663s): 正常项目全景在大画幅表面出现，项目名称与当前阶段先清晰，流程其余部分保持可辨；Full-width surface，三层纵深。
Scene 2 (1.663–3.402s): 商机与项目立项节点依旁白点亮，证据线从左侧起点开始绘制；Rule-of-thirds，svg-path-draw。
Scene 3 (3.402–5.292s): 镜头沿证据线移动到样品认可，样品来源单据的局部高亮随后落下；multi-phase-camera，主体仍占内容区 65% 以上。
Scene 4 (5.292–7.787s): 证据线延伸到报价审批，状态与审批来源依次出现；coordinate-target-zoom，前一节点退为次级但不消失。
Scene 5 (7.787–9.828s): 镜头继续到销售订单与采购履约，两个相邻节点按因果次序点亮；Full-width strip，运动只沿同一证据轴。
Scene 6 (9.828–11.491s): 交付签收成为最终焦点，证据线完整贯通；Asymmetric 70/30，最后一段在后半程落地。
Scene 7 (11.491–12.096s): 六个节点与来源单据标记同时清晰，短标签“每一步都有来源”保持静止。

## Frame 7 — 发票、回款、结项证据

- scene: 镜头从采购收货移动到已付款发票和收付款记录，再落到零异常与操作审计
- voiceover: "履约完成后，销售发票已付款，收付款记录已提交，业务异常为零；操作记录保留了结项证据。"
- duration: 10.325s
- transition_in: crossfade 0.4s
- status: animated
- src: compositions/frames/07-normal-closure.html
- type: benefit_highlight
- persuasion: Evidence-first payoff
- beat: completion
- blueprint: camera-journey (Adapt)
- asset_candidates: assets/product/08-normal-finance-closure.png — 正常项目财务、零异常和审计证据
- focal: assets/product/08-normal-finance-closure.png
- roles: 08-normal-finance-closure = background (dim ~8%)
- rules: multi-phase-camera coordinate-target-zoom dynamic-content-sequencing

narrativeRole: 把“交付完成”继续推进到财务与严格结项，收紧完整闭环。
keyMessage: 项目结项依赖真实交付、发票、回款和审计证据。

Adapt: 保留“镜头在一张真实证据面上按路线旅行”的签名动作；路线从收货到付款、再到异常与审计，最终形成结项印章。
Scene 1 (0.–2.151s): 财务结项截图铺满内容区，镜头落在采购收货证据，左上显示短标题“交付之后”；Full-width surface，主界面首秒可见。
Scene 2 (2.151–4.56s): 镜头沿固定轨迹移动到销售发票，“已付款”状态被蓝色框精准标记；coordinate-target-zoom。
Scene 3 (4.56–6.883s): 镜头继续到收付款记录，“已提交”在旁白落点时出现第二个校验标记；multi-phase-camera，路径与上一个移动方向一致。
Scene 4 (6.883–9.034s): 业务异常区域放大，“0”以大号等宽数字计数落定，前两项校验缩为右侧证据轨迹；Asymmetric 60/40，dynamic-content-sequencing。
Scene 5 (9.034–10.325s): 操作记录成为最终焦点，四段证据由细线收束为“可结项”印章并保持静止；Centered payoff，不做退出动画。

## Frame 8 — 延期被确定性规则发现

- scene: 延期项目全景截图中，客户交期、供应商到货日、高风险标签和未开始节点依次放大
- voiceover: "延期场景中，系统比较供应商到货日和客户交期，命中确定性规则后标记高风险，后续节点不再被虚假推进。"
- duration: 12.437s
- transition_in: push-slide LEFT 0.45s
- status: animated
- src: compositions/frames/08-delay-detection.html
- type: feature_showcase
- persuasion: Negative contrast
- beat: urgency + control
- blueprint: device-surface-showcase (Adapt)
- asset_candidates: assets/product/03-supplier-delay.png — 供应商延期高风险项目全景
- focal: assets/product/03-supplier-delay.png
- roles: 03-supplier-delay = background (dim ~10%)
- rules: multi-phase-camera coordinate-target-zoom ai-tracking-box

narrativeRole: 展示系统如何从真实日期关系发现风险，而不是依赖不可解释的 AI 判断。
keyMessage: 确定性风险规则会阻止错误的乐观状态继续传播。

Adapt: 保留“真实界面表面上的逐点检查”签名动作；将镜头路径设计成日期 A、日期 B、规则结果、后续节点四步因果链。
Scene 1 (0.–1.99s): 延期项目全景铺满内容区，项目状态与时间轴先可见；Full-width surface，风险标签暂不抢焦点。
Scene 2 (1.99–4.477s): 镜头定位客户交期，日期 A 被蓝色追踪框锁定并在侧边生成简短标注；Rule-of-thirds，coordinate-target-zoom。
Scene 3 (4.477–6.965s): 镜头沿水平路径移动到供应商到货日，日期 B 进入同一比较尺；Split-screen comparison，ai-tracking-box 精准围住两项来源值。
Scene 4 (6.965–9.784s): 比较尺显示“到货日晚于客户交期”，高风险标签在规则命中时落定；Asymmetric 60/40，主结论位于上方黄金区。
Scene 5 (9.784–12.437s): 镜头落到后续未开始节点，一条止动线阻断虚假推进，日期与高风险结果保留在侧边作为因果证据；Layered-depth，结尾静止阅读。

## Frame 9 — 整改关闭也要留痕

- scene: 延期异常与操作记录纵向滚动，根因、整改证据、验证人、验证时间四个校验项逐项打勾
- voiceover: "异常关闭不是点一下按钮。根因、整改证据、验证人和验证时间都要齐全，并留下独立审计记录。"
- duration: 11.563s
- transition_in: crossfade 0.4s
- status: animated
- src: compositions/frames/09-delay-remediation.html
- type: feature_showcase
- persuasion: Risk reversal
- beat: trust
- blueprint: transcript-scroll-artifact-reveal (Adapt)
- asset_candidates: assets/product/09-delay-remediation.png — 延期异常已关闭与操作审计证据
- focal: assets/product/09-delay-remediation.png
- roles: 09-delay-remediation = background (dim ~8%)
- rules: 3d-page-scroll dynamic-content-sequencing svg-path-draw

narrativeRole: 把风险发现推进到整改与独立验证，完成第二条 Demo Loop。
keyMessage: 异常关闭必须满足证据字段，并保留独立可审计记录。

Adapt: 保留“证据面纵向推进、关键条目从记录中被提取为可核对产物”的签名动作；四个关闭条件按校验顺序出现。
Scene 1 (0.–2.207s): 延期异常与操作记录截图以纵向证据面出现，异常编号和关闭状态先清晰；Asymmetric 70/30，3d-page-scroll 只做一次可控推进。
Scene 2 (2.207–4.625s): 镜头停到根因字段，第一枚校验项从原字段锚点提取到右侧证据栏；Rule-of-thirds，dynamic-content-sequencing。
Scene 3 (4.625–7.148s): 整改证据字段进入焦点，第二枚校验项与来源位置以细线相连；Layered-depth，svg-path-draw。
Scene 4 (7.148–9.356s): 验证人与验证时间依次提取为第三、第四枚校验项，证据栏在后半段才完整；Asymmetric 60/40，四项按旁白落点逐一出现。
Scene 5 (9.356–11.563s): 操作审计记录成为最终焦点，四项校验收束为“独立验证完成”，画面静止保持便于核对。

## Frame 10 — 退样不覆盖历史

- scene: 两轮样品请求与两条客户反馈拆成左右两列，中间以关联线连接第一轮退样和第二轮认可
- voiceover: "退样场景保留第一轮反馈，生成第二轮样品请求，再记录客户认可；两轮证据互相链接，不覆盖历史。"
- duration: 11.776s
- transition_in: push-slide LEFT 0.45s
- status: animated
- src: compositions/frames/10-resample.html
- type: feature_showcase
- persuasion: Show-don't-tell proof
- beat: clarity + confidence
- blueprint: comparison-split (Adapt)
- asset_candidates: assets/product/04-resample.png — 两轮样品与客户反馈项目全景
- focal: assets/product/04-resample.png
- roles: 04-resample = background (dim ~10%)
- rules: split-tilt-cards card-morph-anchor svg-path-draw

narrativeRole: 完成第三条 Demo Loop，证明返工不是覆盖状态，而是保留版本链。
keyMessage: 重新打样保留前后轮次和客户决策证据。

Adapt: 保留“左右两种状态并列、由中间关系轴完成对照”的签名动作；左列承载第一轮退样，右列承载第二轮认可，原截图作为证据底层。
Scene 1 (0.–1.806s): 项目全景截图出现，第一轮样品请求从左侧来源区域展开成卡片；Split-screen 左列先建立，右列保留空位，card-morph-anchor。
Scene 2 (1.806–4.396s): 第一轮客户反馈“退样”从对应记录锚点进入左列下方，与样品请求形成纵向因果；Left 50%，层级由状态标签与位置共同区分。
Scene 3 (4.396–6.595s): 第二轮样品请求从右侧来源区域展开，左右两列由中间轮次轴分隔；split-tilt-cards 的签名对照姿态落定。
Scene 4 (6.595–9.028s): 第二轮客户认可进入右列下方，右列由弱到强成为当前主视觉；Split-screen，认可状态在旁白落点出现。
Scene 5 (9.028–11.776s): 四张证据卡之间绘制来源关联线，中央显示“保留历史，不覆盖”，两轮记录共同保持清晰；svg-path-draw，结尾静止阅读。

## Frame 11 — 管理驾驶舱与压力数据

- scene: 驾驶舱截图中的项目数、在途金额、风险和异常依次计数，最后镜头落到最近项目下钻入口
- voiceover: "在合成压力数据下，管理驾驶舱按权限汇总二百零二个项目、在途金额、风险和未关闭异常，并支持下钻。"
- duration: 12.736s
- transition_in: zoom-through 0.5s
- status: animated
- src: compositions/frames/11-cockpit.html
- type: feature_showcase
- persuasion: Statistical proof
- beat: scale + control
- blueprint: dataviz-countup (Adapt)
- asset_candidates: assets/product/05-management-cockpit.png — 管理驾驶舱与合成压力数据
- focal: assets/product/05-management-cockpit.png
- roles: 05-management-cockpit = background (dim ~8%)
- rules: counting-dynamic-scale chart-scrub-readout stat-bars-and-fills coordinate-target-zoom

narrativeRole: 从单项目切到管理视角，同时明确数字来自合成压力数据。
keyMessage: 驾驶舱在权限边界内汇总并支持回到明细。

Adapt: 保留“核心数字计数、图表随读数揭示、最终回到可下钻记录”的签名动作；所有指标直接对应真实驾驶舱截图。
Scene 1 (0.–1.819s): 管理驾驶舱截图铺满内容区，“合成压力数据”标签先落定，四项指标仍以低对比保留；Full-width surface，主界面首秒可见。
Scene 2 (1.819–4.185s): 项目数从 0 计到 202，数字卡成为画面主视觉；Asymmetric 60/40，counting-dynamic-scale。
Scene 3 (4.185–6.55s): 在途金额卡按人民币格式计数并填充对应进度条，项目数退为次级；Two-column dataviz，stat-bars-and-fills。
Scene 4 (6.55–8.915s): 风险指标进入焦点，相关图表读数随高亮线同步推进；Layered-depth，chart-scrub-readout。
Scene 5 (8.915–11.099s): 未关闭异常指标在后半程揭示，四项管理信息形成完整仪表区；Full-width strip，所有数字稳定停留。
Scene 6 (11.099–12.736s): 镜头定位最近项目下钻入口，短标签“按权限汇总 · 可回到明细”落定并保持；coordinate-target-zoom，不模拟点击。

## Frame 12 — 权限与 AI 都有边界

- scene: 角色、项目、公司、门户四张权限卡依次组装，AI 默认关闭卡最后落在只读护栏内
- voiceover: "权限按角色、项目、公司和门户四层隔离。AI 只读分析、默认关闭，失败也不会提交单据或改业务状态。"
- duration: 11.712s
- transition_in: crossfade 0.4s
- status: animated
- src: compositions/frames/12-guardrails.html
- type: benefit_highlight
- persuasion: Risk reversal
- beat: peace of mind
- blueprint: grid-card-assemble (Adapt)
- asset_candidates: assets/product/01-workbench-overview.png — 工作台中 AI 默认关闭提示
- focal: assets/product/01-workbench-overview.png
- roles: 01-workbench-overview = supporting
- rules: anchored-layout-expand dynamic-content-sequencing svg-path-draw

narrativeRole: 回答企业系统最常见的权限、安全和 AI 可控性问题。
keyMessage: 权限隔离和安全降级是业务边界，不是演示装饰。

Adapt: 保留“四张卡从网格组装并由中心边界统一约束”的签名动作；截图只作为 AI 默认关闭的真实证据，权限四层用简洁结构卡表达。
Scene 1 (0.–1.991s): “角色”权限卡从左上锚点展开，边界线只覆盖当前卡；Grid 2×2 起始位，anchored-layout-expand。
Scene 2 (1.991–4.099s): “项目”卡在右上出现，与角色卡通过一条访问路径相连；Grid 2×2，两卡同层但主次清晰。
Scene 3 (4.099–6.207s): “公司”卡在左下出现，边界线扩展为三层隔离；dynamic-content-sequencing。
Scene 4 (6.207–8.198s): “门户”卡补齐右下，四层权限卡形成完整网格，中心显示“最小权限”；Grid 2×2 满幅，svg-path-draw 收束边界。
Scene 5 (8.198–11.712s): 工作台中的 AI 默认关闭提示从截图锚点提取为横向护栏卡，“只读分析 / 默认关闭 / 失败不改状态”依旁白逐项出现；Full-width strip，四张权限卡退为上方证据，结尾保持静止。

## Frame 13 — 工程证据可复现

- scene: 四张数据卡依次计数到 170/170、148/148、3/3 和 RESTORE_CHECK_PASSED，底部出现静态、集成、浏览器、恢复四层标签
- voiceover: "工程证据同样可复现：一百七十项静态测试、一百四十八项 Frappe 集成测试、三项浏览器闭环全部通过，备份恢复校验通过。"
- duration: 15.488s
- transition_in: zoom-through 0.5s
- status: animated
- src: compositions/frames/13-engineering-proof.html
- type: feature_showcase
- persuasion: Statistical proof
- beat: trust + confidence
- blueprint: dataviz-countup (Adapt)
- asset_candidates:
- focal: none（四张验收数据卡为主视觉）
- roles: none（本镜头无外部素材）
- rules: counting-dynamic-scale stat-bars-and-fills dynamic-content-sequencing

narrativeRole: 用当前仓库实际验收结果收束工程可信度，不把界面完成等同于系统完成。
keyMessage: 项目有四层可复现证据，并完成过隔离恢复演练。

Adapt: 保留“数字逐项计数并汇总为一张可信结论”的签名动作；四张卡对应仓库已验证的静态、集成、浏览器与恢复证据。
Scene 1 (0.–2.144s): 四格验收矩阵轮廓从中央展开，标题“可复现的工程证据”先落定，各数值保持空位；Grid 2×2，主视觉覆盖内容区约 65%。
Scene 2 (2.144–4.766s): 第一张卡计数到 170/170，并在下方填满“静态测试”短条；左上焦点，counting-dynamic-scale 与 stat-bars-and-fills。
Scene 3 (4.766–7.625s): 第二张卡计数到 148/148，“Frappe 集成”标签随后出现；右上焦点，第一张卡保留为次级证据。
Scene 4 (7.625–10.127s): 第三张卡计数到 3/3，“浏览器闭环”在数字落定时显现；左下焦点，dynamic-content-sequencing。
Scene 5 (10.127–13.344s): 第四张卡从校验进度变为 `RESTORE_CHECK_PASSED`，恢复标记最后压入；右下焦点，长文本作为等宽证据而非旁白复述。
Scene 6 (13.344–15.488s): 四张卡共同清晰，中心关系线收束为“静态 · 集成 · 端到端 · 恢复”四层证据链并静止保持。

## Frame 14 — 打开仓库，继续下钻

- scene: 手机工作台短暂滑入证明多端适配，随后清场并组装品牌标识与“源码 · 演示脚本 · 验收证据”三项 CTA
- voiceover: "这不是一张概念图。打开仓库，按演示脚本，从任一场景继续下钻。"
- duration: 8.213s
- transition_in: blur-crossfade 0.45s
- status: animated
- src: compositions/frames/14-cta.html
- type: cta
- persuasion: Direct demonstration invitation
- beat: motivation
- blueprint: logo-assemble-lockup (Adapt)
- asset_candidates: assets/product/06-mobile-workbench.png — 手机宽度工作台; assets/brand/autoflow-360-logo.svg — AutoFlow 360 品牌标识
- focal: assets/brand/autoflow-360-logo.svg
- roles: 06-mobile-workbench = supporting · autoflow-360-logo = cutout
- rules: viewport-change center-outward-expansion svg-path-draw

narrativeRole: 给出招聘场景中的下一步动作，不虚构公开链接或商业采用。
keyMessage: 作品集最终交付是可阅读、可运行、可复现、可提问的仓库。

Adapt: 保留“辅助画面清场后，品牌组件汇聚并锁定 CTA”的签名动作；手机工作台只证明多端适配，最终聚焦仓库中的三类交付证据。
Scene 1 (0.–1.877s): 手机工作台从左侧进入并在上方内容区短暂停留，真实界面保持可辨；Asymmetric 60/40，viewport-change 体现桌面到手机的尺度变化。
Scene 2 (1.877–3.52s): 手机表面沿同一曲线移到左侧次级位置，“不是概念图”作为短结论在右侧落定；Rule-of-thirds，不展示旁白全文。
Scene 3 (3.52–5.866s): 手机画面淡为背景，品牌标识从流程节点向中央组装，“AutoFlow 360”锁定；Centered lockup，center-outward-expansion 与 svg-path-draw。
Scene 4 (5.866–8.213s): “源码 · 演示脚本 · 验收证据”三项 CTA 在标识下方依次出现，最终画面静止并留出半秒阅读；Centered，唯一最终镜头允许克制淡出。
