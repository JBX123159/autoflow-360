import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "autoflow_360"
DOCTYPE_ROOT = APP_ROOT / "autoflow_360" / "doctype"
EXCEPTION_ROOT = DOCTYPE_ROOT / "business_exception"
ACTION_ROOT = DOCTYPE_ROOT / "corrective_action"
WORKFLOW_SERVICE = APP_ROOT / "services" / "exception_workflow.py"
EXCEPTION_API = APP_ROOT / "api" / "exception.py"
EXCEPTION_SCRIPT = APP_ROOT / "public" / "js" / "business_exception.js"
EXCEPTION_TEST = APP_ROOT / "tests" / "test_exception_workflow.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ExceptionWorkflowContractTest(unittest.TestCase):
    def test_models_service_api_script_and_runtime_tests_exist(self):
        paths = (
            EXCEPTION_ROOT / "business_exception.json",
            EXCEPTION_ROOT / "business_exception.py",
            ACTION_ROOT / "corrective_action.json",
            ACTION_ROOT / "corrective_action.py",
            WORKFLOW_SERVICE,
            EXCEPTION_API,
            EXCEPTION_SCRIPT,
            EXCEPTION_TEST,
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"缺少文件：{path}")

    def test_exception_model_contains_source_audit_workflow_and_verification(self):
        data = load_json(EXCEPTION_ROOT / "business_exception.json")
        fields = {field["fieldname"]: field for field in data["fields"]}

        self.assertEqual(data["name"], "Business Exception")
        self.assertEqual(fields["customer_project"]["options"], "Customer Project")
        self.assertEqual(fields["reference_name"]["options"], "reference_doctype")
        self.assertEqual(fields["actions"]["options"], "Corrective Action")
        for fieldname in ("raised_by", "raised_at", "verified_by", "verified_at"):
            self.assertEqual(fields[fieldname]["read_only"], 1)
        self.assertIn("已发现", fields["status"]["options"])
        self.assertIn("已关闭", fields["status"]["options"])

    def test_corrective_action_requires_owner_due_date_status_and_evidence(self):
        data = load_json(ACTION_ROOT / "corrective_action.json")
        fields = {field["fieldname"]: field for field in data["fields"]}

        for fieldname in ("action", "owner_user", "due_date", "status"):
            self.assertEqual(fields[fieldname]["reqd"], 1)
        self.assertEqual(fields["owner_user"]["options"], "User")
        self.assertIn("已完成", fields["status"]["options"])
        self.assertEqual(fields["completed_at"]["read_only"], 1)

    def test_controllers_block_direct_status_audit_changes_and_deletion(self):
        exception = (EXCEPTION_ROOT / "business_exception.py").read_text(
            encoding="utf-8"
        )
        action = (ACTION_ROOT / "corrective_action.py").read_text(encoding="utf-8")

        self.assertIn("from_exception_workflow", exception)
        self.assertIn("cannot be changed directly", exception)
        self.assertIn("cannot be deleted", exception)
        self.assertIn("completed_at", action)
        self.assertIn("evidence", action)

    def test_service_uses_adjacent_transitions_locks_and_private_owned_files(self):
        source = WORKFLOW_SERVICE.read_text(encoding="utf-8")

        self.assertIn("TRANSITIONS = {", source)
        self.assertIn("def transition_exception(", source)
        self.assertIn("filelock", source)
        self.assertIn("for_update=True", source)
        self.assertIn('"owner": frappe.session.user', source)
        self.assertIn('"is_private": 1', source)
        self.assertIn("root_cause", source)
        self.assertIn("corrective actions", source)
        self.assertNotIn("frappe.db.commit", source)

    def test_high_risk_verifier_must_be_independent(self):
        source = WORKFLOW_SERVICE.read_text(encoding="utf-8")

        self.assertIn("raised_by", source)
        self.assertIn("responsible_user", source)
        self.assertIn("owner_user", source)
        self.assertIn("Independent verification", source)

    def test_post_api_and_desk_buttons_use_guarded_service(self):
        api = EXCEPTION_API.read_text(encoding="utf-8")
        script = EXCEPTION_SCRIPT.read_text(encoding="utf-8")
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")

        self.assertIn('@frappe.whitelist(methods=["POST"])', api)
        self.assertIn("def change_exception_status(", api)
        self.assertNotIn("allow_guest=True", api)
        self.assertIn("change_exception_status", script)
        self.assertIn("verification_evidence", script)
        self.assertIn('"Business Exception": "public/js/business_exception.js"', hooks)

    def test_runtime_tests_cover_sequence_evidence_independence_and_integration(self):
        source = EXCEPTION_TEST.read_text(encoding="utf-8")
        for test_name in (
            "test_status_cannot_be_changed_directly",
            "test_exception_cannot_skip_root_cause",
            "test_assignment_requires_responsible_owner",
            "test_pending_verification_requires_completed_actions_and_evidence",
            "test_high_risk_creator_cannot_verify_own_exception",
            "test_high_risk_responsible_user_cannot_verify_own_work",
            "test_foreign_verification_file_is_rejected",
            "test_independent_verifier_closes_with_audit_evidence",
            "test_cancellation_requires_reason_and_is_idempotent",
            "test_guest_cannot_transition_exception",
            "test_open_high_exception_blocks_project_and_creates_risk",
            "test_closed_high_exception_no_longer_blocks_project",
        ):
            self.assertIn(test_name, source)
        self.assertIn("IntegrationTestCase", source)
        self.assertIn("SYNTHETIC", source)


if __name__ == "__main__":
    unittest.main()
