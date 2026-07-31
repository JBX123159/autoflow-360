import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

import frappe
from frappe import _
from frappe.utils import cstr, flt
from frappe.utils.synchronization import filelock

from autoflow_360.services.idempotency import make_idempotency_key


CLOSURE_APPROVAL_TYPE = "项目结项"
CLOSURE_READY_STAGE = "待回款"
CLOSED_STAGE = "已结项"
AMOUNT_TOLERANCE = 0.01


@dataclass(frozen=True, slots=True)
class ClosureGap:
	code: str
	message: str
	reference_doctype: str | None = None
	reference_name: str | None = None


def _normalize_project_name(project_name: str) -> str:
	project_name = cstr(project_name).strip()
	if not project_name:
		frappe.throw(_("Customer Project is required."))
	return project_name


def _project_lock_name(operation: str, project_name: str) -> str:
	return "autoflow-project-closure-" + make_idempotency_key(
		operation,
		project_name,
	)


def _lock_project_row(project_name: str) -> None:
	if not frappe.db.get_value(
		"Customer Project",
		project_name,
		"name",
		for_update=True,
	):
		frappe.throw(_("Customer Project {0} no longer exists.").format(project_name))


def _submitted_orders(project_name: str) -> list[frappe._dict]:
	return frappe.get_all(
		"Sales Order",
		filters={"custom_customer_project": project_name, "docstatus": 1},
		fields=["name", "per_delivered", "per_billed", "grand_total"],
		order_by="name asc",
	)


def _submitted_deliveries(project_name: str) -> list[frappe._dict]:
	return frappe.get_all(
		"Delivery Note",
		filters={"custom_customer_project": project_name, "docstatus": 1},
		fields=["name", "customer", "grand_total"],
		order_by="name asc",
	)


def _customer_receipts(delivery_names: list[str]) -> list[frappe._dict]:
	if not delivery_names:
		return []
	return frappe.get_all(
		"Customer Receipt",
		filters={"delivery_note": ["in", delivery_names]},
		fields=["name", "delivery_note", "customer", "received_at", "portal_user"],
		order_by="delivery_note asc",
	)


def _submitted_invoices(project_name: str) -> list[frappe._dict]:
	return frappe.get_all(
		"Sales Invoice",
		filters={"custom_customer_project": project_name, "docstatus": 1},
		fields=[
			"name",
			"grand_total",
			"outstanding_amount",
			"is_pos",
		],
		order_by="name asc",
	)


def _payment_entries(invoice_names: list[str]) -> list[frappe._dict]:
	if not invoice_names:
		return []
	return frappe.db.sql(
		"""
		select
			reference.reference_name as sales_invoice,
			reference.parent as payment_entry,
			reference.allocated_amount
		from `tabPayment Entry Reference` reference
		inner join `tabPayment Entry` payment
			on payment.name = reference.parent and payment.docstatus = 1
		where reference.reference_doctype = 'Sales Invoice'
			and reference.reference_name in %(invoice_names)s
		order by reference.reference_name asc, reference.parent asc
		""",
		{"invoice_names": invoice_names},
		as_dict=True,
	)


def _open_high_exceptions(project_name: str) -> list[str]:
	if not frappe.db.exists("DocType", "Business Exception"):
		return []
	meta = frappe.get_meta("Business Exception")
	if not all(
		meta.has_field(fieldname)
		for fieldname in ("customer_project", "risk_level", "status")
	):
		return []
	return frappe.get_all(
		"Business Exception",
		filters={
			"customer_project": project_name,
			"risk_level": "高",
			"status": ["not in", ["已关闭", "已取消"]],
		},
		pluck="name",
		order_by="name asc",
	)


def _open_high_project_risks(project_name: str) -> list[str]:
	if not frappe.db.exists("DocType", "Project Risk"):
		return []
	meta = frappe.get_meta("Project Risk")
	if not all(
		meta.has_field(fieldname)
		for fieldname in ("customer_project", "risk_level", "status")
	):
		return []
	return frappe.get_all(
		"Project Risk",
		filters={
			"customer_project": project_name,
			"risk_level": "高",
			"status": ["not in", ["已关闭"]],
		},
		pluck="name",
		order_by="name asc",
	)


