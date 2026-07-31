import frappe
from frappe.utils import cstr


CUSTOMER_PORTAL_ROLE = "AutoFlow Customer Portal"
SUPPLIER_PORTAL_ROLE = "AutoFlow Supplier Portal"
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


def is_supplier_portal_user(user: str | None = None) -> bool:
	user = _current_user(user)
	if not user or user in {"Guest", "Administrator"}:
		return False
	roles = set(frappe.get_roles(user))
	return SUPPLIER_PORTAL_ROLE in roles and not roles.intersection(
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


def get_supplier_names_for_user(user: str | None = None) -> list[str]:
	user = _current_user(user)
	if not user or user == "Guest":
		return []
	if user == "Administrator":
		return frappe.get_all("Supplier", pluck="name")
	if SUPPLIER_PORTAL_ROLE not in frappe.get_roles(user):
		return []
	return frappe.get_all(
		"Portal User",
		filters={"user": user, "parenttype": "Supplier"},
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
	ptype: str | None = None,
):
	user = _current_user(user)
	if not is_customer_portal_user(user):
		return None
	if ptype == "create":
		return True
	return doc.customer in get_customer_names_for_user(user)


def _customer_query(table_name: str, user: str | None = None) -> str:
	user = _current_user(user)
	if not is_customer_portal_user(user):
		return ""
	customers = get_customer_names_for_user(user)
	if not customers:
		return "1=0"
	escaped_customers = ", ".join(
		frappe.db.escape(customer) for customer in customers
	)
	return f"`tab{table_name}`.`customer` in ({escaped_customers})"


def customer_delivery_query(user: str | None = None) -> str:
	return _customer_query("Delivery Note", user)


def customer_receipt_query(user: str | None = None) -> str:
	return _customer_query("Customer Receipt", user)


def customer_delivery_has_permission(
	doc,
	user: str | None = None,
	ptype: str | None = None,
):
	user = _current_user(user)
	if not is_customer_portal_user(user):
		return None
	if ptype != "read":
		return False
	return doc.customer in get_customer_names_for_user(user)


def customer_receipt_has_permission(
	doc,
	user: str | None = None,
	ptype: str | None = None,
):
	return customer_delivery_has_permission(doc, user=user, ptype=ptype)


def _supplier_query(table_name: str, user: str | None = None) -> str:
	user = _current_user(user)
	if not is_supplier_portal_user(user):
		return ""
	suppliers = get_supplier_names_for_user(user)
	if not suppliers:
		return "1=0"
	escaped_suppliers = ", ".join(
		frappe.db.escape(name) for name in suppliers
	)
	return f"`tab{table_name}`.`supplier` in ({escaped_suppliers})"


def supplier_quotation_query(user: str | None = None) -> str:
	return _supplier_query("Supplier Quotation", user)


def purchase_order_query(user: str | None = None) -> str:
	return _supplier_query("Purchase Order", user)


def request_for_quotation_query(user: str | None = None) -> str:
	user = _current_user(user)
	if not is_supplier_portal_user(user):
		return ""
	suppliers = get_supplier_names_for_user(user)
	if not suppliers:
		return "1=0"
	escaped_suppliers = ", ".join(
		frappe.db.escape(name) for name in suppliers
	)
	return (
		"exists (select 1 from `tabRequest for Quotation Supplier` invited "
		"where invited.parent = `tabRequest for Quotation`.name "
		f"and invited.supplier in ({escaped_suppliers}))"
	)


def supplier_item_query(user: str | None = None) -> str:
	user = _current_user(user)
	if not is_supplier_portal_user(user):
		return ""
	suppliers = get_supplier_names_for_user(user)
	if not suppliers:
		return "1=0"
	escaped_suppliers = ", ".join(
		frappe.db.escape(name) for name in suppliers
	)
	return (
		"exists (select 1 from `tabRequest for Quotation Item` rfq_item "
		"inner join `tabRequest for Quotation` rfq "
		"on rfq.name = rfq_item.parent and rfq.docstatus = 1 "
		"inner join `tabRequest for Quotation Supplier` invited "
		"on invited.parent = rfq.name "
		"where rfq_item.item_code = `tabItem`.name "
		f"and invited.supplier in ({escaped_suppliers}))"
	)


def _supplier_rfq_companies(user: str | None = None) -> list[str]:
	user = _current_user(user)
	suppliers = get_supplier_names_for_user(user)
	if not suppliers:
		return []
	return frappe.db.sql(
		"""
		select distinct rfq.company
		from `tabRequest for Quotation` rfq
		inner join `tabRequest for Quotation Supplier` invited
			on invited.parent = rfq.name
		where rfq.docstatus = 1
			and invited.supplier in %(suppliers)s
		""",
		{"suppliers": suppliers},
		pluck=True,
	)


def supplier_account_query(user: str | None = None) -> str:
	user = _current_user(user)
	if not is_supplier_portal_user(user):
		return ""
	companies = _supplier_rfq_companies(user)
	if not companies:
		return "1=0"
	escaped_companies = ", ".join(
		frappe.db.escape(company) for company in companies
	)
	return (
		"`tabAccount`.`account_type` = 'Payable' "
		f"and `tabAccount`.`company` in ({escaped_companies})"
	)


def supplier_rfq_has_permission(
	doc,
	user: str | None = None,
	ptype: str | None = None,
):
	user = _current_user(user)
	if not is_supplier_portal_user(user):
		return None
	if ptype != "read":
		return False
	suppliers = get_supplier_names_for_user(user)
	if not suppliers:
		return False
	return bool(
		frappe.db.exists(
			"Request for Quotation Supplier",
			{
				"parent": doc.name,
				"parenttype": "Request for Quotation",
				"supplier": ["in", suppliers],
			},
		)
	)


def supplier_item_has_permission(
	doc,
	user: str | None = None,
	ptype: str | None = None,
):
	user = _current_user(user)
	if not is_supplier_portal_user(user):
		return None
	if ptype != "read":
		return False
	suppliers = get_supplier_names_for_user(user)
	if not suppliers:
		return False
	return bool(
		frappe.db.sql(
			"""
			select 1
			from `tabRequest for Quotation Item` rfq_item
			inner join `tabRequest for Quotation` rfq
				on rfq.name = rfq_item.parent and rfq.docstatus = 1
			inner join `tabRequest for Quotation Supplier` invited
				on invited.parent = rfq.name
			where rfq_item.item_code = %(item_code)s
				and invited.supplier in %(suppliers)s
			limit 1
			""",
			{"item_code": doc.name, "suppliers": suppliers},
		)
	)


def supplier_account_has_permission(
	doc,
	user: str | None = None,
	ptype: str | None = None,
):
	user = _current_user(user)
	if not is_supplier_portal_user(user):
		return None
	if ptype not in {"read", "select"}:
		return False
	return bool(
		doc.account_type == "Payable"
		and doc.company in _supplier_rfq_companies(user)
	)


def supplier_document_has_permission(
	doc,
	user: str | None = None,
	ptype: str | None = None,
):
	user = _current_user(user)
	if not is_supplier_portal_user(user):
		return None
	if ptype == "read":
		return doc.supplier in get_supplier_names_for_user(user)
	return False
