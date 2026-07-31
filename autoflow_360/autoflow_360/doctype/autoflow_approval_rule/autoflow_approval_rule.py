import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


ALLOWED_APPROVAL_DOCTYPES = (
	"Sample Request",
	"Quotation",
	"Purchase Order",
	"Delivery Date Change",
	"Business Exception",
	"Customer Project",
	"Payment Entry",
)
RISK_LEVELS = {"低": 1, "中": 2, "高": 3}


class AutoFlowApprovalRule(Document):
	def validate(self) -> None:
		if self.document_type not in ALLOWED_APPROVAL_DOCTYPES:
			frappe.throw(_("Unsupported approval document type."))
		if self.role in {"All", "Guest"}:
			frappe.throw(_("Approval rules require an attributable desk role."))
		if flt(self.amount_limit) < 0:
			frappe.throw(_("Amount limit cannot be negative."))
		if not 0 <= flt(self.discount_limit) <= 100:
			frappe.throw(_("Discount limit must be between 0 and 100."))
		if self.risk_level not in RISK_LEVELS:
			frappe.throw(_("Invalid approval risk level."))
