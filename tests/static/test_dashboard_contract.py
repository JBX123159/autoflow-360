import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "autoflow_360"
PAGES = APP / "autoflow_360" / "page"
WORKBENCH = PAGES / "autoflow_workbench"
COCKPIT = PAGES / "autoflow_cockpit"
ANALYTICS = APP / "api" / "analytics.py"
CSS = APP / "public" / "css" / "autoflow.css"
PROJECT_JS = APP / "public" / "js" / "customer_project.js"
RUNTIME_TEST = APP / "tests" / "test_analytics_api.py"


class TestDashboardContract(unittest.TestCase):
    def test_pages_assets_api_and_tests_exist(self):
        paths = (
            WORKBENCH / "autoflow_workbench.json",
            WORKBENCH / "autoflow_workbench.js",
            WORKBENCH / "autoflow_workbench.py",
            COCKPIT / "autoflow_cockpit.json",
            COCKPIT / "autoflow_cockpit.js",
            COCKPIT / "autoflow_cockpit.py",
            CSS,
            ANALYTICS,
            PROJECT_JS,
            RUNTIME_TEST,
        )
        for path in paths:
            self.assertTrue(path.exists(), str(path))
            if path.suffix == ".py":
                ast.parse(path.read_text(encoding="utf-8"))
            if path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))

    def test_pages_are_limited_to_internal_business_roles(self):
        required_roles = {
            "AutoFlow Administrator",
            "AutoFlow Sales Operations",
            "AutoFlow Project Manager",
            "AutoFlow Procurement",
            "AutoFlow Warehouse",
            "AutoFlow Finance",
            "AutoFlow Executive",
        }
        workbench = json.loads((WORKBENCH / "autoflow_workbench.json").read_text(encoding="utf-8"))
        cockpit = json.loads((COCKPIT / "autoflow_cockpit.json").read_text(encoding="utf-8"))
        self.assertTrue(required_roles.issubset({row["role"] for row in workbench["roles"]}))
        self.assertEqual(
            {"AutoFlow Administrator", "AutoFlow Executive"},
            {row["role"] for row in cockpit["roles"]},
        )

    def test_api_is_get_only_permission_scoped_and_has_panorama(self):
        source = ANALYTICS.read_text(encoding="utf-8")
        self.assertIn('methods=["GET"]', source)
        self.assertIn("get_workbench_data", source)
        self.assertIn("get_management_cockpit", source)
        self.assertIn("get_project_panorama", source)
        self.assertIn("frappe.get_list", source)
        self.assertNotIn("frappe.get_all", source)
        self.assertNotIn("ignore_permissions", source)
        self.assertNotIn("frappe.db.sql", source)

    def test_workbench_renders_loading_empty_error_and_safe_text(self):
        source = (WORKBENCH / "autoflow_workbench.js").read_text(encoding="utf-8")
        for marker in ("renderLoading", "renderEmpty", "renderError", "escapeHtml", "frappe.call"):
            self.assertIn(marker, source)
        self.assertIn("Intl.NumberFormat", source)
        self.assertNotIn("frappe.format(value", source)
        self.assertNotIn("window.addEventListener(\"scroll\"", source)
        self.assertNotIn("—", source)
        self.assertNotIn("–", source)

    def test_cockpit_has_filters_metric_definitions_and_drilldown(self):
        source = (COCKPIT / "autoflow_cockpit.js").read_text(encoding="utf-8")
        for marker in ("company", "definition", "drilldown", "renderLoading", "renderError", "frappe.call"):
            self.assertIn(marker, source)
        self.assertIn("Intl.NumberFormat", source)
        self.assertNotIn("frappe.format(metric.value", source)
        self.assertNotIn("—", source)
        self.assertNotIn("–", source)

    def test_css_uses_required_grid_responsive_states_and_one_accent(self):
        source = CSS.read_text(encoding="utf-8")
        compact = " ".join(source.split())
        self.assertIn("220px minmax(0, 7fr) minmax(280px, 3fr)", compact)
        self.assertIn("@media (max-width: 991px)", source)
        self.assertIn("@media (max-width: 767px)", source)
        self.assertIn("prefers-reduced-motion", source)
        self.assertIn("--af-accent", source)
        self.assertIn(":focus-visible", source)

    def test_project_form_exposes_panorama_and_audit_entries(self):
        source = PROJECT_JS.read_text(encoding="utf-8")
        for label in (
            "打开项目全景",
            "关联单据",
            "风险与异常",
            "AI 分析",
            "操作记录",
        ):
            self.assertIn(label, source)

    def test_global_css_is_registered_without_new_frontend_dependency(self):
        hooks = (APP / "hooks.py").read_text(encoding="utf-8")
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("app_include_css", hooks)
        self.assertIn("autoflow.css", hooks)
        self.assertNotIn("react", pyproject.lower())
        self.assertNotIn("tailwind", pyproject.lower())


if __name__ == "__main__":
    unittest.main()
