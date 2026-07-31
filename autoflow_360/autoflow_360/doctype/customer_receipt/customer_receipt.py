import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, now_datetime

from autoflow_360.permissions.portal import (
	get_customer_names_for_user,
	is_customer_portal_user,
)


class CustomerReceipt(Document):
	def before_insert(self) -> None:
		if not self.flags.from_customer_receipt_service:
			frappe.throw(
				_("Customer receipt can only be created through the receipt service."),
				frappe.PermissionError,
			)
		if not is_customer_portal_user():
			raise frappe.PermissionError

		delivery = frappe.get_doc("Delivery Note", self.delivery_note)
		if delivery.docstatus != 1:
			frappe.throw(_("Customer receipt requires a submitted Delivery Note."))
		if not cstr(delivery.custom_customer_project).strip():
			frappe.throw(_("Delivery Note must be linked to a customer project."))
		if delivery.customer not in get_customer_names_for_user():
			raise frappe.PermissionError

		self.customer = delivery.customer
		self.customer_project = delivery.custom_customer_project
		self.portal_user = frappe.session.user
		self.received_at = now_datetime()
		self.received_by = self._linked_contact(delivery.customer)

	def _linked_contact(self, customer: str) -> str | None:
		contact = frappe.db.get_value(
			"Contact",
			{"user": frappe.session.user},
			"name",
		)
		if not contact:
			return None
		if not frappe.db.exists(
			"Dynamic Link",
			{
				"parent": contact,
				"parenttype": "Contact",
				"link_doctype": "Customer",
				"link_name": customer,
			},
		):
			return None
		return contact

	def validate(self) -> None:
		if self.get_doc_before_save():
			frappe.throw(_("Customer receipt cannot be changed."))
		if not self.delivery_note:
			frappe.throw(_("Delivery Note is required."))
		if self.proof_file and not frappe.db.exists(
			"File",
			{
				"file_url": self.proof_file,
				"owner": frappe.session.user,
				"is_private": 1,
			},
		):
			raise frappe.PermissionError
