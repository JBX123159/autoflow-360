import frappe
from frappe.utils import cstr


CUSTOMER_PORTAL_ROLE = "AutoFlow Customer Portal"
INTERNAL_PROJECT_ROLES = {
	"System Manager",
	"AutoFlow Administrator",
	"AutoFlow Sales Operations",
	"AutoFlow Project Manager",
	"AutoFlow Procurement",
	"AutoFlow Warehouse",
	"AutoFlow Finance",
	"AutoFlow Executive",
}


def _current_user(user: str | None = None) -> str:
	return cstr(user or frappe.session.user).strip()


def is_customer_portal_user(user: str | None = None) -> bool:
	user = _current_user(user)
	if not user or user in {"Guest", "Administrator"}:
		return False
	roles = set(frappe.get_roles(user))
	return CUSTOMER_PORTAL_ROLE in roles and not roles.intersection(
		INTERNAL_PROJECT_ROLES
	)


def get_customer_names_for_user(user: str | None = None) -> list[str]:
	user = _current_user(user)
	if not user or user == "Guest":
		return []
	if user == "Administrator":
		return frappe.get_all("Customer", pluck="name")
	if CUSTOMER_PORTAL_ROLE not in frappe.get_roles(user):
		return []
	return frappe.get_all(
		"Portal User",
		filters={"user": user, "parenttype": "Customer"},
		pluck="parent",
	)


def can_access_customer_project(
	project_name: str,
	user: str | None = None,
) -> bool:
	user = _current_user(user)
	if not user or user == "Guest" or not cstr(project_name).strip():
		return False

	project = frappe.get_doc("Customer Project", project_name)
	if user == "Administrator":
		return True

	roles = set(frappe.get_roles(user))
	if roles.intersection(INTERNAL_PROJECT_ROLES):
		return bool(
			frappe.has_permission(
				"Customer Project",
				"read",
				user=user,
				doc=project,
			)
		)
	if CUSTOMER_PORTAL_ROLE not in roles:
		return False
	return project.customer in get_customer_names_for_user(user)


def customer_feedback_query(user: str | None = None) -> str:
	user = _current_user(user)
	if not is_customer_portal_user(user):
		return ""

	customers = get_customer_names_for_user(user)
	if not customers:
		return "1=0"
	escaped_customers = ", ".join(frappe.db.escape(name) for name in customers)
	return f"`tabCustomer Feedback`.`customer` in ({escaped_customers})"


def customer_feedback_has_permission(
	doc,
	user: str | None = None,
	permission_type: str | None = None,
):
	user = _current_user(user)
	if not is_customer_portal_user(user):
		return None
	if permission_type == "create":
		return True
	return doc.customer in get_customer_names_for_user(user)
