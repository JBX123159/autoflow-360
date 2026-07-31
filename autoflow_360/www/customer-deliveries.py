import frappe
from frappe import _

from autoflow_360.permissions.portal import (
	get_customer_names_for_user,
	is_customer_portal_user,
)


def _require_customer_portal() -> list[str]:
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Please sign in to view customer deliveries."), frappe.PermissionError)
	if user != "Administrator" and not is_customer_portal_user(user):
		raise frappe.PermissionError
	return get_customer_names_for_user(user)


def get_context(context):
	context.no_cache = 1
	context.title = _("My Deliveries")
	customers = _require_customer_portal()
	if not customers:
		context.deliveries = []
		return context

	deliveries = frappe.get_list(
		"Delivery Note",
		filters={"customer": ["in", customers], "docstatus": 1},
		fields=[
			"name",
			"customer",
			"customer_name",
			"posting_date",
			"status",
			"currency",
			"grand_total",
			"custom_customer_project",
		],
		order_by="posting_date desc, name desc",
	)
	if not deliveries:
		context.deliveries = []
		return context

	delivery_names = [delivery.name for delivery in deliveries]
	items = frappe.get_all(
		"Delivery Note Item",
		filters={"parent": ["in", delivery_names]},
		fields=["parent", "item_code", "item_name", "qty", "uom", "warehouse"],
		order_by="idx asc",
	)
	items_by_delivery: dict[str, list] = {}
	for item in items:
		items_by_delivery.setdefault(item.parent, []).append(item)

	receipts = frappe.get_list(
		"Customer Receipt",
		filters={"delivery_note": ["in", delivery_names]},
		fields=["name", "delivery_note", "received_at", "received_by", "proof_file"],
	)
	receipt_by_delivery = {receipt.delivery_note: receipt for receipt in receipts}
	for delivery in deliveries:
		delivery.items = items_by_delivery.get(delivery.name, [])
		delivery.receipt = receipt_by_delivery.get(delivery.name)
	context.deliveries = deliveries
	return context
