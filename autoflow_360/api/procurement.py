import frappe

from autoflow_360.services.procurement import (
	make_project_rfq,
	make_purchase_order_from_supplier_quote,
	update_supplier_eta,
)


@frappe.whitelist(methods=["POST"])
def create_rfq(material_request_name: str, suppliers: list[str]) -> str:
	return make_project_rfq(material_request_name, suppliers)


@frappe.whitelist(methods=["POST"])
def create_purchase_order(supplier_quotation_name: str) -> str:
	return make_purchase_order_from_supplier_quote(supplier_quotation_name)


@frappe.whitelist(methods=["POST"])
def set_supplier_eta(purchase_order_name: str, eta: str, reason: str) -> str:
	return update_supplier_eta(purchase_order_name, eta, reason)
