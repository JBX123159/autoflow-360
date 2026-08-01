import frappe
from frappe.utils import cstr

from autoflow_360.permissions.portal import (
	INTERNAL_PROJECT_ROLES,
	get_customer_names_for_user,
	is_customer_portal_user,
	is_supplier_portal_user,
)


INTERNAL_GLOBAL_READ_ROLES = {
	"AutoFlow Administrator",
	"AutoFlow Executive",
}


def _current_user(user: str | None = None) -> str:
	return cstr(user or frappe.session.user).strip()


def _allowed_companies(user: str) -> set[str]:
	rows = frappe.get_all(
		"User Permission",
		filters={
			"user": user,
			"allow": "Company",
		},
		fields=["for_value", "applicable_for"],
	)
	return {
		cstr(row.for_value).strip()
		for row in rows
		if cstr(row.for_value).strip()
		and cstr(row.applicable_for).strip() in {"", "Customer Project"}
	}


def _company_query_condition(user: str) -> str:
	allowed_companies = _allowed_companies(user)
	if not allowed_companies:
		return ""
	escaped = ", ".join(
		frappe.db.escape(company) for company in sorted(allowed_companies)
	)
	return f"`tabCustomer Project`.`company` in ({escaped})"


def _member_query_condition(user: str) -> str:
	escaped_user = frappe.db.escape(user)
	return (
		f"(`tabCustomer Project`.`project_manager` = {escaped_user} "
		"or exists (select 1 from `tabProject Member` project_member "
		"where project_member.parent = `tabCustomer Project`.`name` "
		"and project_member.parenttype = 'Customer Project' "
		f"and project_member.user = {escaped_user}))"
	)


def _customer_query_condition(user: str) -> str:
	customers = get_customer_names_for_user(user)
	if not customers:
		return "1=0"
	escaped = ", ".join(
		frappe.db.escape(customer) for customer in sorted(customers)
	)
	return f"`tabCustomer Project`.`customer` in ({escaped})"


def _combine_conditions(*conditions: str) -> str:
	active = [condition for condition in conditions if condition]
	return " and ".join(f"({condition})" for condition in active)


def customer_project_query(user: str | None = None) -> str:
	user = _current_user(user)
	if user == "Administrator":
		return ""
	if not user or user == "Guest":
		return "1=0"

	company_condition = _company_query_condition(user)
	if is_customer_portal_user(user):
		return _combine_conditions(
			_customer_query_condition(user),
			company_condition,
		)
	if is_supplier_portal_user(user):
		return "1=0"

	roles = set(frappe.get_roles(user))
	if not roles.intersection(INTERNAL_PROJECT_ROLES):
		return "1=0"
	if roles.intersection(INTERNAL_GLOBAL_READ_ROLES):
		return company_condition
	return _combine_conditions(
		_member_query_condition(user),
		company_condition,
	)


def customer_project_has_permission(
	doc,
	user: str | None = None,
	ptype: str | None = None,
) -> bool | None:
	user = _current_user(user)
	permission_type = cstr(ptype or "read").strip()
	if user == "Administrator":
		return True
	if not user or user == "Guest":
		return False

	allowed_companies = _allowed_companies(user)
	if allowed_companies and doc.company not in allowed_companies:
		return False

	if is_customer_portal_user(user):
		customer_names = get_customer_names_for_user(user)
		return bool(
			permission_type == "read"
			and doc.customer in customer_names
		)
	if is_supplier_portal_user(user):
		return False

	roles = set(frappe.get_roles(user))
	if not roles.intersection(INTERNAL_PROJECT_ROLES):
		return False
	if roles.intersection(INTERNAL_GLOBAL_READ_ROLES):
		return True
	if doc.project_manager == user:
		return True
	if frappe.db.exists(
		"Project Member",
		{
			"parent": doc.name,
			"parenttype": "Customer Project",
			"user": user,
		},
	):
		return True
	return False
