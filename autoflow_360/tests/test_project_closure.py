import frappe
from frappe.tests import IntegrationTestCase

from autoflow_360.services.project_closure import (
	close_project,
	create_project_closure_request,
	get_closure_gaps,
)
from autoflow_360.tests.factories import (
	add_project_member,
	make_approval_rule,
	make_customer_project,
	make_fulfilled_project,
	make_internal_user,
)


CLOSURE_SUMMARY = "SYNTHETIC 项目已完成交付、开票、回款和客户签收，证据齐全。"


class TestProjectClosure(IntegrationTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")

	def _approve_closure(self, project):
		make_approval_rule(
			role="AutoFlow Executive",
			document_type="Customer Project",
		)
		requester = make_internal_user("AutoFlow Project Manager")
		approver = make_internal_user("AutoFlow Executive")
		add_project_member(project.name, requester.name)

		frappe.set_user(requester.name)
		request_name = create_project_closure_request(project.name)
		frappe.set_user(approver.name)
		frappe.get_doc("AutoFlow Approval Request", request_name).approve(
			"SYNTHETIC closure evidence approved"
		)
		frappe.set_user(requester.name)
		return requester, request_name

	def test_missing_sales_order_is_explained(self):
		project = make_customer_project("SYNTHETIC closure without order")

		codes = {gap.code for gap in get_closure_gaps(project.name)}

		self.assertIn("NO_SALES_ORDER", codes)

	def test_missing_customer_receipt_blocks_closure(self):
		project = make_fulfilled_project(confirm_receipt=False)

		codes = {gap.code for gap in get_closure_gaps(project.name)}

		self.assertIn("CUSTOMER_RECEIPT_MISSING", codes)

	def test_unpaid_invoice_blocks_closure(self):
		project = make_fulfilled_project(outstanding_amount=100)

		codes = {gap.code for gap in get_closure_gaps(project.name)}

		self.assertIn("UNPAID_RECEIVABLE", codes)
		with self.assertRaises(frappe.ValidationError):
			close_project(project.name, CLOSURE_SUMMARY)

	def test_zero_outstanding_without_payment_entry_is_not_enough(self):
		project = make_fulfilled_project(outstanding_amount=100)
		invoice_name = frappe.db.get_value(
			"Sales Invoice",
			{
				"custom_customer_project": project.name,
				"docstatus": 1,
			},
			"name",
		)
		frappe.db.set_value(
			"Sales Invoice",
			invoice_name,
			"outstanding_amount",
			0,
			update_modified=False,
		)

		codes = {gap.code for gap in get_closure_gaps(project.name)}

		self.assertIn("PAYMENT_EVIDENCE_MISSING", codes)

	def test_approval_is_required_after_all_evidence(self):
		project = make_fulfilled_project()

		self.assertEqual(get_closure_gaps(project.name), [])
		with self.assertRaises(frappe.ValidationError):
			close_project(project.name, CLOSURE_SUMMARY)

	def test_repeated_closure_request_reuses_pending_snapshot(self):
		project = make_fulfilled_project()
		requester = make_internal_user("AutoFlow Project Manager")
		add_project_member(project.name, requester.name)
		frappe.set_user(requester.name)

		first = create_project_closure_request(project.name)
		second = create_project_closure_request(project.name)

		self.assertEqual(first, second)

	def test_changed_evidence_invalidates_approval(self):
		project = make_fulfilled_project()
		requester, _request_name = self._approve_closure(project)
		project.reload()
		project.expected_amount += 1
		project.save()
		frappe.set_user(requester.name)

		with self.assertRaises(frappe.ValidationError):
			close_project(project.name, CLOSURE_SUMMARY)

	def test_direct_stage_change_cannot_bypass_service(self):
		project = make_fulfilled_project()
		project.stage = "已结项"

		with self.assertRaises(frappe.ValidationError):
			project.save(ignore_permissions=True)

	def test_complete_evidence_and_approval_allow_idempotent_closure(self):
		project = make_fulfilled_project()
		requester, _request_name = self._approve_closure(project)
		frappe.set_user(requester.name)

		first = close_project(project.name, CLOSURE_SUMMARY)
		second = close_project(project.name, CLOSURE_SUMMARY)

		self.assertEqual(first, project.name)
		self.assertEqual(second, project.name)
		self.assertEqual(
			frappe.db.get_value("Customer Project", project.name, "stage"),
			"已结项",
		)

	def test_closed_project_payment_evidence_cannot_be_cancelled(self):
		project = make_fulfilled_project()
		requester, _request_name = self._approve_closure(project)
		frappe.set_user(requester.name)
		close_project(project.name, CLOSURE_SUMMARY)
		payment_name = frappe.db.get_value(
			"Payment Entry",
			{
				"custom_customer_project": project.name,
				"docstatus": 1,
			},
			"name",
		)
		frappe.set_user("Administrator")

		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc("Payment Entry", payment_name).cancel()

	def test_closure_summary_is_immutable(self):
		project = make_fulfilled_project()
		requester, _request_name = self._approve_closure(project)
		frappe.set_user(requester.name)
		close_project(project.name, CLOSURE_SUMMARY)
		project.reload()
		project.closure_summary = "SYNTHETIC 尝试覆盖原始结项复盘内容。"

		with self.assertRaises(frappe.ValidationError):
			project.save(ignore_permissions=True)
