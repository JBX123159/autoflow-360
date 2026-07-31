import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "autoflow_360"
DOCTYPE_ROOT = APP_ROOT / "autoflow_360" / "doctype"
RECEIPT_ROOT = DOCTYPE_ROOT / "customer_receipt"
DELIVERY_SERVICE = APP_ROOT / "services" / "delivery.py"
PORTAL_API = APP_ROOT / "api" / "portal.py"
PORTAL_PERMISSION = APP_ROOT / "permissions" / "portal.py"
DELIVERY_TEST = APP_ROOT / "tests" / "test_delivery.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class DeliveryContractTest(unittest.TestCase):
    def test_required_model_service_portal_and_tests_exist(self):
        paths = (
            RECEIPT_ROOT / "customer_receipt.json",
            RECEIPT_ROOT / "customer_receipt.py",
            DELIVERY_SERVICE,
            APP_ROOT / "www" / "customer-deliveries.py",
            APP_ROOT / "www" / "customer-deliveries.html",
            APP_ROOT / "templates" / "pages" / "customer_deliveries.html",
            DELIVERY_TEST,
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"缺少文件：{path}")

    def test_receipt_is_unique_attributed_immutable_and_project_linked(self):
        data = load_json(RECEIPT_ROOT / "customer_receipt.json")
        fields = {field["fieldname"]: field for field in data["fields"]}
        controller = (RECEIPT_ROOT / "customer_receipt.py").read_text(
            encoding="utf-8"
        )

        self.assertEqual(data["name"], "Customer Receipt")
        self.assertEqual(fields["delivery_note"]["options"], "Delivery Note")
        self.assertEqual(fields["delivery_note"]["unique"], 1)
        self.assertEqual(fields["customer"]["options"], "Customer")
        self.assertEqual(fields["customer_project"]["options"], "Customer Project")
        self.assertEqual(fields["portal_user"]["options"], "User")
        for fieldname in (
            "delivery_note",
            "customer",
            "customer_project",
            "received_by",
            "received_at",
            "proof_file",
            "portal_user",
        ):
            self.assertEqual(fields[fieldname]["read_only"], 1)
        self.assertIn("from_customer_receipt_service", controller)
        self.assertIn("get_doc_before_save", controller)
        self.assertIn("cannot be changed", controller)

    def test_delivery_service_aggregates_stock_blocks_overdelivery_and_locks(self):
        source = DELIVERY_SERVICE.read_text(encoding="utf-8")

        self.assertIn("def validate_delivery_stock(", source)
        self.assertIn("def confirm_customer_receipt(", source)
        self.assertIn("required_by_stock_key", source)
        self.assertIn("delivered_by_order_item", source)
        self.assertIn("for_update=True", source)
        self.assertIn("filelock", source)
        self.assertIn("actual_qty", source)
        self.assertIn("stock_qty", source)
        self.assertIn("against_sales_order", source)
        self.assertNotIn("frappe.db.commit", source)

    def test_customer_identity_attachment_and_idempotency_are_server_guarded(self):
        source = DELIVERY_SERVICE.read_text(encoding="utf-8")

        self.assertIn("is_customer_portal_user", source)
        self.assertIn("get_customer_names_for_user", source)
        self.assertIn('"owner": frappe.session.user', source)
        self.assertIn('"Customer Receipt"', source)
        self.assertIn('"delivery_note": delivery.name', source)
        self.assertNotIn("allow_guest", source)

    def test_portal_permissions_filter_delivery_and_receipt_rows(self):
        source = PORTAL_PERMISSION.read_text(encoding="utf-8")
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")

        for function_name in (
            "customer_delivery_query",
            "customer_receipt_query",
            "customer_delivery_has_permission",
            "customer_receipt_has_permission",
        ):
            self.assertIn(f"def {function_name}(", source)
        for doctype in ("Delivery Note", "Customer Receipt"):
            self.assertIn(f'"{doctype}"', hooks)
        self.assertIn("permission_query_conditions", hooks)
        self.assertIn("has_permission", hooks)

    def test_portal_api_page_and_hook_cover_the_complete_flow(self):
        api = PORTAL_API.read_text(encoding="utf-8")
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        page = (APP_ROOT / "www" / "customer-deliveries.py").read_text(
            encoding="utf-8"
        )
        template = (
            APP_ROOT / "templates" / "pages" / "customer_deliveries.html"
        ).read_text(encoding="utf-8")

        self.assertIn("def confirm_delivery_receipt(", api)
        self.assertIn('@frappe.whitelist(methods=["POST"])', api)
        self.assertNotIn("allow_guest=True", api)
        self.assertIn('"route": "/customer-deliveries"', hooks)
        for event in ("before_validate", "before_submit", "on_submit"):
            self.assertIn(f'"{event}"', hooks)
        self.assertIn("frappe.get_list", page)
        self.assertIn("get_customer_names_for_user", page)
        self.assertIn(
            "autoflow_360.api.portal.confirm_delivery_receipt",
            template,
        )

    def test_runtime_tests_cover_stock_overdelivery_identity_and_receipt_evidence(self):
        source = DELIVERY_TEST.read_text(encoding="utf-8")
        for test_name in (
            "test_insufficient_stock_blocks_delivery_submission",
            "test_overdelivery_blocks_delivery_submission",
            "test_customer_cannot_confirm_another_customer_delivery",
            "test_receipt_is_idempotent_immutable_and_attributed",
            "test_foreign_proof_file_is_rejected",
            "test_guest_cannot_confirm_delivery",
            "test_customer_delivery_list_isolated_by_customer",
        ):
            self.assertIn(test_name, source)
        self.assertIn("IntegrationTestCase", source)
        self.assertIn("SYNTHETIC", source)


if __name__ == "__main__":
    unittest.main()
