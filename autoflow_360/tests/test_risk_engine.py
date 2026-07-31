import json
from datetime import timedelta

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate, nowdate

from autoflow_360.risk_engine.scheduled import scan_daily_risks
from autoflow_360.risk_engine.service import evaluate_project, upsert_risks
from autoflow_360.tests.factories import (
	make_expiring_quotation_project,
	make_inactive_project,
	make_overdue_project,
	make_pending_feedback_project,
	make_project_with_stock_gap,
	make_project_with_supplier_eta_after_delivery,
	make_unpaid_project,
)


SYNTHETIC_RULE_MARKER = "SYNTHETIC"


def _finding(project, rule_code: str):
	return next(
		item
		for item in evaluate_project(project.name)
		if item.rule_code == rule_code
	)


class TestRiskEngine(IntegrationTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")

	def test_supplier_eta_after_delivery_is_high_risk(self):
		project = make_project_with_supplier_eta_after_delivery()

		finding = _finding(project, "SUPPLIER_DELAY")

		self.assertEqual(finding.level, "高")
		self.assertEqual(finding.reference_doctype, "Purchase Order")
		self.assertGreater(
			getdate(finding.inputs["supplier_eta"]),
			getdate(finding.inputs["customer_delivery_date"]),
		)

	def test_overdue_milestone_has_exact_evidence(self):
		project = make_overdue_project(days_overdue=9)

		finding = _finding(project, "MILESTONE_OVERDUE")

		self.assertEqual(finding.level, "高")
		self.assertEqual(finding.inputs["days_overdue"], 9)
		self.assertEqual(finding.reference_doctype, "Project Milestone")

	def test_pending_sample_feedback_is_detected(self):
		project = make_pending_feedback_project(days_waiting=5)

		finding = _finding(project, "SAMPLE_FEEDBACK_DELAY")

		self.assertEqual(finding.reference_doctype, "Sample Request")
		self.assertGreaterEqual(finding.inputs["days_waiting"], 5)

	def test_quotation_expiry_is_detected(self):
		project = make_expiring_quotation_project(days_until_expiry=2)
		quotations = frappe.get_all(
			"Quotation",
			filters={"custom_customer_project": project.name},
			fields=[
				"name",
				"docstatus",
				"custom_customer_confirmed",
				"valid_till",
			],
		)
		self.assertEqual(len(quotations), 1)
		self.assertEqual(quotations[0].docstatus, 1)
		self.assertFalse(quotations[0].custom_customer_confirmed)
		self.assertEqual(
			(quotations[0].valid_till - getdate(nowdate())).days,
			2,
		)

		finding = _finding(project, "QUOTATION_EXPIRY")

		self.assertEqual(finding.reference_doctype, "Quotation")
		self.assertEqual(finding.inputs["days_until_expiry"], 2)

	def test_stock_gap_is_explained(self):
		project = make_project_with_stock_gap()

		finding = _finding(project, "STOCK_DELIVERY_GAP")

		self.assertEqual(finding.reference_doctype, "Sales Order")
		self.assertTrue(finding.inputs["gaps"])
		self.assertGreater(finding.inputs["gaps"][0]["required_qty"], 0)

	def test_overdue_receivable_evidence_is_persisted(self):
		project = make_unpaid_project(days_overdue=8)
		finding = _finding(project, "RECEIVABLE_OVERDUE")

		names = upsert_risks(project.name, [finding])
		risk = frappe.get_doc("Project Risk", names[0])
		inputs = json.loads(risk.rule_inputs)

		self.assertEqual(risk.reference_doctype, "Sales Invoice")
		self.assertGreater(inputs["outstanding_amount"], 0)
		self.assertEqual(inputs["days_overdue"], 8)

	def test_inactive_project_is_detected(self):
		project = make_inactive_project(days_inactive=10)

		finding = _finding(project, "PROJECT_INACTIVE")

		self.assertEqual(finding.reference_name, project.name)
		self.assertEqual(finding.inputs["days_inactive"], 10)

	def test_repeated_scan_does_not_duplicate_open_risk(self):
		project = make_overdue_project()

		first = upsert_risks(project.name, evaluate_project(project.name))
		second = upsert_risks(project.name, evaluate_project(project.name))

		self.assertEqual(first, second)
		self.assertEqual(
			frappe.db.count("Project Risk", {"customer_project": project.name}),
			1,
		)

	def test_scheduler_scans_active_projects_and_updates_overall_level(self):
		project = make_overdue_project(days_overdue=9)

		scan_daily_risks()

		self.assertEqual(
			frappe.db.count("Project Risk", {"customer_project": project.name}),
			1,
		)
		self.assertEqual(
			frappe.db.get_value(
				"Customer Project",
				project.name,
				"overall_risk_level",
			),
			"高",
		)

	def test_changed_finding_updates_existing_risk(self):
		project = make_overdue_project(days_overdue=2)
		first_name = upsert_risks(
			project.name,
			evaluate_project(project.name),
		)[0]
		first_inputs = frappe.db.get_value(
			"Project Risk",
			first_name,
			"rule_inputs",
		)
		project.reload()
		project.milestones[0].planned_date = getdate(nowdate()) - timedelta(days=10)
		project.save()

		second_name = upsert_risks(
			project.name,
			evaluate_project(project.name),
		)[0]
		second_inputs = frappe.db.get_value(
			"Project Risk",
			second_name,
			"rule_inputs",
		)

		self.assertEqual(first_name, second_name)
		self.assertNotEqual(first_inputs, second_inputs)

	def test_stale_risk_moves_to_verification(self):
		project = make_overdue_project()
		risk_name = upsert_risks(
			project.name,
			evaluate_project(project.name),
		)[0]
		project.reload()
		project.milestones[0].status = "已完成"
		project.save()

		upsert_risks(project.name, evaluate_project(project.name))

		self.assertEqual(
			frappe.db.get_value("Project Risk", risk_name, "status"),
			"待验证",
		)

	def test_closed_risk_reopens_without_duplicate(self):
		project = make_overdue_project()
		findings = evaluate_project(project.name)
		risk_name = upsert_risks(project.name, findings)[0]
		frappe.db.set_value(
			"Project Risk",
			risk_name,
			{
				"status": "已关闭",
				"resolved_at": frappe.utils.now_datetime(),
				"verified_by": "Administrator",
			},
		)

		reopened_name = upsert_risks(project.name, findings)[0]

		self.assertEqual(reopened_name, risk_name)
		self.assertEqual(
			frappe.db.get_value("Project Risk", risk_name, "status"),
			"已发现",
		)
		self.assertEqual(
			frappe.db.count("Project Risk", {"customer_project": project.name}),
			1,
		)