def get_closure_gaps(project_name: str) -> list[ClosureGap]:
	project = frappe.get_doc(
		"Customer Project",
		_normalize_project_name(project_name),
	)
	project.check_permission("read")

	gaps: list[ClosureGap] = []
	if project.stage not in {CLOSURE_READY_STAGE, CLOSED_STAGE}:
		gaps.append(
			ClosureGap(
				"PROJECT_STAGE_NOT_READY",
				_("Project must reach the payment-pending stage before closure."),
				"Customer Project",
				project.name,
			)
		)

	orders = _submitted_orders(project.name)
	if not orders:
		gaps.append(
			ClosureGap(
				"NO_SALES_ORDER",
				_("No submitted Sales Order exists."),
			)
		)
	for order in orders:
		if flt(order.per_delivered) < 100 - AMOUNT_TOLERANCE:
			gaps.append(
				ClosureGap(
					"DELIVERY_INCOMPLETE",
					_("Sales Order delivery is incomplete."),
					"Sales Order",
					order.name,
				)
			)
		if flt(order.per_billed) < 100 - AMOUNT_TOLERANCE:
			gaps.append(
				ClosureGap(
					"BILLING_INCOMPLETE",
					_("Sales Order billing is incomplete."),
					"Sales Order",
					order.name,
				)
			)

	deliveries = _submitted_deliveries(project.name)
	delivery_names = [delivery.name for delivery in deliveries]
	receipts = _customer_receipts(delivery_names)
	receipted_deliveries = {receipt.delivery_note for receipt in receipts}
	for delivery in deliveries:
		if delivery.name not in receipted_deliveries:
			gaps.append(
				ClosureGap(
					"CUSTOMER_RECEIPT_MISSING",
					_("Customer receipt confirmation is missing."),
					"Delivery Note",
					delivery.name,
				)
			)

	invoices = _submitted_invoices(project.name)
	if not invoices:
		gaps.append(
			ClosureGap(
				"NO_SALES_INVOICE",
				_("No submitted Sales Invoice exists."),
			)
		)
	payment_entries = _payment_entries([invoice.name for invoice in invoices])
	paid_invoices = {entry.sales_invoice for entry in payment_entries}
	for invoice in invoices:
		if flt(invoice.outstanding_amount) > AMOUNT_TOLERANCE:
			gaps.append(
				ClosureGap(
					"UNPAID_RECEIVABLE",
					_("Sales Invoice still has an outstanding receivable."),
					"Sales Invoice",
					invoice.name,
				)
			)
		elif (
			flt(invoice.grand_total) > AMOUNT_TOLERANCE
			and not invoice.is_pos
			and invoice.name not in paid_invoices
		):
			gaps.append(
				ClosureGap(
					"PAYMENT_EVIDENCE_MISSING",
					_("A submitted Payment Entry is required as collection evidence."),
					"Sales Invoice",
					invoice.name,
				)
			)

	for exception_name in _open_high_exceptions(project.name):
		gaps.append(
			ClosureGap(
				"OPEN_HIGH_EXCEPTION",
				_("A high-risk business exception is still open."),
				"Business Exception",
				exception_name,
			)
		)
	for risk_name in _open_high_project_risks(project.name):
		gaps.append(
			ClosureGap(
				"OPEN_HIGH_RISK",
				_("A high project risk is still open."),
				"Project Risk",
				risk_name,
			)
		)
	return gaps


def prevent_closed_project_evidence_change(
	doc,
	method: str | None = None,
) -> None:
	project_name = cstr(getattr(doc, "custom_customer_project", None)).strip()
	if not project_name and doc.doctype == "Payment Entry":
		invoice_names = [
			row.reference_name
			for row in list(doc.get("references") or [])
			if row.reference_doctype == "Sales Invoice"
		]
		if invoice_names:
			projects = frappe.get_all(
				"Sales Invoice",
				filters={"name": ["in", invoice_names]},
				pluck="custom_customer_project",
			)
			project_name = next((name for name in projects if name), "")
	if not project_name:
		return
	if frappe.db.get_value("Customer Project", project_name, "stage") == CLOSED_STAGE:
		frappe.throw(
			_("Closed project evidence cannot be cancelled or changed."),
		)


def _snapshot_rows(rows: list[frappe._dict]) -> list[dict[str, Any]]:
	return [
		{
			key: round(flt(value), 6)
			if isinstance(value, (float, int)) and not isinstance(value, bool)
			else value
			for key, value in sorted(dict(row).items())
		}
		for row in rows
	]


