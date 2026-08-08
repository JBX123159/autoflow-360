from urllib.parse import quote, urlencode

import frappe
from frappe import _
from frappe.utils import add_days, cstr, flt, getdate, now_datetime, nowdate

from autoflow_360.ai.service import analyze_project
from autoflow_360.services.sales_conversion import approval_request_has_authority


INTERNAL_ROLES = {
	"AutoFlow Administrator",
	"AutoFlow Sales Operations",
	"AutoFlow Project Manager",
	"AutoFlow Procurement",
	"AutoFlow Warehouse",
	"AutoFlow Finance",
	"AutoFlow Executive",
}
MANAGEMENT_ROLES = {"AutoFlow Administrator", "AutoFlow Executive"}
ROLE_PRIORITY = (
	"AutoFlow Executive",
	"AutoFlow Project Manager",
	"AutoFlow Sales Operations",
	"AutoFlow Procurement",
	"AutoFlow Warehouse",
	"AutoFlow Finance",
	"AutoFlow Administrator",
)
ACTIVE_STAGES = {
	"潜在项目",
	"样品阶段",
	"报价阶段",
	"已定点",
	"订单履约",
	"已交付",
	"待回款",
	"暂停",
}
FLOW_STAGES = (
	("opportunity", "商机与立项", "潜在项目"),
	("sample", "样品认可", "样品阶段"),
	("quotation", "报价审批", "报价阶段"),
	("award", "客户定点", "已定点"),
	("fulfilment", "订单履约", "订单履约"),
	("delivery", "交付签收", "已交付"),
	("collection", "开票回款", "待回款"),
	("closure", "项目结项", "已结项"),
)
RELATED_DOCUMENT_GROUPS = {
	"samples": (
		("Sample Request", "customer_project"),
		("Customer Feedback", "customer_project"),
	),
	"sales": (
		("Quotation", "custom_customer_project"),
		("Sales Order", "custom_customer_project"),
	),
	"procurement": (
		("Material Request", "custom_customer_project"),
		("Request for Quotation", "custom_customer_project"),
		("Supplier Quotation", "custom_customer_project"),
		("Purchase Order", "custom_customer_project"),
		("Purchase Receipt", "custom_customer_project"),
		("Purchase Invoice", "custom_customer_project"),
	),
	"delivery": (
		("Delivery Note", "custom_customer_project"),
		("Customer Receipt", "customer_project"),
	),
	"finance": (
		("Sales Invoice", "custom_customer_project"),
		("Payment Entry", "custom_customer_project"),
	),
}
MAX_WORKBENCH_PROJECTS = 50
MAX_LIST_ROWS = 50


def _current_user() -> str:
	return cstr(frappe.session.user).strip()


def _current_roles() -> set[str]:
	return set(frappe.get_roles(_current_user()))


def _require_internal_user() -> tuple[str, set[str]]:
	user = _current_user()
	roles = _current_roles()
	if user == "Guest" or (user != "Administrator" and not roles.intersection(INTERNAL_ROLES)):
		raise frappe.PermissionError
	return user, roles


def _require_management_user() -> tuple[str, set[str]]:
	user, roles = _require_internal_user()
	if user != "Administrator" and not roles.intersection(MANAGEMENT_ROLES):
		raise frappe.PermissionError
	return user, roles


def _primary_role(roles: set[str], user: str) -> str:
	if user == "Administrator" and not roles.intersection(INTERNAL_ROLES):
		return "Administrator"
	return next((role for role in ROLE_PRIORITY if role in roles), "Internal User")


def _slug(doctype: str) -> str:
	return cstr(doctype).strip().lower().replace(" ", "-")


def _form_route(doctype: str, name: str) -> str:
	return f"/app/{_slug(doctype)}/{quote(cstr(name), safe='')}"


def _list_route(doctype: str, filters: dict | None = None) -> str:
	base = f"/app/{_slug(doctype)}"
	if not filters:
		return base
	clean_filters = {
		cstr(key): cstr(value)
		for key, value in filters.items()
		if value not in (None, "")
	}
	return f"{base}?{urlencode(clean_filters)}" if clean_filters else base


