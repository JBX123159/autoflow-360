(() => {
function escapeHtml(value) {
	return frappe.utils
		.escape_html(String(value ?? ""))
		.replaceAll('"', "&quot;")
		.replaceAll("'", "&#39;");
}

function safeRoute(route) {
	const value = String(route || "");
	return value.startsWith("/app/") ? escapeHtml(value) : "#";
}

function formatWorkbenchDate(value) {
	if (!value) {
		return "未设置";
	}
	try {
		return frappe.datetime.str_to_user(String(value));
	} catch (error) {
		return String(value);
	}
}

function formatWorkbenchAmount(value, currency) {
	try {
		const numericValue = Number(value || 0);
		const currencyCode = String(currency || "CNY").trim().toUpperCase() || "CNY";
		return new Intl.NumberFormat("zh-CN", {
			style: "currency",
			currency: currencyCode,
			minimumFractionDigits: 2,
			maximumFractionDigits: 2,
		}).format(Number.isFinite(numericValue) ? numericValue : 0);
	} catch (error) {
		return `${currency || ""} ${Number(value || 0).toLocaleString()}`.trim();
	}
}

function renderLoading() {
	return `
		<div class="autoflow-page" aria-busy="true" aria-label="正在加载工作台">
			<div class="af-shell">
				${Array.from({ length: 3 }, () => `
					<div class="af-skeleton">
						<div class="af-skeleton-line"></div>
						<div class="af-skeleton-line"></div>
						<div class="af-skeleton-line"></div>
					</div>
				`).join("")}
			</div>
		</div>
	`;
}

function renderEmpty(title, message) {
	return `
		<div class="af-empty">
			<h3>${escapeHtml(title)}</h3>
			<p class="af-muted">${escapeHtml(message)}</p>
		</div>
	`;
}

function renderError(message) {
	return `
		<div class="autoflow-page">
			<div class="af-error" role="alert">
				<h3>工作台暂时无法加载</h3>
				<p class="af-muted">${escapeHtml(message || "请稍后重试，核心业务单据不受影响。")}</p>
				<button type="button" class="af-action af-retry">重新加载</button>
			</div>
		</div>
	`;
}

function renderSectionList(rows, emptyTitle, emptyMessage, metaBuilder) {
	if (!rows.length) {
		return `<div class="af-panel-body">${renderEmpty(emptyTitle, emptyMessage)}</div>`;
	}
	return `
		<div class="af-list">
			${rows.map((row) => `
				<div class="af-list-row">
					<div class="af-list-copy">
						<a class="af-list-title" href="${safeRoute(row.route)}">${escapeHtml(row.title || row.name)}</a>
						<div class="af-list-meta">${escapeHtml(metaBuilder(row))}</div>
					</div>
					<a class="af-text-link" href="${safeRoute(row.route)}">查看</a>
				</div>
			`).join("")}
		</div>
	`;
}

class AutoFlowWorkbench {
	constructor(page) {
		this.page = page;
		this.$main = page.main;
		this.data = null;
		this.panorama = null;
		this.selectedProject = null;
		this.pendingSection = null;
		this.bindEvents();
		this.page.add_inner_button("刷新", () => this.refresh());
		this.page.add_inner_button("管理驾驶舱", () => frappe.set_route("autoflow-cockpit"));
	}

	bindEvents() {
		this.$main.on("click", ".af-retry", () => this.refresh());
		this.$main.on("click", ".af-project-open", async (event) => {
			const projectName = $(event.currentTarget).attr("data-project");
			if (!projectName) {
				return;
			}
			this.selectedProject = projectName;
			this.pendingSection = "overview";
			await this.loadPanorama();
		});
		this.$main.on("click", ".af-back-workbench", () => {
			this.selectedProject = null;
			this.panorama = null;
			this.render();
		});
		this.$main.on("click", ".af-run-ai", async (event) => {
			if (!this.selectedProject) {
				return;
			}
			const $button = $(event.currentTarget);
			$button.prop("disabled", true).text("正在生成");
			try {
				await frappe.call({
					method: "autoflow_360.api.analytics.create_project_analysis",
					type: "POST",
					args: {
						project_name: this.selectedProject,
						analysis_type: "风险摘要",
					},
				});
				frappe.show_alert({ message: "AI 分析记录已生成", indicator: "green" });
				await this.loadPanorama();
			} catch (error) {
				frappe.msgprint({
					title: "AI 分析未完成",
					indicator: "orange",
					message: "已保留可审计的降级记录，项目业务状态未被修改。",
				});
			} finally {
				$button.prop("disabled", false).text("生成风险摘要");
			}
		});
	}

	async show() {
		if (frappe.route_options && frappe.route_options.project) {
			this.selectedProject = frappe.route_options.project;
			this.pendingSection = frappe.route_options.section || "overview";
			frappe.route_options = null;
		}
		await this.refresh();
	}

	async refresh() {
		this.$main.html(renderLoading());
		try {
			const response = await frappe.call({
				method: "autoflow_360.api.analytics.get_workbench_data",
				type: "GET",
			});
			this.data = response.message;
			if (this.selectedProject) {
				await this.fetchPanorama();
			}
			this.render();
		} catch (error) {
			this.$main.html(renderError(error.message));
		}
	}

	async fetchPanorama() {
		const response = await frappe.call({
			method: "autoflow_360.api.analytics.get_project_panorama",
			type: "GET",
			args: { project_name: this.selectedProject },
		});
		this.panorama = response.message;
	}

	async loadPanorama() {
		this.$main.html(renderLoading());
		try {
			await this.fetchPanorama();
			this.render();
		} catch (error) {
			this.$main.html(renderError(error.message));
		}
	}

	render() {
		if (!this.data) {
			this.$main.html(renderError("没有收到工作台数据。"));
			return;
		}
		const html = `
			<div class="autoflow-page">
				<div class="af-shell">
					${this.renderNavigation()}
					<main class="af-main" id="af-main-content">
						${this.selectedProject && this.panorama ? this.renderPanorama() : this.renderOverview()}
					</main>
					<aside class="af-aside" aria-label="风险与 AI 辅助">
						${this.renderRiskAside()}
						${this.renderAIAside()}
					</aside>
				</div>
			</div>
		`;
		this.$main.html(html);
		this.focusPendingSection();
	}

	focusPendingSection() {
		if (!this.pendingSection) {
			return;
		}
		const target = this.$main.find(`#af-section-${this.pendingSection}`).get(0);
		if (target) {
			target.scrollIntoView({ block: "start" });
		}
		this.pendingSection = null;
	}

	renderNavigation() {
		const inPanorama = Boolean(this.selectedProject && this.panorama);
		return `
			<nav class="af-nav" aria-label="角色工作台导航">
				<div class="af-brand">
					<strong>AutoFlow 360</strong>
					<span class="af-kicker">${escapeHtml(this.data.role)}</span>
				</div>
				<div class="af-nav-list">
					<a class="af-nav-link" ${inPanorama ? "" : 'aria-current="page"'} href="/app/autoflow-workbench">我的工作台</a>
					<a class="af-nav-link" href="/app/customer-project">客户项目</a>
					<a class="af-nav-link" href="/app/project-risk">项目风险</a>
					<a class="af-nav-link" href="/app/business-exception">业务异常</a>
					<a class="af-nav-link" href="/app/autoflow-approval-request">审批中心</a>
					<a class="af-nav-link" href="/app/ai-analysis">AI 分析</a>
				</div>
			</nav>
		`;
	}

	renderOverview() {
		return `
			<section class="af-attention-grid" aria-label="需要行动的事项">
				<div class="af-panel">
					<div class="af-panel-header"><h2>待我审批</h2><span class="af-chip">${this.data.approvals.length} 项</span></div>
					${renderSectionList(
						this.data.approvals,
						"暂无待审批",
						"符合本人授权范围的待审批事项会显示在这里。",
						(row) => `${row.company || "未设置公司"}，申请人 ${row.requested_by || "未设置"}`,
					)}
				</div>
				<div class="af-panel">
					<div class="af-panel-header"><h2>七日内节点</h2><span class="af-chip">${this.data.due_within_seven_days.length} 项</span></div>
					${renderSectionList(
						this.data.due_within_seven_days,
						"七日内无到期项",
						"下一步行动、客户交期和项目里程碑均无临近到期项。",
						(row) => `${formatWorkbenchDate(row.due_date)}，负责人 ${row.owner || "未设置"}`,
					)}
				</div>
			</section>
			<section class="af-panel" aria-labelledby="af-project-heading">
				<div class="af-panel-header">
					<div><h2 id="af-project-heading">我的项目</h2><span class="af-kicker">最近更新且当前有权读取</span></div>
					<a class="af-text-link" href="/app/customer-project">打开项目列表</a>
				</div>
				${this.renderProjectTable()}
			</section>
		`;
	}

	renderProjectTable() {
		if (!this.data.projects.length) {
			return `<div class="af-panel-body">${renderEmpty("暂无可见项目", "加入项目成员或获得公司范围授权后，项目会显示在这里。")}</div>`;
		}
		return `
			<div class="af-table-wrap">
				<table class="af-table">
					<thead><tr><th>项目</th><th>客户</th><th>阶段</th><th>风险</th><th>预计金额</th><th>下一步</th></tr></thead>
					<tbody>
						${this.data.projects.map((row) => `
							<tr>
								<td><button type="button" class="af-project-open" data-project="${escapeHtml(row.name)}">${escapeHtml(row.title || row.name)}</button><div class="af-list-meta">${escapeHtml(row.name)}</div></td>
								<td>${escapeHtml(row.customer || "未设置")}</td>
								<td><span class="af-chip">${escapeHtml(row.stage || "未设置")}</span></td>
								<td><span class="af-chip" data-risk="${escapeHtml(row.overall_risk_level)}">${escapeHtml(row.overall_risk_level || "低")}</span></td>
								<td class="af-number">${escapeHtml(formatWorkbenchAmount(row.expected_amount, row.currency))}</td>
								<td>${escapeHtml(row.next_action || "未设置")}<div class="af-list-meta">${escapeHtml(formatWorkbenchDate(row.next_action_due_date))}</div></td>
							</tr>
						`).join("")}
					</tbody>
				</table>
			</div>
		`;
	}

	renderRiskAside() {
		const risks = this.selectedProject && this.panorama ? this.panorama.risks : this.data.high_risks;
		return `
			<section class="af-panel" id="af-section-risks">
				<div class="af-panel-header"><h2>${this.selectedProject ? "项目风险" : "高风险"}</h2><span class="af-chip" data-risk="高">${risks.length} 项</span></div>
				${renderSectionList(
					risks,
					"暂无高风险",
					"确定性风险引擎未发现当前需要升级处理的事项。",
					(row) => `${row.status || "未设置状态"}，到期 ${formatWorkbenchDate(row.due_date)}`,
				)}
			</section>
		`;
	}

	renderAIAside() {
		if (!this.selectedProject || !this.panorama) {
			return `
				<section class="af-panel">
					<div class="af-panel-header"><h2>AI 助手</h2><span class="af-chip">默认关闭</span></div>
					<div class="af-panel-body">
						<p class="af-muted">打开一个项目后可主动生成带真实来源的风险摘要。AI 不会提交单据或修改业务状态。</p>
					</div>
				</section>
			`;
		}
		return `
			<section class="af-panel" id="af-section-ai">
				<div class="af-panel-header"><h2>AI 助手</h2><span class="af-chip">${this.panorama.ai_analyses.length} 条记录</span></div>
				<div class="af-panel-body">
					<button type="button" class="af-action af-run-ai">生成风险摘要</button>
					<p class="af-muted" style="margin: 10px 0 0;">结果必须引用当前可读的真实业务记录，失败时安全降级。</p>
				</div>
				${renderSectionList(
					this.panorama.ai_analyses.slice(0, 5),
					"尚无 AI 分析",
					"AI 默认关闭，只有主动调用或显式启用周报任务时才会生成。",
					(row) => `${row.status || "未设置状态"}，${formatWorkbenchDate(row.requested_at)}`,
				)}
			</section>
		`;
	}

	renderPanorama() {
		const project = this.panorama.project;
		return `
			<section class="af-panorama" id="af-section-overview">
				<div class="af-panorama-title">
					<div>
						<button type="button" class="af-project-open af-back-workbench">返回工作台</button>
						<h2>${escapeHtml(project.title || project.name)}</h2>
						<div class="af-list-meta">${escapeHtml(project.name)}，${escapeHtml(project.customer || "未设置客户")}</div>
					</div>
					<a class="af-action af-secondary" href="${safeRoute(project.route)}">打开标准表单</a>
				</div>
				<div class="af-summary-grid">
					${this.renderSummaryItem("阶段", project.stage)}
					${this.renderSummaryItem("负责人", project.project_manager)}
					${this.renderSummaryItem("客户交期", formatWorkbenchDate(project.customer_delivery_date))}
					${this.renderSummaryItem("预计金额", formatWorkbenchAmount(project.expected_amount, project.currency), true)}
				</div>
				<section class="af-panel" id="af-section-flow">
					<div class="af-panel-header"><h2>端到端流程</h2><span class="af-chip" data-risk="${escapeHtml(project.overall_risk_level)}">风险 ${escapeHtml(project.overall_risk_level)}</span></div>
					<div class="af-flow">
						${this.panorama.flow.map((step) => `
							<div class="af-flow-step">
								<strong>${escapeHtml(step.label)}</strong>
								<span class="af-chip" data-status="${escapeHtml(step.status)}">${escapeHtml(step.status)}</span>
							</div>
						`).join("")}
					</div>
				</section>
				<section id="af-section-documents">
					<div class="af-panel-header af-panel"><div><h2>关联单据</h2><span class="af-kicker">只显示当前用户可读取的来源记录</span></div></div>
					<div class="af-document-groups">${this.renderDocumentGroups()}</div>
				</section>
				<section class="af-attention-grid" id="af-section-exceptions">
					<div class="af-panel">
						<div class="af-panel-header"><h2>业务异常</h2><span class="af-chip">${this.panorama.exceptions.length} 项</span></div>
						${renderSectionList(this.panorama.exceptions, "暂无业务异常", "当前项目没有可读的业务异常记录。", (row) => `${row.status || "未设置状态"}，${row.risk_level || "未设置风险"}`)}
					</div>
					<div class="af-panel" id="af-section-audit">
						<div class="af-panel-header"><h2>操作记录</h2><span class="af-chip">${this.panorama.audit.length} 条</span></div>
						${renderSectionList(this.panorama.audit, "暂无字段变更", "项目创建后尚未产生可读的版本变更记录。", (row) => `${row.owner || "未知用户"}，${formatWorkbenchDate(row.creation)}`)}
					</div>
				</section>
			</section>
		`;
	}

	renderSummaryItem(label, value, numeric = false) {
		return `
			<div class="af-summary-item">
				<span class="af-summary-label">${escapeHtml(label)}</span>
				<strong class="${numeric ? "af-number" : ""}">${escapeHtml(value || "未设置")}</strong>
			</div>
		`;
	}

	renderDocumentGroups() {
		const labels = {
			samples: "样品与反馈",
			sales: "销售",
			procurement: "采购",
			delivery: "交付",
			finance: "财务",
		};
		return Object.entries(this.panorama.documents).map(([group, rows]) => `
			<div class="af-document-group">
				<h3>${escapeHtml(labels[group] || group)} <span class="af-kicker">${rows.length} 条</span></h3>
				${rows.length ? `
					<div class="af-list">
						${rows.map((row) => `
							<div class="af-list-row">
								<div class="af-list-copy"><a class="af-list-title" href="${safeRoute(row.route)}">${escapeHtml(row.name)}</a><div class="af-list-meta">${escapeHtml(row.doctype)}，${escapeHtml(String(row.status ?? "未设置"))}</div></div>
								<a class="af-text-link" href="${safeRoute(row.route)}">查看</a>
							</div>
						`).join("")}
					</div>
				` : `<div class="af-panel-body"><p class="af-muted">当前无可读记录。</p></div>`}
			</div>
		`).join("");
	}
}

frappe.pages["autoflow-workbench"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "AutoFlow 工作台",
		single_column: true,
	});
	wrapper.autoflowWorkbench = new AutoFlowWorkbench(page);
};

frappe.pages["autoflow-workbench"].on_page_show = function (wrapper) {
	wrapper.autoflowWorkbench.show();
};
})();
