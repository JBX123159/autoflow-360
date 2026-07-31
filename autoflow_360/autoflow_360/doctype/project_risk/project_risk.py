import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, now_datetime


ALLOWED_RISK_LEVELS = {"低", "中", "高"}
ALLOWED_STATUSES = {"已发现", "处理中", "待验证", "已关闭"}
USER_TRANSITIONS = {
	"已发现": {"处理中"},
	"处理中": {"待验证"},
	"待验证": {"处理中", "已关闭"},
	"已关闭": set(),
}
ENGINE_FIELDS = (
	"customer_project",
	"risk_type",
	"risk_level",
	"title",
	"description",
	"rule_code",
	"reference_doctype",
	"reference_name",
	"rule_inputs",
	"deduplication_key",
)


class ProjectRisk(Document):
	def before_insert(self) -> None:
		if not self.flags.from_risk_engine:
			frappe.throw(
				_("Project Risk can only be created by the risk engine."),
				frappe.PermissionError,
			)

	def validate(self) -> None:
		if self.risk_level not in ALLOWED_RISK_LEVELS:
			frappe.throw(_("Invalid project risk level."))
		if self.status not in ALLOWED_STATUSES:
			frappe.throw(_("Invalid project risk status."))
		if not all(cstr(self.get(fieldname)).strip() for fieldname in ENGINE_FIELDS):
			frappe.throw(_("Project Risk requires complete rule evidence."))
		try:
			inputs = frappe.parse_json(self.rule_inputs)
		except (TypeError, ValueError):
			frappe.throw(_("Project Risk rule inputs must be valid JSON."))
		if not isinstance(inputs, dict):
			frappe.throw(_("Project Risk rule inputs must be a JSON object."))

		previous = self.get_doc_before_save()
		if not previous:
			if self.status != "已发现":
				frappe.throw(_("New project risks must start as discovered."))
			return
		if not self.flags.from_risk_engine:
			for fieldname in ENGINE_FIELDS:
				if self.get(fieldname) != previous.get(fieldname):
					frappe.throw(
						_("Risk engine evidence cannot be changed manually.")
					)
			if self.status != previous.status:
				if self.status not in USER_TRANSITIONS.get(previous.status, set()):
					frappe.throw(_("Invalid project risk status transition."))
				if self.status == "已关闭":
					self.resolved_at = now_datetime()
					self.verified_by = frappe.session.user

	def on_trash(self) -> None:
		if not self.flags.from_risk_engine:
			frappe.throw(
				_("Project Risk records are audit evidence and cannot be deleted."),
				frappe.PermissionError,
			)
