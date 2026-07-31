import frappe
from frappe import _
from frappe.utils import cstr

from autoflow_360.permissions.portal import can_access_customer_project
from autoflow_360.services.procurement import (
	submit_supplier_quote as submit_quote,
	update_supplier_eta,
)
from autoflow_360.services.delivery import confirm_customer_receipt
from autoflow_360.services.sample_workflow import record_customer_feedback


def _validate_owned_attachment(attachment: str | None) -> str | None:
	attachment = cstr(attachment).strip()
	if not attachment:
		return None
	if not frappe.db.exists(
		"File",
		{"file_url": attachment, "owner": frappe.session.user},
	):
		frappe.throw(_("Attachment must be a file uploaded by the current user."))
	return attachment


@frappe.whitelist(methods=["POST"])
def submit_sample_feedback(
	sample_name: str,
	decision: str,
	comments: str,
	attachment: str | None = None,
) -> str:
	normalized_sample_name = cstr(sample_name).strip()
	if not normalized_sample_name:
		frappe.throw(_("Sample request is required."))
	sample = frappe.get_doc("Sample Request", normalized_sample_name)
	if not can_access_customer_project(sample.customer_project):
		raise frappe.PermissionError
	return record_customer_feedback(
		sample.name,
		decision,
		comments,
		_validate_owned_attachment(attachment),
	)


@frappe.whitelist(methods=["POST"])
def submit_supplier_quote(
	rfq_name: str,
	items: list[dict] | str,
	valid_till: str,
) -> str:
	parsed_items = frappe.parse_json(items) if isinstance(items, str) else items
	return submit_quote(rfq_name, parsed_items, valid_till)


@frappe.whitelist(methods=["POST"])
def confirm_supplier_eta(
	purchase_order_name: str,
	eta: str,
	reason: str,
) -> str:
	return update_supplier_eta(purchase_order_name, eta, reason)


@frappe.whitelist(methods=["POST"])
def confirm_delivery_receipt(
	delivery_note_name: str,
	proof_file: str | None = None,
) -> str:
	return confirm_customer_receipt(delivery_note_name, proof_file)
