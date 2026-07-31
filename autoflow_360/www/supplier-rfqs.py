import frappe
from frappe import _
from frappe.utils import nowdate

from autoflow_360.permissions.portal import (
	get_supplier_names_for_user,
	is_supplier_portal_user,
)


def _require_supplier_portal() -> list[str]:
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Please sign in to view supplier RFQs."), frappe.PermissionError)
	if user != "Administrator" and not is_supplier_portal_user(user):
		raise frappe.PermissionError
	return get_supplier_names_for_user(user)


def get_context(context):
	context.no_cache = 1
	context.title = _("Supplier RFQs")
	context.today = nowdate()
	suppliers = _require_supplier_portal()
	if not suppliers:
		context.rfqs = []
		return context

	invites = frappe.get_all(
		"Request for Quotation Supplier",
		filters={
			"parenttype": "Request for Quotation",
			"supplier": ["in", suppliers],
		},
		fields=["parent", "supplier"],
	)
	rfq_names = list(dict.fromkeys(row.parent for row in invites))
	if not rfq_names:
		context.rfqs = []
		return context

	rfqs = frappe.get_list(
		"Request for Quotation",
		filters={"name": ["in", rfq_names], "docstatus": 1},
		fields=[
			"name",
			"company",
			"transaction_date",
			"schedule_date",
			"custom_customer_project",
		],
		order_by="transaction_date desc, name desc",
	)
	if not rfqs:
		context.rfqs = []
		return context
	items = frappe.get_all(
		"Request for Quotation Item",
		filters={"parent": ["in", [rfq.name for rfq in rfqs]]},
		fields=[
			"name",
			"parent",
			"item_code",
			"item_name",
			"description",
			"qty",
			"uom",
			"schedule_date",
		],
		order_by="idx asc",
	)
	items_by_rfq: dict[str, list] = {}
	for item in items:
		items_by_rfq.setdefault(item.parent, []).append(item)

	existing_quotes = frappe.get_list(
		"Supplier Quotation",
		filters={
			"custom_source_rfq": ["in", [rfq.name for rfq in rfqs]],
			"supplier": ["in", suppliers],
			"docstatus": ["<", 2],
		},
		fields=["name", "custom_source_rfq", "docstatus", "status"],
	)
	quote_by_rfq = {quote.custom_source_rfq: quote for quote in existing_quotes}
	for rfq in rfqs:
		rfq.items = items_by_rfq.get(rfq.name, [])
		rfq.current_quote = quote_by_rfq.get(rfq.name)
	context.rfqs = rfqs
	return context
