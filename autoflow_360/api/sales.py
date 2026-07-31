import frappe

from autoflow_360.services.sales_conversion import (
	create_quotation_approval_request,
	create_sales_order_from_quotation,
)


@frappe.whitelist(methods=["POST"])
def request_quotation_approval(quotation_name: str) -> str:
	return create_quotation_approval_request(quotation_name)


@frappe.whitelist(methods=["POST"])
def create_sales_order(quotation_name: str) -> str:
	return create_sales_order_from_quotation(quotation_name)
