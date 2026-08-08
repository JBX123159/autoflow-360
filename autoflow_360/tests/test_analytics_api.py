from datetime import timedelta

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate, nowdate

from autoflow_360.api.analytics import (
	get_management_cockpit,
	get_project_panorama,
	get_workbench_data,
)
from autoflow_360.tests.factories import (
	SYNTHETIC_COMPANY,
	add_company_user_permission,
	get_foreign_company,
	make_approval_rule,
	make_customer_approved_sample,
	make_customer_portal_user,
	make_customer_project,
	make_customer_project_with_member,
	make_internal_user,
	make_over_limit_approval_request,
	make_project_for_company,
	make_project_with_risk,
)


class TestAnalyticsAPI(IntegrationTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")

	def test_workbench_returns_actionable_sections_with_routes(self):
		project = make_customer_project("SYNTHETIC Workbench Structure")

		data = get_workbench_data()

		self.assertEqual(
			set(data),
			{"role", "approvals", "high_risks", "due_within_seven_days", "projects"},
		)
		self.assertIn(project.name, {row["name"] for row in data["projects"]})
		for section in ("approvals", "high_risks", "due_within_seven_days", "projects"):
			for item in data[section]:
				self.assertTrue(item["doctype"], section)
				self.assertTrue(item["name"], section)
				self.assertTrue(item["route"], section)

	def test_workbench_excludes_hidden_project_risk_and_due_item(self):
		hidden = make_project_with_risk()
		user = make_internal_user("AutoFlow Project Manager")
		visible = make_customer_project_with_member(user.name)
		visible.append(
			"milestones",
			{
				"milestone_name": "SYNTHETIC Visible seven-day milestone",
				"planned_date": getdate(nowdate()) + timedelta(days=3),
				"owner_user": user.name,
				"status": "进行中",
			},
		)
		visible.save()
		frappe.set_user(user.name)

		data = get_workbench_data()

		self.assertIn(visible.name, {row["name"] for row in data["projects"]})
		self.assertNotIn(hidden.name, {row["name"] for row in data["projects"]})
		self.assertNotIn(
			hidden.name,
			{row["customer_project"] for row in data["high_risks"]},
		)
		self.assertNotIn(
			hidden.name,
			{row["customer_project"] for row in data["due_within_seven_days"]},
		)

	def test_workbench_shows_only_approvals_current_user_can_decide(self):
		requester = make_internal_user("AutoFlow Project Manager")
		approver = make_internal_user("AutoFlow Executive")
		make_approval_rule(role="AutoFlow Executive")
		request = make_over_limit_approval_request(requester.name)

		frappe.set_user(approver.name)
		approver_names = {row["name"] for row in get_workbench_data()["approvals"]}
		frappe.set_user(requester.name)
		requester_names = {row["name"] for row in get_workbench_data()["approvals"]}

		self.assertIn(request.name, approver_names)
		self.assertNotIn(request.name, requester_names)

	def test_portal_user_cannot_open_internal_workbench(self):
		portal_user = make_customer_portal_user()
		frappe.set_user(portal_user.name)

		with self.assertRaises(frappe.PermissionError):
			get_workbench_data()

	def test_cockpit_metrics_have_definition_unit_and_drilldown(self):
		make_customer_project("SYNTHETIC Cockpit Metric")

		data = get_management_cockpit({"company": SYNTHETIC_COMPANY})

		self.assertEqual(data["filters"]["company"], SYNTHETIC_COMPANY)
		self.assertTrue(data["metrics"])
		for metric in data["metrics"]:
			self.assertTrue(metric["code"])
			self.assertTrue(metric["label"])
			self.assertTrue(metric["definition"])
			self.assertIn("value", metric)
			self.assertTrue(metric["unit"])
			self.assertTrue(metric["drilldown"])
		self.assertIn("stage_distribution", data)
		self.assertIn("risk_distribution", data)
		self.assertIn("exception_summary", data)

	def test_cockpit_rejects_user_without_management_role(self):
		user = make_internal_user("AutoFlow Project Manager")
		frappe.set_user(user.name)

		with self.assertRaises(frappe.PermissionError):
			get_management_cockpit()

	def test_cockpit_accepts_explicit_executive_role(self):
		project = make_customer_project("SYNTHETIC Executive Cockpit")
		user = make_internal_user("AutoFlow Executive")
		frappe.set_user(user.name)

		data = get_management_cockpit()

		self.assertIn(project.name, {row["name"] for row in data["recent_projects"]})

	def test_cockpit_respects_company_user_permission(self):
		foreign_company = get_foreign_company()
		allowed = make_project_for_company(SYNTHETIC_COMPANY)
		blocked = make_project_for_company(foreign_company)
		user = make_internal_user("AutoFlow Executive")
		add_company_user_permission(user.name, SYNTHETIC_COMPANY)
		frappe.set_user(user.name)

		data = get_management_cockpit()

		visible_names = {row["name"] for row in data["recent_projects"]}
		self.assertIn(allowed.name, visible_names)
		self.assertNotIn(blocked.name, visible_names)

	def test_cockpit_keeps_different_currencies_separate(self):
		make_customer_project("SYNTHETIC Currency CNY", currency="CNY")
		make_customer_project("SYNTHETIC Currency USD", currency="USD")

		data = get_management_cockpit({"company": SYNTHETIC_COMPANY})
		pipeline = next(metric for metric in data["metrics"] if metric["code"] == "PIPELINE_VALUE")

		self.assertIsInstance(pipeline["value"], dict)
		self.assertIn("CNY", pipeline["value"])
		self.assertIn("USD", pipeline["value"])
		self.assertEqual(pipeline["unit"], "按币种")

	def test_cockpit_rejects_unknown_filter_keys(self):
		with self.assertRaises(frappe.ValidationError):
			get_management_cockpit({"unsafe_filter": "SYNTHETIC"})

	def test_project_panorama_returns_traceable_sections(self):
		project = make_project_with_risk()

		data = get_project_panorama(project.name)

		self.assertEqual(
			set(data),
			{"project", "flow", "documents", "risks", "exceptions", "ai_analyses", "audit"},
		)
		self.assertEqual(data["project"]["name"], project.name)
		self.assertEqual(data["project"]["currency"], project.currency)
		self.assertTrue(data["flow"])
		self.assertIn(project.risk_name, {row["name"] for row in data["risks"]})
		for section in ("risks", "exceptions", "ai_analyses", "audit"):
			for row in data[section]:
				self.assertTrue(row["doctype"], section)
				self.assertTrue(row["name"], section)
				self.assertTrue(row["route"], section)

	def test_project_panorama_includes_feedback_linked_through_sample(self):
		project = make_customer_project("SYNTHETIC Panorama Feedback")
		sample = make_customer_approved_sample(project.name)

		data = get_project_panorama(project.name)

		feedback_names = {
			row["name"]
			for row in data["documents"]["samples"]
			if row["doctype"] == "Customer Feedback"
		}
		self.assertIn(sample.feedback, feedback_names)

	def test_project_panorama_denies_unreadable_project(self):
		project = make_customer_project("SYNTHETIC Hidden Panorama")
		user = make_internal_user("AutoFlow Project Manager")
		frappe.set_user(user.name)

		with self.assertRaises(frappe.PermissionError):
			get_project_panorama(project.name)

	def test_workbench_and_cockpit_pages_are_installed(self):
		self.assertTrue(frappe.db.exists("Page", "autoflow-workbench"))
		self.assertTrue(frappe.db.exists("Page", "autoflow-cockpit"))


if __name__ == "__main__":
	import unittest

	unittest.main()
