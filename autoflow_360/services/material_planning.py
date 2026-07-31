import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate, now_datetime, nowdate
from frappe.utils.synchronization import filelock

from autoflow_360.services.idempotency import make_idempotency_key


BLOCKED_ORDER_STATUSES = {"On Hold", "Closed"}


@dataclass(frozen=True, slots=True)
class MaterialGap:
	item_code: str
	warehouse: str
	stock_uom: str
	ordered_qty: float
	actual_qty: float
	reserved_qty: float
	available_qty: float
	incoming_qty: float
	safety_stock: float
	required_qty: float
	required_by: str


def _normalized_quantity(value: Any) -> float:
	quantity = round(flt(value), 6)
	return 0.0 if abs(quantity) < 0.000001 else quantity


def _validate_order(order) -> None:
	if order.docstatus != 1:
		frappe.throw(_("Sales Order must be submitted before material planning."))
	if cstr(order.status).strip() in BLOCKED_ORDER_STATUSES:
		frappe.throw(
			_("Sales Order status {0} does not allow material planning.").format(
				order.status
			)
		)
	if not cstr(order.custom_customer_project).strip():
		frappe.throw(_("Sales Order must be linked to a customer project."))


def _group_open_stock_demand(order) -> list[dict[str, Any]]:
	positions: dict[tuple[str, str], dict[str, Any]] = {}
	item_cache: dict[str, dict[str, Any]] = {}

	for row in list(order.items or []):
		item_code = cstr(row.item_code).strip()
		if not item_code:
			continue
		if item_code not in item_cache:
			item = frappe.db.get_value(
				"Item",
				item_code,
				["is_stock_item", "stock_uom", "safety_stock"],
				as_dict=True,
			)
			if not item:
				frappe.throw(_("Item {0} no longer exists.").format(item_code))
			item_cache[item_code] = item
		item = item_cache[item_code]

		if not item.is_stock_item or bool(row.delivered_by_supplier):
			continue
		warehouse = cstr(row.warehouse).strip()
		if not warehouse:
			frappe.throw(
				_("Stock item {0} requires a warehouse for material planning.").format(
					item_code
				)
			)

		conversion_factor = flt(row.conversion_factor) or 1
		current_order_reserved = max(
			flt(row.stock_qty) - flt(row.delivered_qty) * conversion_factor,
			0,
		)
		current_order_reserved = _normalized_quantity(current_order_reserved)
		required_by = row.delivery_date or order.delivery_date
		if not required_by:
			frappe.throw(
				_("Stock item {0} requires a delivery date.").format(item_code)
			)

		position_key = (item_code, warehouse)
		position = positions.setdefault(
			position_key,
			{
				"item_code": item_code,
				"warehouse": warehouse,
				"stock_uom": item.stock_uom,
				"current_order_reserved": 0.0,
				"safety_stock": max(_normalized_quantity(item.safety_stock), 0),
				"required_by": getdate(required_by),
			},
		)
		position["current_order_reserved"] += current_order_reserved
		position["required_by"] = min(
			getdate(position["required_by"]),
			getdate(required_by),
		)

	return list(positions.values())


def calculate_material_gap(sales_order_name: str) -> list[MaterialGap]:
	"""Explain open project demand after stock, reservations and inbound supply."""
	sales_order_name = cstr(sales_order_name).strip()
	if not sales_order_name:
		frappe.throw(_("Sales Order is required."))

	order = frappe.get_doc("Sales Order", sales_order_name)
	order.check_permission("read")
	_validate_order(order)

	gaps: list[MaterialGap] = []
	for position in _group_open_stock_demand(order):
		bin_values = frappe.db.get_value(
			"Bin",
			{
				"item_code": position["item_code"],
				"warehouse": position["warehouse"],
			},
			["actual_qty", "reserved_qty", "ordered_qty"],
			as_dict=True,
		) or frappe._dict()

		ordered_qty = _normalized_quantity(position["current_order_reserved"])
		actual_qty = _normalized_quantity(bin_values.get("actual_qty"))
		total_reserved_qty = max(
			_normalized_quantity(bin_values.get("reserved_qty")),
			0,
		)
		current_order_reserved = ordered_qty
		other_reserved = max(total_reserved_qty - current_order_reserved, 0)
		other_reserved = _normalized_quantity(other_reserved)
		available_qty = _normalized_quantity(actual_qty - other_reserved)
		incoming_qty = max(
			_normalized_quantity(bin_values.get("ordered_qty")),
			0,
		)
		safety_stock = max(_normalized_quantity(position["safety_stock"]), 0)
		required_qty = max(
			_normalized_quantity(
				ordered_qty + safety_stock - available_qty - incoming_qty
			),
			0,
		)

		gaps.append(
			MaterialGap(
				item_code=position["item_code"],
				warehouse=position["warehouse"],
				stock_uom=position["stock_uom"],
				ordered_qty=ordered_qty,
				actual_qty=actual_qty,
				reserved_qty=other_reserved,
				available_qty=available_qty,
				incoming_qty=incoming_qty,
				safety_stock=safety_stock,
				required_qty=required_qty,
				required_by=cstr(position["required_by"]),
			)
		)

	return sorted(gaps, key=lambda gap: (gap.required_by, gap.item_code, gap.warehouse))


