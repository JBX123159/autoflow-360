import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "autoflow_360"
DOCTYPE_ROOT = APP_ROOT / "autoflow_360" / "doctype"
PLAN_ROOT = DOCTYPE_ROOT / "project_material_plan"
ITEM_ROOT = DOCTYPE_ROOT / "project_material_plan_item"
SERVICE_PATH = APP_ROOT / "services" / "material_planning.py"
API_PATH = APP_ROOT / "api" / "material.py"
RUNTIME_TEST_PATH = APP_ROOT / "tests" / "test_material_planning.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class MaterialPlanningContractTest(unittest.TestCase):
    def test_models_service_api_and_runtime_tests_exist(self):
        paths = (
            PLAN_ROOT / "project_material_plan.json",
            PLAN_ROOT / "project_material_plan.py",
            ITEM_ROOT / "project_material_plan_item.json",
            ITEM_ROOT / "project_material_plan_item.py",
            SERVICE_PATH,
            API_PATH,
            RUNTIME_TEST_PATH,
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"缺少文件：{path}")

    def test_material_plan_has_unique_source_and_explainable_rows(self):
        plan = load_json(PLAN_ROOT / "project_material_plan.json")
        item = load_json(ITEM_ROOT / "project_material_plan_item.json")
        plan_fields = {field["fieldname"]: field for field in plan["fields"]}
        item_fields = {field["fieldname"]: field for field in item["fields"]}

        self.assertEqual(plan["name"], "Project Material Plan")
        self.assertEqual(plan_fields["sales_order"]["options"], "Sales Order")
        self.assertEqual(plan_fields["sales_order"]["unique"], 1)
        self.assertEqual(plan_fields["items"]["options"], "Project Material Plan Item")
        self.assertEqual(plan_fields["calculation_key"]["read_only"], 1)
        self.assertEqual(item["istable"], 1)
        for fieldname in (
            "item_code",
            "warehouse",
            "stock_uom",
            "ordered_qty",
            "actual_qty",
            "reserved_qty",
            "available_qty",
            "incoming_qty",
            "safety_stock",
            "required_qty",
            "required_by",
        ):
            self.assertIn(fieldname, item_fields)
        self.assertEqual(item_fields["required_qty"]["non_negative"], 1)
        self.assertNotIn("non_negative", item_fields["actual_qty"])
        self.assertNotIn("non_negative", item_fields["available_qty"])

    def test_service_uses_current_order_adjusted_reservation_and_idempotency(self):
        source = SERVICE_PATH.read_text(encoding="utf-8")

        self.assertIn("@dataclass(frozen=True, slots=True)", source)
        self.assertIn("def calculate_material_gap(", source)
        self.assertIn("def create_material_request(", source)
        self.assertIn("current_order_reserved", source)
        self.assertIn("other_reserved", source)
        self.assertIn("actual_qty", source)
        self.assertIn("ordered_qty", source)
        self.assertIn("safety_stock", source)
        self.assertIn("filelock", source)
        self.assertIn("for_update=True", source)
        self.assertIn("custom_source_sales_order", source)
        self.assertIn("Project Material Plan", source)
        self.assertNotIn("frappe.db.commit", source)

    def test_custom_field_api_and_sales_order_button_are_registered(self):
        custom_fields = (APP_ROOT / "setup" / "custom_fields.py").read_text(
            encoding="utf-8"
        )
        api_source = API_PATH.read_text(encoding="utf-8")
        sales_order_js = (APP_ROOT / "public" / "js" / "sales_order.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('"custom_source_sales_order"', custom_fields)
        self.assertIn('@frappe.whitelist(methods=["POST"])', api_source)
        self.assertNotIn("allow_guest=True", api_source)
        self.assertIn("autoflow_360.api.material.plan_sales_order", sales_order_js)

    def test_runtime_tests_cover_stock_math_boundaries_and_reuse(self):
        source = RUNTIME_TEST_PATH.read_text(encoding="utf-8")
        for test_name in (
            "test_available_stock_reduces_required_quantity",
            "test_current_order_reservation_is_not_double_counted",
            "test_other_reservations_safety_stock_and_incoming_are_explained",
            "test_negative_stock_increases_required_quantity",
            "test_no_request_is_created_without_gap",
            "test_repeated_request_creation_is_idempotent",
            "test_draft_sales_order_is_rejected",
            "test_missing_warehouse_is_rejected",
        ):
            self.assertIn(test_name, source)
        self.assertIn("IntegrationTestCase", source)
        self.assertIn("SYNTHETIC", source)


if __name__ == "__main__":
    unittest.main()
