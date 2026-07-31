import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "autoflow_360"
RISK_ROOT = APP_ROOT / "autoflow_360" / "doctype" / "project_risk"
ENGINE_ROOT = APP_ROOT / "risk_engine"
RISK_TEST = APP_ROOT / "tests" / "test_risk_engine.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class RiskEngineContractTest(unittest.TestCase):
    def test_model_engine_scheduler_and_runtime_tests_exist(self):
        paths = (
            RISK_ROOT / "project_risk.json",
            RISK_ROOT / "project_risk.py",
            ENGINE_ROOT / "types.py",
            ENGINE_ROOT / "rules.py",
            ENGINE_ROOT / "service.py",
            ENGINE_ROOT / "scheduled.py",
            RISK_TEST,
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"缺少文件：{path}")

    def test_project_risk_has_unique_evidence_and_verification_fields(self):
        data = load_json(RISK_ROOT / "project_risk.json")
        fields = {field["fieldname"]: field for field in data["fields"]}

        self.assertEqual(data["name"], "Project Risk")
        self.assertEqual(fields["customer_project"]["options"], "Customer Project")
        self.assertEqual(fields["risk_level"]["options"], "低\n中\n高")
        self.assertEqual(fields["reference_name"]["options"], "reference_doctype")
        self.assertEqual(fields["rule_inputs"]["fieldtype"], "JSON")
        self.assertEqual(fields["rule_inputs"]["read_only"], 1)
        self.assertEqual(fields["deduplication_key"]["unique"], 1)
        for fieldname in ("resolved_at", "verified_by"):
            self.assertEqual(fields[fieldname]["read_only"], 1)

    def test_finding_is_frozen_and_contains_explainable_evidence(self):
        source = (ENGINE_ROOT / "types.py").read_text(encoding="utf-8")

        self.assertIn("@dataclass(frozen=True, slots=True)", source)
        for fieldname in (
            "rule_code",
            "risk_type",
            "level",
            "title",
            "description",
            "reference_doctype",
            "reference_name",
            "inputs",
            "owner_user",
            "due_date",
        ):
            self.assertIn(f"{fieldname}:", source)

    def test_rule_registry_contains_exact_eight_read_only_rules(self):
        source = (ENGINE_ROOT / "rules.py").read_text(encoding="utf-8")
        expected = (
            "find_overdue_milestones",
            "find_pending_sample_feedback",
            "find_quotation_expiry",
            "find_stock_delivery_gap",
            "find_supplier_delay",
            "find_open_high_exceptions",
            "find_overdue_receivables",
            "find_inactive_project",
        )
        for function_name in expected:
            self.assertIn(f"def {function_name}(", source)
        registry = source[source.index("RULES = (") :]
        for function_name in expected:
            self.assertIn(function_name, registry)
        self.assertNotIn("insert(", source)
        self.assertNotIn("db.set_value", source)

    def test_service_locks_validates_upserts_reopens_and_marks_stale(self):
        source = (ENGINE_ROOT / "service.py").read_text(encoding="utf-8")

        for function_name in ("evaluate_project", "make_risk_key", "upsert_risks"):
            self.assertIn(f"def {function_name}(", source)
        self.assertIn("filelock", source)
        self.assertIn("for_update=True", source)
        self.assertIn("deduplication_key", source)
        self.assertIn('"待验证"', source)
        self.assertIn('"已发现"', source)
        self.assertIn("overall_risk_level", source)
        self.assertNotIn("frappe.db.commit", source)

    def test_risk_controller_guards_evidence_and_status_values(self):
        source = (RISK_ROOT / "project_risk.py").read_text(encoding="utf-8")

        self.assertIn("ALLOWED_RISK_LEVELS", source)
        self.assertIn("ALLOWED_STATUSES", source)
        self.assertIn("from_risk_engine", source)
        self.assertIn("rule_inputs", source)
        self.assertIn("deduplication_key", source)

    def test_hourly_and_daily_schedulers_are_registered(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        scheduled = (ENGINE_ROOT / "scheduled.py").read_text(encoding="utf-8")

        self.assertIn("scheduler_events", hooks)
        self.assertIn("scan_delivery_risks", hooks)
        self.assertIn("scan_daily_risks", hooks)
        self.assertIn("def _scan_active_projects(", scheduled)
        self.assertIn('"已结项"', scheduled)
        self.assertIn('"失败"', scheduled)
        self.assertIn('"取消"', scheduled)

    def test_runtime_tests_cover_rules_evidence_dedup_stale_and_reopen(self):
        source = RISK_TEST.read_text(encoding="utf-8")
        for test_name in (
            "test_supplier_eta_after_delivery_is_high_risk",
            "test_overdue_milestone_has_exact_evidence",
            "test_pending_sample_feedback_is_detected",
            "test_quotation_expiry_is_detected",
            "test_stock_gap_is_explained",
            "test_overdue_receivable_evidence_is_persisted",
            "test_inactive_project_is_detected",
            "test_repeated_scan_does_not_duplicate_open_risk",
            "test_scheduler_scans_active_projects_and_updates_overall_level",
            "test_changed_finding_updates_existing_risk",
            "test_stale_risk_moves_to_verification",
            "test_closed_risk_reopens_without_duplicate",
        ):
            self.assertIn(test_name, source)
        self.assertIn("IntegrationTestCase", source)
        self.assertIn("SYNTHETIC", source)


if __name__ == "__main__":
    unittest.main()
