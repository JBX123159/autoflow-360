import frappe
from frappe.utils import cstr

from autoflow_360.services.material_planning import create_material_request


@frappe.whitelist(methods=["POST"])
def plan_sales_order(sales_order_name: str) -> dict[str, str | None]:
	sales_order_name = cstr(sales_order_name).strip()
	request_name = create_material_request(sales_order_name)
	plan_name = frappe.db.get_value(
		"Project Material Plan",
		{"sales_order": sales_order_name},
		"name",
	)
	if plan_name and not frappe.has_permission(
		"Project Material Plan",
		"read",
		plan_name,
	):
		plan_name = None
	return {
		"material_request": request_name,
		"material_plan": plan_name,
	}
