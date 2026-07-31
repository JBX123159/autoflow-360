import frappe

from autoflow_360.services.deal_conversion import create_project_from_deal
from autoflow_360.services.project_closure import (
	close_project,
	create_project_closure_request,
	get_closure_status,
)


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


@frappe.whitelist(methods=["GET"])
def get_project_closure_status(project_name: str) -> dict:
	return get_closure_status(project_name)


@frappe.whitelist(methods=["POST"])
def request_project_closure(project_name: str) -> str:
	return create_project_closure_request(project_name)


@frappe.whitelist(methods=["POST"])
def finalize_project_closure(project_name: str, closure_summary: str) -> str:
	return close_project(project_name, closure_summary)
