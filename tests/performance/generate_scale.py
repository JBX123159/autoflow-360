import json
from datetime import timedelta

import frappe
from frappe.utils import getdate, now_datetime, nowdate

from autoflow_360.demo.seed import DEMO_CURRENCY, seed_demo_data


PROJECT_TARGET = 200
SAMPLE_TARGET = 1_000
ORDER_TARGET = 500
EVIDENCE_TARGET = 5_000
BATCH_SIZE = 500
PERFORMANCE_PREFIX = "PERF-"
SYNTHETIC_CLASSIFICATION = "合成性能数据 · 不代表真实经营规模或成效"
RISK_TARGET = 2_000
EXCEPTION_TARGET = 1_500
VERSION_TARGET = EVIDENCE_TARGET - RISK_TARGET - EXCEPTION_TARGET


def _bulk_insert(doctype: str, fields: list[str], values: list[tuple]) -> None:
	if not values:
		return
	frappe.db.bulk_insert(
		doctype,
		fields=fields,
		values=values,
		ignore_duplicates=True,
		chunk_size=BATCH_SIZE,
	)


def _common_values(name: str, timestamp) -> tuple:
	return (name, timestamp, timestamp, "Administrator", "Administrator", 0, 0)


def _demo_context() -> dict[str, str]:
	demo_projects = seed_demo_data()
	normal_project = demo_projects["normal"]
	project = frappe.get_doc("Customer Project", normal_project)
	sample = frappe.get_all(
		"Sample Request",
		filters={"customer_project": normal_project},
		fields=["name", "customer_contact"],
		order_by="round_number asc",
		limit=1,
	)[0]
	item_code = frappe.db.get_value(
		"Sample Item",
		{"parent": sample.name, "parenttype": "Sample Request"},
		"item_code",
	)
	sales_order = frappe.get_all(
		"Sales Order",
		filters={"custom_customer_project": normal_project, "docstatus": 1},
		pluck="name",
		limit=1,
	)[0]
	purchase_order = frappe.get_all(
		"Purchase Order",
		filters={"custom_customer_project": normal_project, "docstatus": 1},
		pluck="name",
		limit=1,
	)[0]
	return {
		"company": project.company,
		"customer": project.customer,
		"supplier": frappe.db.get_value("Purchase Order", purchase_order, "supplier"),
		"contact": sample.customer_contact,
		"item_code": item_code,
		"warehouse": frappe.db.get_value("Sales Order Item", {"parent": sales_order}, "warehouse"),
		"uom": frappe.get_cached_value("Item", item_code, "stock_uom"),
	}


def _ensure_projects(context: dict[str, str]) -> list[str]:
	timestamp = now_datetime()
	today = getdate(nowdate())
	project_fields = [
		"name",
		"creation",
		"modified",
		"modified_by",
		"owner",
		"docstatus",
		"idx",
		"naming_series",
		"project_name",
		"company",
		"customer",
		"product_family",
		"currency",
		"expected_amount",
		"probability",
		"project_manager",
		"target_award_date",
		"customer_delivery_date",
		"last_meaningful_activity",
		"stage",
		"overall_risk_level",
		"next_action",
		"next_action_owner",
		"next_action_due_date",
		"is_demo",
		"demo_key",
		"data_classification",
	]
	project_rows = []
	member_rows = []
	for index in range(1, PROJECT_TARGET + 1):
		project_name = f"{PERFORMANCE_PREFIX}PROJECT-{index:04d}"
		project_rows.append(
			_common_values(project_name, timestamp)
			+ (
				"AF-.YYYY.-.#####",
				f"{project_name} · 合成性能项目",
				context["company"],
				context["customer"],
				"汽车轻量化结构件",
				DEMO_CURRENCY,
				100_000 + index * 1_000,
				50,
				"Administrator",
				today + timedelta(days=30),
				today + timedelta(days=90),
				timestamp,
				"潜在项目",
				"低",
				"合成性能基线验证",
				"Administrator",
				today + timedelta(days=7),
				1,
				project_name,
				SYNTHETIC_CLASSIFICATION,
			)
		)
		member_name = f"{PERFORMANCE_PREFIX}MEMBER-{index:04d}"
		member_rows.append(
			_common_values(member_name, timestamp)
			+ (
				project_name,
				"project_members",
				"Customer Project",
				"Administrator",
				"合成性能项目负责人",
			)
		)
	_bulk_insert("Customer Project", project_fields, project_rows)
	_bulk_insert(
		"Project Member",
		[
			"name",
			"creation",
			"modified",
			"modified_by",
			"owner",
			"docstatus",
			"idx",
			"parent",
			"parentfield",
			"parenttype",
			"user",
			"responsibility",
		],
		member_rows,
	)
	frappe.db.commit()
	return [f"{PERFORMANCE_PREFIX}PROJECT-{index:04d}" for index in range(1, PROJECT_TARGET + 1)]


