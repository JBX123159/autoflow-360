import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "autoflow_360"
DOCTYPE_ROOT = APP_ROOT / "autoflow_360" / "doctype"
RULE_ROOT = DOCTYPE_ROOT / "autoflow_approval_rule"
REQUEST_ROOT = DOCTYPE_ROOT / "autoflow_approval_request"
SERVICE_PATH = APP_ROOT / "services" / "sales_conversion.py"
WORKFLOW_PATH = APP_ROOT / "setup" / "workflows.py"
API_PATH = APP_ROOT / "api" / "sales.py"
RUNTIME_TEST_PATH = REQUEST_ROOT / "test_sales_conversion.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class SalesConversionContractTest(unittest.TestCase):
    def test_approval_models_service_workflow_api_and_tests_exist(self):
        paths = (
            RULE_ROOT / "autoflow_approval_rule.json",
            RULE_ROOT / "autoflow_approval_rule.py",
            REQUEST_ROOT / "autoflow_approval_request.json",
            REQUEST_ROOT / "autoflow_approval_request.py",
            SERVICE_PATH,
            WORKFLOW_PATH,
            API_PATH,
            APP_ROOT / "public" / "js" / "quotation.js",
            APP_ROOT / "public" / "js" / "sales_order.js",
            RUNTIME_TEST_PATH,
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"缺少文件：{path}")

    def test_approval_rule_has_explicit_authority_boundaries(self):
        data = load_json(RULE_ROOT / "autoflow_approval_rule.json")
        fields = {field["fieldname"]: field for field in data["fields"]}

        self.assertEqual(data["name"], "AutoFlow Approval Rule")
        self.assertEqual(fields["company"]["options"], "Company")
        self.assertEqual(fields["role"]["options"], "Role")
        self.assertEqual(fields["amount_limit"]["non_negative"], 1)
        self.assertEqual(fields["discount_limit"]["non_negative"], 1)
        self.assertEqual(fields["risk_level"]["options"], "低\n中\n高")
        self.assertEqual(fields["active"]["default"], "1")

    def test_approval_request_is_a_submittable_immutable_audit_record(self):
        data = load_json(REQUEST_ROOT / "autoflow_approval_request.json")
        fields = {field["fieldname"]: field for field in data["fields"]}
        controller = (REQUEST_ROOT / "autoflow_approval_request.py").read_text(
            encoding="utf-8"
        )

        self.assertEqual(data["is_submittable"], 1)
        self.assertEqual(fields["reference_name"]["fieldtype"], "Dynamic Link")
        self.assertEqual(fields["reference_name"]["options"], "reference_doctype")
        self.assertEqual(fields["request_snapshot"]["fieldtype"], "JSON")
        for fieldname in (
            "requested_by",
            "requested_at",
            "status",
            "approver",
            "decision_at",
            "request_snapshot",
        ):
            self.assertEqual(fields[fieldname]["read_only"], 1, fieldname)

        self.assertNotIn("user: str", controller)
        self.assertIn("frappe.session.user", controller)
        self.assertIn("get_doc_before_save", controller)
        self.assertIn("request_snapshot", controller)
        self.assertIn("requested_by", controller)

    def test_sales_service_guards_quote_and_idempotent_order_creation(self):
        source = SERVICE_PATH.read_text(encoding="utf-8")

        self.assertIn('status": "客户认可"', source)
        self.assertIn("valid_till", source)
        self.assertIn("custom_customer_confirmed", source)
        self.assertIn("custom_floor_rate", source)
        self.assertIn("filelock", source)
        self.assertIn("for_update=True", source)
        self.assertIn("custom_source_quotation", source)
        self.assertIn("make_sales_order", source)
        self.assertNotIn("frappe.db.commit", source)

    def test_workflows_separate_sample_approval_from_business_status(self):
        source = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn('"Sample Request",\n\t\t"approval_status"', source)
        self.assertIn('"AutoFlow Approval Request",\n\t\t"status"', source)
        self.assertIn('"allow_self_approval": 0', source)
        self.assertIn("Workflow State", source)
        self.assertIn("Workflow Action Master", source)

    def test_post_only_api_and_hooks_are_registered(self):
        api_source = API_PATH.read_text(encoding="utf-8")
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")

        self.assertGreaterEqual(
            api_source.count('@frappe.whitelist(methods=["POST"])'),
            2,
        )
        self.assertNotIn("allow_guest=True", api_source)
        self.assertIn('"Quotation": "public/js/quotation.js"', hooks)
        self.assertIn('"Sales Order": "public/js/sales_order.js"', hooks)
        self.assertIn("validate_quotation_submission", hooks)

    def test_runtime_tests_cover_required_security_and_conversion_cases(self):
        source = RUNTIME_TEST_PATH.read_text(encoding="utf-8")
        for test_name in (
            "test_unapproved_sample_blocks_quotation_submission",
            "test_over_limit_quote_without_approval_cannot_submit",
            "test_expired_submitted_quotation_cannot_convert",
            "test_repeated_conversion_creates_one_sales_order",
            "test_unconfirmed_quotation_cannot_convert",
            "test_requester_cannot_approve_own_request",
            "test_other_user_cannot_be_impersonated_for_approval",
            "test_unconfigured_user_cannot_bypass_rule_through_workflow",
            "test_terminal_approval_status_cannot_be_saved_as_draft",
            "test_sample_workflow_keeps_business_status_separate",
            "test_changed_quotation_invalidates_approval_snapshot",
            "test_approved_unchanged_quote_can_submit",
        ):
            self.assertIn(test_name, source)
        self.assertIn("IntegrationTestCase", source)
        self.assertIn("SYNTHETIC", source)


if __name__ == "__main__":
    unittest.main()
