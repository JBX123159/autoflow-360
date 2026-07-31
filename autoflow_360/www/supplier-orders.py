import frappe
from frappe import _

from autoflow_360.permissions.portal import (
	get_supplier_names_for_user,
	is_supplier_portal_user,
)


def _require_supplier_portal() -> list[str]:
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Please sign in to view supplier orders."), frappe.PermissionError)
	if user != "Administrator" and not is_supplier_portal_user(user):
		raise frappe.PermissionError
	return get_supplier_names_for_user(user)


def get_context(context):
	context.no_cache = 1
	context.title = _("Supplier Purchase Orders")
	suppliers = _require_supplier_portal()
	if not suppliers:
		context.orders = []
		return context

	orders = frappe.get_list(
		"Purchase Order",
		filters={"supplier": ["in", suppliers], "docstatus": 1},
		fields=[
			"name",
			"supplier",
			"supplier_name",
			"transaction_date",
			"schedule_date",
			"status",
			"currency",
			"grand_total",
			"custom_supplier_eta",
			"custom_customer_project",
		],
		order_by="transaction_date desc, name desc",
	)
	if not orders:
		context.orders = []
		return context
	items = frappe.get_all(
		"Purchase Order Item",
		filters={"parent": ["in", [order.name for order in orders]]},
		fields=["parent", "item_code", "item_name", "qty", "uom", "schedule_date"],
		order_by="idx asc",
	)
	items_by_order: dict[str, list] = {}
	for item in items:
		items_by_order.setdefault(item.parent, []).append(item)
	for order in orders:
		order.items = items_by_order.get(order.name, [])
	context.orders = orders
	return context