def _ensure_samples(context: dict[str, str], project_names: list[str]) -> None:
	timestamp = now_datetime()
	today = getdate(nowdate())
	sample_rows = []
	item_rows = []
	feedback_rows = []
	for index in range(1, SAMPLE_TARGET + 1):
		project_name = project_names[(index - 1) % len(project_names)]
		sample_name = f"{PERFORMANCE_PREFIX}SAMPLE-{index:05d}"
		feedback_name = f"{PERFORMANCE_PREFIX}FEEDBACK-{index:05d}"
		sample_rows.append(
			_common_values(sample_name, timestamp)
			+ (
				"SMP-.YYYY.-.#####",
				project_name,
				1,
				f"{sample_name} 合成性能样件",
				today + timedelta(days=14),
				context["contact"],
				"已通过",
				"客户认可",
				"通过",
				"合成物流",
				f"PERF-TRACK-{index:05d}",
				timestamp,
				feedback_name,
			)
		)
		item_rows.append(
			_common_values(f"{PERFORMANCE_PREFIX}SAMPLE-ITEM-{index:05d}", timestamp)
			+ (
				sample_name,
				"items",
				"Sample Request",
				context["item_code"],
				1,
				context["uom"],
				"合成性能规格",
				"通过",
			)
		)
		feedback_rows.append(
			_common_values(feedback_name, timestamp)
			+ (
				sample_name,
				context["customer"],
				context["contact"],
				"客户认可",
				"合成性能数据反馈，不代表真实客户意见。",
				"Administrator",
				timestamp,
			)
		)
	_bulk_insert(
		"Sample Request",
		[
			"name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
			"naming_series", "customer_project", "round_number", "purpose", "required_date",
			"customer_contact", "approval_status", "status", "inspection_status", "carrier",
			"tracking_number", "dispatch_time", "feedback",
		],
		sample_rows,
	)
	_bulk_insert(
		"Sample Item",
		[
			"name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
			"parent", "parentfield", "parenttype", "item_code", "quantity", "uom", "specification",
			"inspection_result",
		],
		item_rows,
	)
	_bulk_insert(
		"Customer Feedback",
		[
			"name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
			"sample_request", "customer", "contact", "decision", "comments", "submitted_by", "submitted_at",
		],
		feedback_rows,
	)
	frappe.db.commit()


