from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cstr, flt
from frappe.utils.synchronization import filelock

from autoflow_360.permissions.portal import (
	get_customer_names_for_user,
	is_customer_portal_user,
)
from autoflow_360.services.idempotency import make_idempotency_key


def _delivery_lock_name(operation: str, source_name: str) -> str:
	return "autoflow-delivery-" + make_idempotency_key(operation, source_name)


def _lock_document_row(doctype: str, name: str) -> None:
	if not frappe.db.get_value(doctype, name, "name", for_update=True):
		frappe.throw(_("{0} {1} no longer exists.").format(doctype, name))


def _validate_order_sources(doc) -> None:
	delivered_by_order_item: dict[str, float] = defaultdict(float)
	order_sources: dict[str, frappe._dict] = {}
	for row in list(doc.get("items") or []):
		order_name = cstr(row.against_sales_order).strip()
		order_item_name = cstr(row.so_detail).strip()
		if not order_name or not order_item_name:
			frappe.throw(_("Every project delivery item must come from a Sales Order."))
		if flt(row.stock_qty) <= 0:
			frappe.throw(_("Delivery stock quantity must be greater than zero."))

		source = frappe.db.get_value(
			"Sales Order Item",
			order_item_name,
			["parent", "item_code", "stock_qty"],
			as_dict=True,
			for_update=True,
		)
		if not source or source.parent != order_name or source.item_code != row.item_code:
			frappe.throw(_("Delivery item does not match its Sales Order source."))
		if frappe.db.get_value("Sales Order", order_name, "docstatus") != 1:
			frappe.throw(_("Delivery requires a submitted Sales Order."))
		if (
			frappe.db.get_value(
				"Sales Order",
				order_name,
				"custom_customer_project",
			)
			!= doc.custom_customer_project
		):
			frappe.throw(_("Delivery and Sales Order must belong to one customer project."))

		order_sources[order_item_name] = source
		delivered_by_order_item[order_item_name] += flt(row.stock_qty)

	for order_item_name, current_quantity in delivered_by_order_item.items():
		previous_quantity = flt(
			frappe.db.sql(
				"""
				select coalesce(sum(item.stock_qty), 0)
				from `tabDelivery Note Item` item
				inner join `tabDelivery Note` delivery
					on delivery.name = item.parent and delivery.docstatus = 1
				where item.so_detail = %(order_item)s
					and delivery.name != %(delivery_note)s
				""",
				{
					"order_item": order_item_name,
					"delivery_note": doc.name or "",
				},
			)[0][0]
		)
		ordered_quantity = flt(order_sources[order_item_name].stock_qty)
		if previous_quantity + current_quantity > ordered_quantity + 1e-9:
			frappe.throw(
				_("Delivery quantity exceeds the remaining Sales Order quantity."),
			)


def _validate_available_stock(doc) -> None:
	required_by_stock_key: dict[tuple[str, str], float] = defaultdict(float)
	for row in list(doc.get("items") or []):
		if not frappe.get_cached_value("Item", row.item_code, "is_stock_item"):
			continue
		warehouse = cstr(row.warehouse).strip()
		if not warehouse:
			frappe.throw(_("Every stock delivery item requires a warehouse."))
		required_by_stock_key[(row.item_code, warehouse)] += flt(row.stock_qty)

	for item_code, warehouse in sorted(required_by_stock_key):
		required_quantity = required_by_stock_key[(item_code, warehouse)]
		available_quantity = flt(
			frappe.db.get_value(
				"Bin",
				{"item_code": item_code, "warehouse": warehouse},
				"actual_qty",
				for_update=True,
			)
		)
		if available_quantity + 1e-9 < required_quantity:
			frappe.throw(
				_(
					"Insufficient stock for {0} in {1}: required {2}, available {3}."
				).format(
					item_code,
					warehouse,
					required_quantity,
					available_quantity,
				)
			)


def validate_delivery_stock(doc, method: str | None = None) -> None:
	if not cstr(doc.get("custom_customer_project")).strip() or doc.get("is_return"):
		return
	if not doc.get("items"):
		frappe.throw(_("Project Delivery Note requires at least one item."))
	_validate_order_sources(doc)
	_validate_available_stock(doc)


def _validate_proof_file(proof_file: str | None) -> str | None:
	proof_file = cstr(proof_file).strip()
	if not proof_file:
		return None
	if not frappe.db.exists(
		"File",
		{
			"file_url": proof_file,
			"owner": frappe.session.user,
			"is_private": 1,
		},
	):
		raise frappe.PermissionError
	return proof_file


def _authorize_customer_delivery(delivery) -> None:
	if not is_customer_portal_user():
		raise frappe.PermissionError
	if delivery.customer not in get_customer_names_for_user():
		raise frappe.PermissionError


def confirm_customer_receipt(
	delivery_note: str,
	proof_file: str | None = None,
) -> str:
	delivery_note = cstr(delivery_note).strip()
	if not delivery_note:
		frappe.throw(_("Delivery Note is required."))
	delivery = frappe.get_doc("Delivery Note", delivery_note)
	_authorize_customer_delivery(delivery)
	validated_proof_file = _validate_proof_file(proof_file)

	with filelock(
		_delivery_lock_name("customer-receipt", delivery.name),
		timeout=15,
	):
		_lock_document_row("Delivery Note", delivery.name)
		delivery.reload()
		_authorize_customer_delivery(delivery)
		if delivery.docstatus != 1:
			frappe.throw(_("Delivery Note must be submitted before receipt."))
		if not cstr(delivery.custom_customer_project).strip():
			frappe.throw(_("Delivery Note must be linked to a customer project."))

		existing = frappe.db.get_value(
			"Customer Receipt",
			{"delivery_note": delivery.name},
			"name",
		)
		if existing:
			return existing

		receipt = frappe.get_doc(
			{
				"doctype": "Customer Receipt",
				"delivery_note": delivery.name,
				"proof_file": validated_proof_file,
			}
		)
		receipt.flags.from_customer_receipt_service = True
		receipt.insert(ignore_permissions=True)
		return receipt.name