def _project_rows(*, filters: dict | None = None, limit: int = MAX_WORKBENCH_PROJECTS) -> list:
	return frappe.get_list(
		"Customer Project",
		filters=filters or {},
		fields=[
			"name",
			"project_name",
			"company",
			"customer",
			"product_family",
			"currency",
			"expected_amount",
			"probability",
			"project_manager",
			"stage",
			"overall_risk_level",
			"customer_delivery_date",
			"next_action",
			"next_action_owner",
			"next_action_due_date",
			"modified",
		],
		order_by="modified desc",
		limit=limit,
	)


def _project_item(row) -> dict:
	return {
		"doctype": "Customer Project",
		"name": row.name,
		"title": row.project_name,
		"company": row.company,
		"customer": row.customer,
		"product_family": row.product_family,
		"currency": row.currency,
		"expected_amount": flt(row.expected_amount),
		"probability": flt(row.probability),
		"project_manager": row.project_manager,
		"stage": row.stage,
		"overall_risk_level": row.overall_risk_level,
		"customer_delivery_date": row.customer_delivery_date,
		"next_action": row.next_action,
		"next_action_owner": row.next_action_owner,
		"next_action_due_date": row.next_action_due_date,
		"modified": row.modified,
		"route": _form_route("Customer Project", row.name),
	}


def _user_approvals(user: str) -> list[dict]:
	if not frappe.has_permission("AutoFlow Approval Request", "read"):
		return []
	rows = frappe.get_list(
		"AutoFlow Approval Request",
		filters={"status": "待审批", "docstatus": 0},
		fields=[
			"name",
			"approval_type",
			"reference_doctype",
			"reference_name",
			"company",
			"requested_by",
			"requested_at",
		],
		order_by="requested_at asc",
		limit=MAX_LIST_ROWS,
	)
	result: list[dict] = []
	for row in rows:
		if row.requested_by == user:
			continue
		try:
			request = frappe.get_doc("AutoFlow Approval Request", row.name)
			if not approval_request_has_authority(request, user):
				continue
		except (frappe.PermissionError, frappe.ValidationError):
			continue
		result.append(
			{
				"doctype": "AutoFlow Approval Request",
				"name": row.name,
				"title": row.approval_type,
				"approval_type": row.approval_type,
				"reference_doctype": row.reference_doctype,
				"reference_name": row.reference_name,
				"company": row.company,
				"requested_by": row.requested_by,
				"requested_at": row.requested_at,
				"route": _form_route("AutoFlow Approval Request", row.name),
			}
		)
	return result


def _high_risks(project_names: list[str]) -> list[dict]:
	if not project_names or not frappe.has_permission("Project Risk", "read"):
		return []
	rows = frappe.get_list(
		"Project Risk",
		filters={
			"customer_project": ["in", project_names],
			"risk_level": "高",
			"status": ["!=", "已关闭"],
		},
		fields=["name", "title", "customer_project", "status", "owner_user", "due_date"],
		order_by="due_date asc, modified desc",
		limit=MAX_LIST_ROWS,
	)
	return [
		{
			"doctype": "Project Risk",
			"name": row.name,
			"title": row.title,
			"customer_project": row.customer_project,
			"status": row.status,
			"owner": row.owner_user,
			"due_date": row.due_date,
			"route": _form_route("Project Risk", row.name),
		}
		for row in rows
	]


def _due_items(project_rows: list) -> list[dict]:
	start_date = getdate(nowdate())
	end_date = getdate(add_days(start_date, 7))
	items: list[dict] = []
	for row in project_rows:
		if row.stage not in ACTIVE_STAGES:
			continue
		for fieldname, title, owner in (
			("next_action_due_date", row.next_action or "下一步行动", row.next_action_owner),
			("customer_delivery_date", "客户交付日期", row.project_manager),
		):
			due_date = row.get(fieldname)
			if due_date and start_date <= getdate(due_date) <= end_date:
				items.append(
					{
						"doctype": "Customer Project",
						"name": row.name,
						"customer_project": row.name,
						"title": title,
						"due_date": due_date,
						"owner": owner,
						"route": _form_route("Customer Project", row.name),
					}
				)

		project = frappe.get_doc("Customer Project", row.name)
		project.check_permission("read")
		for milestone in project.milestones:
			if milestone.status in {"已完成", "已取消"} or not milestone.planned_date:
				continue
			if start_date <= getdate(milestone.planned_date) <= end_date:
				items.append(
					{
						"doctype": "Customer Project",
						"name": row.name,
						"customer_project": row.name,
						"title": milestone.milestone_name,
						"due_date": milestone.planned_date,
						"owner": milestone.owner_user,
						"route": _form_route("Customer Project", row.name),
					}
				)
	items.sort(key=lambda item: (cstr(item["due_date"]), cstr(item["title"])))
	return items[:MAX_LIST_ROWS]