def _ensure_orders(context: dict[str, str], project_names: list[str]) -> None:
	timestamp = now_datetime()
	today = getdate(nowdate())
	sales_rows = []
	sales_item_rows = []
	purchase_rows = []
	purchase_item_rows = []
	for index in range(1, ORDER_TARGET + 1):
		project_name = project_names[(index - 1) % len(project_names)]
		sales_name = f"{PERFORMANCE_PREFIX}SO-{index:04d}"
		purchase_name = f"{PERFORMANCE_PREFIX}PO-{index:04d}"
		sales_rows.append(
			_common_values(sales_name, timestamp)
			+ (
				"SAL-ORD-.YYYY.-",
				context["customer"],
				context["customer"],
				context["company"],
				DEMO_CURRENCY,
				1,
				today,
				today + timedelta(days=30),
				"Sales",
				"Draft",
				10,
				12_000,
				12_000,
				project_name,
			)
		)
		sales_item_rows.append(
			_common_values(f"{PERFORMANCE_PREFIX}SO-ITEM-{index:04d}", timestamp)
			+ (
				sales_name,
				"items",
				"Sales Order",
				context["item_code"],
				context["item_code"],
				10,
				context["uom"],
				context["uom"],
				1,
				1_200,
				12_000,
				context["warehouse"],
				today + timedelta(days=30),
			)
		)
		purchase_rows.append(
			_common_values(purchase_name, timestamp)
			+ (
				"PUR-ORD-.YYYY.-",
				context["supplier"],
				context["supplier"],
				context["company"],
				DEMO_CURRENCY,
				1,
				today,
				today + timedelta(days=25),
				"Draft",
				10,
				8_000,
				8_000,
				project_name,
				today + timedelta(days=25),
			)
		)
		purchase_item_rows.append(
			_common_values(f"{PERFORMANCE_PREFIX}PO-ITEM-{index:04d}", timestamp)
			+ (
				purchase_name,
				"items",
				"Purchase Order",
				context["item_code"],
				context["item_code"],
				10,
				context["uom"],
				context["uom"],
				1,
				800,
				8_000,
				context["warehouse"],
				today + timedelta(days=25),
			)
		)
	_bulk_insert(
		"Sales Order",
		[
			"name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
			"naming_series", "customer", "customer_name", "company", "currency", "conversion_rate",
			"transaction_date", "delivery_date", "order_type", "status", "total_qty", "grand_total",
			"base_grand_total", "custom_customer_project",
		],
		sales_rows,
	)
	_bulk_insert(
		"Sales Order Item",
		[
			"name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
			"parent", "parentfield", "parenttype", "item_code", "item_name", "qty", "uom", "stock_uom",
			"conversion_factor", "rate", "amount", "warehouse", "delivery_date",
		],
		sales_item_rows,
	)
	_bulk_insert(
		"Purchase Order",
		[
			"name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
			"naming_series", "supplier", "supplier_name", "company", "currency", "conversion_rate",
			"transaction_date", "schedule_date", "status", "total_qty", "grand_total", "base_grand_total",
			"custom_customer_project", "custom_supplier_eta",
		],
		purchase_rows,
	)
	_bulk_insert(
		"Purchase Order Item",
		[
			"name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
			"parent", "parentfield", "parenttype", "item_code", "item_name", "qty", "uom", "stock_uom",
			"conversion_factor", "rate", "amount", "warehouse", "schedule_date",
		],
		purchase_item_rows,
	)
	frappe.db.commit()


