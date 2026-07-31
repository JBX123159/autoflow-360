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
	"""Reconcile AutoFlow project, sales, planning and procurement fields."""
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
	fields["Request for Quotation"].append(
		{
			"fieldname": "custom_source_material_request",
			"label": "Source Material Request",
			"fieldtype": "Link",
			"options": "Material Request",
			"insert_after": "custom_customer_project",
			"module": "AutoFlow 360",
			"in_standard_filter": 1,
			"no_copy": 1,
			"read_only": 1,
		}
	)
	fields["Supplier Quotation"].append(
		{
			"fieldname": "custom_source_rfq",
			"label": "Source Request for Quotation",
			"fieldtype": "Link",
			"options": "Request for Quotation",
			"insert_after": "custom_customer_project",
			"module": "AutoFlow 360",
			"in_standard_filter": 1,
			"no_copy": 1,
			"read_only": 1,
		}
	)
	fields["Purchase Order"].extend(
		[
			{
				"fieldname": "custom_source_supplier_quotation",
				"label": "Source Supplier Quotation",
				"fieldtype": "Link",
				"options": "Supplier Quotation",
				"insert_after": "custom_customer_project",
				"module": "AutoFlow 360",
				"in_standard_filter": 1,
				"no_copy": 1,
				"read_only": 1,
			},
			{
				"fieldname": "custom_supplier_eta",
				"label": "Supplier ETA",
				"fieldtype": "Date",
				"insert_after": "custom_source_supplier_quotation",
				"module": "AutoFlow 360",
				"allow_on_submit": 1,
				"in_standard_filter": 1,
				"no_copy": 1,
				"read_only": 1,
			},
		]
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
