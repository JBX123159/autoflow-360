import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


ANALYSIS_TYPES = {
	"风险摘要",
	"下一步行动",
	"管理周报",
	"根因草稿",
	"供应商报价总结",
	"结项复盘",
}
STATUSES = {"处理中", "成功", "降级", "失败"}
TERMINAL_STATUSES = {"成功", "降级", "失败"}
IMMUTABLE_AUDIT_FIELDS = (
	"customer_project",
	"analysis_type",
	"requested_by",
	"requested_at",
	"provider",
	"model",
	"prompt_version",
	"input_hash",
	"status",
	"output_json",
	"display_text",
	"latency_ms",
	"error_code",
	"error_message",
)
FEEDBACK_FIELDS = ("adopted", "user_revision", "user_feedback")


def _source_snapshot(doc) -> tuple[tuple[str, str, str], ...]:
	return tuple(
		(
			source.reference_doctype,
			source.reference_name,
			source.label,
		)
		for source in doc.sources
	)


class AIAnalysis(Document):
	def before_insert(self) -> None:
		if frappe.session.user == "Guest" or not self.flags.from_ai_service:
			raise frappe.PermissionError
		self.requested_by = frappe.session.user
		self.requested_at = now_datetime()
		self.status = "处理中"
		self.output_json = None
		self.display_text = None
		self.latency_ms = 0
		self.error_code = None
		self.error_message = None
		self.set("sources", [])

	def validate(self) -> None:
		if self.analysis_type not in ANALYSIS_TYPES:
			frappe.throw(_("Invalid AI analysis type."))
		if self.status not in STATUSES:
			frappe.throw(_("Invalid AI analysis status."))
		project = frappe.get_doc("Customer Project", self.customer_project)
		project.check_permission("read")

		previous = self.get_doc_before_save()
		if not previous:
			if not self.flags.from_ai_service or self.status != "处理中":
				raise frappe.PermissionError
			return

		if self.flags.from_ai_service:
			self._validate_service_update(previous)
			return

		for fieldname in IMMUTABLE_AUDIT_FIELDS:
			if self.get(fieldname) != previous.get(fieldname):
				frappe.throw(_("AI audit fields cannot be changed directly."))
		if _source_snapshot(self) != _source_snapshot(previous):
			frappe.throw(_("AI source references cannot be changed directly."))
		if any(self.get(field) != previous.get(field) for field in FEEDBACK_FIELDS):
			if frappe.session.user != self.requested_by:
				frappe.throw(
					_("Only the requester can review this AI analysis."),
					frappe.PermissionError,
				)

	def _validate_service_update(self, previous) -> None:
		if previous.status != "处理中" or self.status not in TERMINAL_STATUSES:
			frappe.throw(_("Invalid AI service status transition."))
		if self.status == "成功":
			if not self.output_json or not self.display_text or not self.sources:
				frappe.throw(_("Successful AI analysis requires output and sources."))
			if self.error_code or self.error_message:
				frappe.throw(_("Successful AI analysis cannot contain an error."))
		else:
			if not self.error_code or not self.error_message:
				frappe.throw(_("Degraded AI analysis requires a safe error code."))
			if self.sources:
				frappe.throw(_("Degraded AI analysis cannot retain unverified sources."))

	def on_trash(self) -> None:
		frappe.throw(
			_("AI Analysis is audit evidence and cannot be deleted."),
			frappe.PermissionError,
		)
