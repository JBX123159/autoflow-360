import hashlib
import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate, nowdate
from frappe.utils.synchronization import filelock

from autoflow_360.autoflow_360.doctype.autoflow_approval_rule.autoflow_approval_rule import (
	RISK_LEVELS,
)
from autoflow_360.services.idempotency import make_idempotency_key


APPROVED_STATUS = "已通过"


def _normalized_number(value: Any) -> float:
	return round(flt(value), 6)


def _source_amount(source) -> float:
	for fieldname in (
		"base_grand_total",
		"grand_total",
		"rounded_total",
		"total",
		"expected_amount",
		"paid_amount",
	):
		value = getattr(source, fieldname, None)
		if value is not None:
			return max(_normalized_number(value), 0)
	return 0


def _source_risk_level(source) -> str:
	for fieldname in ("overall_risk_level", "risk_level"):
		value = cstr(getattr(source, fieldname, None)).strip()
		if value in RISK_LEVELS:
			return value
	project_name = cstr(
		getattr(source, "custom_customer_project", None)
		or getattr(source, "customer_project", None)
	).strip()
	if project_name and frappe.db.exists("Customer Project", project_name):
		project_risk = cstr(
			frappe.db.get_value(
				"Customer Project",
				project_name,
				"overall_risk_level",
			)
		).strip()
		if project_risk in RISK_LEVELS:
			return project_risk
	return "低"


def _snapshot_items(source) -> tuple[list[dict[str, Any]], float, bool]:
	items: list[dict[str, Any]] = []
	maximum_discount = 0.0
	has_floor_breach = False
	for row in list(getattr(source, "items", None) or []):
		rate = max(_normalized_number(getattr(row, "rate", 0)), 0)
		floor_rate = max(
			_normalized_number(getattr(row, "custom_floor_rate", 0)),
			0,
		)
		discount = max(
			_normalized_number(getattr(row, "discount_percentage", 0)),
			0,
		)
		floor_discount = 0.0
		if floor_rate > 0 and rate < floor_rate:
			has_floor_breach = True
			floor_discount = _normalized_number(
				(floor_rate - rate) / floor_rate * 100
			)
		maximum_discount = max(maximum_discount, discount, floor_discount)
		items.append(
			{
				"item_code": cstr(getattr(row, "item_code", None)).strip(),
				"description": cstr(getattr(row, "description", None)).strip(),
				"quantity": _normalized_number(
					getattr(row, "qty", None)
					or getattr(row, "quantity", 0)
				),
				"rate": rate,
				"discount_percentage": discount,
				"floor_rate": floor_rate,
				"amount": _normalized_number(getattr(row, "amount", 0)),
			}
		)
	return items, maximum_discount, has_floor_breach


def _snapshot_taxes(source) -> list[dict[str, Any]]:
	return [
		{
			"charge_type": cstr(getattr(row, "charge_type", None)).strip(),
			"account_head": cstr(getattr(row, "account_head", None)).strip(),
			"description": cstr(getattr(row, "description", None)).strip(),
			"rate": _normalized_number(getattr(row, "rate", 0)),
			"tax_amount": _normalized_number(getattr(row, "tax_amount", 0)),
			"included_in_print_rate": int(
				bool(getattr(row, "included_in_print_rate", 0))
			),
		}
		for row in list(getattr(source, "taxes", None) or [])
	]


def _snapshot_payment_schedule(source) -> list[dict[str, Any]]:
	return [
		{
			"payment_term": cstr(getattr(row, "payment_term", None)).strip(),
			"invoice_portion": _normalized_number(
				getattr(row, "invoice_portion", 0)
			),
			"due_date": cstr(getattr(row, "due_date", None)).strip(),
			"payment_amount": _normalized_number(
				getattr(row, "payment_amount", 0)
			),
		}
		for row in list(getattr(source, "payment_schedule", None) or [])
	]


