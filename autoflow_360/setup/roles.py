import frappe


ROLES = (
	"AutoFlow Sales Operations",
	"AutoFlow Project Manager",
	"AutoFlow Procurement",
	"AutoFlow Warehouse",
	"AutoFlow Finance",
	"AutoFlow Executive",
	"AutoFlow Administrator",
	"AutoFlow Customer Portal",
	"AutoFlow Supplier Portal",
)

PORTAL_ROLES = {
	"AutoFlow Customer Portal",
	"AutoFlow Supplier Portal",
}


def ensure_roles() -> None:
	"""Create the fixed roles and reconcile their desk-access boundary."""
	for role_name in ROLES:
		expected_desk_access = 0 if role_name in PORTAL_ROLES else 1
		existing_role = frappe.db.exists("Role", role_name)
		if existing_role:
			role = frappe.get_doc("Role", existing_role)
			if int(role.desk_access or 0) != expected_desk_access:
				role.desk_access = expected_desk_access
				role.save(ignore_permissions=True)
			continue

		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role_name,
				"desk_access": expected_desk_access,
			}
		).insert(ignore_permissions=True)