def _project_exceptions(project_names: list[str]) -> list[dict]:
	if not project_names or not frappe.has_permission("Business Exception", "read"):
		return []
	rows = frappe.get_list(
		"Business Exception",
		filters={"customer_project": ["in", project_names]},
		fields=[
			"name",
			"customer_project",
			"exception_type",
			"risk_level",
			"status",
			"responsible_user",
			"target_close_date",
		],
		order_by="modified desc",
		limit=MAX_LIST_ROWS,
	)
	return [
		{
			"doctype": "Business Exception",
			"name": row.name,
			"title": row.exception_type,
			"customer_project": row.customer_project,
			"risk_level": row.risk_level,
			"status": row.status,
			"owner": row.responsible_user,
			"due_date": row.target_close_date,
			"route": _form_route("Business Exception", row.name),
		}
		for row in rows
	]


def _parse_cockpit_filters(filters: dict | str | None) -> dict:
	if isinstance(filters, str):
		try:
			filters = frappe.parse_json(filters)
		except (TypeError, ValueError):
			frappe.throw(_("驾驶舱筛选条件必须是有效 JSON。"), frappe.ValidationError)
	if filters is None:
		return {}
	if not isinstance(filters, dict):
		frappe.throw(_("驾驶舱筛选条件必须是对象。"), frappe.ValidationError)
	unknown = set(filters).difference({"company"})
	if unknown:
		frappe.throw(_("驾驶舱包含不支持的筛选条件。"), frappe.ValidationError)
	company = cstr(filters.get("company")).strip()
	if len(company) > 140:
		frappe.throw(_("公司筛选值过长。"), frappe.ValidationError)
	return {"company": company} if company else {}


def _currency_totals(project_rows: list) -> dict[str, float]:
	totals: dict[str, float] = {}
	for row in project_rows:
		currency = cstr(row.currency).strip() or "未设置"
		totals[currency] = totals.get(currency, 0) + flt(row.expected_amount)
	return {currency: round(value, 2) for currency, value in sorted(totals.items())}


def _metric(
	code: str,
	label: str,
	definition: str,
	value,
	unit: str,
	drilldown: str,
) -> dict:
	return {
		"code": code,
		"label": label,
		"definition": definition,
		"value": value,
		"unit": unit,
		"drilldown": drilldown,
	}


def _flow_for_stage(stage: str, project_name: str) -> list[dict]:
	stage_names = [item[2] for item in FLOW_STAGES]
	if stage not in stage_names:
		return [
			{
				"code": code,
				"label": label,
				"stage": stage_name,
				"status": "未开始",
				"route": _form_route("Customer Project", project_name),
			}
			for code, label, stage_name in FLOW_STAGES
		] + [
			{
				"code": "terminal",
				"label": stage,
				"stage": stage,
				"status": "当前",
				"route": _form_route("Customer Project", project_name),
			}
		]
	current_index = stage_names.index(stage)
	return [
		{
			"code": code,
			"label": label,
			"stage": stage_name,
			"status": "已完成" if index < current_index else "当前" if index == current_index else "未开始",
			"route": _form_route("Customer Project", project_name),
		}
		for index, (code, label, stage_name) in enumerate(FLOW_STAGES)
	]


