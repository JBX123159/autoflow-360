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

function renderLoading() {
	return `
		<div class="autoflow-page" aria-busy="true" aria-label="正在加载管理驾驶舱">
			<div class="af-cockpit">
				<div class="af-skeleton">
					<div class="af-skeleton-line"></div>
					<div class="af-skeleton-line"></div>
					<div class="af-skeleton-line"></div>
				</div>
				<div class="af-cockpit-grid">
					${Array.from({ length: 3 }, () => `
						<div class="af-skeleton">
							<div class="af-skeleton-line"></div>
							<div class="af-skeleton-line"></div>
						</div>
					`).join("")}
				</div>
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
				<h3>管理驾驶舱暂时无法加载</h3>
				<p class="af-muted">${escapeHtml(message || "请检查权限或筛选条件后重试。")}</p>
				<button type="button" class="af-action af-retry">重新加载</button>
			</div>
		</div>
	`;
}

function formatNumber(value) {
	return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatMetricValue(metric) {
	if (metric.value && typeof metric.value === "object") {
		return Object.entries(metric.value)
			.map(([currency, amount]) => `${currency} ${formatNumber(amount)}`)
			.join(" / ");
	}
	if (/^[A-Z]{3}$/.test(metric.unit || "")) {
		try {
			const numericValue = Number(metric.value || 0);
			return new Intl.NumberFormat("zh-CN", {
				style: "currency",
				currency: metric.unit,
				minimumFractionDigits: 2,
				maximumFractionDigits: 2,
			}).format(Number.isFinite(numericValue) ? numericValue : 0);
		} catch (error) {
			return `${metric.unit} ${formatNumber(metric.value)}`;
		}
	}
	return `${formatNumber(metric.value)} ${metric.unit || ""}`.trim();
}

function renderDefinitionList(data, emptyMessage) {
	const entries = Object.entries(data || {});
	if (!entries.length) {
		return renderEmpty("暂无汇总数据", emptyMessage);
	}
	return `
		<dl class="af-definition-list">
			${entries.map(([label, value]) => `
				<dt>${escapeHtml(label)}</dt>
				<dd>${escapeHtml(formatNumber(value))}</dd>
			`).join("")}
		</dl>
	`;
}

class AutoFlowCockpit {
	constructor(page) {
		this.page = page;
		this.$main = page.main;
		this.data = null;
		this.companyField = page.add_field({
			fieldname: "company",
			label: "公司",
			fieldtype: "Link",
			options: "Company",
			change: () => this.refresh(),
		});
		this.page.add_inner_button("刷新", () => this.refresh());
		this.page.add_inner_button("返回工作台", () => frappe.set_route("autoflow-workbench"));
		this.$main.on("click", ".af-retry", () => this.refresh());
	}

	async refresh() {
		this.$main.html(renderLoading());
		const company = this.companyField.get_value();
		try {
			const response = await frappe.call({
				method: "autoflow_360.api.analytics.get_management_cockpit",
				type: "GET",
				args: { filters: company ? { company } : {} },
			});
			this.data = response.message;
			this.render();
		} catch (error) {
			this.$main.html(renderError(error.message));
		}
	}

	render() {
		if (!this.data) {
			this.$main.html(renderError("没有收到驾驶舱数据。"));
			return;
		}
		this.$main.html(`
			<div class="autoflow-page">
				<div class="af-cockpit">
					<section aria-label="管理指标">
						${this.renderMetrics()}
					</section>
					<section class="af-cockpit-grid" aria-label="分布与异常">
						${this.renderDistributionPanel("项目阶段", this.data.stage_distribution, "当前筛选范围内没有项目。")}
						${this.renderDistributionPanel("项目风险", this.data.risk_distribution, "当前筛选范围内没有风险分布。")}
						${this.renderDistributionPanel("异常状态", this.data.exception_summary, "当前筛选范围内没有业务异常。")}
					</section>
					${this.renderCurrencyTotals()}
					${this.renderRecentProjects()}
				</div>
			</div>
		`);
	}

	renderMetrics() {
		return `
			<div class="af-metrics">
				${this.data.metrics.map((metric) => `
					<article class="af-metric">
						<span class="af-metric-label">${escapeHtml(metric.label)}</span>
						<strong class="af-metric-value">${escapeHtml(formatMetricValue(metric))}</strong>
						<p class="af-metric-definition">${escapeHtml(metric.definition)}</p>
						<a class="af-text-link" href="${safeRoute(metric.drilldown)}">下钻查看</a>
					</article>
				`).join("")}
			</div>
		`;
	}

	renderDistributionPanel(title, data, emptyMessage) {
		return `
			<section class="af-panel">
				<div class="af-panel-header"><h2>${escapeHtml(title)}</h2></div>
				<div class="af-panel-body">${renderDefinitionList(data, emptyMessage)}</div>
			</section>
		`;
	}

	renderCurrencyTotals() {
		const entries = Object.entries(this.data.currency_totals || {});
		if (!entries.length) {
			return "";
		}
		return `
			<section class="af-panel">
				<div class="af-panel-header">
					<div><h2>在途金额币种拆分</h2><span class="af-kicker">不使用推测汇率，不同币种分别展示</span></div>
				</div>
				<div class="af-summary-grid">
					${entries.map(([currency, value]) => `
						<div class="af-summary-item">
							<span class="af-summary-label">${escapeHtml(currency)}</span>
							<strong class="af-number">${escapeHtml(`${currency} ${formatNumber(value)}`)}</strong>
						</div>
					`).join("")}
				</div>
			</section>
		`;
	}

	renderRecentProjects() {
		const rows = this.data.recent_projects || [];
		return `
			<section class="af-panel">
				<div class="af-panel-header">
					<div><h2>最近项目</h2><span class="af-kicker">按当前用户权限与公司筛选返回</span></div>
					<a class="af-text-link" href="/app/customer-project">项目列表</a>
				</div>
				${rows.length ? `
					<div class="af-table-wrap">
						<table class="af-table">
							<thead><tr><th>项目</th><th>客户</th><th>阶段</th><th>风险</th><th>预计金额</th><th>下一步</th></tr></thead>
							<tbody>
								${rows.map((row) => `
									<tr>
										<td><a class="af-list-title" href="${safeRoute(row.route)}">${escapeHtml(row.title || row.name)}</a><div class="af-list-meta">${escapeHtml(row.name)}</div></td>
										<td>${escapeHtml(row.customer || "未设置")}</td>
										<td><span class="af-chip">${escapeHtml(row.stage || "未设置")}</span></td>
										<td><span class="af-chip" data-risk="${escapeHtml(row.overall_risk_level)}">${escapeHtml(row.overall_risk_level || "低")}</span></td>
										<td class="af-number">${escapeHtml(`${row.currency || ""} ${formatNumber(row.expected_amount)}`.trim())}</td>
										<td>${escapeHtml(row.next_action || "未设置")}</td>
									</tr>
								`).join("")}
							</tbody>
						</table>
					</div>
				` : `<div class="af-panel-body">${renderEmpty("暂无项目", "当前筛选范围内没有可读取的客户项目。")}</div>`}
			</section>
		`;
	}
}

frappe.pages["autoflow-cockpit"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "AutoFlow 管理驾驶舱",
		single_column: true,
	});
	wrapper.autoflowCockpit = new AutoFlowCockpit(page);
};

frappe.pages["autoflow-cockpit"].on_page_show = function (wrapper) {
	wrapper.autoflowCockpit.refresh();
};
})();
