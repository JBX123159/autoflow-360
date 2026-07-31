from collections.abc import Iterable
from typing import Any

import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate, nowdate
from frappe.utils.synchronization import filelock

from autoflow_360.permissions.portal import (
	get_supplier_names_for_user,
	is_supplier_portal_user,
)
from autoflow_360.services.idempotency import make_idempotency_key


BLOCKED_PURCHASE_ORDER_STATUSES = {"Closed", "Completed", "Cancelled"}


def _procurement_lock_name(operation: str, source_name: str) -> str:
	return "autoflow-procurement-" + make_idempotency_key(
		operation,
		source_name,
	)


def _lock_source_row(doctype: str, name: str) -> None:
	if not frappe.db.get_value(
		doctype,
		name,
		"name",
		for_update=True,
	):
		frappe.throw(_("{0} {1} no longer exists.").format(doctype, name))


def _normalize_suppliers(suppliers: Iterable[str]) -> list[str]:
	if isinstance(suppliers, (str, bytes)) or not isinstance(suppliers, Iterable):
		frappe.throw(_("Suppliers must be provided as a list."))
	normalized = list(
		dict.fromkeys(cstr(supplier).strip() for supplier in suppliers if cstr(supplier).strip())
	)
	if not normalized:
		frappe.throw(_("At least one supplier is required."))
	for supplier in normalized:
		if not frappe.db.exists("Supplier", supplier):
			frappe.throw(_("Supplier {0} does not exist.").format(supplier))
		if frappe.db.get_value("Supplier", supplier, "disabled"):
			frappe.throw(_("Supplier {0} is disabled.").format(supplier))
	return normalized


def make_project_rfq(material_request_name: str, suppliers: list[str]) -> str:
	material_request_name = cstr(material_request_name).strip()
	if not material_request_name:
		frappe.throw(_("Material Request is required."))
	request = frappe.get_doc("Material Request", material_request_name)
	request.check_permission("read")
	frappe.has_permission("Request for Quotation", "create", throw=True)
	normalized_suppliers = _normalize_suppliers(suppliers)

	with filelock(
		_procurement_lock_name("request-for-quotation", request.name),
		timeout=15,
	):
		_lock_source_row("Material Request", request.name)
		request.reload()
		if request.docstatus != 1:
			frappe.throw(_("Material Request must be submitted before creating an RFQ."))
		if request.material_request_type != "Purchase":
			frappe.throw(_("Only a Purchase Material Request can create an RFQ."))
		if not cstr(request.custom_customer_project).strip():
			frappe.throw(_("Material Request must be linked to a customer project."))
		if not request.items:
			frappe.throw(_("Material Request requires at least one item."))

		existing = frappe.db.get_value(
			"Request for Quotation",
			{
				"custom_source_material_request": request.name,
				"docstatus": ["<", 2],
			},
			"name",
		)
		if existing:
			frappe.get_doc("Request for Quotation", existing).check_permission("read")
			return existing

		schedule_dates = [
			getdate(row.schedule_date)
			for row in request.items
			if row.schedule_date
		]
		if len(schedule_dates) != len(request.items):
			frappe.throw(_("Every Material Request item requires a schedule date."))
		for row in request.items:
			if flt(row.qty) <= 0:
				frappe.throw(_("Material Request item quantity must be positive."))

		rfq = frappe.get_doc(
			{
				"doctype": "Request for Quotation",
				"company": request.company,
				"transaction_date": getdate(nowdate()),
				"schedule_date": max(schedule_dates),
				"custom_customer_project": request.custom_customer_project,
				"custom_source_material_request": request.name,
				"suppliers": [
					{"supplier": supplier, "send_email": 0}
					for supplier in normalized_suppliers
				],
				"items": [
					{
						"item_code": row.item_code,
						"item_name": row.item_name,
						"description": row.description,
						"qty": row.qty,
						"uom": row.uom,
						"stock_uom": row.stock_uom,
						"conversion_factor": row.conversion_factor,
						"stock_qty": row.stock_qty,
						"warehouse": row.warehouse,
						"schedule_date": row.schedule_date,
						"material_request": request.name,
						"material_request_item": row.name,
					}
					for row in request.items
				],
			}
		)
		rfq.insert()
		rfq.submit()
		return rfq.name


