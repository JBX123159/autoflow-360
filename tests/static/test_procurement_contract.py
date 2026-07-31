import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "autoflow_360"
DOCTYPE_ROOT = APP_ROOT / "autoflow_360" / "doctype"
ETA_ROOT = DOCTYPE_ROOT / "supplier_eta_history"
PROCUREMENT_SERVICE = APP_ROOT / "services" / "procurement.py"
PROJECT_LINKING_SERVICE = APP_ROOT / "services" / "project_linking.py"
PROCUREMENT_API = APP_ROOT / "api" / "procurement.py"
PORTAL_API = APP_ROOT / "api" / "portal.py"
PORTAL_PERMISSION = APP_ROOT / "permissions" / "portal.py"
PORTAL_PERMISSION_SETUP = APP_ROOT / "setup" / "permissions.py"
PROCUREMENT_TEST = APP_ROOT / "tests" / "test_procurement.py"
SUPPLIER_PORTAL_TEST = APP_ROOT / "tests" / "test_supplier_portal.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ProcurementContractTest(unittest.TestCase):
    def test_required_services_model_pages_scripts_and_tests_exist(self):
        paths = (
            ETA_ROOT / "supplier_eta_history.json",
            ETA_ROOT / "supplier_eta_history.py",
            PROCUREMENT_SERVICE,
            PROJECT_LINKING_SERVICE,
            PROCUREMENT_API,
            APP_ROOT / "public" / "js" / "material_request.js",
            APP_ROOT / "public" / "js" / "supplier_quotation.js",
            APP_ROOT / "public" / "js" / "purchase_order.js",
            APP_ROOT / "www" / "supplier-rfqs.py",
            APP_ROOT / "www" / "supplier-rfqs.html",
            APP_ROOT / "www" / "supplier-orders.py",
            APP_ROOT / "www" / "supplier-orders.html",
            APP_ROOT / "templates" / "pages" / "supplier_rfqs.html",
            APP_ROOT / "templates" / "pages" / "supplier_orders.html",
            PORTAL_PERMISSION_SETUP,
            PROCUREMENT_TEST,
            SUPPLIER_PORTAL_TEST,
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"缺少文件：{path}")

    def test_eta_history_is_attributed_immutable_and_project_linked(self):
        data = load_json(ETA_ROOT / "supplier_eta_history.json")
        fields = {field["fieldname"]: field for field in data["fields"]}
        controller = (ETA_ROOT / "supplier_eta_history.py").read_text(
            encoding="utf-8"
        )

        self.assertEqual(data["name"], "Supplier ETA History")
        for fieldname, options in (
            ("purchase_order", "Purchase Order"),
            ("company", "Company"),
            ("supplier", "Supplier"),
            ("customer_project", "Customer Project"),
            ("changed_by", "User"),
        ):
            self.assertEqual(fields[fieldname]["options"], options)
        for fieldname in (
            "previous_eta",
            "new_eta",
            "changed_by",
            "changed_at",
            "change_reason",
        ):
            self.assertEqual(fields[fieldname]["read_only"], 1)
        self.assertIn("from_supplier_eta_service", controller)
        self.assertIn("get_doc_before_save", controller)
        self.assertIn("cannot be changed", controller)

    def test_procurement_custom_fields_preserve_each_source(self):
        source = (APP_ROOT / "setup" / "custom_fields.py").read_text(
            encoding="utf-8"
        )
        for fieldname in (
            "custom_source_material_request",
            "custom_source_rfq",
            "custom_source_supplier_quotation",
            "custom_supplier_eta",
        ):
            self.assertIn(f'"{fieldname}"', source)

    def test_procurement_service_uses_official_mappers_locks_and_permissions(self):
        source = PROCUREMENT_SERVICE.read_text(encoding="utf-8")

        for function_name in (
            "make_project_rfq",
            "submit_supplier_quote",
            "make_purchase_order_from_supplier_quote",
            "update_supplier_eta",
        ):
            self.assertIn(f"def {function_name}(", source)
        self.assertIn("add_items", source)
        self.assertIn("make_purchase_order", source)
        self.assertIn("get_supplier_names_for_user", source)
        self.assertIn("filelock", source)
        self.assertIn("for_update=True", source)
        self.assertIn("custom_source_material_request", source)
        self.assertIn("custom_source_rfq", source)
        self.assertIn("custom_source_supplier_quotation", source)
        self.assertIn("custom_supplier_eta", source)
        self.assertNotIn("frappe.db.commit", source)

    def test_supplier_permissions_use_standard_portal_link_and_list_filters(self):
        source = PORTAL_PERMISSION.read_text(encoding="utf-8")
        setup_source = PORTAL_PERMISSION_SETUP.read_text(encoding="utf-8")

        self.assertIn('parenttype": "Supplier"', source)
        self.assertIn("is_supplier_portal_user", source)
        self.assertIn("supplier_quotation_query", source)
        self.assertIn("purchase_order_query", source)
        self.assertIn("supplier_document_has_permission", source)
        self.assertIn('ptype == "read"', source)
        for doctype in (
            "Request for Quotation",
            "Supplier Quotation",
            "Purchase Order",
            "Item",
            "Account",
        ):
            self.assertIn(f'"{doctype}"', setup_source)
        self.assertIn('"read"', setup_source)
        self.assertIn('"select"', setup_source)
        for permission_type in ("write", "create", "delete", "submit"):
            self.assertNotIn(f'ptype="{permission_type}"', setup_source)

    def test_post_only_apis_and_hooks_register_the_complete_flow(self):
        procurement_api = PROCUREMENT_API.read_text(encoding="utf-8")
        portal_api = PORTAL_API.read_text(encoding="utf-8")
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")

        self.assertGreaterEqual(
            procurement_api.count('@frappe.whitelist(methods=["POST"])'),
            3,
        )
        self.assertGreaterEqual(
            portal_api.count('@frappe.whitelist(methods=["POST"])'),
            3,
        )
        self.assertNotIn("allow_guest=True", procurement_api + portal_api)
        for route in ("/supplier-rfqs", "/supplier-orders"):
            self.assertIn(f'"route": "{route}"', hooks)
        for doctype in (
            "Supplier Quotation",
            "Purchase Order",
            "Purchase Receipt",
            "Purchase Invoice",
            "Payment Entry",
        ):
            self.assertIn(f'"{doctype}"', hooks)
        self.assertIn("permission_query_conditions", hooks)
        self.assertIn("has_permission", hooks)

    def test_portal_templates_only_post_through_guarded_endpoints(self):
        rfq_template = (
            APP_ROOT / "templates" / "pages" / "supplier_rfqs.html"
        ).read_text(encoding="utf-8")
        order_template = (
            APP_ROOT / "templates" / "pages" / "supplier_orders.html"
        ).read_text(encoding="utf-8")

        self.assertIn("autoflow_360.api.portal.submit_supplier_quote", rfq_template)
        self.assertIn("rfq_item", rfq_template)
        self.assertIn("autoflow_360.api.portal.confirm_supplier_eta", order_template)
        self.assertNotIn("supplier:", rfq_template)
        self.assertNotIn("supplier:", order_template)

    def test_runtime_tests_cover_sources_idempotency_and_supplier_isolation(self):
        procurement = PROCUREMENT_TEST.read_text(encoding="utf-8")
        portal = SUPPLIER_PORTAL_TEST.read_text(encoding="utf-8")
        for test_name in (
            "test_rfq_keeps_project_source_and_submits",
            "test_repeated_rfq_creation_is_idempotent",
            "test_supplier_quote_keeps_rfq_rows_and_submits",
            "test_supplier_quote_converts_to_one_project_purchase_order",
            "test_eta_change_keeps_immutable_history",
            "test_downstream_documents_inherit_one_project",
        ):
            self.assertIn(test_name, procurement)
        for test_name in (
            "test_supplier_cannot_read_competitor_quote_or_order",
            "test_uninvited_supplier_cannot_quote_rfq",
            "test_supplier_cannot_forge_rfq_item",
            "test_supplier_cannot_update_competitor_eta",
            "test_guest_cannot_use_supplier_endpoints",
            "test_supplier_templates_render_empty_state",
        ):
            self.assertIn(test_name, portal)
        self.assertIn("IntegrationTestCase", procurement)
        self.assertIn("IntegrationTestCase", portal)
        self.assertIn("SYNTHETIC", procurement + portal)


if __name__ == "__main__":
    unittest.main()
