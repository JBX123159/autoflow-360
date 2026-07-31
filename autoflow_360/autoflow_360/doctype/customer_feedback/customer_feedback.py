import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, now_datetime

from autoflow_360.permissions.portal import (
	can_access_customer_project,
	is_customer_portal_user,
)


DECISIONS = {"客户认可", "重新打样", "拒绝"}
IMMUTABLE_FIELDS = (
	"sample_request",
	"customer",
	"contact",
	"decision",
	"comments",
	"attachment",
	"submitted_by",
	"submitted_at",
)


class CustomerFeedback(Document):
	def before_insert(self) -> None:
		self.submitted_by = frappe.session.user
		self.submitted_at = now_datetime()

	def validate(self) -> None:
		if self.decision not in DECISIONS:
			frappe.throw(_("Invalid feedback decision."))
		if not cstr(self.comments).strip():
			frappe.throw(_("Feedback comments are required."))
		if len(cstr(self.comments)) > 500:
			frappe.throw(_("Feedback comments cannot exceed 500 characters."))

		sample = frappe.get_doc("Sample Request", self.sample_request)
		expected_customer = frappe.db.get_value(
			"Customer Project",
			sample.customer_project,
			"customer",
		)
		if self.customer != expected_customer or self.contact != sample.customer_contact:
			frappe.throw(_("Feedback customer or contact does not match the sample."))

		if is_customer_portal_user() and not can_access_customer_project(
			sample.customer_project
		):
			raise frappe.PermissionError

		previous = self.get_doc_before_save()
		if previous and any(
			previous.get(fieldname) != self.get(fieldname)
			for fieldname in IMMUTABLE_FIELDS
		):
			frappe.throw(_("Submitted customer feedback cannot be changed."))
