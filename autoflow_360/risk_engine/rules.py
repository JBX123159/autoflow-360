from dataclasses import asdict
from datetime import timedelta

import frappe
from frappe.utils import (
	date_diff,
	flt,
	get_datetime,
	getdate,
	now_datetime,
	nowdate,
)

from autoflow_360.risk_engine.types import RiskFinding
from autoflow_360.services.material_planning import calculate_material_gap


def _setting_days(fieldname: str, default: int) -> int:
	value = frappe.db.get_single_value("AutoFlow Settings", fieldname)
	try:
		return max(int(value), 1)
	except (TypeError, ValueError):
		return default


def find_overdue_milestones(project) -> list[RiskFinding]:
	today = getdate(nowdate())
	findings: list[RiskFinding] = []
	for milestone in list(project.milestones or []):
		if milestone.status in {"已完成", "已取消"}:
			continue
		planned_date = getdate(milestone.planned_date)
		if planned_date >= today:
			continue
		days_overdue = date_diff(today, planned_date)
		findings.append(
			RiskFinding(
				rule_code="MILESTONE_OVERDUE",
				risk_type="项目节点延期",
				level="高" if days_overdue >= 7 else "中",
				title=f"项目节点逾期：{milestone.milestone_name}",
				description=f"节点已逾期 {days_overdue} 天，当前状态为 {milestone.status}。",
				reference_doctype="Project Milestone",
				reference_name=milestone.name,
				inputs={
					"milestone_name": milestone.milestone_name,
					"planned_date": str(planned_date),
					"status": milestone.status,
					"days_overdue": days_overdue,
				},
				owner_user=milestone.owner_user or project.project_manager,
				due_date=planned_date,
			)
		)
	return findings


def find_pending_sample_feedback(project) -> list[RiskFinding]:
	warning_days = _setting_days("feedback_warning_days", 3)
	today = getdate(nowdate())
	findings: list[RiskFinding] = []
	for sample in frappe.get_all(
		"Sample Request",
		filters={
			"customer_project": project.name,
			"status": ["in", ["已发出", "等待反馈"]],
			"feedback": ["is", "not set"],
		},
		fields=["name", "status", "dispatch_time", "customer_contact"],
	):
		if not sample.dispatch_time:
			continue
		dispatch_date = getdate(sample.dispatch_time)
		days_waiting = date_diff(today, dispatch_date)
		if days_waiting < warning_days:
			continue
		findings.append(
			RiskFinding(
				rule_code="SAMPLE_FEEDBACK_DELAY",
				risk_type="样品反馈延期",
				level="高" if days_waiting >= warning_days * 2 else "中",
				title="样品发出后长期未获客户反馈",
				description=f"{sample.name} 已等待客户反馈 {days_waiting} 天。",
				reference_doctype="Sample Request",
				reference_name=sample.name,
				inputs={
					"dispatch_time": str(sample.dispatch_time),
					"status": sample.status,
					"days_waiting": days_waiting,
					"warning_days": warning_days,
				},
				owner_user=project.project_manager,
				due_date=dispatch_date + timedelta(days=warning_days),
			)
		)
	return findings


def find_quotation_expiry(project) -> list[RiskFinding]:
	warning_days = _setting_days("quotation_expiry_warning_days", 7)
	today = getdate(nowdate())
	findings: list[RiskFinding] = []
	for quotation in frappe.get_all(
		"Quotation",
		filters={
			"custom_customer_project": project.name,
			"docstatus": 1,
		},
		fields=[
			"name",
			"valid_till",
			"grand_total",
			"currency",
			"custom_customer_confirmed",
		],
	):
		if quotation.custom_customer_confirmed or not quotation.valid_till:
			continue
		valid_till = getdate(quotation.valid_till)
		days_until_expiry = date_diff(valid_till, today)
		if days_until_expiry > warning_days:
			continue
		findings.append(
			RiskFinding(
				rule_code="QUOTATION_EXPIRY",
				risk_type="报价有效期风险",
				level="高" if days_until_expiry < 0 else "中",
				title="客户未确认的报价即将或已经到期",
				description=f"{quotation.name} 距有效期截止还有 {days_until_expiry} 天。",
				reference_doctype="Quotation",
				reference_name=quotation.name,
				inputs={
					"valid_till": str(valid_till),
					"days_until_expiry": days_until_expiry,
					"warning_days": warning_days,
					"grand_total": flt(quotation.grand_total),
					"currency": quotation.currency,
				},
				owner_user=project.project_manager,
				due_date=valid_till,
			)
		)
	return findings


def find_stock_delivery_gap(project) -> list[RiskFinding]:
	findings: list[RiskFinding] = []
	for order in frappe.get_all(
		"Sales Order",
		filters={
			"custom_customer_project": project.name,
			"docstatus": 1,
			"status": ["not in", ["Completed", "Closed", "On Hold"]],
		},
		fields=["name", "delivery_date"],
	):
		gaps = [
			asdict(gap)
			for gap in calculate_material_gap(order.name)
			if gap.required_qty > 0
		]
		if not gaps:
			continue
		earliest_required = min(getdate(gap["required_by"]) for gap in gaps)
		findings.append(
			RiskFinding(
				rule_code="STOCK_DELIVERY_GAP",
				risk_type="库存交付缺口",
				level="高" if earliest_required <= getdate(project.customer_delivery_date) else "中",
				title="销售订单存在未覆盖的物料缺口",
				description=f"{order.name} 有 {len(gaps)} 个物料/仓库组合仍有缺口。",
				reference_doctype="Sales Order",
				reference_name=order.name,
				inputs={"gaps": gaps, "delivery_date": str(order.delivery_date or "")},
				owner_user=project.project_manager,
				due_date=earliest_required,
			)
		)
	return findings


