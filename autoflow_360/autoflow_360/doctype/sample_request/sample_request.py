import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, flt


FINAL_FEEDBACK_STATUSES = {"客户认可", "重新打样", "拒绝"}
DISPATCHED_STATUSES = {"已发出", "等待反馈", *FINAL_FEEDBACK_STATUSES}


class SampleRequest(Document):
	def before_insert(self) -> None:
		if not self.round_number:
			self.round_number = 1

	def validate(self) -> None:
		self._validate_round_chain()
		self._validate_items()
		self._validate_inspection()
		self._validate_dispatch_fields()
		self._validate_feedback_link()

	def _validate_round_chain(self) -> None:
		round_number = int(self.round_number or 0)
		if round_number < 1:
			frappe.throw(_("Sample round number must be at least 1."))

		previous = self.get_doc_before_save()
		if previous and (
			previous.customer_project != self.customer_project
			or int(previous.round_number or 0) != round_number
			or previous.previous_sample_request != self.previous_sample_request
		):
			frappe.throw(_("Sample project and round chain cannot be changed."))

		if not self.previous_sample_request:
			if round_number != 1:
				frappe.throw(_("The first sample request must use round 1."))
			return

		parent = frappe.get_doc("Sample Request", self.previous_sample_request)
		if parent.customer_project != self.customer_project:
			frappe.throw(_("Resample must belong to the same customer project."))
		if round_number != int(parent.round_number or 0) + 1:
			frappe.throw(_("Resample round must follow the previous round."))

	def _validate_items(self) -> None:
		items = list(self.items or [])
		if not items:
			frappe.throw(_("At least one sample item is required."))

		for row in items:
			if flt(row.quantity) <= 0:
				frappe.throw(_("Sample item quantity must be greater than zero."))
			if not all(
				(
					cstr(row.item_code).strip(),
					cstr(row.uom).strip(),
					cstr(row.specification).strip(),
				)
			):
				frappe.throw(
					_("Every sample item requires an item, UOM and specification.")
				)

	def _validate_inspection(self) -> None:
		if self.inspection_status != "通过":
			return
		if any(item.inspection_result != "通过" for item in self.items):
			frappe.throw(
				_("Every sample item must pass before overall inspection can pass.")
			)

	def _validate_dispatch_fields(self) -> None:
		if self.status not in DISPATCHED_STATUSES:
			return
		if self.inspection_status != "通过":
			frappe.throw(_("Dispatched samples must have passed inspection."))
		if not all(
			(
				cstr(self.carrier).strip(),
				cstr(self.tracking_number).strip(),
				self.dispatch_time,
			)
		):
			frappe.throw(
				_("Carrier, tracking number and dispatch time are required.")
			)

	def _validate_feedback_link(self) -> None:
		if self.status in FINAL_FEEDBACK_STATUSES and not self.feedback:
			frappe.throw(_("A final feedback status requires customer feedback."))
		if not self.feedback:
			return
		linked_sample = frappe.db.get_value(
			"Customer Feedback",
			self.feedback,
			"sample_request",
		)
		if linked_sample and linked_sample != self.name:
			frappe.throw(_("Customer feedback belongs to another sample request."))
