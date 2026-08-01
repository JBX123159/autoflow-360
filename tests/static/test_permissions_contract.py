import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT_PERMISSION = ROOT / "autoflow_360" / "permissions" / "project.py"
HOOKS = ROOT / "autoflow_360" / "hooks.py"
SETUP_PERMISSIONS = ROOT / "autoflow_360" / "setup" / "permissions.py"
SALES_CONVERSION = ROOT / "autoflow_360" / "services" / "sales_conversion.py"
RUNTIME_TEST = ROOT / "autoflow_360" / "tests" / "test_permissions.py"
PROJECT_JSON = (
    ROOT
    / "autoflow_360"
    / "autoflow_360"
    / "doctype"
    / "customer_project"
    / "customer_project.json"
)


class TestPermissionsContract(unittest.TestCase):
    def test_permission_service_and_runtime_tests_exist(self):
        self.assertTrue(PROJECT_PERMISSION.exists())
        self.assertTrue(RUNTIME_TEST.exists())
        ast.parse(PROJECT_PERMISSION.read_text(encoding="utf-8"))
        ast.parse(RUNTIME_TEST.read_text(encoding="utf-8"))

    def test_project_query_covers_membership_company_and_portal_party(self):
        source = PROJECT_PERMISSION.read_text(encoding="utf-8")
        self.assertIn("INTERNAL_GLOBAL_READ_ROLES", source)
        self.assertIn("Project Member", source)
        self.assertIn("parenttype", source)
        self.assertIn("frappe.db.escape", source)
        self.assertIn("User Permission", source)
        self.assertIn("Company", source)
        self.assertIn("get_customer_names_for_user", source)
        self.assertIn('return "1=0"', source)

    def test_record_guard_denies_cross_company_and_unassigned_access(self):
        source = PROJECT_PERMISSION.read_text(encoding="utf-8")
        self.assertIn("customer_project_has_permission", source)
        self.assertIn("doc.company not in allowed_companies", source)
        self.assertIn("doc.project_manager == user", source)
        self.assertIn("doc.customer in customer_names", source)
        self.assertIn("is_supplier_portal_user", source)
        self.assertIn("permission_type", source)

    def test_hooks_register_list_and_record_guards(self):
        source = HOOKS.read_text(encoding="utf-8")
        self.assertIn('"Customer Project": "autoflow_360.permissions.project.customer_project_query"', source)
        self.assertIn('"Customer Project": "autoflow_360.permissions.project.customer_project_has_permission"', source)

    def test_business_approval_uses_explicit_user_roles(self):
        source = SALES_CONVERSION.read_text(encoding="utf-8")
        self.assertIn('"Has Role"', source)
        self.assertIn('"parenttype": "User"', source)
        self.assertNotIn("roles = frappe.get_roles(user)", source)

    def test_customer_portal_gets_read_entry_point_only(self):
        source = SETUP_PERMISSIONS.read_text(encoding="utf-8")
        self.assertIn('"Customer Project"', source)
        project = json.loads(PROJECT_JSON.read_text(encoding="utf-8"))
        portal_rows = [
            row
            for row in project["permissions"]
            if row["role"] == "AutoFlow Customer Portal"
        ]
        self.assertEqual(len(portal_rows), 1)
        self.assertEqual(portal_rows[0].get("read"), 1)
        self.assertFalse(portal_rows[0].get("write", 0))

    def test_runtime_matrix_names_all_seven_internal_roles_and_two_portals(self):
        source = RUNTIME_TEST.read_text(encoding="utf-8")
        for role in (
            "AutoFlow Administrator",
            "AutoFlow Sales Operations",
            "AutoFlow Project Manager",
            "AutoFlow Procurement",
            "AutoFlow Warehouse",
            "AutoFlow Finance",
            "AutoFlow Executive",
            "AutoFlow Customer Portal",
            "AutoFlow Supplier Portal",
        ):
            self.assertIn(role, source)
        self.assertIn("test_system_manager_is_not_automatic_business_approver", source)


if __name__ == "__main__":
    unittest.main()