def _supplier_for_rfq(rfq) -> str:
	if not is_supplier_portal_user():
		raise frappe.PermissionError
	linked_suppliers = set(get_supplier_names_for_user())
	invited_suppliers = {cstr(row.supplier).strip() for row in rfq.suppliers}
	allowed_suppliers = sorted(linked_suppliers.intersection(invited_suppliers))
	if not allowed_suppliers:
		raise frappe.PermissionError
	if len(allowed_suppliers) > 1:
		frappe.throw(
			_("The current user is linked to multiple suppliers invited to this RFQ.")
		)
	return allowed_suppliers[0]


def _normalize_supplier_quote_items(
	rfq,
	items: list[dict[str, Any]],
) -> dict[str, frappe._dict]:
	if not isinstance(items, list) or not items:
		frappe.throw(_("At least one quotation item is required."))
	allowed_rows = {row.name: row for row in rfq.items}
	normalized: dict[str, frappe._dict] = {}
	for raw_item in items:
		if not isinstance(raw_item, dict):
			frappe.throw(_("Every quotation item must be an object."))
		item = frappe._dict(raw_item)
		rfq_item = cstr(item.get("rfq_item")).strip()
		if not rfq_item or rfq_item not in allowed_rows:
			frappe.throw(_("Quotation item does not belong to this RFQ."))
		if rfq_item in normalized:
			frappe.throw(_("An RFQ item cannot be quoted more than once."))
		rate = flt(item.get("rate"))
		if rate <= 0:
			frappe.throw(_("Quotation rate must be greater than zero."))
		expected_delivery_date = item.get("expected_delivery_date") or allowed_rows[
			rfq_item
		].schedule_date
		if not expected_delivery_date:
			frappe.throw(_("Every quotation item requires an expected delivery date."))
		if getdate(expected_delivery_date) < getdate(rfq.transaction_date):
			frappe.throw(_("Expected delivery cannot be before the RFQ date."))
		normalized[rfq_item] = frappe._dict(
			{
				"rate": rate,
				"expected_delivery_date": getdate(expected_delivery_date),
			}
		)
	return normalized


def submit_supplier_quote(
	rfq_name: str,
	items: list[dict[str, Any]],
	valid_till: str,
) -> str:
	rfq_name = cstr(rfq_name).strip()
	if not rfq_name:
		frappe.throw(_("Request for Quotation is required."))
	rfq = frappe.get_doc("Request for Quotation", rfq_name)
	supplier = _supplier_for_rfq(rfq)
	valid_till_date = getdate(valid_till) if cstr(valid_till).strip() else None
	if not valid_till_date or valid_till_date < getdate(nowdate()):
		frappe.throw(_("Supplier quotation validity must end today or later."))
	normalized_items = _normalize_supplier_quote_items(rfq, items)

	with filelock(
		_procurement_lock_name("supplier-quotation", f"{rfq.name}-{supplier}"),
		timeout=15,
	):
		_lock_source_row("Request for Quotation", rfq.name)
		rfq.reload()
		if rfq.docstatus != 1:
			frappe.throw(_("Request for Quotation must be submitted."))
		if supplier not in {row.supplier for row in rfq.suppliers}:
			raise frappe.PermissionError

		existing = frappe.db.get_value(
			"Supplier Quotation",
			{
				"custom_source_rfq": rfq.name,
				"supplier": supplier,
				"docstatus": ["<", 2],
			},
			"name",
		)
		if existing:
			return existing

		from erpnext.buying.doctype.request_for_quotation.request_for_quotation import (
			add_items,
		)

		company_currency = frappe.db.get_value(
			"Company",
			rfq.company,
			"default_currency",
		)
		if not company_currency:
			frappe.throw(_("RFQ company requires a default currency."))
		quote_items = []
		for row in rfq.items:
			values = normalized_items.get(row.name)
			if not values:
				continue
			item = row.as_dict()
			item["rate"] = values.rate
			quote_items.append(item)
		quote = frappe.get_doc(
			{
				"doctype": "Supplier Quotation",
				"supplier": supplier,
				"company": rfq.company,
				"currency": company_currency,
				"buying_price_list": rfq.get("buying_price_list"),
				"terms": rfq.get("terms"),
			}
		)
		add_items(quote, supplier, quote_items)
		quote.flags.ignore_permissions = True
		quote.run_method("set_missing_values")
		quote.transaction_date = getdate(nowdate())
		quote.valid_till = valid_till_date
		quote.custom_customer_project = rfq.custom_customer_project
		quote.custom_source_rfq = rfq.name
		selected_rows = []
		for row in quote.items:
			values = normalized_items.get(row.request_for_quotation_item)
			if not values:
				continue
			row.rate = values.rate
			row.expected_delivery_date = values.expected_delivery_date
			selected_rows.append(row)
		if len(selected_rows) != len(normalized_items):
			frappe.throw(_("One or more RFQ items could not be mapped."))
		quote.set("items", selected_rows)
		quote.flags.ignore_permissions = True
		quote.insert()
		quote.submit()
		return quote.name


