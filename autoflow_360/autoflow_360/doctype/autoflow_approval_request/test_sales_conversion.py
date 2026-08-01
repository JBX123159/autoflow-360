from datetime import timedelta

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate, nowdate

from autoflow_360.services.sales_conversion import (
	create_quotation_approval_request,
	create_sales_order_from_quotation,
)
from autoflow_360.tests.factories import (
	make_approval_rule,
	make_customer_approved_sample,
	make_customer_project,
	make_internal_user,
	make_quotation,
	make_sample_request,
)


IGNORE_TEST_RECORD_DEPENDENCIES = [
	"AutoFlow Approval Request",
	"AutoFlow Approval Rule",
	"Company",
	"Contact",
	"Currency",
	"Customer",
	"Customer Feedback",
	"Customer Project",
	"Item",
	"Quotation",
	"Sales Order",
	"Sample Request",
	"UOM",
	"User",
]


class TestSalesConversion(IntegrationTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")

	def _make_project(self, suffix: str):
		return make_customer_project(f"SYNTHETIC {suffix}")

	def _make_submitted_quotation(
		self,
		suffix: str,
		*,
		customer_confirmed: bool = True,
	):
		project = self._make_project(suffix)
		make_customer_approved_sample(project.name)
		authority = make_internal_user("AutoFlow Executive")
		make_approval_rule(role="AutoFlow Executive")
		quotation = make_quotation(
			customer_project=project.name,
			customer_confirmed=customer_confirmed,
		)
		frappe.set_user(authority.name)
		try:
			quotation.submit()
		finally:
			frappe.set_user("Administrator")
		return quotation

	def test_unapproved_sample_blocks_quotation_submission(self):
		project = self._make_project("unapproved sample quote")
		make_sample_request(customer_project=project.name)
		make_approval_rule(role="System Manager")
		quotation = make_quotation(customer_project=project.name)

		with self.assertRaises(frappe.ValidationError):
			quotation.submit()

	def test_over_limit_quote_without_approval_cannot_submit(self):
		project = self._make_project("price authority gate")
		make_customer_approved_sample(project.name)
		quotation = make_quotation(
			customer_project=project.name,
			floor_rate=200,
		)

		with self.assertRaises(frappe.ValidationError):
			quotation.submit()

	def test_expired_submitted_quotation_cannot_convert(self):
		quotation = self._make_submitted_quotation("expired conversion")
		frappe.db.set_value(
			"Quotation",
			quotation.name,
			"valid_till",
			getdate(nowdate()) - timedelta(days=1),
			update_modified=False,
		)

		with self.assertRaises(frappe.ValidationError):
			create_sales_order_from_quotation(quotation.name)

	def test_repeated_conversion_creates_one_sales_order(self):
		quotation = self._make_submitted_quotation("idempotent conversion")

		first = create_sales_order_from_quotation(quotation.name)
		second = create_sales_order_from_quotation(quotation.name)

		self.assertEqual(first, second)
		self.assertEqual(
			frappe.db.count(
				"Sales Order",
				{"custom_source_quotation": quotation.name},
			),
			1,
		)

	def test_unconfirmed_quotation_cannot_convert(self):
		quotation = self._make_submitted_quotation(
			"unconfirmed conversion",
			customer_confirmed=False,
		)

		with self.assertRaises(frappe.ValidationError):
			create_sales_order_from_quotation(quotation.name)

	def test_requester_cannot_approve_own_request(self):
		project = self._make_project("self approval")
		make_customer_approved_sample(project.name)
		quotation = make_quotation(
			customer_project=project.name,
			floor_rate=200,
		)
		request_name = create_quotation_approval_request(quotation.name)
		request = frappe.get_doc("AutoFlow Approval Request", request_name)

		with self.assertRaises(frappe.PermissionError):
			request.approve()

	def test_other_user_cannot_be_impersonated_for_approval(self):
		project = self._make_project("impersonation guard")
		make_customer_approved_sample(project.name)
		quotation = make_quotation(
			customer_project=project.name,
			floor_rate=200,
		)
		request_name = create_quotation_approval_request(quotation.name)
		request = frappe.get_doc("AutoFlow Approval Request", request_name)
		approver = make_internal_user("AutoFlow Warehouse")

		with self.assertRaises(TypeError):
			request.approve(user=approver.name)

	def test_unconfigured_user_cannot_bypass_rule_through_workflow(self):
		project = self._make_project("workflow authority guard")
		make_customer_approved_sample(project.name)
		quotation = make_quotation(
			customer_project=project.name,
			floor_rate=200,
		)
		request_name = create_quotation_approval_request(quotation.name)
		approver = make_internal_user("AutoFlow Warehouse")

		frappe.set_user(approver.name)
		request = frappe.get_doc("AutoFlow Approval Request", request_name)
		with self.assertRaises(frappe.PermissionError):
			apply_workflow(request.as_dict(), "通过")

	def test_terminal_approval_status_cannot_be_saved_as_draft(self):
		project = self._make_project("draft terminal status guard")
		make_customer_approved_sample(project.name)
		quotation = make_quotation(
			customer_project=project.name,
			floor_rate=200,
		)
		request_name = create_quotation_approval_request(quotation.name)
		approver = make_internal_user("AutoFlow Executive")
		make_approval_rule(role="AutoFlow Executive")

		frappe.set_user(approver.name)
		request = frappe.get_doc("AutoFlow Approval Request", request_name)
		request.status = "已通过"
		with self.assertRaises(frappe.ValidationError):
			request.save()

	def test_sample_workflow_keeps_business_status_separate(self):
		project = self._make_project("sample approval state")
		sample = make_sample_request(customer_project=project.name)
		project_manager = make_internal_user("AutoFlow Project Manager")
		sales_operations = make_internal_user("AutoFlow Sales Operations")

		frappe.set_user(project_manager.name)
		sample = apply_workflow(sample.as_dict(), "提交审批")
		self.assertEqual(sample.approval_status, "待审批")
		self.assertEqual(sample.status, "草稿")

		frappe.set_user(sales_operations.name)
		sample = apply_workflow(sample.as_dict(), "通过")
		self.assertEqual(sample.approval_status, "已通过")
		self.assertEqual(sample.status, "制作中")

	def test_changed_quotation_invalidates_approval_snapshot(self):
		project = self._make_project("stale approval snapshot")
		make_customer_approved_sample(project.name)
		quotation = make_quotation(
			customer_project=project.name,
			floor_rate=200,
		)
		request_name = create_quotation_approval_request(quotation.name)
		approver = make_internal_user("AutoFlow Executive")
		make_approval_rule(role="AutoFlow Executive")

		frappe.set_user(approver.name)
		request = frappe.get_doc("AutoFlow Approval Request", request_name)
		request.approve("SYNTHETIC approved within authority")
		self.assertEqual(request.status, "已通过")
		self.assertEqual(request.approver, approver.name)

		frappe.set_user("Administrator")
		quotation.reload()
		quotation.items[0].rate = 90
		quotation.save()
		with self.assertRaises(frappe.ValidationError):
			quotation.submit()

	def test_approved_unchanged_quote_can_submit(self):
		project = self._make_project("current approval snapshot")
		make_customer_approved_sample(project.name)
		quotation = make_quotation(
			customer_project=project.name,
			floor_rate=200,
		)
		request_name = create_quotation_approval_request(quotation.name)
		approver = make_internal_user("AutoFlow Executive")
		make_approval_rule(role="AutoFlow Executive")

		frappe.set_user(approver.name)
		request = frappe.get_doc("AutoFlow Approval Request", request_name)
		request.approve("SYNTHETIC unchanged commercial terms")

		frappe.set_user("Administrator")
		quotation.reload()
		quotation.submit()
		self.assertEqual(quotation.docstatus, 1)
