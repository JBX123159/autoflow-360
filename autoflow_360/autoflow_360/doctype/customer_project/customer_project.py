import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, flt, getdate, now_datetime

from autoflow_360.services.project_status import validate_stage_transition


class CustomerProject(Document):
	def before_insert(self) -> None:
		if not self.last_meaningful_activity:
			self.last_meaningful_activity = now_datetime()
		if not self.data_classification:
			self.data_classification = "内部"

	def validate(self) -> None:
		self._validate_dates()
		self._validate_members()
		self._validate_numeric_boundaries()
		previous = self.get_doc_before_save()
		validate_stage_transition(
			previous.stage if previous else None,
			self.stage,
		)
		self._validate_closure_guard(previous)
		self._validate_side_stage_reason()

	def _validate_closure_guard(self, previous) -> None:
		if not previous:
			return
		if (
			previous.stage != "已结项"
			and self.stage == "已结项"
			and not self.flags.from_project_closure_service
		):
			frappe.throw(_("Customer Project cannot be closed directly."))
		if (
			previous.stage == "已结项"
			and cstr(self.closure_summary).strip()
			!= cstr(previous.closure_summary).strip()
		):
			frappe.throw(_("Closure summary cannot be changed after closure."))

	def _validate_dates(self) -> None:
		if not self.target_award_date or not self.customer_delivery_date:
			return
		if getdate(self.target_award_date) > getdate(self.customer_delivery_date):
			frappe.throw(
				_("Target award date cannot be after customer delivery date.")
			)

	def _validate_members(self) -> None:
		members = list(self.project_members or [])
		if not members:
			frappe.throw(_("At least one project member is required."))

		seen_users: set[str] = set()
		for row in members:
			user = cstr(row.user).strip()
			responsibility = cstr(row.responsibility).strip()
			if not user or not responsibility:
				frappe.throw(
					_("Every project member requires a user and responsibility.")
				)
			if user in seen_users:
				frappe.throw(
					_("Project member {0} is listed more than once.").format(user)
				)
			seen_users.add(user)

		if self.project_manager not in seen_users:
			frappe.throw(_("Project manager must also be a project member."))

	def _validate_numeric_boundaries(self) -> None:
		if flt(self.expected_amount) < 0:
			frappe.throw(_("Expected amount cannot be negative."))
		probability = flt(self.probability)
		if probability < 0 or probability > 100:
			frappe.throw(_("Probability must be between 0 and 100."))

	def _validate_side_stage_reason(self) -> None:
		reasons = {
			"暂停": self.pause_reason,
			"失败": self.failure_reason,
			"取消": self.cancellation_reason,
		}
		if self.stage in reasons and not cstr(reasons[self.stage]).strip():
			frappe.throw(
				_("A reason is required for stage {0}.").format(self.stage)
			)
