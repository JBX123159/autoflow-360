import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, now_datetime


EXCEPTION_TYPES = {"供应商延期", "来料质量", "库存差异", "客户投诉", "价格偏差", "单据错误"}
RISK_LEVELS = {"低", "中", "高"}
STATUSES = {"已发现", "已分级", "已分派", "根因分析中", "整改中", "待验证", "已关闭", "已取消"}
TERMINAL_STATUSES = {"已关闭", "已取消"}
IMMUTABLE_SOURCE_FIELDS = (
	"customer_project",
	"reference_doctype",
	"reference_name",
	"raised_by",
	"raised_at",
)
VERIFICATION_FIELDS = (
	"verification_evidence",
	"verified_by",
	"verified_at",
	"cancellation_reason",
)


class BusinessException(Document):
	def before_insert(self) -> None:
		if frappe.session.user == "Guest":
			raise frappe.PermissionError
		self.raised_by = frappe.session.user
		self.raised_at = now_datetime()
		self.status = "已发现"
		self.verification_evidence = None
		self.verified_by = None
		self.verified_at = None
		self.cancellation_reason = None

	def validate(self) -> None:
		if self.exception_type not in EXCEPTION_TYPES:
			frappe.throw(_("Invalid business exception type."))
		if self.risk_level not in RISK_LEVELS:
			frappe.throw(_("Invalid business exception risk level."))
		if self.status not in STATUSES:
			frappe.throw(_("Invalid business exception status."))
		self._validate_reference()
		self._validate_actions()

		previous = self.get_doc_before_save()
		if not previous:
			return
		if previous.status in TERMINAL_STATUSES:
			frappe.throw(_("Terminal business exceptions cannot be changed."))
		for fieldname in IMMUTABLE_SOURCE_FIELDS:
			if self.get(fieldname) != previous.get(fieldname):
				frappe.throw(_("Business exception source audit cannot be changed."))
		if not self.flags.from_exception_workflow:
			if self.status != previous.status:
				frappe.throw(_("Business exception status cannot be changed directly."))
			for fieldname in VERIFICATION_FIELDS:
				if self.get(fieldname) != previous.get(fieldname):
					frappe.throw(_("Verification audit fields cannot be changed directly."))

	def _validate_reference(self) -> None:
		if not self.reference_doctype or not self.reference_name:
			frappe.throw(_("Business exception requires a source document."))
		source = frappe.get_doc(self.reference_doctype, self.reference_name)
		source.check_permission("read")
		if source.doctype == "Customer Project":
			source_project = source.name
		else:
			source_project = cstr(
				getattr(source, "custom_customer_project", None)
				or getattr(source, "customer_project", None)
			).strip()
		if source_project and source_project != self.customer_project:
			frappe.throw(_("Exception source belongs to another customer project."))

	def _validate_actions(self) -> None:
		for action in self.actions:
			action.validate()

	def on_trash(self) -> None:
		frappe.throw(
			_("Business Exception is audit evidence and cannot be deleted."),
			frappe.PermissionError,
		)
