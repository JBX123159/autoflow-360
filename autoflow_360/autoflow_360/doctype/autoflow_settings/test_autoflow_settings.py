import frappe
from frappe.tests.utils import FrappeTestCase

from autoflow_360.autoflow_360.doctype.autoflow_settings.autoflow_settings import (
	AutoFlowSettings,
)
from autoflow_360.install import after_install
from autoflow_360.setup.custom_fields import PROJECT_LINK_DOCTYPES
from autoflow_360.setup.roles import ROLES


def make_settings(**overrides) -> AutoFlowSettings:
	values = {
		"doctype": "AutoFlow Settings",
		"feedback_warning_days": 3,
		"quotation_expiry_warning_days": 7,
		"project_inactive_days": 7,
		"high_risk_score": 70,
		"ai_enabled": 0,
		"ai_provider": "Disabled",
		"ai_base_url": "",
		"ai_model": "",
	}
	values.update(overrides)
	return AutoFlowSettings(values)


class TestAutoFlowSettings(FrappeTestCase):
	def test_required_roles_and_custom_fields_exist(self):
		for role in ROLES:
			self.assertTrue(frappe.db.exists("Role", role), role)

		for doctype in PROJECT_LINK_DOCTYPES:
			self.assertTrue(
				frappe.get_meta(doctype).has_field("custom_customer_project"),
				doctype,
			)

	def test_installation_is_idempotent(self):
		after_install()
		after_install()

		for role in ROLES:
			self.assertEqual(frappe.db.count("Role", {"name": role}), 1, role)
			expected_desk_access = 0 if role.endswith(" Portal") else 1
			self.assertEqual(
				frappe.db.get_value("Role", role, "desk_access"),
				expected_desk_access,
				role,
			)

		for doctype in PROJECT_LINK_DOCTYPES:
			self.assertEqual(
				frappe.db.count(
					"Custom Field",
					{
						"dt": doctype,
						"fieldname": "custom_customer_project",
					},
				),
				1,
				doctype,
			)

	def test_positive_day_settings_are_required(self):
		for fieldname in (
			"feedback_warning_days",
			"quotation_expiry_warning_days",
			"project_inactive_days",
		):
			settings = make_settings(**{fieldname: 0})
			with self.subTest(fieldname=fieldname), self.assertRaises(
				frappe.ValidationError
			):
				settings.validate()

	def test_high_risk_score_must_be_between_one_and_one_hundred(self):
		for score in (0, 101):
			with self.subTest(score=score), self.assertRaises(
				frappe.ValidationError
			):
				make_settings(high_risk_score=score).validate()

	def test_enabled_ai_requires_provider_model_and_base_url(self):
		for overrides in (
			{
				"ai_enabled": 1,
				"ai_provider": "Disabled",
				"ai_model": "qwen",
				"ai_base_url": "http://localhost:11434/v1",
			},
			{
				"ai_enabled": 1,
				"ai_provider": "OpenAI Compatible",
				"ai_model": "",
				"ai_base_url": "http://localhost:11434/v1",
			},
			{
				"ai_enabled": 1,
				"ai_provider": "OpenAI Compatible",
				"ai_model": "qwen",
				"ai_base_url": "",
			},
		):
			with self.subTest(overrides=overrides), self.assertRaises(
				frappe.ValidationError
			):
				make_settings(**overrides).validate()

	def test_valid_free_local_ai_configuration_is_accepted(self):
		make_settings(
			ai_enabled=1,
			ai_provider="OpenAI Compatible",
			ai_model="qwen",
			ai_base_url="http://localhost:11434/v1",
		).validate()
