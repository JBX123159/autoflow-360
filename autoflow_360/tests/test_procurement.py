import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate

from autoflow_360.services.procurement import (
	make_project_rfq,
	make_purchase_order_from_supplier_quote,
	update_supplier_eta,
)
from autoflow_360.services.project_linking import propagate_project_link
from autoflow_360.tests.factories import (
	make_project_material_request,
	make_purchase_invoice_from_order,
	make_purchase_receipt_from_order,
	make_submitted_project_purchase_order,
	make_supplier_portal_account,
	make_supplier_quotation,
)


class TestProcurement(IntegrationTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")

	def test_rfq_keeps_project_source_and_submits(self):
		request = make_project_material_request()
		supplier = make_supplier_portal_account()

		rfq_name = make_project_rfq(request.name, [supplier.name])
		rfq = frappe.get_doc("Request for Quotation", rfq_name)

		self.assertEqual(rfq.docstatus, 1)
		self.assertEqual(rfq.custom_customer_project, request.custom_customer_project)
		self.assertEqual(rfq.custom_source_material_request, request.name)
		self.assertEqual([row.supplier for row in rfq.suppliers], [supplier.name])
		self.assertEqual(rfq.items[0].material_request, request.name)
		self.assertEqual(rfq.items[0].material_request_item, request.items[0].name)

	def test_repeated_rfq_creation_is_idempotent(self):
		request = make_project_material_request()
		supplier = make_supplier_portal_account()

		first = make_project_rfq(request.name, [supplier.name])
		second = make_project_rfq(request.name, [supplier.name])

		self.assertEqual(first, second)
		self.assertEqual(
			frappe.db.count(
				"Request for Quotation",
				{
					"custom_source_material_request": request.name,
					"docstatus": ["<", 2],
				},
			),
			1,
		)

	def test_supplier_quote_keeps_rfq_rows_and_submits(self):
		quote = make_supplier_quotation(rate=37.5)
		rfq = frappe.get_doc("Request for Quotation", quote.custom_source_rfq)

		self.assertEqual(quote.docstatus, 1)
		self.assertEqual(quote.custom_customer_project, rfq.custom_customer_project)
		self.assertEqual(len(quote.items), len(rfq.items))
		self.assertEqual(quote.items[0].request_for_quotation, rfq.name)
		self.assertEqual(
			quote.items[0].request_for_quotation_item,
			rfq.items[0].name,
		)
		self.assertAlmostEqual(quote.items[0].rate, 37.5)

	def test_supplier_quote_converts_to_one_project_purchase_order(self):
		quote = make_supplier_quotation()

		first = make_purchase_order_from_supplier_quote(quote.name)
		second = make_purchase_order_from_supplier_quote(quote.name)
		order = frappe.get_doc("Purchase Order", first)

		self.assertEqual(first, second)
		self.assertEqual(order.docstatus, 0)
		self.assertEqual(order.custom_customer_project, quote.custom_customer_project)
		self.assertEqual(order.custom_source_supplier_quotation, quote.name)
		self.assertEqual(order.items[0].supplier_quotation, quote.name)
		self.assertTrue(order.custom_supplier_eta)
		self.assertEqual(
			frappe.db.count(
				"Purchase Order",
				{
					"custom_source_supplier_quotation": quote.name,
					"docstatus": ["<", 2],
				},
			),
			1,
		)

	def test_eta_change_keeps_immutable_history(self):
		order = make_submitted_project_purchase_order()
		initial_eta = getdate(order.custom_supplier_eta)
		first_eta = add_days(initial_eta, 3)
		second_eta = add_days(initial_eta, 7)

		update_supplier_eta(order.name, str(first_eta), "SYNTHETIC first confirmation")
		update_supplier_eta(order.name, str(second_eta), "SYNTHETIC capacity change")
		history_names = frappe.get_all(
			"Supplier ETA History",
			filters={"purchase_order": order.name},
			order_by="changed_at asc",
			pluck="name",
		)
		first = frappe.get_doc("Supplier ETA History", history_names[0])
		second = frappe.get_doc("Supplier ETA History", history_names[1])

		self.assertEqual(len(history_names), 2)
		self.assertEqual(getdate(first.previous_eta), initial_eta)
		self.assertEqual(getdate(first.new_eta), first_eta)
		self.assertEqual(getdate(second.previous_eta), first_eta)
		self.assertEqual(getdate(second.new_eta), second_eta)
		self.assertEqual(first.customer_project, order.custom_customer_project)
		first.change_reason = "SYNTHETIC overwrite attempt"
		with self.assertRaises(frappe.ValidationError):
			first.save()

	def test_downstream_documents_inherit_one_project(self):
		order = make_submitted_project_purchase_order()

		receipt = make_purchase_receipt_from_order(order.name)
		receipt.custom_customer_project = None
		propagate_project_link(receipt)

		invoice = make_purchase_invoice_from_order(order.name)
		invoice.custom_customer_project = None
		propagate_project_link(invoice)
		invoice.insert()

		payment = frappe.new_doc("Payment Entry")
		payment.append(
			"references",
			{
				"reference_doctype": "Purchase Invoice",
				"reference_name": invoice.name,
			},
		)
		propagate_project_link(payment)

		for document in (receipt, invoice, payment):
			self.assertEqual(
				document.custom_customer_project,
				order.custom_customer_project,
			)