def build_approval_snapshot(source) -> dict[str, Any]:
	"""Return a stable, decision-relevant snapshot without mutable audit fields."""
	if source.doctype == "Customer Project":
		from autoflow_360.services.project_closure import (
			build_project_closure_snapshot,
		)

		return build_project_closure_snapshot(source)

	items, maximum_discount, has_floor_breach = _snapshot_items(source)
	payload: dict[str, Any] = {
		"document_type": source.doctype,
		"document_name": source.name,
		"company": cstr(getattr(source, "company", None)).strip(),
		"party_name": cstr(getattr(source, "party_name", None)).strip(),
		"currency": cstr(getattr(source, "currency", None)).strip(),
		"amount": _source_amount(source),
		"maximum_discount": _normalized_number(maximum_discount),
		"has_floor_breach": has_floor_breach,
		"risk_level": _source_risk_level(source),
		"customer_project": cstr(
			getattr(source, "custom_customer_project", None)
			or getattr(source, "customer_project", None)
		).strip(),
		"valid_till": cstr(getattr(source, "valid_till", None)).strip(),
		"transaction_date": cstr(
			getattr(source, "transaction_date", None)
		).strip(),
		"order_type": cstr(getattr(source, "order_type", None)).strip(),
		"selling_price_list": cstr(
			getattr(source, "selling_price_list", None)
		).strip(),
		"taxes_and_charges": cstr(
			getattr(source, "taxes_and_charges", None)
		).strip(),
		"payment_terms_template": cstr(
			getattr(source, "payment_terms_template", None)
		).strip(),
		"terms": cstr(getattr(source, "terms", None)).strip(),
		"items": items,
		"taxes": _snapshot_taxes(source),
		"payment_schedule": _snapshot_payment_schedule(source),
	}
	canonical = json.dumps(
		payload,
		ensure_ascii=False,
		sort_keys=True,
		separators=(",", ":"),
		default=str,
	)
	payload["fingerprint"] = hashlib.sha256(
		canonical.encode("utf-8")
	).hexdigest()
	return payload


def _read_snapshot(request) -> dict[str, Any]:
	try:
		snapshot = frappe.parse_json(request.request_snapshot)
	except (TypeError, ValueError):
		frappe.throw(_("Approval request snapshot is invalid."))
	if not isinstance(snapshot, dict) or not snapshot.get("fingerprint"):
		frappe.throw(_("Approval request snapshot is incomplete."))
	return snapshot


def _get_user_rules(company: str, document_type: str, user: str) -> list[dict]:
	roles = frappe.get_roles(user)
	if not roles:
		return []
	return frappe.get_all(
		"AutoFlow Approval Rule",
		filters={
			"company": company,
			"document_type": document_type,
			"role": ["in", roles],
			"active": 1,
		},
		fields=["name", "role", "amount_limit", "discount_limit", "risk_level"],
	)


def _rule_allows_snapshot(rule: dict, snapshot: dict[str, Any]) -> bool:
	rule_risk = RISK_LEVELS.get(cstr(rule.get("risk_level")), 0)
	snapshot_risk = RISK_LEVELS.get(cstr(snapshot.get("risk_level")), 0)
	return (
		flt(rule.get("amount_limit")) >= flt(snapshot.get("amount"))
		and flt(rule.get("discount_limit"))
		>= flt(snapshot.get("maximum_discount"))
		and rule_risk >= snapshot_risk
	)


def approval_request_has_authority(request, user: str) -> bool:
	"""Validate actor, current source content and one complete authority rule."""
	if user != frappe.session.user:
		return False
	if not frappe.db.exists(request.reference_doctype, request.reference_name):
		return False
	source = frappe.get_doc(request.reference_doctype, request.reference_name)
	source.check_permission("read")
	request_snapshot = _read_snapshot(request)
	current_snapshot = build_approval_snapshot(source)
	if request_snapshot.get("fingerprint") != current_snapshot.get("fingerprint"):
		return False
	if request.company != current_snapshot.get("company"):
		return False
	return any(
		_rule_allows_snapshot(rule, request_snapshot)
		for rule in _get_user_rules(
			request.company,
			request.reference_doctype,
			user,
		)
	)


def requires_price_approval(quotation) -> bool:
	snapshot = build_approval_snapshot(quotation)
	if snapshot["has_floor_breach"]:
		return True
	return not any(
		_rule_allows_snapshot(rule, snapshot)
		for rule in _get_user_rules(
			quotation.company,
			"Quotation",
			frappe.session.user,
		)
	)


def has_current_approved_request(quotation) -> bool:
	current_fingerprint = build_approval_snapshot(quotation)["fingerprint"]
	request_names = frappe.get_all(
		"AutoFlow Approval Request",
		filters={
			"reference_doctype": "Quotation",
			"reference_name": quotation.name,
			"status": APPROVED_STATUS,
			"docstatus": 1,
		},
		pluck="name",
	)
	for request_name in request_names:
		request = frappe.get_doc("AutoFlow Approval Request", request_name)
		if _read_snapshot(request).get("fingerprint") == current_fingerprint:
			return True
	return False


