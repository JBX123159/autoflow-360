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
	"""Reconcile AutoFlow project, quotation, sales and planning fields."""
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
	fields["Quotation"].append(
		{
			"fieldname": "custom_customer_confirmed",
			"label": "Customer Confirmed",
			"fieldtype": "Check",
			"insert_after": "custom_customer_project",
			"module": "AutoFlow 360",
			"allow_on_submit": 1,
			"default": "0",
			"in_standard_filter": 1,
			"no_copy": 1,
		}
	)
	fields["Quotation Item"] = [
		{
			"fieldname": "custom_floor_rate",
			"label": "Floor Rate",
			"fieldtype": "Currency",
			"insert_after": "discount_percentage",
			"module": "AutoFlow 360",
			"non_negative": 1,
			"default": "0",
		}
	]
	fields["Sales Order"].append(
		{
			"fieldname": "custom_source_quotation",
			"label": "Source Quotation",
			"fieldtype": "Link",
			"options": "Quotation",
			"insert_after": "custom_customer_project",
			"module": "AutoFlow 360",
			"in_standard_filter": 1,
			"no_copy": 1,
			"read_only": 1,
			"unique": 1,
		}
	)
	fields["Material Request"].append(
		{
			"fieldname": "custom_source_sales_order",
			"label": "Source Sales Order",
			"fieldtype": "Link",
			"options": "Sales Order",
			"insert_after": "custom_customer_project",
			"module": "AutoFlow 360",
			"in_standard_filter": 1,
			"no_copy": 1,
			"read_only": 1,
		}
	)
	# Task 4 can be migrated before Task 5 introduces Customer Project. A complete
	# fresh install syncs all DocTypes before after_install, so normal validation
	# remains enabled there.
	project_doctype_exists = bool(frappe.db.exists("DocType", "Customer Project"))
	create_custom_fields(
		fields,
		ignore_validate=not project_doctype_exists,
		update=True,
	)