def _ensure_evidence(project_names: list[str]) -> None:
	timestamp = now_datetime()
	today = getdate(nowdate())
	risk_rows = []
	for index in range(1, RISK_TARGET + 1):
		project_name = project_names[(index - 1) % len(project_names)]
		name = f"{PERFORMANCE_PREFIX}RISK-{index:05d}"
		risk_rows.append(
			_common_values(name, timestamp)
			+ (
				"RISK-.YYYY.-.#####",
				project_name,
				"合成性能风险",
				("低", "中", "高")[(index - 1) % 3],
				f"{name} 合成性能风险",
				SYNTHETIC_CLASSIFICATION,
				"已发现",
				"Administrator",
				today + timedelta(days=7),
				"PERF_SYNTHETIC",
				"Customer Project",
				project_name,
				json.dumps({"synthetic": True, "index": index}, ensure_ascii=False),
				name,
			)
		)
	_bulk_insert(
		"Project Risk",
		[
			"name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
			"naming_series", "customer_project", "risk_type", "risk_level", "title", "description",
			"status", "owner_user", "due_date", "rule_code", "reference_doctype", "reference_name",
			"rule_inputs", "deduplication_key",
		],
		risk_rows,
	)

	exception_rows = []
	for index in range(1, EXCEPTION_TARGET + 1):
		project_name = project_names[(index - 1) % len(project_names)]
		name = f"{PERFORMANCE_PREFIX}EXCEPTION-{index:05d}"
		exception_rows.append(
			_common_values(name, timestamp)
			+ (
				"EXC-.YYYY.-.#####",
				project_name,
				"供应商延期",
				("低", "中", "高")[(index - 1) % 3],
				"已发现",
				"Customer Project",
				project_name,
				f"{name} · {SYNTHETIC_CLASSIFICATION}",
				"仅用于目标规模查询和页面性能测量。",
				"Administrator",
				timestamp,
			)
		)
	_bulk_insert(
		"Business Exception",
		[
			"name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
			"naming_series", "customer_project", "exception_type", "risk_level", "status",
			"reference_doctype", "reference_name", "description", "impact", "raised_by", "raised_at",
		],
		exception_rows,
	)

	version_rows = []
	for index in range(1, VERSION_TARGET + 1):
		project_name = project_names[(index - 1) % len(project_names)]
		name = f"{PERFORMANCE_PREFIX}VERSION-{index:05d}"
		version_rows.append(
			_common_values(name, timestamp)
			+ (
				"Customer Project",
				project_name,
				json.dumps(
					{"changed": [["next_action", "待处理", "合成性能基线验证"]]},
					ensure_ascii=False,
				),
			)
		)
	_bulk_insert(
		"Version",
		[
			"name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
			"ref_doctype", "docname", "data",
		],
		version_rows,
	)
	frappe.db.commit()


def _count(doctype: str, name_pattern: str) -> int:
	return frappe.db.count(doctype, {"name": ["like", name_pattern]})


def _record_counts() -> dict[str, int]:
	counts = {
		"customer_projects": _count("Customer Project", "PERF-PROJECT-%"),
		"sample_requests": _count("Sample Request", "PERF-SAMPLE-%"),
		"customer_feedback": _count("Customer Feedback", "PERF-FEEDBACK-%"),
		"sales_orders": _count("Sales Order", "PERF-SO-%"),
		"purchase_orders": _count("Purchase Order", "PERF-PO-%"),
		"project_risks": _count("Project Risk", "PERF-RISK-%"),
		"business_exceptions": _count("Business Exception", "PERF-EXCEPTION-%"),
		"versions": _count("Version", "PERF-VERSION-%"),
	}
	counts["risk_exception_version_total"] = (
		counts["project_risks"] + counts["business_exceptions"] + counts["versions"]
	)
	return counts


def _validate_counts(counts: dict[str, int]) -> None:
	required = {
		"customer_projects": PROJECT_TARGET,
		"sample_requests": SAMPLE_TARGET,
		"customer_feedback": SAMPLE_TARGET,
		"sales_orders": ORDER_TARGET,
		"purchase_orders": ORDER_TARGET,
		"risk_exception_version_total": EVIDENCE_TARGET,
	}
	missing = {
		name: {"required": target, "actual": counts.get(name, 0)}
		for name, target in required.items()
		if counts.get(name, 0) < target
	}
	if missing:
		frappe.throw(f"合成性能数据未达到目标规模：{missing}")


def run() -> dict:
	"""幂等创建固定规模的合成数据；不会删除或改写三条演示场景。"""
	context = _demo_context()
	project_names = _ensure_projects(context)
	_ensure_samples(context, project_names)
	_ensure_orders(context, project_names)
	_ensure_evidence(project_names)
	counts = _record_counts()
	_validate_counts(counts)
	return {
		"classification": SYNTHETIC_CLASSIFICATION,
		"targets": {
			"projects": PROJECT_TARGET,
			"samples_and_feedback_each": SAMPLE_TARGET,
			"sales_and_purchase_orders_each": ORDER_TARGET,
			"risk_exception_version_total": EVIDENCE_TARGET,
		},
		"counts": counts,
	}
