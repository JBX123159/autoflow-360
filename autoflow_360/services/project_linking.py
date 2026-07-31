import frappe
from frappe import _
from frappe.utils import cstr


ROW_SOURCE_FIELDS = {
	"Purchase Receipt": (("purchase_order", "Purchase Order"),),
	"Purchase Invoice": (
		("purchase_order", "Purchase Order"),
		("purchase_receipt", "Purchase Receipt"),
	),
	"Delivery Note": (("against_sales_order", "Sales Order"),),
	"Sales Invoice": (("sales_order", "Sales Order"),),
}


def _project_from_source(source_doctype: str, source_name: str) -> str | None:
	if not frappe.db.exists(source_doctype, source_name):
		frappe.throw(
			_("Source {0} {1} no longer exists.").format(
				source_doctype,
				source_name,
			)
		)
	return cstr(
		frappe.db.get_value(
			source_doctype,
			source_name,
			"custom_customer_project",
		)
	).strip()


def _row_source_projects(doc) -> set[str]:
	projects: set[str] = set()
	for fieldname, source_doctype in ROW_SOURCE_FIELDS.get(doc.doctype, ()):
		for row in list(doc.get("items") or []):
			source_name = cstr(row.get(fieldname)).strip()
			if not source_name:
				continue
			project = _project_from_source(source_doctype, source_name)
			if project:
				projects.add(project)
	return projects


def _payment_source_projects(doc) -> set[str]:
	projects: set[str] = set()
	for row in list(doc.get("references") or []):
		if row.reference_doctype not in {"Sales Invoice", "Purchase Invoice"}:
			continue
		project = _project_from_source(
			row.reference_doctype,
			row.reference_name,
		)
		if project:
			projects.add(project)
	return projects


def propagate_project_link(doc, method: str | None = None) -> None:
	projects = (
		_payment_source_projects(doc)
		if doc.doctype == "Payment Entry"
		else _row_source_projects(doc)
	)
	current_project = cstr(doc.get("custom_customer_project")).strip()
	if current_project:
		projects.add(current_project)
	if len(projects) > 1:
		frappe.throw(_("One document cannot combine multiple customer projects."))
	if projects:
		doc.custom_customer_project = projects.pop()
