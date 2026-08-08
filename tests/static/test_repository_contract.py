from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class RepositoryContractTest(unittest.TestCase):
    def test_required_documents_exist(self):
        for relative_path in (
            "README.md",
            "NOTICE.md",
            "LICENSE",
            "Product-Spec.md",
            "docs/research/upstream-baseline.md",
            "docs/superpowers/specs/2026-07-29-autoflow-360-design.md",
            "scripts/check-environment.ps1",
        ):
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)

    def test_readme_states_upstream_and_custom_scope(self):
        content = (ROOT / "README.md").read_text(encoding="utf-8")
        for required_text in (
            "AutoFlow 360",
            "Frappe CRM",
            "ERPNext",
            "已实现的自主扩展",
            "合成数据",
            "三条可复现演示",
            "本地运行",
            "验证",
            "来源与许可证",
        ):
            self.assertIn(required_text, content)

    def test_license_is_agpl(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("GNU AFFERO GENERAL PUBLIC LICENSE", license_text)
        self.assertIn("Version 3, 19 November 2007", license_text)

    def test_notice_lists_all_upstreams_and_licenses(self):
        content = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
        for required_text in (
            "https://github.com/frappe/frappe | MIT",
            "https://github.com/frappe/payments | MIT",
            "https://github.com/frappe/erpnext | GPL-3.0",
            "https://github.com/frappe/crm | AGPL-3.0",
            "https://github.com/frappe/frappe_docker | MIT",
        ):
            self.assertIn(required_text, content)

    def test_readme_describes_three_paths_and_exact_license(self):
        content = (ROOT / "README.md").read_text(encoding="utf-8")
        for required_text in ("正常交付", "供应商延期", "重新打样", "AGPL-3.0-only"):
            self.assertIn(required_text, content)

    def test_gitignore_covers_runtime_and_test_outputs(self):
        entries = {
            line.strip()
            for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        required_entries = {
            ".runtime/",
            ".venv/",
            "__pycache__/",
            "*.py[cod]",
            ".pytest_cache/",
            "node_modules/",
            "sites/",
            "logs/",
            "*.log",
            "playwright-report/",
              "test-results/",
              "videos/*/capture/",
			"videos/*/.thumbnails/",
			"videos/*/snapshots/",
			"videos/*/renders/",
			"videos/*/.hyperframes/frame-packets/",
          }
        self.assertTrue(required_entries.issubset(entries), required_entries - entries)

    def test_upstream_baseline_declares_pins_and_pending_hashes(self):
        content = (ROOT / "docs/research/upstream-baseline.md").read_text(encoding="utf-8")
        for required_text in (
            "Frappe Framework",
            "Frappe Payments",
            "version-16",
            "ERPNext",
            "Frappe CRM",
            "main",
            "frappe_docker",
            "精确提交哈希",
        ):
            self.assertIn(required_text, content)

    def test_task_three_updates_all_upstream_hashes_and_date(self):
        plan = (
            ROOT
            / "docs/superpowers/plans/2026-07-29-autoflow-360-implementation.md"
        ).read_text(encoding="utf-8")
        task_three = plan.split("### Task 3:", maxsplit=1)[1].split("\n---", maxsplit=1)[0]
        self.assertIn("Modify: `docs/research/upstream-baseline.md`", task_three)
        self.assertIn("四个 40 位提交哈希", task_three)
        self.assertIn("获取日期", task_three)
        self.assertIn("expected_projects = {", task_three)
        self.assertIn("for line in content.splitlines()", task_three)
        self.assertIn("self.assertEqual(len(revisions), 1, project)", task_three)
        self.assertIn("self.assertEqual(len(set(dates)), 1)", task_three)
        self.assertRegex(
            task_three,
            r"git add [^\n]*docs/research/upstream-baseline\.md",
        )

    def test_custom_scope_and_unfinished_delivery_are_truthfully_labeled(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for required_text in (
            "已实现的自主扩展",
            "未上线真实企业",
            "公开仓库 [完整集成验收]",
            "Frappe 148/148",
            "RESTORE_CHECK_PASSED",
            "v1.0.0-rc2` 多架构镜像构建",
            "公开镜像为 `ghcr.io/jbx123159/autoflow-360:v1.0.0-rc2`",
            "当前没有长期公网业务站点",
        ):
            self.assertIn(required_text, readme)

        self.assertNotIn("已上线真实企业", readme)
        self.assertNotIn("产生真实营收", readme)

    def test_task_one_matches_public_static_test_contract(self):
        command = "python -m unittest discover -s tests/static -v"
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        plan = (
            ROOT
            / "docs/superpowers/plans/2026-07-29-autoflow-360-implementation.md"
        ).read_text(encoding="utf-8")
        task_one = plan.split("### Task 1:", maxsplit=1)[1].split("\n---", maxsplit=1)[0]

        self.assertIn(command, readme)
        self.assertIn(command, task_one)
        self.assertNotIn("docs/deployment/local-development.md", task_one)
        self.assertIn("Create: `tests/static/test_environment_check.py`", task_one)
        self.assertRegex(
            task_one,
            r"git add [^\n]*tests/static/test_environment_check\.py",
        )

    def test_task_one_plan_matches_verified_environment_and_truth_contract(self):
        plan = (
            ROOT
            / "docs/superpowers/plans/2026-07-29-autoflow-360-implementation.md"
        ).read_text(encoding="utf-8")
        task_one = plan.split("### Task 1:", maxsplit=1)[1].split("\n---", maxsplit=1)[0]

        for required_text in (
            "规划中的自主新增范围",
            "计划自主实现，当前状态以实际代码和测试为准",
            "Docker Compose 需要 v2",
            "Ubuntu 发行版必须使用 WSL2",
            "ConvertTo-CleanLines",
            "NUL",
            "test_environment_check.py",
        ):
            self.assertIn(required_text, task_one)

        self.assertNotIn("本仓库的自主新增能力包括", task_one)


if __name__ == "__main__":
    unittest.main()
