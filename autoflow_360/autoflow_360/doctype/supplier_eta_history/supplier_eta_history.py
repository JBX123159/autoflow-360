import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, getdate, now_datetime


class SupplierETAHistory(Document):
	def before_insert(self) -> None:
		if not self.flags.from_supplier_eta_service:
			frappe.throw(
				_("Supplier ETA history can only be created through the ETA service."),
				frappe.PermissionError,
			)

		order = frappe.get_doc("Purchase Order", self.purchase_order)
		if order.docstatus != 1:
			frappe.throw(_("Supplier ETA requires a submitted Purchase Order."))
		if not cstr(order.custom_customer_project).strip():
			frappe.throw(_("Purchase Order must be linked to a customer project."))

		self.company = order.company
		self.supplier = order.supplier
		self.customer_project = order.custom_customer_project
		self.previous_eta = order.custom_supplier_eta or None
		self.changed_by = frappe.session.user
		self.changed_at = now_datetime()

	def validate(self) -> None:
		previous = self.get_doc_before_save()
		if previous:
			frappe.throw(_("Supplier ETA history cannot be changed."))

		reason = cstr(self.change_reason).strip()
		if not reason:
			frappe.throw(_("A supplier ETA change reason is required."))
		self.change_reason = reason

		order_date = frappe.db.get_value(
			"Purchase Order",
			self.purchase_order,
			"transaction_date",
		)
		if not self.new_eta:
			frappe.throw(_("A new supplier ETA is required."))
		if order_date and getdate(self.new_eta) < getdate(order_date):
			frappe.throw(_("Supplier ETA cannot be before the Purchase Order date."))
		if self.previous_eta and getdate(self.new_eta) == getdate(self.previous_eta):
			frappe.throw(_("Supplier ETA must change before history is recorded."))
