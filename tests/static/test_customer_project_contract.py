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
DOCTYPE_ROOT = APP_ROOT / "autoflow_360" / "doctype"
CUSTOMER_PROJECT_ROOT = DOCTYPE_ROOT / "customer_project"
PROJECT_STATUS_PATH = APP_ROOT / "services" / "project_status.py"

MAIN_STAGE_SEQUENCE = (
    "潜在项目",
    "样品阶段",
    "报价阶段",
    "已定点",
    "订单履约",
    "已交付",
    "待回款",
    "已结项",
)
SIDE_STAGES = {"暂停", "失败", "取消"}
SIDE_STAGE_SEQUENCE = ("暂停", "失败", "取消")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@contextmanager
def load_project_status_module(frappe_module: types.ModuleType):
    module_name = "_autoflow_project_status_contract"
    spec = importlib.util.spec_from_file_location(module_name, PROJECT_STATUS_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"无法加载模块：{PROJECT_STATUS_PATH}")
    module = importlib.util.module_from_spec(spec)
    frappe_utils_module = types.ModuleType("frappe.utils")
    frappe_utils_module.cstr = lambda value: "" if value is None else str(value)
    with patch.dict(
        sys.modules,
        {"frappe": frappe_module, "frappe.utils": frappe_utils_module},
    ):
        spec.loader.exec_module(module)
        yield module


