import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, flt


IMMUTABLE_SOURCE_FIELDS = (
	"sales_order",
	"customer_project",
	"company",
)
NON_NEGATIVE_ITEM_FIELDS = (
	"ordered_qty",
	"reserved_qty",
	"incoming_qty",
	"safety_stock",
	"required_qty",
)


class ProjectMaterialPlan(Document):
	def validate(self) -> None:
		self._validate_source()
		self._validate_items()
		self._validate_request_link()

	def _validate_source(self) -> None:
		previous = self.get_doc_before_save()
		if previous:
			for fieldname in IMMUTABLE_SOURCE_FIELDS:
				if self.get(fieldname) != previous.get(fieldname):
					frappe.throw(
						_("Material plan source field {0} cannot be changed.").format(
							fieldname
						)
					)

		order = frappe.db.get_value(
			"Sales Order",
			self.sales_order,
			["company", "custom_customer_project"],
			as_dict=True,
		)
		if not order:
			frappe.throw(_("Sales Order {0} does not exist.").format(self.sales_order))
		if order.company != self.company:
			frappe.throw(_("Material plan company must match its Sales Order."))
		if order.custom_customer_project != self.customer_project:
			frappe.throw(_("Material plan project must match its Sales Order."))

	def _validate_items(self) -> None:
		seen_positions: set[tuple[str, str]] = set()
		for row in list(self.items or []):
			position = (
				cstr(row.item_code).strip(),
				cstr(row.warehouse).strip(),
			)
			if not all(position):
				frappe.throw(_("Every material plan row requires an item and warehouse."))
			if position in seen_positions:
				frappe.throw(
					_("Item {0} is listed more than once for warehouse {1}.").format(
						*position
					)
				)
			seen_positions.add(position)

			for fieldname in NON_NEGATIVE_ITEM_FIELDS:
				if flt(row.get(fieldname)) < 0:
					frappe.throw(
						_("Material plan field {0} cannot be negative.").format(
							fieldname
						)
					)

	def _validate_request_link(self) -> None:
		if self.status == "已生成物料需求" and not self.material_request:
			frappe.throw(_("A generated material plan requires a Material Request."))
		if not self.material_request:
			return

		request = frappe.db.get_value(
			"Material Request",
			self.material_request,
			["custom_source_sales_order", "docstatus"],
			as_dict=True,
		)
		if not request or request.docstatus == 2:
			frappe.throw(_("Material plan cannot link a cancelled Material Request."))
		if request.custom_source_sales_order != self.sales_order:
			frappe.throw(_("Material Request source must match the material plan."))
