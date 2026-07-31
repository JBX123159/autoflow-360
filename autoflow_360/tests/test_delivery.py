import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.file_manager import save_file

from autoflow_360.services.delivery import confirm_customer_receipt
from autoflow_360.tests.factories import (
	make_customer_portal_user,
	make_delivery_note,
	make_foreign_customer,
	make_submitted_delivery_note,
)


class TestDelivery(IntegrationTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")

	def test_insufficient_stock_blocks_delivery_submission(self):
		delivery = make_delivery_note(quantity=10, available_stock=4)

		with self.assertRaises(frappe.ValidationError):
			delivery.submit()

	def test_overdelivery_blocks_delivery_submission(self):
		delivery = make_delivery_note(quantity=10, available_stock=20)
		delivery.items[0].qty = 11
		delivery.items[0].stock_qty = 11

		with self.assertRaises(frappe.ValidationError):
			delivery.submit()

	def test_customer_cannot_confirm_another_customer_delivery(self):
		delivery = make_submitted_delivery_note()
		other_customer = make_foreign_customer()
		portal_user = make_customer_portal_user(customer=other_customer.name)

		frappe.set_user(portal_user.name)
		with self.assertRaises(frappe.PermissionError):
			confirm_customer_receipt(delivery.name)

	def test_receipt_is_idempotent_immutable_and_attributed(self):
		delivery = make_submitted_delivery_note()
		portal_user = make_customer_portal_user(customer=delivery.customer)

		frappe.set_user(portal_user.name)
		first = confirm_customer_receipt(delivery.name)
		second = confirm_customer_receipt(delivery.name)
		receipt = frappe.get_doc("Customer Receipt", first)

		self.assertEqual(first, second)
		self.assertEqual(receipt.delivery_note, delivery.name)
		self.assertEqual(receipt.customer, delivery.customer)
		self.assertEqual(
			receipt.customer_project,
			delivery.custom_customer_project,
		)
		self.assertEqual(receipt.portal_user, portal_user.name)
		self.assertTrue(receipt.received_at)
		receipt.proof_file = "/private/files/SYNTHETIC-overwrite.pdf"
		with self.assertRaises(frappe.ValidationError):
			receipt.save(ignore_permissions=True)

	def test_foreign_proof_file_is_rejected(self):
		delivery = make_submitted_delivery_note()
		portal_user = make_customer_portal_user(customer=delivery.customer)
		file_doc = save_file(
			"SYNTHETIC-foreign-proof.txt",
			b"synthetic proof owned by Administrator",
			None,
			None,
			is_private=1,
		)

		frappe.set_user(portal_user.name)
		with self.assertRaises(frappe.PermissionError):
			confirm_customer_receipt(delivery.name, file_doc.file_url)

	def test_guest_cannot_confirm_delivery(self):
		delivery = make_submitted_delivery_note()

		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			confirm_customer_receipt(delivery.name)

	def test_customer_delivery_list_isolated_by_customer(self):
		delivery = make_submitted_delivery_note()
		own_user = make_customer_portal_user(customer=delivery.customer)
		other_customer = make_foreign_customer()
		other_user = make_customer_portal_user(customer=other_customer.name)

		frappe.set_user(own_user.name)
		self.assertIn(
			delivery.name,
			frappe.get_list("Delivery Note", pluck="name"),
		)

		frappe.set_user(other_user.name)
		self.assertNotIn(
			delivery.name,
			frappe.get_list("Delivery Note", pluck="name"),
		)