def find_supplier_delay(project) -> list[RiskFinding]:
	findings: list[RiskFinding] = []
	for order in frappe.get_all(
		"Purchase Order",
		filters={
			"custom_customer_project": project.name,
			"docstatus": 1,
			"status": ["not in", ["Completed", "Closed"]],
		},
		fields=["name", "custom_supplier_eta", "supplier"],
	):
		if not order.custom_supplier_eta:
			continue
		supplier_eta = getdate(order.custom_supplier_eta)
		customer_delivery_date = getdate(project.customer_delivery_date)
		if supplier_eta <= customer_delivery_date:
			continue
		findings.append(
			RiskFinding(
				rule_code="SUPPLIER_DELAY",
				risk_type="供应商延期",
				level="高",
				title="供应商到货晚于客户交期",
				description=f"{order.name} 的预计到货日晚于客户要求交付日。",
				reference_doctype="Purchase Order",
				reference_name=order.name,
				inputs={
					"supplier": order.supplier,
					"supplier_eta": str(supplier_eta),
					"customer_delivery_date": str(customer_delivery_date),
				},
				owner_user=project.project_manager,
				due_date=customer_delivery_date,
			)
		)
	return findings


def find_open_high_exceptions(project) -> list[RiskFinding]:
	if not frappe.db.exists("DocType", "Business Exception"):
		return []
	meta = frappe.get_meta("Business Exception")
	if not all(
		meta.has_field(fieldname)
		for fieldname in (
			"customer_project",
			"risk_level",
			"status",
			"target_close_date",
			"responsible_user",
		)
	):
		return []
	return [
		RiskFinding(
			rule_code="HIGH_EXCEPTION_OPEN",
			risk_type="高风险异常",
			level="高",
			title="高风险异常尚未关闭",
			description=f"{row.name} 仍处于 {row.status}。",
			reference_doctype="Business Exception",
			reference_name=row.name,
			inputs={
				"status": row.status,
				"target_close_date": str(row.target_close_date or ""),
			},
			owner_user=row.responsible_user or project.project_manager,
			due_date=row.target_close_date,
		)
		for row in frappe.get_all(
			"Business Exception",
			filters={
				"customer_project": project.name,
				"risk_level": "高",
				"status": ["not in", ["已关闭", "已取消"]],
			},
			fields=["name", "status", "target_close_date", "responsible_user"],
		)
	]


def find_overdue_receivables(project) -> list[RiskFinding]:
	today = getdate(nowdate())
	findings: list[RiskFinding] = []
	for invoice in frappe.get_all(
		"Sales Invoice",
		filters={
			"custom_customer_project": project.name,
			"docstatus": 1,
			"outstanding_amount": [">", 0],
		},
		fields=["name", "due_date", "outstanding_amount", "currency", "customer"],
	):
		if not invoice.due_date or getdate(invoice.due_date) >= today:
			continue
		due_date = getdate(invoice.due_date)
		days_overdue = date_diff(today, due_date)
		findings.append(
			RiskFinding(
				rule_code="RECEIVABLE_OVERDUE",
				risk_type="应收账款逾期",
				level="高" if days_overdue >= 7 else "中",
				title="销售发票已逾期未结清",
				description=f"{invoice.name} 已逾期 {days_overdue} 天。",
				reference_doctype="Sales Invoice",
				reference_name=invoice.name,
				inputs={
					"due_date": str(due_date),
					"days_overdue": days_overdue,
					"outstanding_amount": flt(invoice.outstanding_amount),
					"currency": invoice.currency,
					"customer": invoice.customer,
				},
				owner_user=project.project_manager,
				due_date=due_date,
			)
		)
	return findings


def find_inactive_project(project) -> list[RiskFinding]:
	warning_days = _setting_days("project_inactive_days", 7)
	if not project.last_meaningful_activity:
		return []
	last_activity = get_datetime(project.last_meaningful_activity)
	days_inactive = max((now_datetime() - last_activity).days, 0)
	if days_inactive < warning_days:
		return []
	return [
		RiskFinding(
			rule_code="PROJECT_INACTIVE",
			risk_type="项目长期无活动",
			level="高" if days_inactive >= warning_days * 2 else "中",
			title="项目长期没有有效活动",
			description=f"项目已连续 {days_inactive} 天没有记录有效活动。",
			reference_doctype="Customer Project",
			reference_name=project.name,
			inputs={
				"last_meaningful_activity": str(last_activity),
				"days_inactive": days_inactive,
				"warning_days": warning_days,
			},
			owner_user=project.project_manager,
			due_date=getdate(nowdate()),
		)
	]


RULES = (
	find_overdue_milestones,
	find_pending_sample_feedback,
	find_quotation_expiry,
	find_stock_delivery_gap,
	find_supplier_delay,
	find_open_high_exceptions,
	find_overdue_receivables,
	find_inactive_project,
)