def validate_quotation_submission(doc, method: str | None = None) -> None:
	if not cstr(getattr(doc, "custom_customer_project", None)).strip():
		return
	approved_sample = frappe.db.exists(
		"Sample Request",
		{
			"customer_project": doc.custom_customer_project,
			"status": "客户认可",
		},
	)
	if not approved_sample:
		frappe.throw(
			_("A customer-approved sample is required before quotation submission.")
		)
	if doc.valid_till and getdate(doc.valid_till) < getdate(nowdate()):
		frappe.throw(_("Expired quotation cannot be submitted."))
	if requires_price_approval(doc) and not has_current_approved_request(doc):
		frappe.throw(
			_("Quotation exceeds the current user's price authority.")
		)


def _quotation_lock_name(operation: str, quotation_name: str) -> str:
	return "autoflow-quotation-" + make_idempotency_key(
		operation,
		quotation_name,
	)


def _lock_quotation_row(quotation_name: str) -> None:
	if not frappe.db.get_value(
		"Quotation",
		quotation_name,
		"name",
		for_update=True,
	):
		frappe.throw(_("Quotation {0} no longer exists.").format(quotation_name))


def create_quotation_approval_request(quotation_name: str) -> str:
	quotation_name = cstr(quotation_name).strip()
	if not quotation_name:
		frappe.throw(_("Quotation is required."))
	quotation = frappe.get_doc("Quotation", quotation_name)
	quotation.check_permission("write")
	if quotation.docstatus != 0:
		frappe.throw(_("Only a draft quotation can request price approval."))
	if not cstr(quotation.custom_customer_project).strip():
		frappe.throw(_("Quotation must be linked to a customer project."))
	if not requires_price_approval(quotation):
		frappe.throw(_("This quotation is within the current user's authority."))

	with filelock(_quotation_lock_name("approval", quotation.name), timeout=15):
		_lock_quotation_row(quotation.name)
		quotation.reload()
		fingerprint = build_approval_snapshot(quotation)["fingerprint"]
		pending_names = frappe.get_all(
			"AutoFlow Approval Request",
			filters={
				"reference_doctype": "Quotation",
				"reference_name": quotation.name,
				"status": "待审批",
				"docstatus": 0,
			},
			pluck="name",
		)
		for request_name in pending_names:
			request = frappe.get_doc("AutoFlow Approval Request", request_name)
			if _read_snapshot(request).get("fingerprint") == fingerprint:
				return request.name

		request = frappe.get_doc(
			{
				"doctype": "AutoFlow Approval Request",
				"reference_doctype": "Quotation",
				"reference_name": quotation.name,
				"approval_type": "报价价格权限",
			}
		)
		request.insert()
		return request.name


def create_sales_order_from_quotation(quotation_name: str) -> str:
	quotation_name = cstr(quotation_name).strip()
	if not quotation_name:
		frappe.throw(_("Quotation is required."))
	quotation = frappe.get_doc("Quotation", quotation_name)
	quotation.check_permission("read")
	frappe.has_permission("Sales Order", "create", throw=True)

	with filelock(_quotation_lock_name("sales-order", quotation.name), timeout=15):
		_lock_quotation_row(quotation.name)
		quotation.reload()
		if quotation.docstatus != 1:
			frappe.throw(_("Quotation must be submitted before conversion."))
		if not cstr(quotation.custom_customer_project).strip():
			frappe.throw(_("Quotation must be linked to a customer project."))
		if quotation.valid_till and getdate(quotation.valid_till) < getdate(nowdate()):
			frappe.throw(_("Expired quotation cannot be converted."))
		if not quotation.custom_customer_confirmed:
			frappe.throw(_("Customer has not confirmed this quotation."))

		existing = frappe.db.get_value(
			"Sales Order",
			{"custom_source_quotation": quotation.name},
			"name",
		)
		if existing:
			frappe.get_doc("Sales Order", existing).check_permission("read")
			return existing

		from erpnext.selling.doctype.quotation.quotation import make_sales_order

		order = make_sales_order(quotation.name)
		order.custom_customer_project = quotation.custom_customer_project
		order.custom_source_quotation = quotation.name
		delivery_date = frappe.db.get_value(
			"Customer Project",
			quotation.custom_customer_project,
			"customer_delivery_date",
		)
		if delivery_date:
			order.delivery_date = delivery_date
			for item in order.items:
				item.delivery_date = delivery_date
		try:
			order.insert()
		except frappe.DuplicateEntryError:
			existing = frappe.db.get_value(
				"Sales Order",
				{"custom_source_quotation": quotation.name},
				"name",
			)
			if not existing:
				raise
			return existing
		return order.name
