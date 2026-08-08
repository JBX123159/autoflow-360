import frappe


PROJECT_FIELDS = (
	"name",
	"stage",
	"customer_delivery_date",
	"overall_risk_level",
	"next_action",
	"next_action_owner",
	"next_action_due_date",
)
RELATED_DOCTYPES = {
	"Project Risk": (
		"name",
		"risk_level",
		"title",
		"description",
		"status",
		"due_date",
		"reference_doctype",
		"reference_name",
	),
	"Business Exception": (
		"name",
		"exception_type",
		"risk_level",
		"status",
		"description",
		"impact",
		"target_close_date",
	),
	"Sample Request": (
		"name",
		"status",
		"inspection_status",
		"required_date",
		"dispatch_time",
	),
}
STANDARD_DOCTYPES = {
	"Quotation": ("name", "status", "transaction_date", "valid_till", "grand_total"),
	"Sales Order": ("name", "status", "transaction_date", "delivery_date", "grand_total"),
	"Purchase Order": ("name", "status", "transaction_date", "schedule_date", "grand_total"),
	"Delivery Note": ("name", "status", "posting_date", "grand_total"),
	"Sales Invoice": ("name", "status", "posting_date", "due_date", "outstanding_amount"),
	"Payment Entry": ("name", "status", "posting_date", "paid_amount"),
}


def _rows_for_project(
	doctype: str,
	project_field: str,
	project_name: str,
	fields: tuple[str, ...],
) -> list[dict]:
	if not frappe.has_permission(doctype, "read"):
		return []
	rows = frappe.get_list(
		doctype,
		filters={project_field: project_name},
		fields=list(fields),
		order_by="name asc",
		limit_page_length=100,
	)
	return [dict(row) for row in rows]


def build_project_context(
	project_name: str,
) -> tuple[dict, set[tuple[str, str]]]:
	project = frappe.get_doc("Customer Project", project_name)
	project.check_permission("read")
	allowed_sources: set[tuple[str, str]] = {("Customer Project", project.name)}
	context = {
		"project": {field: project.get(field) for field in PROJECT_FIELDS},
		"risks": [],
		"exceptions": [],
		"samples": [],
		"business_documents": {},
	}

	context_keys = {
		"Project Risk": "risks",
		"Business Exception": "exceptions",
		"Sample Request": "samples",
	}
	for doctype, fields in RELATED_DOCTYPES.items():
		rows = _rows_for_project(
			doctype,
			"customer_project",
			project.name,
			fields,
		)
		context[context_keys[doctype]] = rows
		allowed_sources.update((doctype, row["name"]) for row in rows)

	for doctype, fields in STANDARD_DOCTYPES.items():
		rows = _rows_for_project(
			doctype,
			"custom_customer_project",
			project.name,
			fields,
		)
		context["business_documents"][doctype] = rows
		allowed_sources.update((doctype, row["name"]) for row in rows)

	return context, allowed_sources
