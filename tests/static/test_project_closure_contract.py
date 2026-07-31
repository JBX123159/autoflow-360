from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "autoflow_360"
CLOSURE_SERVICE = APP_ROOT / "services" / "project_closure.py"
PROJECT_API = APP_ROOT / "api" / "project.py"
PROJECT_CONTROLLER = (
    APP_ROOT
    / "autoflow_360"
    / "doctype"
    / "customer_project"
    / "customer_project.py"
)
CLOSURE_SCRIPT = APP_ROOT / "public" / "js" / "customer_project.js"
CLOSURE_TEST = APP_ROOT / "tests" / "test_project_closure.py"


class ProjectClosureContractTest(unittest.TestCase):
    def test_service_script_and_runtime_tests_exist(self):
        for path in (CLOSURE_SERVICE, CLOSURE_SCRIPT, CLOSURE_TEST):
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"缺少文件：{path}")

    def test_closure_gaps_cover_complete_business_evidence(self):
        source = CLOSURE_SERVICE.read_text(encoding="utf-8")

        self.assertIn("class ClosureGap", source)
        self.assertIn("def get_closure_gaps(", source)
        for code in (
            "NO_SALES_ORDER",
            "DELIVERY_INCOMPLETE",
            "BILLING_INCOMPLETE",
            "CUSTOMER_RECEIPT_MISSING",
            "NO_SALES_INVOICE",
            "UNPAID_RECEIVABLE",
            "PAYMENT_EVIDENCE_MISSING",
            "OPEN_HIGH_EXCEPTION",
        ):
            self.assertIn(code, source)

    def test_closure_and_request_are_locked_idempotent_and_snapshot_bound(self):
        source = CLOSURE_SERVICE.read_text(encoding="utf-8")

        for function_name in (
            "create_project_closure_request",
            "has_approved_closure_request",
            "close_project",
            "build_project_closure_snapshot",
        ):
            self.assertIn(f"def {function_name}(", source)
        self.assertIn("filelock", source)
        self.assertIn("for_update=True", source)
        self.assertIn("fingerprint", source)
        self.assertIn('"approval_type": CLOSURE_APPROVAL_TYPE', source)
        self.assertIn("def prevent_closed_project_evidence_change(", source)
        self.assertNotIn("frappe.db.commit", source)

    def test_project_model_blocks_direct_closure_and_summary_mutation(self):
        source = PROJECT_CONTROLLER.read_text(encoding="utf-8")

        self.assertIn("from_project_closure_service", source)
        self.assertIn("cannot be closed directly", source)
        self.assertIn("Closure summary cannot be changed", source)

    def test_customer_project_approval_uses_closure_snapshot(self):
        source = (APP_ROOT / "services" / "sales_conversion.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('source.doctype == "Customer Project"', source)
        self.assertIn("build_project_closure_snapshot", source)

    def test_project_api_exposes_read_status_and_post_only_mutations(self):
        source = PROJECT_API.read_text(encoding="utf-8")

        for function_name in (
            "get_project_closure_status",
            "request_project_closure",
            "finalize_project_closure",
        ):
            self.assertIn(f"def {function_name}(", source)
        self.assertIn('@frappe.whitelist(methods=["GET"])', source)
        self.assertGreaterEqual(
            source.count('@frappe.whitelist(methods=["POST"])'),
            3,
        )
        self.assertNotIn("allow_guest=True", source)

    def test_desk_script_shows_gaps_before_request_or_closure(self):
        source = CLOSURE_SCRIPT.read_text(encoding="utf-8")
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")

        self.assertIn("get_project_closure_status", source)
        self.assertIn("request_project_closure", source)
        self.assertIn("finalize_project_closure", source)
        self.assertIn("closure_summary", source)
        self.assertIn('"Customer Project": "public/js/customer_project.js"', hooks)

    def test_runtime_tests_cover_gaps_approval_staleness_and_immutability(self):
        source = CLOSURE_TEST.read_text(encoding="utf-8")
        for test_name in (
            "test_missing_sales_order_is_explained",
            "test_missing_customer_receipt_blocks_closure",
            "test_unpaid_invoice_blocks_closure",
            "test_zero_outstanding_without_payment_entry_is_not_enough",
            "test_approval_is_required_after_all_evidence",
            "test_repeated_closure_request_reuses_pending_snapshot",
            "test_changed_evidence_invalidates_approval",
            "test_direct_stage_change_cannot_bypass_service",
            "test_complete_evidence_and_approval_allow_idempotent_closure",
            "test_closed_project_payment_evidence_cannot_be_cancelled",
            "test_closure_summary_is_immutable",
        ):
            self.assertIn(test_name, source)
        self.assertIn("IntegrationTestCase", source)
        self.assertIn("SYNTHETIC", source)


if __name__ == "__main__":
    unittest.main()
