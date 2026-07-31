from datetime import timedelta

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate, nowdate

from autoflow_360.tests.factories import make_customer_project


IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Company",
	"Customer",
	"CRM Deal",
	"Currency",
	"User",
]


class TestCustomerProject(IntegrationTestCase):
	def test_valid_synthetic_project_can_be_created(self):
		project = make_customer_project("SYNTHETIC valid customer project")
		self.assertTrue(project.name.startswith("AF-"))
		self.assertEqual(project.stage, "潜在项目")

	def test_target_award_date_cannot_follow_customer_delivery(self):
		project = make_customer_project(
			"SYNTHETIC invalid date project",
			insert=False,
			target_award_date=getdate(nowdate()) + timedelta(days=20),
			customer_delivery_date=getdate(nowdate()) + timedelta(days=10),
		)
		with self.assertRaises(frappe.ValidationError):
			project.insert()

	def test_stage_cannot_skip_from_potential_to_awarded(self):
		project = make_customer_project("SYNTHETIC stage guard project")
		project.stage = "已定点"
		with self.assertRaises(frappe.ValidationError):
			project.save()

	def test_project_requires_at_least_one_member(self):
		project = make_customer_project(
			"SYNTHETIC member guard project",
			insert=False,
		)
		project.set("project_members", [])
		with self.assertRaises(frappe.ValidationError):
			project.insert()

	def test_project_manager_must_be_a_member(self):
		project = make_customer_project(
			"SYNTHETIC manager membership project",
			insert=False,
			project_members=[
				{
					"user": "Guest",
					"responsibility": "SYNTHETIC observer",
				}
			],
		)
		with self.assertRaises(frappe.ValidationError):
			project.insert()

	def test_probability_and_expected_amount_boundaries(self):
		for overrides in (
			{"probability": -1},
			{"probability": 101},
			{"expected_amount": -0.01},
		):
			with self.subTest(overrides=overrides):
				project = make_customer_project(
					"SYNTHETIC numeric boundary project",
					insert=False,
					**overrides,
				)
				with self.assertRaises(frappe.ValidationError):
					project.insert()

	def test_side_stage_requires_reason(self):
		project = make_customer_project("SYNTHETIC side stage project")
		project.stage = "暂停"
		with self.assertRaises(frappe.ValidationError):
			project.save()

		project.reload()
		project.stage = "暂停"
		project.pause_reason = "SYNTHETIC customer schedule hold"
		project.save()
		self.assertEqual(project.stage, "暂停")
