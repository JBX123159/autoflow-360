import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "autoflow_360"
DOCTYPE_ROOT = APP_ROOT / "autoflow_360" / "doctype"
SAMPLE_ROOT = DOCTYPE_ROOT / "sample_request"
FEEDBACK_ROOT = DOCTYPE_ROOT / "customer_feedback"
SAMPLE_ITEM_ROOT = DOCTYPE_ROOT / "sample_item"
SERVICE_PATH = APP_ROOT / "services" / "sample_workflow.py"
PORTAL_API_PATH = APP_ROOT / "api" / "portal.py"
PORTAL_PERMISSION_PATH = APP_ROOT / "permissions" / "portal.py"
PORTAL_PAGE_PATH = APP_ROOT / "www" / "customer-samples.py"
PORTAL_HTML_PATH = APP_ROOT / "www" / "customer-samples.html"
PORTAL_TEMPLATE_PATH = APP_ROOT / "templates" / "pages" / "customer_samples.html"
RUNTIME_TEST_PATH = SAMPLE_ROOT / "test_sample_request.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class SampleWorkflowContractTest(unittest.TestCase):
    def test_required_models_services_portal_and_tests_exist(self):
        paths = (
            SAMPLE_ITEM_ROOT / "sample_item.json",
            SAMPLE_ROOT / "sample_request.json",
            SAMPLE_ROOT / "sample_request.py",
            FEEDBACK_ROOT / "customer_feedback.json",
            FEEDBACK_ROOT / "customer_feedback.py",
            SERVICE_PATH,
            PORTAL_API_PATH,
            PORTAL_PERMISSION_PATH,
            PORTAL_PAGE_PATH,
            PORTAL_HTML_PATH,
            PORTAL_TEMPLATE_PATH,
            RUNTIME_TEST_PATH,
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"缺少文件：{path}")

    def test_sample_item_is_a_required_inspection_child_table(self):
        data = load_json(SAMPLE_ITEM_ROOT / "sample_item.json")
        fields = {field["fieldname"]: field for field in data["fields"]}

        self.assertEqual(data["name"], "Sample Item")
        self.assertEqual(data["istable"], 1)
        self.assertEqual(data["permissions"], [])
        self.assertEqual(
            tuple(fields),
            (
                "item_code",
                "quantity",
                "uom",
                "specification",
                "batch_no",
                "inspection_result",
                "inspection_notes",
            ),
        )
        self.assertEqual(fields["item_code"]["options"], "Item")
        self.assertEqual(fields["uom"]["options"], "UOM")
        self.assertEqual(fields["inspection_result"]["options"], "待检验\n通过\n不通过")

    def test_sample_request_has_stable_round_dispatch_and_feedback_fields(self):
        data = load_json(SAMPLE_ROOT / "sample_request.json")
        fields = {field["fieldname"]: field for field in data["fields"]}
        expected = {
            "customer_project": ("Link", "Customer Project"),
            "round_number": ("Int", None),
            "previous_sample_request": ("Link", "Sample Request"),
            "purpose": ("Data", None),
            "required_date": ("Date", None),
            "customer_contact": ("Link", "Contact"),
            "status": ("Select", None),
            "inspection_status": ("Select", None),
            "items": ("Table", "Sample Item"),
            "carrier": ("Data", None),
            "tracking_number": ("Data", None),
            "dispatch_time": ("Datetime", None),
            "feedback": ("Link", "Customer Feedback"),
        }

        self.assertEqual(data["name"], "Sample Request")
        self.assertEqual(data["autoname"], "naming_series:")
        for fieldname, (fieldtype, options) in expected.items():
            with self.subTest(fieldname=fieldname):
                self.assertEqual(fields[fieldname]["fieldtype"], fieldtype)
                if options:
                    self.assertEqual(fields[fieldname]["options"], options)
        self.assertEqual(
            fields["status"]["options"],
            "草稿\n待审批\n制作中\n检验中\n已发出\n等待反馈\n客户认可\n重新打样\n拒绝",
        )
        self.assertEqual(fields["previous_sample_request"]["unique"], 1)

    def test_feedback_is_unique_append_only_and_attributed(self):
        data = load_json(FEEDBACK_ROOT / "customer_feedback.json")
        fields = {field["fieldname"]: field for field in data["fields"]}
        controller = (FEEDBACK_ROOT / "customer_feedback.py").read_text(
            encoding="utf-8"
        )

        self.assertEqual(data["name"], "Customer Feedback")
        self.assertEqual(fields["sample_request"]["unique"], 1)
        self.assertEqual(fields["decision"]["options"], "客户认可\n重新打样\n拒绝")
        self.assertEqual(fields["submitted_by"]["options"], "User")
        self.assertEqual(fields["submitted_by"]["read_only"], 1)
        self.assertEqual(fields["submitted_at"]["read_only"], 1)
        self.assertIn("get_doc_before_save", controller)
        self.assertIn("cannot be changed", controller)

    def test_service_enforces_inspection_permission_and_concurrency_guards(self):
        source = SERVICE_PATH.read_text(encoding="utf-8")

        self.assertIn('sample.check_permission("write")', source)
        self.assertIn('sample.inspection_status != "通过"', source)
        self.assertIn('item.inspection_result != "通过"', source)
        self.assertIn("filelock", source)
        self.assertIn("for_update=True", source)
        self.assertIn('"Customer Feedback"', source)
        self.assertIn('"previous_sample_request": previous.name', source)
        self.assertNotIn("frappe.db.commit", source)

    def test_portal_api_checks_customer_membership_before_posting(self):
        permission_source = PORTAL_PERMISSION_PATH.read_text(encoding="utf-8")
        api_source = PORTAL_API_PATH.read_text(encoding="utf-8")

        self.assertIn('parenttype": "Customer"', permission_source)
        self.assertIn('user == "Guest"', permission_source)
        self.assertIn("can_access_customer_project", api_source)
        self.assertIn('@frappe.whitelist(methods=["POST"])', api_source)
        self.assertIn("record_customer_feedback", api_source)
        self.assertNotIn("allow_guest=True", api_source)

    def test_portal_page_and_hook_are_registered(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        page = PORTAL_PAGE_PATH.read_text(encoding="utf-8")
        template = PORTAL_TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn("portal_menu_items", hooks)
        self.assertIn('"route": "/customer-samples"', hooks)
        self.assertIn('"role": "AutoFlow Customer Portal"', hooks)
        self.assertIn("get_customer_names_for_user", page)
        self.assertIn("autoflow_360.api.portal.submit_sample_feedback", template)

    def test_runtime_tests_cover_dispatch_feedback_resample_and_portal_boundary(self):
        source = RUNTIME_TEST_PATH.read_text(encoding="utf-8")
        for test_name in (
            "test_new_sample_advances_customer_project_stage",
            "test_uninspected_sample_cannot_be_dispatched",
            "test_failed_item_cannot_be_dispatched",
            "test_feedback_is_append_only",
            "test_resample_links_previous_round",
            "test_guest_cannot_record_feedback",
            "test_customer_portal_membership_controls_project_access",
            "test_linked_portal_user_can_record_feedback",
            "test_portal_template_renders_empty_state",
        ):
            self.assertIn(test_name, source)
        self.assertIn("IntegrationTestCase", source)
        self.assertIn("SYNTHETIC", source)


if __name__ == "__main__":
    unittest.main()
