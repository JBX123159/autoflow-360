import ast
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "autoflow_360"
SETTINGS_ROOT = APP_ROOT / "autoflow_360" / "doctype" / "autoflow_settings"

EXPECTED_ROLES = (
    "AutoFlow Sales Operations",
    "AutoFlow Project Manager",
    "AutoFlow Procurement",
    "AutoFlow Warehouse",
    "AutoFlow Finance",
    "AutoFlow Executive",
    "AutoFlow Administrator",
    "AutoFlow Customer Portal",
    "AutoFlow Supplier Portal",
)

EXPECTED_PROJECT_LINK_DOCTYPES = (
    "Quotation",
    "Sales Order",
    "Delivery Note",
    "Sales Invoice",
    "Material Request",
    "Request for Quotation",
    "Supplier Quotation",
    "Purchase Order",
    "Purchase Receipt",
    "Purchase Invoice",
    "Payment Entry",
)


def load_constant(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{path} 中缺少常量 {name}")


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"无法加载模块：{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def fake_frappe_modules(frappe_module: types.ModuleType):
    custom_field_module = types.ModuleType(
        "frappe.custom.doctype.custom_field.custom_field"
    )
    custom_field_module.create_custom_fields = frappe_module.create_custom_fields

    document_module = types.ModuleType("frappe.model.document")
    document_module.Document = type("Document", (), {})

    modules = {
        "frappe": frappe_module,
        "frappe.custom": types.ModuleType("frappe.custom"),
        "frappe.custom.doctype": types.ModuleType("frappe.custom.doctype"),
        "frappe.custom.doctype.custom_field": types.ModuleType(
            "frappe.custom.doctype.custom_field"
        ),
        "frappe.custom.doctype.custom_field.custom_field": custom_field_module,
        "frappe.model": types.ModuleType("frappe.model"),
        "frappe.model.document": document_module,
    }
    with patch.dict(sys.modules, modules):
        yield


class SystemFoundationContractTest(unittest.TestCase):
    def test_role_and_project_link_constants_are_complete(self):
        roles = load_constant(APP_ROOT / "setup" / "roles.py", "ROLES")
        doctypes = load_constant(
            APP_ROOT / "setup" / "custom_fields.py",
            "PROJECT_LINK_DOCTYPES",
        )

        self.assertEqual(roles, EXPECTED_ROLES)
        self.assertEqual(doctypes, EXPECTED_PROJECT_LINK_DOCTYPES)
        self.assertEqual(len(set(roles)), 9)
        self.assertEqual(len(set(doctypes)), 11)

    def test_hooks_register_install_and_migrate_handlers(self):
        hooks_path = APP_ROOT / "hooks.py"
        tree = ast.parse(hooks_path.read_text(encoding="utf-8"))
        assignments = {
            target.id: ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
            and target.id in {"after_install", "after_migrate"}
        }

        self.assertEqual(
            assignments,
            {
                "after_install": "autoflow_360.install.after_install",
                "after_migrate": "autoflow_360.install.after_migrate",
            },
        )

    def test_settings_doctype_has_exact_required_fields_and_permissions(self):
        data = json.loads(
            (SETTINGS_ROOT / "autoflow_settings.json").read_text(encoding="utf-8")
        )
        fields = {field["fieldname"]: field for field in data["fields"]}

        self.assertEqual(data["doctype"], "DocType")
        self.assertEqual(data["name"], "AutoFlow Settings")
        self.assertEqual(data["module"], "AutoFlow 360")
        self.assertEqual(data["issingle"], 1)
        self.assertEqual(
            tuple(fields),
            (
                "feedback_warning_days",
                "quotation_expiry_warning_days",
                "project_inactive_days",
                "high_risk_score",
                "ai_enabled",
                "ai_provider",
                "ai_base_url",
                "ai_model",
                "ai_api_key",
            ),
        )
        for fieldname, default in (
            ("feedback_warning_days", "3"),
            ("quotation_expiry_warning_days", "7"),
            ("project_inactive_days", "7"),
            ("high_risk_score", "70"),
        ):
            self.assertEqual(fields[fieldname]["fieldtype"], "Int")
            self.assertEqual(fields[fieldname]["default"], default)
            self.assertEqual(fields[fieldname]["reqd"], 1)

        self.assertEqual(fields["ai_enabled"]["fieldtype"], "Check")
        self.assertEqual(fields["ai_enabled"]["default"], "0")
        self.assertEqual(fields["ai_provider"]["fieldtype"], "Select")
        self.assertEqual(
            fields["ai_provider"]["options"],
            "Disabled\nOpenAI Compatible",
        )
        self.assertEqual(fields["ai_provider"]["default"], "Disabled")
        self.assertEqual(fields["ai_api_key"]["fieldtype"], "Password")
        self.assertEqual(
            data["permissions"],
            [
                {"role": "AutoFlow Administrator", "read": 1, "write": 1},
                {"role": "System Manager", "read": 1, "write": 1},
            ],
        )

    def test_role_and_custom_field_setup_is_idempotent(self):
        test_case = self
        role_names: set[str] = set()
        role_access: dict[str, int] = {}
        inserted_roles: list[dict] = []
        custom_field_calls: list[tuple[dict, bool, bool]] = []
        state = {"project_doctype_exists": False}

        class FakeDatabase:
            @staticmethod
            def exists(doctype, name):
                if doctype == "Role":
                    return name if name in role_names else None
                test_case.assertEqual((doctype, name), ("DocType", "Customer Project"))
                return name if state["project_doctype_exists"] else None

        class FakeRole:
            def __init__(self, values):
                self.values = values
                self.name = values["role_name"]
                self.desk_access = values["desk_access"]

            def insert(self, *, ignore_permissions):
                test_case.assertTrue(ignore_permissions)
                inserted_roles.append(self.values)
                role_names.add(self.values["role_name"])
                role_access[self.values["role_name"]] = self.values["desk_access"]

            def save(self, *, ignore_permissions):
                test_case.assertTrue(ignore_permissions)
                role_access[self.name] = self.desk_access

        def get_doc(*args):
            if len(args) == 1:
                return FakeRole(args[0])
            test_case.assertEqual(args[0], "Role")
            role_name = args[1]
            return FakeRole(
                {
                    "doctype": "Role",
                    "role_name": role_name,
                    "desk_access": role_access[role_name],
                }
            )

        frappe_module = types.ModuleType("frappe")
        frappe_module.db = FakeDatabase()
        frappe_module.get_doc = get_doc
        frappe_module.create_custom_fields = (
            lambda fields, *, ignore_validate, update: custom_field_calls.append(
                (fields, ignore_validate, update)
            )
        )
        frappe_module._ = lambda message: message

        with fake_frappe_modules(frappe_module):
            roles_module = load_module(
                APP_ROOT / "setup" / "roles.py",
                "_autoflow_roles_contract",
            )
            custom_fields_module = load_module(
                APP_ROOT / "setup" / "custom_fields.py",
                "_autoflow_custom_fields_contract",
            )

            roles_module.ensure_roles()
            role_access["AutoFlow Administrator"] = 0
            role_access["AutoFlow Customer Portal"] = 1
            roles_module.ensure_roles()
            custom_fields_module.ensure_custom_fields()
            state["project_doctype_exists"] = True
            custom_fields_module.ensure_custom_fields()

        self.assertEqual(len(inserted_roles), 9)
        self.assertEqual(role_names, set(EXPECTED_ROLES))
        for role_name in EXPECTED_ROLES:
            is_portal = role_name.endswith(" Portal")
            self.assertEqual(role_access[role_name], 0 if is_portal else 1)

        self.assertEqual(len(custom_field_calls), 2)
        self.assertEqual(
            [ignore_validate for _, ignore_validate, _ in custom_field_calls],
            [True, False],
        )
        for fields, _, update in custom_field_calls:
            self.assertTrue(update)
            self.assertEqual(tuple(fields), EXPECTED_PROJECT_LINK_DOCTYPES)
            for doctype in EXPECTED_PROJECT_LINK_DOCTYPES:
                self.assertEqual(
                    fields[doctype],
                    [
                        {
                            "fieldname": "custom_customer_project",
                            "label": "Customer Project",
                            "fieldtype": "Link",
                            "options": "Customer Project",
                            "insert_after": "company",
                            "module": "AutoFlow 360",
                            "in_standard_filter": 1,
                            "no_copy": 1,
                        }
                    ],
                )

    def test_settings_controller_rejects_invalid_boundaries_and_ai_configuration(self):
        class FakeValidationError(Exception):
            pass

        frappe_module = types.ModuleType("frappe")
        frappe_module.create_custom_fields = lambda fields, *, update: None
        frappe_module._ = lambda message: message
        frappe_module.throw = lambda message: (_ for _ in ()).throw(
            FakeValidationError(message)
        )

        with fake_frappe_modules(frappe_module):
            settings_module = load_module(
                SETTINGS_ROOT / "autoflow_settings.py",
                "_autoflow_settings_contract",
            )

        valid_values = {
            "feedback_warning_days": 3,
            "quotation_expiry_warning_days": 7,
            "project_inactive_days": 7,
            "high_risk_score": 70,
            "ai_enabled": 0,
            "ai_provider": "Disabled",
            "ai_base_url": "",
            "ai_model": "",
        }

        for fieldname, invalid_value, expected_message in (
            ("feedback_warning_days", 0, "greater than zero"),
            ("quotation_expiry_warning_days", -1, "greater than zero"),
            ("project_inactive_days", 1.5, "whole number"),
            ("feedback_warning_days", "not-a-number", "whole number"),
        ):
            settings = settings_module.AutoFlowSettings()
            for name, value in valid_values.items():
                setattr(settings, name, value)
            setattr(settings, fieldname, invalid_value)
            with self.subTest(
                field=fieldname,
                invalid_value=invalid_value,
            ), self.assertRaisesRegex(
                FakeValidationError,
                expected_message,
            ):
                settings.validate()

        for fieldname in (
            "feedback_warning_days",
            "quotation_expiry_warning_days",
            "project_inactive_days",
        ):
            settings = settings_module.AutoFlowSettings()
            for name, value in valid_values.items():
                setattr(settings, name, value)
            setattr(settings, fieldname, 0)
            with self.subTest(field=fieldname), self.assertRaisesRegex(
                FakeValidationError,
                "greater than zero",
            ):
                settings.validate()

        for invalid_score in (0, 101):
            settings = settings_module.AutoFlowSettings()
            for name, value in valid_values.items():
                setattr(settings, name, value)
            settings.high_risk_score = invalid_score
            with self.subTest(score=invalid_score), self.assertRaisesRegex(
                FakeValidationError,
                "between 1 and 100",
            ):
                settings.validate()

        invalid_ai_values = (
            ("Disabled", "qwen", "http://localhost:11434/v1", "AI Provider"),
            ("OpenAI Compatible", "", "http://localhost:11434/v1", "AI Model"),
            ("OpenAI Compatible", "qwen", "", "AI Base URL"),
            ("OpenAI Compatible", "qwen", "localhost:11434", "http or https"),
        )
        for provider, model, base_url, message in invalid_ai_values:
            settings = settings_module.AutoFlowSettings()
            for name, value in valid_values.items():
                setattr(settings, name, value)
            settings.ai_enabled = 1
            settings.ai_provider = provider
            settings.ai_model = model
            settings.ai_base_url = base_url
            with self.subTest(
                provider=provider,
                model=model,
                base_url=base_url,
            ), self.assertRaisesRegex(FakeValidationError, message):
                settings.validate()

        settings = settings_module.AutoFlowSettings()
        for name, value in valid_values.items():
            setattr(settings, name, value)
        settings.ai_enabled = 2
        with self.assertRaisesRegex(FakeValidationError, "either 0 or 1"):
            settings.validate()

        settings = settings_module.AutoFlowSettings()
        for name, value in valid_values.items():
            setattr(settings, name, value)
        settings.ai_enabled = 1
        settings.ai_provider = 123
        settings.ai_model = "qwen"
        settings.ai_base_url = "http://localhost:11434/v1"
        with self.assertRaisesRegex(FakeValidationError, "AI Provider must be text"):
            settings.validate()

        valid_settings = settings_module.AutoFlowSettings()
        for name, value in {
            **valid_values,
            "ai_enabled": 1,
            "ai_provider": "OpenAI Compatible",
            "ai_base_url": "http://localhost:11434/v1",
            "ai_model": "qwen",
        }.items():
            setattr(valid_settings, name, value)
        valid_settings.validate()


if __name__ == "__main__":
    unittest.main()
