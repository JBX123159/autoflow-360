import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "autoflow_360"
AI = APP / "ai"
ANALYSIS = APP / "autoflow_360" / "doctype" / "ai_analysis"
SOURCE = APP / "autoflow_360" / "doctype" / "ai_source_reference"
RUNTIME_TEST = APP / "tests" / "test_ai_service.py"


class TestAIServiceContract(unittest.TestCase):
    def test_ai_modules_models_api_and_runtime_tests_exist(self):
        paths = (
            ANALYSIS / "ai_analysis.json",
            ANALYSIS / "ai_analysis.py",
            SOURCE / "ai_source_reference.json",
            AI / "schemas.py",
            AI / "context_builder.py",
            AI / "audit.py",
            AI / "service.py",
            AI / "providers" / "base.py",
            AI / "providers" / "disabled.py",
            AI / "providers" / "openai_compatible.py",
            APP / "api" / "analytics.py",
            RUNTIME_TEST,
        )
        for path in paths:
            self.assertTrue(path.exists(), str(path))
            if path.suffix == ".py":
                ast.parse(path.read_text(encoding="utf-8"))

    def test_analysis_model_contains_trace_and_feedback_fields(self):
        model = json.loads((ANALYSIS / "ai_analysis.json").read_text(encoding="utf-8"))
        fields = {field["fieldname"]: field for field in model["fields"]}
        required = {
            "customer_project",
            "analysis_type",
            "requested_by",
            "requested_at",
            "provider",
            "model",
            "prompt_version",
            "input_hash",
            "status",
            "output_json",
            "display_text",
            "latency_ms",
            "error_code",
            "error_message",
            "sources",
            "adopted",
            "user_revision",
            "user_feedback",
        }
        self.assertTrue(required.issubset(fields))
        for fieldname in required - {"adopted", "user_revision", "user_feedback"}:
            self.assertEqual(fields[fieldname].get("read_only"), 1, fieldname)

    def test_controller_protects_audit_fields_and_deletion(self):
        source = (ANALYSIS / "ai_analysis.py").read_text(encoding="utf-8")
        self.assertIn("from_ai_service", source)
        self.assertIn("IMMUTABLE_AUDIT_FIELDS", source)
        self.assertIn("requested_by", source)
        self.assertIn("get_doc_before_save", source)
        self.assertIn("on_trash", source)

    def test_context_is_permission_checked_and_minimized(self):
        source = (AI / "context_builder.py").read_text(encoding="utf-8")
        self.assertIn('project.check_permission("read")', source)
        self.assertIn("frappe.get_list", source)
        self.assertNotIn("frappe.get_all", source)
        self.assertIn("allowed_sources", source)
        self.assertIn("Project Risk", source)
        self.assertIn("Business Exception", source)
        self.assertIn("Sample Request", source)

    def test_service_validates_sources_and_never_writes_business_docs(self):
        source = (AI / "service.py").read_text(encoding="utf-8")
        self.assertIn("validate_result_sources", source)
        self.assertIn("parse_ai_result", source)
        self.assertIn("input_hash", source)
        self.assertIn('analysis.status = "降级"', source)
        self.assertNotIn("ignore_permissions=True", source)
        self.assertNotIn("frappe.db.commit", source)
        self.assertNotIn("project.save", source)

    def test_provider_maps_network_errors_without_exposing_key(self):
        source = (AI / "providers" / "openai_compatible.py").read_text(encoding="utf-8")
        self.assertIn("requests.Timeout", source)
        self.assertIn("requests.ConnectionError", source)
        self.assertIn("429", source)
        self.assertIn("response_format", source)
        self.assertNotIn("print(", source)

    def test_api_is_post_only_and_scheduler_is_opt_in(self):
        api = (APP / "api" / "analytics.py").read_text(encoding="utf-8")
        hooks = (APP / "hooks.py").read_text(encoding="utf-8")
        self.assertIn('methods=["POST"]', api)
        self.assertIn("analyze_project", api)
        self.assertIn("weekly_long", hooks)
        self.assertIn("generate_weekly_drafts", hooks)

    def test_runtime_suite_covers_security_degradation_and_audit(self):
        source = RUNTIME_TEST.read_text(encoding="utf-8")
        for test_name in (
            "test_analysis_contains_existing_source_records",
            "test_unknown_source_rejects_model_output",
            "test_provider_failure_does_not_change_business_documents",
            "test_user_cannot_analyze_unreadable_project",
            "test_customer_portal_cannot_invoke_internal_ai",
            "test_audit_fields_cannot_be_changed_directly",
            "test_weekly_generation_is_disabled_by_default",
        ):
            self.assertIn(test_name, source)


if __name__ == "__main__":
    unittest.main()
