import frappe
from frappe.permissions import add_permission


SUPPLIER_PORTAL_ROLE = "AutoFlow Supplier Portal"
SUPPLIER_PORTAL_READ_DOCTYPES = (
	"Request for Quotation",
	"Supplier Quotation",
	"Purchase Order",
	"Item",
)
SUPPLIER_PORTAL_SELECT_DOCTYPES = ("Account",)
CUSTOMER_PORTAL_ROLE = "AutoFlow Customer Portal"
CUSTOMER_PORTAL_READ_DOCTYPES = (
	"Delivery Note",
	"Customer Receipt",
)


def _ensure_permission(
	doctype: str,
	role: str,
	permission_type: str,
) -> None:
	filters = {
		"parent": doctype,
		"role": role,
		"permlevel": 0,
		"if_owner": 0,
	}
	permission_name = frappe.db.exists("Custom DocPerm", filters)
	if not permission_name:
		add_permission(doctype, role, ptype=permission_type)
		return

	permission = frappe.get_doc("Custom DocPerm", permission_name)
	if not permission.get(permission_type):
		permission.set(permission_type, 1)
		permission.save(ignore_permissions=True)


def ensure_supplier_portal_permissions() -> None:
	"""Install only permissions required by protected supplier portal flows."""
	for doctype in SUPPLIER_PORTAL_READ_DOCTYPES:
		_ensure_permission(doctype, SUPPLIER_PORTAL_ROLE, "read")
	for doctype in SUPPLIER_PORTAL_SELECT_DOCTYPES:
		_ensure_permission(doctype, SUPPLIER_PORTAL_ROLE, "select")


def ensure_customer_portal_permissions() -> None:
	"""Install read entry points protected by customer row-level guards."""
	for doctype in CUSTOMER_PORTAL_READ_DOCTYPES:
		_ensure_permission(doctype, CUSTOMER_PORTAL_ROLE, "read")
