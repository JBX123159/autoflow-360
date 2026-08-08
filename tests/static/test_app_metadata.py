from pathlib import Path
import ast
import tomllib
import unittest
import xml.etree.ElementTree as ElementTree


ROOT = Path(__file__).resolve().parents[2]


class AppMetadataTest(unittest.TestCase):
    def test_pyproject_contract(self):
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project = data["project"]

        self.assertEqual(project["name"], "autoflow-360")
        self.assertEqual(project["requires-python"], ">=3.14,<3.15")
        self.assertEqual(project["license"], "AGPL-3.0-only")
        self.assertEqual(project["dynamic"], ["version"])
        self.assertNotIn("version", project)
        self.assertEqual(data["build-system"]["build-backend"], "flit_core.buildapi")
        self.assertIn("flit_core >=3.11,<4", data["build-system"]["requires"])
        self.assertEqual(data["tool"]["flit"]["module"]["name"], "autoflow_360")
        self.assertEqual(
            data["tool"]["bench"]["frappe-dependencies"]["frappe"],
            ">=16.0.0,<17.0.0",
        )

    def test_static_version_declaration(self):
        package_init = ROOT / "autoflow_360" / "__init__.py"
        tree = ast.parse(package_init.read_text(encoding="utf-8"))
        versions = {
            target.id: node.value.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            for target in node.targets
            if isinstance(target, ast.Name) and target.id == "__version__"
        }

        self.assertEqual(versions.get("__version__"), "0.1.0")

    def test_expected_python_packages_exist(self):
        package_directories = [
            "autoflow_360",
            "autoflow_360/config",
            "autoflow_360/autoflow_360",
            "autoflow_360/api",
            "autoflow_360/ai",
            "autoflow_360/ai/providers",
            "autoflow_360/permissions",
            "autoflow_360/risk_engine",
            "autoflow_360/services",
            "autoflow_360/setup",
            "autoflow_360/tests",
        ]

        for relative_directory in package_directories:
            with self.subTest(package=relative_directory):
                self.assertTrue((ROOT / relative_directory / "__init__.py").is_file())

    def test_hooks_are_valid_python(self):
        hooks_path = ROOT / "autoflow_360" / "hooks.py"
        content = hooks_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
        assignments = {
            target.id: ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
            and target.id in {"app_license", "required_apps"}
        }

        self.assertEqual(assignments["app_license"], "AGPL-3.0-only")
        self.assertEqual(assignments["required_apps"], ["payments", "erpnext", "crm"])

    def test_v16_apps_screen_entry_uses_an_existing_svg(self):
        hooks_path = ROOT / "autoflow_360" / "hooks.py"
        tree = ast.parse(hooks_path.read_text(encoding="utf-8"))
        assignments = {
            target.id: ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name) and target.id == "add_to_apps_screen"
        }

        self.assertEqual(
            assignments["add_to_apps_screen"],
            [
                {
                    "name": "autoflow_360",
                    "logo": "/assets/autoflow_360/images/autoflow-360-logo.svg",
                    "title": "AutoFlow 360",
                    "route": "/desk",
                }
            ],
        )

        logo_path = (
            ROOT
            / "autoflow_360"
            / "public"
            / "images"
            / "autoflow-360-logo.svg"
        )
        self.assertTrue(logo_path.is_file())
        root_element = ElementTree.parse(logo_path).getroot()
        self.assertEqual(root_element.tag, "{http://www.w3.org/2000/svg}svg")

    def test_module_name_is_stable(self):
        modules = (ROOT / "autoflow_360" / "modules.txt").read_text(encoding="utf-8")
        self.assertEqual(modules.strip(), "AutoFlow 360")

    def test_patch_sections_are_declared(self):
        patches = (ROOT / "autoflow_360" / "patches.txt").read_text(encoding="utf-8")
        self.assertEqual(
            [line.strip() for line in patches.splitlines() if line.strip()],
            ["[pre_model_sync]", "[post_model_sync]"],
        )

    def test_implementation_plan_uses_the_supported_python_minor_line(self):
        plan = (
            ROOT
            / "docs"
            / "superpowers"
            / "plans"
            / "2026-07-29-autoflow-360-implementation.md"
        ).read_text(encoding="utf-8")

        self.assertNotIn("Python 3.14+", plan)
        self.assertNotIn('requires-python = ">=3.14"', plan)
        self.assertIn("Python 3.14.x", plan)
        self.assertIn("Python 固定为 3.14.x（即 `>=3.14,<3.15`）", plan)
        self.assertIn("- Consumes: Python 3.14.x 与 Frappe v16 应用目录约定。", plan)
        self.assertGreaterEqual(plan.count('">=3.14,<3.15"'), 2)

    def test_implementation_plan_covers_v16_entry_and_real_wheel_build(self):
        plan = (
            ROOT
            / "docs"
            / "superpowers"
            / "plans"
            / "2026-07-29-autoflow-360-implementation.md"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "- Create: `autoflow_360/public/images/autoflow-360-logo.svg`",
            plan,
        )
        self.assertIn("- Create: `tests/build/test_wheel_metadata.py`", plan)
        self.assertIn("add_to_apps_screen = [", plan)
        self.assertIn('"route": "/desk"', plan)
        self.assertIn(
            "python -m unittest tests.build.test_wheel_metadata -v",
            plan,
        )
        self.assertIn(
            "git add pyproject.toml autoflow_360 tests/static/test_app_metadata.py tests/build",
            plan,
        )

    def test_task_two_pyproject_example_matches_real_build_metadata(self):
        plan = (
            ROOT
            / "docs"
            / "superpowers"
            / "plans"
            / "2026-07-29-autoflow-360-implementation.md"
        ).read_text(encoding="utf-8")
        task_two = plan.split("### Task 2:", 1)[1].split("### Task 3:", 1)[0]
        pyproject_example = task_two.split("```toml", 1)[1].split("```", 1)[0]

        self.assertIn(
            '\nlicense = "AGPL-3.0-only"\n',
            pyproject_example,
        )
        self.assertIn(
            '[tool.flit.module]\nname = "autoflow_360"',
            pyproject_example,
        )
        self.assertIn(
            "超时诊断必须包含 timeout 值、stdout 和 stderr",
            task_two,
        )

    def test_desktop_entry_is_valid_python_without_importing_frappe(self):
        desktop = (ROOT / "autoflow_360" / "config" / "desktop.py").read_text(
            encoding="utf-8"
        )
        ast.parse(desktop)


if __name__ == "__main__":
    unittest.main()
