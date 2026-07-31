import frappe

from autoflow_360.services.deal_conversion import create_project_from_deal


@frappe.whitelist(methods=["POST"])
def convert_deal(
	deal_name: str,
	company: str,
	customer: str,
	product_family: str,
	delivery_date: str,
) -> str:
	return create_project_from_deal(
		deal_name,
		company,
		customer,
		product_family,
		delivery_date,
	)
