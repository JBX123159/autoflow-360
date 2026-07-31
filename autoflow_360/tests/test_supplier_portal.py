from datetime import timedelta

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate, nowdate

from autoflow_360.services.procurement import (
	make_purchase_order_from_supplier_quote,
	submit_supplier_quote,
	update_supplier_eta,
)
from autoflow_360.tests.factories import (
	make_project_request_for_quotation,
	make_supplier_portal_account,
	make_supplier_quotation,
	make_two_suppliers_with_portal_users,
)


def _quote_items(rfq, *, rfq_item: str | None = None):
	return [
		{
			"rfq_item": rfq_item or row.name,
			"rate": 25,
			"expected_delivery_date": row.schedule_date,
		}
		for row in rfq.items[:1]
	]


class TestSupplierPortal(IntegrationTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")

	def test_supplier_can_read_invited_rfq(self):
		supplier, competitor = make_two_suppliers_with_portal_users()
		rfq = make_project_request_for_quotation([supplier.name])
		item = frappe.get_doc("Item", rfq.items[0].item_code)
		payable_account = frappe.get_doc(
			"Account",
			frappe.db.get_value("Company", rfq.company, "default_payable_account"),
		)
		receivable_account = frappe.get_doc(
			"Account",
			frappe.db.get_value("Company", rfq.company, "default_receivable_account"),
		)

		frappe.set_user(supplier.portal_user)
		self.assertIn("AutoFlow Supplier Portal", frappe.get_roles())
		read_roles = {
			permission.role
			for permission in frappe.get_meta("Request for Quotation").permissions
			if permission.read
		}
		self.assertIn("AutoFlow Supplier Portal", read_roles)
		self.assertTrue(
			frappe.has_permission("Request for Quotation", "read", doc=rfq)
		)
		self.assertTrue(frappe.has_permission("Item", "read", doc=item))
		self.assertTrue(
			frappe.has_permission("Account", "read", doc=payable_account)
		)
		self.assertFalse(
			frappe.has_permission("Account", "read", doc=receivable_account)
		)
		self.assertIn(
			rfq.name,
			frappe.get_list("Request for Quotation", pluck="name"),
		)

		frappe.set_user(competitor.portal_user)
		self.assertFalse(frappe.has_permission("Item", "read", doc=item))
		self.assertFalse(
			frappe.has_permission("Account", "read", doc=payable_account)
		)
		self.assertNotIn(
			rfq.name,
			frappe.get_list("Request for Quotation", pluck="name"),
		)

	def test_supplier_cannot_read_competitor_quote_or_order(self):
		first, second = make_two_suppliers_with_portal_users()
		quote = make_supplier_quotation(first)
		order_name = make_purchase_order_from_supplier_quote(quote.name)
		order = frappe.get_doc("Purchase Order", order_name)

		frappe.set_user(first.portal_user)
		self.assertTrue(
			frappe.has_permission("Supplier Quotation", "read", doc=quote)
		)
		self.assertTrue(frappe.has_permission("Purchase Order", "read", doc=order))

		frappe.set_user(second.portal_user)
		self.assertFalse(
			frappe.has_permission("Supplier Quotation", "read", doc=quote)
		)
		self.assertFalse(frappe.has_permission("Purchase Order", "read", doc=order))

	def test_uninvited_supplier_cannot_quote_rfq(self):
		invited, uninvited = make_two_suppliers_with_portal_users()
		rfq = make_project_request_for_quotation([invited.name])

		frappe.set_user(uninvited.portal_user)
		with self.assertRaises(frappe.PermissionError):
			submit_supplier_quote(
				rfq.name,
				_quote_items(rfq),
				str(getdate(nowdate()) + timedelta(days=30)),
			)

	def test_supplier_cannot_forge_rfq_item(self):
		supplier = make_supplier_portal_account()
		rfq = make_project_request_for_quotation([supplier.name])

		frappe.set_user(supplier.portal_user)
		with self.assertRaises(frappe.ValidationError):
			submit_supplier_quote(
				rfq.name,
				_quote_items(rfq, rfq_item="SYNTHETIC-FORGED-RFQ-ITEM"),
				str(getdate(nowdate()) + timedelta(days=30)),
			)

	def test_supplier_cannot_update_competitor_eta(self):
		first, second = make_two_suppliers_with_portal_users()
		quote = make_supplier_quotation(first)
		order_name = make_purchase_order_from_supplier_quote(quote.name)
		order = frappe.get_doc("Purchase Order", order_name)
		order.submit()

		frappe.set_user(second.portal_user)
		with self.assertRaises(frappe.PermissionError):
			update_supplier_eta(
				order.name,
				str(getdate(order.custom_supplier_eta) + timedelta(days=2)),
				"SYNTHETIC competitor attempt",
			)

	def test_guest_cannot_use_supplier_endpoints(self):
		supplier = make_supplier_portal_account()
		rfq = make_project_request_for_quotation([supplier.name])
		quote = make_supplier_quotation(supplier)
		order_name = make_purchase_order_from_supplier_quote(quote.name)
		order = frappe.get_doc("Purchase Order", order_name)
		order.submit()

		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			submit_supplier_quote(
				rfq.name,
				_quote_items(rfq),
				str(getdate(nowdate()) + timedelta(days=30)),
			)
		with self.assertRaises(frappe.PermissionError):
			update_supplier_eta(
				order.name,
				str(getdate(order.custom_supplier_eta) + timedelta(days=2)),
				"SYNTHETIC guest attempt",
			)

	def test_supplier_templates_render_empty_state(self):
		rfq_html = frappe.render_template(
			"autoflow_360/templates/pages/supplier_rfqs.html",
			{"rfqs": [], "today": nowdate()},
		)
		order_html = frappe.render_template(
			"autoflow_360/templates/pages/supplier_orders.html",
			{"orders": []},
		)

		self.assertIn("No RFQs available", rfq_html)
		self.assertIn("No purchase orders available", order_html)
