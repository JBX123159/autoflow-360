import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


ACTION_STATUSES = {"未开始", "进行中", "已完成"}


class CorrectiveAction(Document):
	def validate(self) -> None:
		if self.status not in ACTION_STATUSES:
			frappe.throw(_("Invalid corrective action status."))
		if self.status == "已完成":
			if not self.evidence:
				frappe.throw(_("Completed corrective actions require evidence."))
			if not self.completed_at:
				self.completed_at = now_datetime()
		else:
			self.completed_at = None
