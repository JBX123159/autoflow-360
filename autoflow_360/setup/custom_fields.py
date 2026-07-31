import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


PROJECT_LINK_DOCTYPES = (
	"Quotation",
	"Sales Order",
	"Delivery Note",
	"Sales Invoice",
	"Material Request",
	"Request for Quotation",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Payment Entry",
)


def ensure_custom_fields() -> None:
	"""Create or reconcile the project Link field on supported ERPNext documents."""
	fields = {
		doctype: [
			{
				"fieldname": "custom_customer_project",
				"label": "Customer Project",
				"fieldtype": "Link",
				"options": "Customer Project",
				"insert_after": "company",
				"module": "AutoFlow 360",
				"in_standard_filter": 1,
				"no_copy": 1,
			}
		]
		for doctype in PROJECT_LINK_DOCTYPES
	}
	# Task 4 can be migrated before Task 5 introduces Customer Project. A complete
	# fresh install syncs all DocTypes before after_install, so normal validation
	# remains enabled there.
	project_doctype_exists = bool(frappe.db.exists("DocType", "Customer Project"))
	create_custom_fields(
		fields,
		ignore_validate=not project_doctype_exists,
		update=True,
	)
