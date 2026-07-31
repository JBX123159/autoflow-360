import ast
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "autoflow_360"
IDEMPOTENCY_PATH = APP_ROOT / "services" / "idempotency.py"
CONVERSION_PATH = APP_ROOT / "services" / "deal_conversion.py"
API_PATH = APP_ROOT / "api" / "project.py"
CLIENT_SCRIPT_PATH = APP_ROOT / "public" / "js" / "crm_deal.js"
TEST_PATH = (
    APP_ROOT
    / "autoflow_360"
    / "doctype"
    / "customer_project"
    / "test_deal_conversion.py"
)


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"无法加载模块：{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DealConversionContractTest(unittest.TestCase):
    def test_required_backend_frontend_and_test_files_exist(self):
        for path in (
            IDEMPOTENCY_PATH,
            CONVERSION_PATH,
            API_PATH,
            CLIENT_SCRIPT_PATH,
            TEST_PATH,
        ):
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"缺少文件：{path}")

    def test_idempotency_key_is_stable_and_operation_scoped(self):
        module = load_module(IDEMPOTENCY_PATH, "_autoflow_idempotency_contract")

        first = module.make_idempotency_key("deal-to-project", " DEAL-1 ")
        second = module.make_idempotency_key("deal-to-project", "DEAL-1")
        other = module.make_idempotency_key("other-operation", "DEAL-1")

        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertEqual(len(first), 64)

    def test_service_uses_permission_checks_lock_and_unique_deal_link(self):
        source = CONVERSION_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }

        self.assertIn("check_permission", calls)
        self.assertIn("insert", calls)
        self.assertIn("filelock", source)
        self.assertIn("for_update=True", source)
        self.assertIn('"crm_deal": deal.name', source)
        self.assertNotIn("ignore_permissions=True", source)

    def test_api_is_post_only_and_client_collects_required_fields(self):
        api_source = API_PATH.read_text(encoding="utf-8")
        client_source = CLIENT_SCRIPT_PATH.read_text(encoding="utf-8")
        hooks_source = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")

        self.assertIn('@frappe.whitelist(methods=["POST"])', api_source)
        self.assertIn("create_project_from_deal", api_source)
        for fieldname in ("company", "customer", "product_family", "delivery_date"):
            self.assertIn(fieldname, client_source)
        self.assertIn("autoflow_360.api.project.convert_deal", client_source)
        self.assertIn('"CRM Deal": "public/js/crm_deal.js"', hooks_source)

    def test_runtime_tests_cover_reuse_mapping_validation_and_permission(self):
        source = TEST_PATH.read_text(encoding="utf-8")

        for test_name in (
            "test_repeated_conversion_returns_same_project",
            "test_deal_fields_are_mapped_to_project",
            "test_required_arguments_are_validated",
            "test_invalid_delivery_date_is_rejected",
            "test_crm_deal_client_hook_is_registered",
            "test_missing_deal_permission_is_rejected",
        ):
            self.assertIn(test_name, source)
        self.assertIn("IntegrationTestCase", source)
        self.assertIn("SYNTHETIC", source)


if __name__ == "__main__":
    unittest.main()
