import frappe
from frappe.tests import IntegrationTestCase

from autoflow_360.services.material_planning import (
	calculate_material_gap,
	create_material_request,
)
from autoflow_360.tests.factories import (
	make_stock_sales_order,
	set_warehouse_stock,
)


SYNTHETIC_WAREHOUSE = "_Test Warehouse - _TC"

class TestMaterialPlanning(IntegrationTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")

	def _make_order_with_stock(
		self,
		*,
		actual_qty: float,
		incoming_qty: float = 0,
		extra_reserved_qty: float = 0,
		safety_stock: float = 0,
	):
		order = make_stock_sales_order(safety_stock=safety_stock)
		item_code = order.items[0].item_code
		set_warehouse_stock(
			item_code,
			SYNTHETIC_WAREHOUSE,
			actual_qty=actual_qty,
			incoming_qty=incoming_qty,
			extra_reserved_qty=extra_reserved_qty,
		)
		return order

	def test_available_stock_reduces_required_quantity(self):
		order = self._make_order_with_stock(actual_qty=4)

		gaps = calculate_material_gap(order.name)

		self.assertEqual(len(gaps), 1)
		self.assertAlmostEqual(gaps[0].ordered_qty, 10)
		self.assertAlmostEqual(gaps[0].actual_qty, 4)
		self.assertAlmostEqual(gaps[0].available_qty, 4)
		self.assertAlmostEqual(gaps[0].required_qty, 6)

	def test_current_order_reservation_is_not_double_counted(self):
		order = self._make_order_with_stock(actual_qty=0)

		gap = calculate_material_gap(order.name)[0]

		self.assertAlmostEqual(gap.reserved_qty, 0)
		self.assertAlmostEqual(gap.required_qty, 10)

	def test_other_reservations_safety_stock_and_incoming_are_explained(self):
		order = self._make_order_with_stock(
			actual_qty=1,
			incoming_qty=4,
			extra_reserved_qty=3,
			safety_stock=2,
		)

		gap = calculate_material_gap(order.name)[0]

		self.assertAlmostEqual(gap.reserved_qty, 3)
		self.assertAlmostEqual(gap.available_qty, -2)
		self.assertAlmostEqual(gap.incoming_qty, 4)
		self.assertAlmostEqual(gap.safety_stock, 2)
		self.assertAlmostEqual(gap.required_qty, 10)

	def test_negative_stock_increases_required_quantity(self):
		order = self._make_order_with_stock(actual_qty=-2)

		gap = calculate_material_gap(order.name)[0]

		self.assertAlmostEqual(gap.actual_qty, -2)
		self.assertAlmostEqual(gap.available_qty, -2)
		self.assertAlmostEqual(gap.required_qty, 12)

	def test_no_request_is_created_without_gap(self):
		order = self._make_order_with_stock(actual_qty=20)

		request_name = create_material_request(order.name)
		plan_name = frappe.db.get_value(
			"Project Material Plan",
			{"sales_order": order.name},
			"name",
		)
		plan = frappe.get_doc("Project Material Plan", plan_name)

		self.assertIsNone(request_name)
		self.assertEqual(plan.status, "无缺口")
		self.assertEqual(len(plan.items), 1)
		self.assertAlmostEqual(plan.items[0].required_qty, 0)
		self.assertFalse(
			frappe.db.exists(
				"Material Request",
				{"custom_source_sales_order": order.name},
			)
		)

	def test_repeated_request_creation_is_idempotent(self):
		order = self._make_order_with_stock(actual_qty=0)

		first = create_material_request(order.name)
		second = create_material_request(order.name)
		request = frappe.get_doc("Material Request", first)
		plan = frappe.get_doc(
			"Project Material Plan",
			{"sales_order": order.name},
		)

		self.assertEqual(first, second)
		self.assertEqual(
			frappe.db.count(
				"Material Request",
				{
					"custom_source_sales_order": order.name,
					"docstatus": ["<", 2],
				},
			),
			1,
		)
		self.assertEqual(len(request.items), 1)
		self.assertAlmostEqual(request.items[0].qty, 10)
		self.assertEqual(plan.status, "已生成物料需求")
		self.assertEqual(plan.material_request, first)

	def test_draft_sales_order_is_rejected(self):
		order = make_stock_sales_order(submit=False)

		with self.assertRaises(frappe.ValidationError):
			calculate_material_gap(order.name)

	def test_missing_warehouse_is_rejected(self):
		order = make_stock_sales_order()
		frappe.db.set_value(
			"Sales Order Item",
			order.items[0].name,
			"warehouse",
			None,
			update_modified=False,
		)

		with self.assertRaises(frappe.ValidationError):
			calculate_material_gap(order.name)