class CustomerProjectContractTest(unittest.TestCase):
    def test_child_doctypes_follow_frappe_v16_table_contract(self):
        member = load_json(
            DOCTYPE_ROOT / "project_member" / "project_member.json"
        )
        milestone = load_json(
            DOCTYPE_ROOT / "project_milestone" / "project_milestone.json"
        )

        for data, name in (
            (member, "Project Member"),
            (milestone, "Project Milestone"),
        ):
            with self.subTest(doctype=name):
                self.assertEqual(data["doctype"], "DocType")
                self.assertEqual(data["name"], name)
                self.assertEqual(data["module"], "AutoFlow 360")
                self.assertEqual(data["istable"], 1)
                self.assertEqual(data["editable_grid"], 1)
                self.assertEqual(data["permissions"], [])

        member_fields = {
            field["fieldname"]: field for field in member["fields"]
        }
        self.assertEqual(tuple(member_fields), ("user", "responsibility"))
        self.assertEqual(member_fields["user"]["fieldtype"], "Link")
        self.assertEqual(member_fields["user"]["options"], "User")
        self.assertEqual(member_fields["user"]["reqd"], 1)
        self.assertEqual(member_fields["responsibility"]["fieldtype"], "Data")
        self.assertEqual(member_fields["responsibility"]["reqd"], 1)

        milestone_fields = {
            field["fieldname"]: field for field in milestone["fields"]
        }
        self.assertEqual(
            tuple(milestone_fields),
            ("milestone_name", "planned_date", "owner_user", "status"),
        )
        self.assertEqual(milestone_fields["planned_date"]["fieldtype"], "Date")
        self.assertEqual(milestone_fields["owner_user"]["options"], "User")
        self.assertEqual(
            milestone_fields["status"]["options"],
            "未开始\n进行中\n已完成\n已取消",
        )

    def test_customer_project_schema_has_stable_fields_and_links(self):
        data = load_json(CUSTOMER_PROJECT_ROOT / "customer_project.json")
        fields = {field["fieldname"]: field for field in data["fields"]}

        expected_fields = {
            "project_name": ("Data", None),
            "company": ("Link", "Company"),
            "customer": ("Link", "Customer"),
            "crm_deal": ("Link", "CRM Deal"),
            "product_family": ("Data", None),
            "currency": ("Link", "Currency"),
            "expected_amount": ("Currency", "currency"),
            "probability": ("Percent", None),
            "project_manager": ("Link", "User"),
            "project_members": ("Table", "Project Member"),
            "milestones": ("Table", "Project Milestone"),
            "target_award_date": ("Date", None),
            "customer_delivery_date": ("Date", None),
            "last_meaningful_activity": ("Datetime", None),
            "stage": ("Select", None),
            "overall_risk_level": ("Select", None),
            "next_action": ("Data", None),
            "next_action_owner": ("Link", "User"),
            "next_action_due_date": ("Date", None),
            "pause_reason": ("Small Text", None),
            "resume_date": ("Date", None),
            "failure_reason": ("Small Text", None),
            "cancellation_reason": ("Small Text", None),
            "closure_summary": ("Long Text", None),
            "is_demo": ("Check", None),
            "demo_key": ("Data", None),
            "data_classification": ("Data", None),
        }
        for fieldname, (fieldtype, options) in expected_fields.items():
            with self.subTest(field=fieldname):
                self.assertIn(fieldname, fields)
                self.assertEqual(fields[fieldname]["fieldtype"], fieldtype)
                if options is not None:
                    self.assertEqual(fields[fieldname]["options"], options)

        for fieldname in (
            "project_name",
            "company",
            "customer",
            "product_family",
            "currency",
            "project_manager",
            "project_members",
            "target_award_date",
            "customer_delivery_date",
        ):
            self.assertEqual(fields[fieldname]["reqd"], 1, fieldname)

        self.assertEqual(fields["crm_deal"]["unique"], 1)
        self.assertEqual(fields["demo_key"]["unique"], 1)
        for fieldname in (
            "last_meaningful_activity",
            "overall_risk_level",
            "is_demo",
            "demo_key",
            "data_classification",
        ):
            self.assertEqual(fields[fieldname]["read_only"], 1, fieldname)

        self.assertEqual(
            fields["stage"]["options"],
            "\n".join((*MAIN_STAGE_SEQUENCE, *SIDE_STAGE_SEQUENCE)),
        )
        self.assertEqual(fields["stage"]["default"], "潜在项目")
        self.assertEqual(fields["overall_risk_level"]["options"], "低\n中\n高")

    def test_customer_project_naming_list_and_permissions_are_explicit(self):
        data = load_json(CUSTOMER_PROJECT_ROOT / "customer_project.json")
        fields = {field["fieldname"]: field for field in data["fields"]}

        self.assertEqual(data["autoname"], "naming_series:")
        self.assertEqual(data["naming_rule"], 'By "Naming Series" field')
        self.assertEqual(fields["naming_series"]["default"], "AF-.YYYY.-.#####")
        self.assertEqual(
            fields["naming_series"]["options"],
            "AF-.YYYY.-.#####",
        )
        self.assertEqual(data["track_changes"], 1)
        self.assertEqual(data["title_field"], "project_name")
        self.assertEqual(data["allow_rename"], 0)

        for fieldname in (
            "project_name",
            "customer",
            "stage",
            "project_manager",
            "customer_delivery_date",
            "overall_risk_level",
        ):
            self.assertEqual(fields[fieldname]["in_list_view"], 1, fieldname)

        permission_roles = {row["role"] for row in data["permissions"]}
        self.assertTrue(
            {
                "System Manager",
                "AutoFlow Administrator",
                "AutoFlow Sales Operations",
                "AutoFlow Project Manager",
                "AutoFlow Executive",
            }.issubset(permission_roles)
        )

    def test_state_machine_allows_only_initial_or_adjacent_main_stages(self):
        class FakeValidationError(Exception):
            pass

        frappe_module = types.ModuleType("frappe")
        frappe_module._ = lambda message: message
        frappe_module.throw = lambda message: (_ for _ in ()).throw(
            FakeValidationError(message)
        )

        with load_project_status_module(frappe_module) as status:
            self.assertEqual(status.MAIN_STAGE_SEQUENCE, MAIN_STAGE_SEQUENCE)
            self.assertEqual(set(status.SIDE_STAGES), SIDE_STAGES)
            status.validate_stage_transition(None, "潜在项目")

            with self.assertRaises(FakeValidationError):
                status.validate_stage_transition(None, "已定点")
            with self.assertRaises(FakeValidationError):
                status.validate_stage_transition(None, "暂停")
            with self.assertRaises(FakeValidationError):
                status.validate_stage_transition("暂停", "样品阶段")
            with self.assertRaises(FakeValidationError):
                status.validate_stage_transition("潜在项目", "未知状态")

            for index, previous in enumerate(MAIN_STAGE_SEQUENCE):
                status.validate_stage_transition(previous, previous)
                status.validate_stage_transition(previous, "暂停")
                if index + 1 < len(MAIN_STAGE_SEQUENCE):
                    status.validate_stage_transition(
                        previous,
                        MAIN_STAGE_SEQUENCE[index + 1],
                    )

                disallowed = set(MAIN_STAGE_SEQUENCE) - {
                    previous,
                    *MAIN_STAGE_SEQUENCE[index + 1 : index + 2],
                }
                for current in disallowed:
                    with self.subTest(previous=previous, current=current):
                        with self.assertRaises(FakeValidationError):
                            status.validate_stage_transition(previous, current)

    def test_derive_stage_skips_future_doctypes_and_custom_fields(self):
        class FakeMeta:
            @staticmethod
            def has_field(fieldname):
                return False

        class FakeDatabase:
            def __init__(self):
                self.calls = []

            def exists(self, doctype, filters):
                self.calls.append((doctype, filters))
                if doctype != "DocType":
                    raise AssertionError(
                        f"缺少字段时不应查询业务表：{doctype}"
                    )
                return filters != "Sample Request"

        database = FakeDatabase()
        project = types.SimpleNamespace(
            doctype="Customer Project",
            name="AF-2026-00001",
            stage="潜在项目",
        )
        frappe_module = types.ModuleType("frappe")
        frappe_module._ = lambda message: message
        frappe_module.throw = lambda message: (_ for _ in ()).throw(
            AssertionError(message)
        )
        frappe_module.db = database
        frappe_module.get_doc = lambda doctype, name: project
        frappe_module.get_meta = lambda doctype: FakeMeta()

        with load_project_status_module(frappe_module) as status:
            self.assertEqual(
                status.derive_project_stage(project.name),
                "潜在项目",
            )

        queried_doctypes = {
            filters
            for doctype, filters in database.calls
            if doctype == "DocType"
        }
        self.assertIn("Sample Request", queried_doctypes)
        self.assertIn("Quotation", queried_doctypes)

    def test_controller_factory_and_client_script_are_present(self):
        controller = (
            CUSTOMER_PROJECT_ROOT / "customer_project.py"
        ).read_text(encoding="utf-8")
        client_script = (
            CUSTOMER_PROJECT_ROOT / "customer_project.js"
        ).read_text(encoding="utf-8")
        factory = (APP_ROOT / "tests" / "factories.py").read_text(
            encoding="utf-8"
        )

        for method_name in (
            "def validate(self)",
            "def _validate_dates(self)",
            "def _validate_members(self)",
            "def _validate_numeric_boundaries(self)",
            "def _validate_side_stage_reason(self)",
        ):
            self.assertIn(method_name, controller)
        self.assertIn('frappe.ui.form.on("Customer Project"', client_script)
        self.assertIn(
            "def make_customer_project(",
            factory,
        )
        self.assertIn("SYNTHETIC", factory)


if __name__ == "__main__":
    unittest.main()