def make_purchase_order_from_supplier_quote(
	supplier_quotation_name: str,
) -> str:
	supplier_quotation_name = cstr(supplier_quotation_name).strip()
	if not supplier_quotation_name:
		frappe.throw(_("Supplier Quotation is required."))
	quote = frappe.get_doc("Supplier Quotation", supplier_quotation_name)
	quote.check_permission("read")
	frappe.has_permission("Purchase Order", "create", throw=True)

	with filelock(
		_procurement_lock_name("purchase-order", quote.name),
		timeout=15,
	):
		_lock_source_row("Supplier Quotation", quote.name)
		quote.reload()
		if quote.docstatus != 1:
			frappe.throw(_("Supplier Quotation must be submitted."))
		if quote.valid_till and getdate(quote.valid_till) < getdate(nowdate()):
			frappe.throw(_("Expired Supplier Quotation cannot create a Purchase Order."))
		if not cstr(quote.custom_customer_project).strip():
			frappe.throw(_("Supplier Quotation must be linked to a customer project."))

		existing = frappe.db.get_value(
			"Purchase Order",
			{
				"custom_source_supplier_quotation": quote.name,
				"docstatus": ["<", 2],
			},
			"name",
		)
		if existing:
			frappe.get_doc("Purchase Order", existing).check_permission("read")
			return existing

		from erpnext.buying.doctype.supplier_quotation.supplier_quotation import (
			make_purchase_order,
		)

		order = make_purchase_order(quote.name)
		order.custom_customer_project = quote.custom_customer_project
		order.custom_source_supplier_quotation = quote.name
		quote_item_by_name = {row.name: row for row in quote.items}
		eta_dates = []
		for row in order.items:
			source = quote_item_by_name.get(row.supplier_quotation_item)
			if source and source.expected_delivery_date:
				row.schedule_date = source.expected_delivery_date
				eta_dates.append(getdate(source.expected_delivery_date))
			elif row.schedule_date:
				eta_dates.append(getdate(row.schedule_date))
		if not eta_dates:
			frappe.throw(_("Purchase Order requires at least one delivery date."))
		order.schedule_date = max(eta_dates)
		order.custom_supplier_eta = max(eta_dates)
		order.insert()
		return order.name


def _authorize_eta_update(order) -> None:
	if is_supplier_portal_user():
		if order.supplier not in get_supplier_names_for_user():
			raise frappe.PermissionError
		return
	order.check_permission("write")


def update_supplier_eta(purchase_order: str, eta: str, reason: str) -> str:
	purchase_order = cstr(purchase_order).strip()
	if not purchase_order:
		frappe.throw(_("Purchase Order is required."))
	new_eta = getdate(eta) if cstr(eta).strip() else None
	change_reason = cstr(reason).strip()
	if not new_eta:
		frappe.throw(_("A new supplier ETA is required."))
	if not change_reason:
		frappe.throw(_("A supplier ETA change reason is required."))

	order = frappe.get_doc("Purchase Order", purchase_order)
	_authorize_eta_update(order)
	with filelock(
		_procurement_lock_name("supplier-eta", order.name),
		timeout=15,
	):
		_lock_source_row("Purchase Order", order.name)
		order.reload()
		_authorize_eta_update(order)
		if order.docstatus != 1 or order.status in BLOCKED_PURCHASE_ORDER_STATUSES:
			frappe.throw(_("Only an open submitted Purchase Order can update ETA."))
		if new_eta < getdate(order.transaction_date):
			frappe.throw(_("Supplier ETA cannot be before the Purchase Order date."))
		if order.custom_supplier_eta and new_eta == getdate(order.custom_supplier_eta):
			frappe.throw(_("Supplier ETA has not changed."))

		history = frappe.get_doc(
			{
				"doctype": "Supplier ETA History",
				"purchase_order": order.name,
				"new_eta": new_eta,
				"change_reason": change_reason,
			}
		)
		history.flags.from_supplier_eta_service = True
		history.insert(ignore_permissions=True)
		order.db_set("custom_supplier_eta", new_eta)
		return order.name
