import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_datetime

from autoflow_360.demo.seed import DEMO_CURRENCY, SCENARIO_KEYS, seed_demo_data


class TestDemoSeed(IntegrationTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")

	def test_seed_is_idempotent_and_creates_three_scenarios(self):
		first = seed_demo_data()
		second = seed_demo_data()

		self.assertEqual(first, second)
		self.assertEqual(set(first), set(SCENARIO_KEYS))
		self.assertEqual(len(set(first.values())), 3)
		self.assertEqual(
			frappe.db.count(
				"Customer Project",
				{"demo_key": ["in", list(SCENARIO_KEYS.values())]},
			),
			3,
		)

	def test_reseed_refreshes_demo_projects_for_workbench_visibility(self):
		projects = seed_demo_data()
		stale_modified = get_datetime("2000-01-01 00:00:00")
		for project_name in projects.values():
			frappe.db.set_value(
				"Customer Project",
				project_name,
				"modified",
				stale_modified,
				update_modified=False,
			)

		seed_demo_data()

		for project_name in projects.values():
			self.assertGreater(
				get_datetime(frappe.db.get_value("Customer Project", project_name, "modified")),
				stale_modified,
			)

	def test_every_demo_project_is_marked_synthetic_and_uses_cny(self):
		result = seed_demo_data()

		for scenario, project_name in result.items():
			project = frappe.get_doc("Customer Project", project_name)
			self.assertEqual(project.demo_key, SCENARIO_KEYS[scenario])
			self.assertEqual(project.demo_scenario, scenario)
			self.assertEqual(project.currency, DEMO_CURRENCY)
			self.assertEqual(project.is_demo, 1)
			self.assertIn("合成", project.data_classification)
			self.assertEqual(
				frappe.get_cached_value("Company", project.company, "default_currency"),
				DEMO_CURRENCY,
			)

	def test_normal_scenario_contains_closed_financial_and_delivery_loop(self):
		project_name = seed_demo_data()["normal"]

		self.assertEqual(
			frappe.db.get_value("Customer Project", project_name, "stage"),
			"已结项",
		)
		for doctype in (
			"Quotation",
			"Sales Order",
			"Purchase Order",
			"Purchase Receipt",
			"Delivery Note",
			"Sales Invoice",
			"Payment Entry",
		):
			self.assertGreater(
				frappe.db.count(
					doctype,
					{"custom_customer_project": project_name, "docstatus": 1},
				),
				0,
				doctype,
			)
		self.assertGreater(
			frappe.db.count(
				"Customer Receipt",
				{"customer_project": project_name},
			),
			0,
		)

	def test_supplier_delay_scenario_keeps_risk_exception_and_recovery_evidence(self):
		project_name = seed_demo_data()["supplier_delay"]

		self.assertGreater(
			frappe.db.count(
				"Project Risk",
				{"customer_project": project_name, "risk_level": "高"},
			),
			0,
		)
		self.assertGreater(
			frappe.db.count(
				"Business Exception",
				{"customer_project": project_name, "status": "已关闭"},
			),
			0,
		)
		self.assertGreater(
			frappe.db.count(
				"Supplier ETA History",
				{"customer_project": project_name},
			),
			0,
		)

	def test_resample_scenario_preserves_both_rounds_and_customer_decisions(self):
		project_name = seed_demo_data()["resample"]
		samples = frappe.get_all(
			"Sample Request",
			filters={"customer_project": project_name},
			fields=["name", "previous_sample_request", "round_number"],
			order_by="round_number asc",
		)

		self.assertEqual(len(samples), 2)
		self.assertEqual(samples[1].previous_sample_request, samples[0].name)
		self.assertEqual(samples[1].round_number, samples[0].round_number + 1)
		self.assertEqual(
			set(
				frappe.get_all(
					"Customer Feedback",
					filters={"sample_request": ["in", [row.name for row in samples]]},
					pluck="decision",
				)
			),
			{"重新打样", "客户认可"},
		)

	def test_reset_requires_exact_explicit_confirmation(self):
		seed_demo_data()

		with self.assertRaises(frappe.ValidationError):
			seed_demo_data(reset=True)
		with self.assertRaises(frappe.ValidationError):
			seed_demo_data(reset=True, confirmation="确认")
