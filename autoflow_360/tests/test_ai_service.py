from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from autoflow_360.tests.factories import (
	add_project_member,
	make_customer_portal_user,
	make_customer_project,
	make_internal_user,
	make_project_with_risk,
)


VALID_RESULT = {
	"summary": "存在可追溯的项目节点延期风险。",
	"risk_level": "高",
	"actions": [
		{
			"text": "确认恢复计划并更新节点日期",
			"owner_role": "AutoFlow Project Manager",
		}
	],
	"uncertainties": ["供应商最终恢复日期仍需人工确认"],
}


class TestAIService(IntegrationTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		settings = frappe.get_single("AutoFlow Settings")
		settings.ai_enabled = 0
		settings.ai_provider = "Disabled"
		settings.ai_base_url = None
		settings.ai_model = None
		settings.ai_api_key = None
		settings.save()

	@staticmethod
	def _result_with_source(doctype: str, name: str) -> dict:
		return {
			**VALID_RESULT,
			"sources": [{"doctype": doctype, "name": name}],
		}

	def test_analysis_contains_existing_source_records(self):
		from autoflow_360.ai.service import analyze_project

		project = make_project_with_risk()
		with patch("autoflow_360.ai.service.get_provider") as provider:
			provider.return_value.generate.return_value = self._result_with_source(
				"Project Risk",
				project.risk_name,
			)
			name = analyze_project(project.name, "风险摘要")
		analysis = frappe.get_doc("AI Analysis", name)

		self.assertEqual(analysis.status, "成功")
		self.assertEqual(analysis.sources[0].reference_name, project.risk_name)
		self.assertEqual(analysis.requested_by, "Administrator")
		self.assertTrue(analysis.input_hash)
		self.assertNotIn("api_key", analysis.output_json.lower())

	def test_unknown_source_rejects_model_output(self):
		from autoflow_360.ai.service import analyze_project

		project = make_customer_project("SYNTHETIC AI Unknown Source")
		with patch("autoflow_360.ai.service.get_provider") as provider:
			provider.return_value.generate.return_value = self._result_with_source(
				"Sales Order",
				"FAKE-SO-0001",
			)
			name = analyze_project(project.name, "风险摘要")
		analysis = frappe.get_doc("AI Analysis", name)

		self.assertEqual(analysis.status, "降级")
		self.assertEqual(analysis.error_code, "unauthorized_source")
		self.assertEqual(analysis.sources, [])

	def test_provider_failure_does_not_change_business_documents(self):
		from autoflow_360.ai.service import analyze_project

		project = make_customer_project("SYNTHETIC AI Provider Failure")
		before_stage = project.stage
		before_todos = frappe.db.count("ToDo")
		with patch("autoflow_360.ai.service.get_provider") as provider:
			provider.return_value.generate.side_effect = TimeoutError(
				"SYNTHETIC timeout details must not reach users"
			)
			name = analyze_project(project.name, "下一步行动")
		analysis = frappe.get_doc("AI Analysis", name)

		self.assertEqual(analysis.status, "降级")
		self.assertEqual(analysis.error_code, "provider_timeout")
		self.assertNotIn("SYNTHETIC timeout", analysis.error_message)
		self.assertEqual(
			frappe.db.get_value("Customer Project", project.name, "stage"),
			before_stage,
		)
		self.assertEqual(frappe.db.count("ToDo"), before_todos)

	def test_malformed_provider_output_degrades_safely(self):
		from autoflow_360.ai.service import analyze_project

		project = make_customer_project("SYNTHETIC AI Malformed Output")
		with patch("autoflow_360.ai.service.get_provider") as provider:
			provider.return_value.generate.return_value = {"summary": "missing fields"}
			name = analyze_project(project.name, "风险摘要")

		self.assertEqual(
			frappe.db.get_value("AI Analysis", name, "status"),
			"降级",
		)
		self.assertEqual(
			frappe.db.get_value("AI Analysis", name, "error_code"),
			"invalid_schema",
		)

	def test_disabled_provider_returns_auditable_degradation(self):
		from autoflow_360.ai.service import analyze_project

		project = make_customer_project("SYNTHETIC AI Disabled")
		name = analyze_project(project.name, "风险摘要")
		analysis = frappe.get_doc("AI Analysis", name)

		self.assertEqual(analysis.provider, "Disabled")
		self.assertEqual(analysis.status, "降级")
		self.assertEqual(analysis.error_code, "provider_disabled")

	def test_user_cannot_analyze_unreadable_project(self):
		from autoflow_360.ai.service import analyze_project

		project = make_customer_project("SYNTHETIC AI Blocked Project")
		user = make_internal_user("AutoFlow Project Manager")
		frappe.set_user(user.name)

		with self.assertRaises(frappe.PermissionError):
			analyze_project(project.name, "风险摘要")

	def test_customer_portal_cannot_invoke_internal_ai(self):
		from autoflow_360.ai.service import analyze_project

		project = make_customer_project("SYNTHETIC AI Portal Project")
		user = make_customer_portal_user()
		frappe.set_user(user.name)

		with self.assertRaises(frappe.PermissionError):
			analyze_project(project.name, "风险摘要")

	def test_member_context_does_not_include_another_project(self):
		from autoflow_360.ai.service import analyze_project

		user = make_internal_user("AutoFlow Project Manager")
		allowed = make_customer_project("SYNTHETIC AI Allowed Context")
		blocked = make_customer_project("SYNTHETIC AI Secret Context")
		add_project_member(allowed.name, user.name)
		frappe.set_user(user.name)
		with patch("autoflow_360.ai.service.get_provider") as provider:
			provider.return_value.generate.return_value = self._result_with_source(
				"Customer Project",
				allowed.name,
			)
			analyze_project(allowed.name, "风险摘要")

		messages = provider.return_value.generate.call_args.kwargs["messages"]
		serialized_messages = frappe.as_json(messages)
		self.assertIn(allowed.name, serialized_messages)
		self.assertNotIn(blocked.name, serialized_messages)

	def test_audit_fields_cannot_be_changed_directly(self):
		from autoflow_360.ai.service import analyze_project

		project = make_customer_project("SYNTHETIC AI Immutable Audit")
		name = analyze_project(project.name, "风险摘要")
		analysis = frappe.get_doc("AI Analysis", name)
		analysis.status = "成功"

		with self.assertRaises(frappe.ValidationError):
			analysis.save()

	def test_only_requester_can_record_feedback(self):
		from autoflow_360.ai.service import analyze_project

		project = make_customer_project("SYNTHETIC AI Feedback")
		name = analyze_project(project.name, "风险摘要")
		analysis = frappe.get_doc("AI Analysis", name)
		analysis.user_feedback = "有帮助"
		analysis.save()

		other_user = make_internal_user("AutoFlow Executive")
		frappe.set_user(other_user.name)
		analysis = frappe.get_doc("AI Analysis", name)
		analysis.user_feedback = "无帮助"
		with self.assertRaises(frappe.PermissionError):
			analysis.save()

	def test_user_cannot_read_analysis_from_unreadable_project(self):
		from autoflow_360.ai.service import analyze_project

		project = make_customer_project("SYNTHETIC AI Hidden Audit")
		name = analyze_project(project.name, "风险摘要")
		user = make_internal_user("AutoFlow Project Manager")
		frappe.set_user(user.name)

		self.assertFalse(
			frappe.has_permission("AI Analysis", "read", doc=name)
		)

	def test_weekly_generation_is_disabled_by_default(self):
		from autoflow_360.ai.service import generate_weekly_drafts

		make_customer_project("SYNTHETIC AI Weekly Disabled")
		with patch("frappe.enqueue") as enqueue:
			count = generate_weekly_drafts()

		self.assertEqual(count, 0)
		enqueue.assert_not_called()

	def test_weekly_generation_enqueues_when_explicitly_enabled(self):
		from autoflow_360.ai.service import generate_weekly_drafts

		project = make_customer_project("SYNTHETIC AI Weekly Enabled")
		settings = frappe.get_single("AutoFlow Settings")
		settings.ai_enabled = 1
		settings.ai_provider = "OpenAI Compatible"
		settings.ai_base_url = "http://localhost:11434/v1"
		settings.ai_model = "qwen3:8b"
		settings.save()
		with patch("frappe.enqueue") as enqueue:
			count = generate_weekly_drafts()

		self.assertGreaterEqual(count, 1)
		self.assertTrue(
			any(
				call.kwargs.get("project_name") == project.name
				for call in enqueue.call_args_list
			)
		)