def _related_documents(project_name: str) -> dict[str, list[dict]]:
	result: dict[str, list[dict]] = {group: [] for group in RELATED_DOCUMENT_GROUPS}
	for group, definitions in RELATED_DOCUMENT_GROUPS.items():
		for doctype, project_field in definitions:
			if not frappe.has_permission(doctype, "read"):
				continue
			meta = frappe.get_meta(doctype)
			if meta.has_field(project_field):
				filters = {project_field: project_name}
			elif doctype == "Customer Feedback":
				visible_samples = [
					row["name"]
					for row in result[group]
					if row["doctype"] == "Sample Request"
				]
				if not visible_samples:
					continue
				filters = {"sample_request": ["in", visible_samples]}
			else:
				continue
			fields = ["name", "modified", "docstatus"]
			if meta.has_field("status"):
				fields.append("status")
			elif meta.has_field("decision"):
				fields.append("decision")
			rows = frappe.get_list(
				doctype,
				filters=filters,
				fields=fields,
				order_by="modified desc",
				limit=MAX_LIST_ROWS,
			)
			for row in rows:
				result[group].append(
					{
						"doctype": doctype,
						"name": row.name,
						"title": row.name,
						"status": row.get("status") or row.get("decision") or row.docstatus,
						"modified": row.modified,
						"route": _form_route(doctype, row.name),
					}
				)
	return result


def _project_risks(project_name: str) -> list[dict]:
	if not frappe.has_permission("Project Risk", "read"):
		return []
	rows = frappe.get_list(
		"Project Risk",
		filters={"customer_project": project_name},
		fields=["name", "title", "risk_level", "status", "owner_user", "due_date", "reference_doctype", "reference_name"],
		order_by="modified desc",
		limit=MAX_LIST_ROWS,
	)
	return [
		{
			"doctype": "Project Risk",
			"name": row.name,
			"title": row.title,
			"risk_level": row.risk_level,
			"status": row.status,
			"owner": row.owner_user,
			"due_date": row.due_date,
			"reference_doctype": row.reference_doctype,
			"reference_name": row.reference_name,
			"route": _form_route("Project Risk", row.name),
		}
		for row in rows
	]


def _project_ai_analyses(project_name: str) -> list[dict]:
	if not frappe.has_permission("AI Analysis", "read"):
		return []
	rows = frappe.get_list(
		"AI Analysis",
		filters={"customer_project": project_name},
		fields=["name", "analysis_type", "status", "requested_by", "requested_at", "display_text", "error_message"],
		order_by="requested_at desc",
		limit=20,
	)
	return [
		{
			"doctype": "AI Analysis",
			"name": row.name,
			"title": row.analysis_type,
			"status": row.status,
			"requested_by": row.requested_by,
			"requested_at": row.requested_at,
			"summary": row.display_text or row.error_message,
			"route": _form_route("AI Analysis", row.name),
		}
		for row in rows
	]


def _project_audit(project_name: str) -> list[dict]:
	if not frappe.has_permission("Version", "read"):
		return []
	rows = frappe.get_list(
		"Version",
		filters={"ref_doctype": "Customer Project", "docname": project_name},
		fields=["name", "owner", "creation"],
		order_by="creation desc",
		limit=20,
	)
	return [
		{
			"doctype": "Version",
			"name": row.name,
			"title": "项目变更记录",
			"owner": row.owner,
			"creation": row.creation,
			"route": _form_route("Version", row.name),
		}
		for row in rows
	]


@frappe.whitelist(methods=["POST"])
def create_project_analysis(project_name: str, analysis_type: str) -> str:
	return analyze_project(project_name, analysis_type)


@frappe.whitelist(methods=["GET"])
def get_workbench_data() -> dict:
	user, roles = _require_internal_user()
	projects = _project_rows()
	project_names = [row.name for row in projects]
	return {
		"role": _primary_role(roles, user),
		"approvals": _user_approvals(user),
		"high_risks": _high_risks(project_names),
		"due_within_seven_days": _due_items(projects),
		"projects": [_project_item(row) for row in projects],
	}