def build_project_closure_snapshot(project) -> dict[str, Any]:
	orders = _submitted_orders(project.name)
	deliveries = _submitted_deliveries(project.name)
	invoices = _submitted_invoices(project.name)
	payload: dict[str, Any] = {
		"document_type": project.doctype,
		"document_name": project.name,
		"company": project.company,
		"customer": project.customer,
		"customer_project": project.name,
		"stage": project.stage,
		"amount": round(flt(project.expected_amount), 6),
		"maximum_discount": 0,
		"has_floor_breach": False,
		"risk_level": project.overall_risk_level or "低",
		"orders": _snapshot_rows(orders),
		"deliveries": _snapshot_rows(deliveries),
		"receipts": _snapshot_rows(
			_customer_receipts([delivery.name for delivery in deliveries])
		),
		"invoices": _snapshot_rows(invoices),
		"payments": _snapshot_rows(
			_payment_entries([invoice.name for invoice in invoices])
		),
		"open_high_exceptions": _open_high_exceptions(project.name),
		"open_high_risks": _open_high_project_risks(project.name),
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


def _request_snapshot(request) -> dict[str, Any]:
	try:
		snapshot = frappe.parse_json(request.request_snapshot)
	except (TypeError, ValueError):
		return {}
	return snapshot if isinstance(snapshot, dict) else {}


def _current_fingerprint(project) -> str:
	return build_project_closure_snapshot(project)["fingerprint"]


def has_approved_closure_request(project_name: str) -> bool:
	project = frappe.get_doc(
		"Customer Project",
		_normalize_project_name(project_name),
	)
	project.check_permission("read")
	current_fingerprint = _current_fingerprint(project)
	request_names = frappe.get_all(
		"AutoFlow Approval Request",
		filters={
			"reference_doctype": "Customer Project",
			"reference_name": project.name,
			"approval_type": CLOSURE_APPROVAL_TYPE,
			"status": "已通过",
			"docstatus": 1,
		},
		pluck="name",
	)
	return any(
		_request_snapshot(
			frappe.get_doc("AutoFlow Approval Request", request_name)
		).get("fingerprint")
		== current_fingerprint
		for request_name in request_names
	)


def create_project_closure_request(project_name: str) -> str:
	project = frappe.get_doc(
		"Customer Project",
		_normalize_project_name(project_name),
	)
	project.check_permission("write")
	if project.stage == CLOSED_STAGE:
		frappe.throw(_("Project is already closed."))
	initial_gaps = get_closure_gaps(project.name)
	if initial_gaps:
		frappe.throw("<br>".join(gap.message for gap in initial_gaps))

	with filelock(_project_lock_name("request", project.name), timeout=15):
		_lock_project_row(project.name)
		project.reload()
		project.check_permission("write")
		gaps = get_closure_gaps(project.name)
		if gaps:
			frappe.throw("<br>".join(gap.message for gap in gaps))
		fingerprint = _current_fingerprint(project)
		pending_names = frappe.get_all(
			"AutoFlow Approval Request",
			filters={
				"reference_doctype": "Customer Project",
				"reference_name": project.name,
				"approval_type": CLOSURE_APPROVAL_TYPE,
				"status": "待审批",
				"docstatus": 0,
			},
			pluck="name",
		)
		for request_name in pending_names:
			request = frappe.get_doc("AutoFlow Approval Request", request_name)
			if _request_snapshot(request).get("fingerprint") == fingerprint:
				return request.name

		request = frappe.get_doc(
			{
				"doctype": "AutoFlow Approval Request",
				"reference_doctype": "Customer Project",
				"reference_name": project.name,
				"approval_type": CLOSURE_APPROVAL_TYPE,
			}
		)
		request.insert()
		return request.name


def get_closure_status(project_name: str) -> dict[str, Any]:
	project = frappe.get_doc(
		"Customer Project",
		_normalize_project_name(project_name),
	)
	project.check_permission("read")
	gaps = get_closure_gaps(project.name)
	request = frappe.get_list(
		"AutoFlow Approval Request",
		filters={
			"reference_doctype": "Customer Project",
			"reference_name": project.name,
			"approval_type": CLOSURE_APPROVAL_TYPE,
		},
		fields=["name", "status", "requested_by", "requested_at", "approver"],
		order_by="creation desc",
		limit=1,
	)
	return {
		"project": project.name,
		"stage": project.stage,
		"gaps": [asdict(gap) for gap in gaps],
		"approved": project.stage == CLOSED_STAGE
		or has_approved_closure_request(project.name),
		"approval_request": request[0] if request else None,
	}


def close_project(project_name: str, summary: str) -> str:
	project = frappe.get_doc(
		"Customer Project",
		_normalize_project_name(project_name),
	)
	project.check_permission("write")
	normalized_summary = cstr(summary).strip()
	if len(normalized_summary) < 10:
		frappe.throw(_("Closure summary must contain at least 10 characters."))

	with filelock(_project_lock_name("close", project.name), timeout=15):
		_lock_project_row(project.name)
		project.reload()
		project.check_permission("write")
		if project.stage == CLOSED_STAGE:
			if cstr(project.closure_summary).strip() != normalized_summary:
				frappe.throw(_("Closure summary cannot be changed after closure."))
			return project.name

		gaps = get_closure_gaps(project.name)
		if gaps:
			frappe.throw("<br>".join(gap.message for gap in gaps))
		if not has_approved_closure_request(project.name):
			frappe.throw(_("Approved project closure request is required."))

		project.closure_summary = normalized_summary
		project.stage = CLOSED_STAGE
		project.flags.from_project_closure_service = True
		project.save()
		return project.name