def _calculation_key(gaps: list[MaterialGap]) -> str:
	payload = json.dumps(
		[asdict(gap) for gap in gaps],
		ensure_ascii=False,
		sort_keys=True,
		separators=(",", ":"),
		default=str,
	)
	return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _upsert_material_plan(order, gaps: list[MaterialGap]):
	plan_name = frappe.db.get_value(
		"Project Material Plan",
		{"sales_order": order.name},
		"name",
	)
	if plan_name:
		plan = frappe.get_doc("Project Material Plan", plan_name)
		plan.check_permission("write")
	else:
		plan = frappe.new_doc("Project Material Plan")
		plan.sales_order = order.name
		plan.customer_project = order.custom_customer_project
		plan.company = order.company

	plan.status = "已计算" if any(gap.required_qty > 0 for gap in gaps) else "无缺口"
	plan.material_request = None
	plan.calculation_key = _calculation_key(gaps)
	plan.calculated_at = now_datetime()
	plan.calculated_by = frappe.session.user
	plan.set("items", [])
	for gap in gaps:
		plan.append("items", asdict(gap))

	if plan.is_new():
		plan.insert()
	else:
		plan.save()
	return plan


def _material_lock_name(sales_order_name: str) -> str:
	return "autoflow-material-plan-" + make_idempotency_key(
		"material-request",
		sales_order_name,
	)


def _lock_sales_order_row(sales_order_name: str) -> None:
	if not frappe.db.get_value(
		"Sales Order",
		sales_order_name,
		"name",
		for_update=True,
	):
		frappe.throw(_("Sales Order {0} no longer exists.").format(sales_order_name))


def create_material_request(sales_order_name: str) -> str | None:
	"""Create one draft purchase request for the submitted project Sales Order."""
	sales_order_name = cstr(sales_order_name).strip()
	if not sales_order_name:
		frappe.throw(_("Sales Order is required."))
	order = frappe.get_doc("Sales Order", sales_order_name)
	order.check_permission("read")
	frappe.has_permission("Material Request", "create", throw=True)

	with filelock(_material_lock_name(order.name), timeout=15):
		_lock_sales_order_row(order.name)
		order.reload()
		_validate_order(order)

		existing = frappe.db.get_value(
			"Material Request",
			{
				"custom_source_sales_order": order.name,
				"docstatus": ["<", 2],
			},
			"name",
		)
		if existing:
			frappe.get_doc("Material Request", existing).check_permission("read")
			return existing

		gaps = calculate_material_gap(order.name)
		if not gaps:
			return None
		plan = _upsert_material_plan(order, gaps)
		shortages = [gap for gap in gaps if gap.required_qty > 0]
		if not shortages:
			return None

		request = frappe.get_doc(
			{
				"doctype": "Material Request",
				"material_request_type": "Purchase",
				"company": order.company,
				"transaction_date": nowdate(),
				"schedule_date": min(
					getdate(gap.required_by) for gap in shortages
				),
				"custom_customer_project": order.custom_customer_project,
				"custom_source_sales_order": order.name,
				"items": [
					{
						"item_code": gap.item_code,
						"qty": gap.required_qty,
						"warehouse": gap.warehouse,
						"schedule_date": gap.required_by,
					}
					for gap in shortages
				],
			}
		)
		request.insert()
		plan.status = "已生成物料需求"
		plan.material_request = request.name
		plan.save()
		return request.name