@frappe.whitelist(methods=["GET"])
def get_management_cockpit(filters: dict | str | None = None) -> dict:
	_require_management_user()
	filters = _parse_cockpit_filters(filters)
	projects = _project_rows(filters=filters, limit=1000)
	project_names = [row.name for row in projects]
	active_projects = [row for row in projects if row.stage in ACTIVE_STAGES]
	high_risk_projects = [row for row in projects if row.overall_risk_level == "高"]
	exceptions = _project_exceptions(project_names)
	open_exceptions = [row for row in exceptions if row["status"] not in {"已关闭", "已取消"}]
	today = getdate(nowdate())
	overdue_actions = [
		row
		for row in active_projects
		if row.next_action_due_date and getdate(row.next_action_due_date) < today
	]
	currency_totals = _currency_totals(active_projects)
	pipeline_value = next(iter(currency_totals.values()), 0) if len(currency_totals) <= 1 else currency_totals
	pipeline_unit = next(iter(currency_totals), "金额") if len(currency_totals) <= 1 else "按币种"
	company_filter = filters.get("company")
	base_filter = {"company": company_filter} if company_filter else {}
	stage_distribution = {
		stage: sum(row.stage == stage for row in projects)
		for stage in sorted({row.stage for row in projects})
	}
	risk_distribution = {
		level: sum(row.overall_risk_level == level for row in projects)
		for level in ("低", "中", "高")
	}
	exception_summary = {
		status: sum(row["status"] == status for row in exceptions)
		for status in sorted({row["status"] for row in exceptions})
	}
	return {
		"filters": filters,
		"generated_at": now_datetime(),
		"currency_totals": currency_totals,
		"metrics": [
			_metric(
				"ACTIVE_PROJECTS",
				"在途项目",
				"当前用户可读取且尚未结项、失败或取消的客户项目数量。",
				len(active_projects),
				"个",
				_list_route("Customer Project", base_filter),
			),
			_metric(
				"PIPELINE_VALUE",
				"在途预计金额",
				"当前可读在途项目预计金额按原币种汇总，不执行推测汇率换算。",
				pipeline_value,
				pipeline_unit,
				_list_route("Customer Project", base_filter),
			),
			_metric(
				"HIGH_RISK_PROJECTS",
				"高风险项目",
				"当前可读项目中总体风险等级为高的项目数量。",
				len(high_risk_projects),
				"个",
				_list_route("Customer Project", {**base_filter, "overall_risk_level": "高"}),
			),
			_metric(
				"OPEN_EXCEPTIONS",
				"未关闭异常",
				"当前可读项目下状态不是已关闭或已取消的业务异常数量。",
				len(open_exceptions),
				"项",
				_list_route("Business Exception"),
			),
			_metric(
				"OVERDUE_ACTIONS",
				"逾期行动",
				"当前可读在途项目中下一步行动到期日早于今天的项目数量。",
				len(overdue_actions),
				"项",
				_list_route("Customer Project", base_filter),
			),
		],
		"stage_distribution": stage_distribution,
		"risk_distribution": risk_distribution,
		"exception_summary": exception_summary,
		"recent_projects": [_project_item(row) for row in projects[:20]],
	}


@frappe.whitelist(methods=["GET"])
def get_project_panorama(project_name: str) -> dict:
	_require_internal_user()
	project_name = cstr(project_name).strip()
	if not project_name:
		frappe.throw(_("客户项目不能为空。"), frappe.ValidationError)
	project = frappe.get_doc("Customer Project", project_name)
	project.check_permission("read")
	exceptions = _project_exceptions([project.name])
	return {
		"project": {
			"doctype": "Customer Project",
			"name": project.name,
			"title": project.project_name,
			"company": project.company,
			"customer": project.customer,
			"product_family": project.product_family,
			"currency": project.currency,
			"expected_amount": flt(project.expected_amount),
			"probability": flt(project.probability),
			"project_manager": project.project_manager,
			"stage": project.stage,
			"overall_risk_level": project.overall_risk_level,
			"customer_delivery_date": project.customer_delivery_date,
			"next_action": project.next_action,
			"next_action_owner": project.next_action_owner,
			"next_action_due_date": project.next_action_due_date,
			"route": _form_route("Customer Project", project.name),
		},
		"flow": _flow_for_stage(project.stage, project.name),
		"documents": _related_documents(project.name),
		"risks": _project_risks(project.name),
		"exceptions": exceptions,
		"ai_analyses": _project_ai_analyses(project.name),
		"audit": _project_audit(project.name),
	}
