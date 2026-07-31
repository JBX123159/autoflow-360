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


def _ensure_permission(doctype: str, permission_type: str) -> None:
	filters = {
		"parent": doctype,
		"role": SUPPLIER_PORTAL_ROLE,
		"permlevel": 0,
		"if_owner": 0,
	}
	permission_name = frappe.db.exists("Custom DocPerm", filters)
	if not permission_name:
		add_permission(doctype, SUPPLIER_PORTAL_ROLE, ptype=permission_type)
		return

	permission = frappe.get_doc("Custom DocPerm", permission_name)
	if not permission.get(permission_type):
		permission.set(permission_type, 1)
		permission.save(ignore_permissions=True)


def ensure_supplier_portal_permissions() -> None:
	"""Install only permissions required by protected supplier portal flows."""
	for doctype in SUPPLIER_PORTAL_READ_DOCTYPES:
		_ensure_permission(doctype, "read")
	for doctype in SUPPLIER_PORTAL_SELECT_DOCTYPES:
		_ensure_permission(doctype, "select")
