from datetime import timedelta

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate, nowdate

from autoflow_360.services.deal_conversion import create_project_from_deal
from autoflow_360.tests.factories import (
	SYNTHETIC_COMPANY,
	SYNTHETIC_CUSTOMER,
	make_crm_deal,
)


IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Company",
	"Customer",
	"CRM Deal",
	"Currency",
	"User",
]


class TestDealConversion(IntegrationTestCase):
	def _arguments(self, deal_name: str) -> dict:
		return {
			"deal_name": deal_name,
			"company": SYNTHETIC_COMPANY,
			"customer": SYNTHETIC_CUSTOMER,
			"product_family": "SYNTHETIC Interior Material",
			"delivery_date": getdate(nowdate()) + timedelta(days=60),
		}

	def test_repeated_conversion_returns_same_project(self):
		deal = make_crm_deal("SYNTHETIC Automotive Deal")
		arguments = self._arguments(deal.name)

		first = create_project_from_deal(**arguments)
		second = create_project_from_deal(**arguments)

		self.assertEqual(first, second)
		self.assertEqual(
			frappe.db.count("Customer Project", {"crm_deal": deal.name}),
			1,
		)

	def test_deal_fields_are_mapped_to_project(self):
		target_award_date = getdate(nowdate()) + timedelta(days=20)
		deal = make_crm_deal(
			"SYNTHETIC Mapping Deal",
			probability=65,
			expected_deal_value=125000,
			expected_closure_date=target_award_date,
		)

		project_name = create_project_from_deal(**self._arguments(deal.name))
		project = frappe.get_doc("Customer Project", project_name)

		self.assertEqual(project.crm_deal, deal.name)
		self.assertEqual(project.project_name, deal.organization_name)
		self.assertEqual(project.project_manager, deal.deal_owner)
		self.assertEqual(project.probability, 65)
		self.assertEqual(project.expected_amount, 125000)
		self.assertEqual(getdate(project.target_award_date), target_award_date)
		self.assertEqual(project.project_members[0].user, deal.deal_owner)

	def test_required_arguments_are_validated(self):
		deal = make_crm_deal("SYNTHETIC Validation Deal")
		arguments = self._arguments(deal.name)
		arguments["product_family"] = " "

		with self.assertRaises(frappe.ValidationError):
			create_project_from_deal(**arguments)

	def test_invalid_delivery_date_is_rejected(self):
		deal = make_crm_deal("SYNTHETIC Invalid Date Deal")
		arguments = self._arguments(deal.name)
		arguments["delivery_date"] = "not-a-date"

		with self.assertRaises(frappe.ValidationError):
			create_project_from_deal(**arguments)

	def test_crm_deal_client_hook_is_registered(self):
		scripts = frappe.get_hooks("doctype_js").get("CRM Deal", [])

		self.assertIn("public/js/crm_deal.js", scripts)

	def test_missing_deal_permission_is_rejected(self):
		deal = make_crm_deal("SYNTHETIC Protected Deal")
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			create_project_from_deal(**self._arguments(deal.name))
