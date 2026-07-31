import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, now_datetime

from autoflow_360.autoflow_360.doctype.autoflow_approval_rule.autoflow_approval_rule import (
	ALLOWED_APPROVAL_DOCTYPES,
)


PENDING_STATUS = "待审批"
DECISION_STATUSES = {"已通过", "已退回", "已拒绝"}
IMMUTABLE_REQUEST_FIELDS = (
	"reference_doctype",
	"reference_name",
	"company",
	"approval_type",
	"requested_by",
	"requested_at",
	"request_snapshot",
)


class AutoFlowApprovalRequest(Document):
	def before_insert(self) -> None:
		from autoflow_360.services.sales_conversion import build_approval_snapshot

		if self.reference_doctype not in ALLOWED_APPROVAL_DOCTYPES:
			frappe.throw(_("Unsupported approval document type."))
		if not cstr(self.reference_name).strip():
			frappe.throw(_("Approval reference is required."))

		source = frappe.get_doc(self.reference_doctype, self.reference_name)
		source.check_permission("read")
		company = cstr(getattr(source, "company", None)).strip()
		if not company:
			frappe.throw(_("The approval reference must belong to a company."))

		self.company = company
		self.requested_by = frappe.session.user
		self.requested_at = now_datetime()
		self.status = PENDING_STATUS
		self.approver = None
		self.decision_at = None
		self.decision_reason = None
		self.request_snapshot = json.dumps(
			build_approval_snapshot(source),
			ensure_ascii=False,
			sort_keys=True,
			separators=(",", ":"),
			default=str,
		)

	def validate(self) -> None:
		previous = self.get_doc_before_save()
		if self.status == PENDING_STATUS and self.docstatus != 0:
			frappe.throw(_("A pending approval request must remain a draft."))
		if self.status in DECISION_STATUSES and self.docstatus != 1:
			frappe.throw(_("A final approval decision must be submitted."))
		if not previous:
			if self.status != PENDING_STATUS:
				frappe.throw(_("A new approval request must start as pending."))
			return

		for fieldname in IMMUTABLE_REQUEST_FIELDS:
			if self.get(fieldname) != previous.get(fieldname):
				frappe.throw(
					_("Approval request field {0} cannot be changed.").format(
						fieldname
					)
				)

		if self.status == previous.status:
			if self.status == PENDING_STATUS and (
				self.approver or self.decision_at
			):
				frappe.throw(_("Pending requests cannot contain decision audit data."))
			return

		if previous.status != PENDING_STATUS or self.status not in DECISION_STATUSES:
			frappe.throw(_("Invalid approval request status transition."))
		self._authorize_decision()

	def _authorize_decision(self) -> None:
		from autoflow_360.services.sales_conversion import (
			approval_request_has_authority,
		)

		acting_user = frappe.session.user
		if acting_user == "Guest":
			raise frappe.PermissionError
		if acting_user == self.requested_by:
			frappe.throw(_("Requester cannot approve their own request."), frappe.PermissionError)
		if not approval_request_has_authority(self, acting_user):
			frappe.throw(_("Current user is outside the configured approval authority."), frappe.PermissionError)

		self.approver = acting_user
		self.decision_at = now_datetime()
		self.decision_reason = cstr(self.decision_reason).strip() or None

	def _decide(self, target_status: str, decision_reason: str | None = None) -> str:
		self.check_permission("write")
		self.reload()
		if self.docstatus != 0 or self.status != PENDING_STATUS:
			frappe.throw(_("Only a pending approval request can be decided."))
		if target_status not in DECISION_STATUSES:
			frappe.throw(_("Invalid approval decision."))

		self.status = target_status
		self.decision_reason = cstr(decision_reason).strip() or None
		self.submit()
		self.add_comment("Workflow", target_status)
		return self.name

	@frappe.whitelist(methods=["POST"])
	def approve(self, decision_reason: str | None = None) -> str:
		return self._decide("已通过", decision_reason)

	@frappe.whitelist(methods=["POST"])
	def return_request(self, decision_reason: str | None = None) -> str:
		return self._decide("已退回", decision_reason)

	@frappe.whitelist(methods=["POST"])
	def reject(self, decision_reason: str | None = None) -> str:
		return self._decide("已拒绝", decision_reason)
