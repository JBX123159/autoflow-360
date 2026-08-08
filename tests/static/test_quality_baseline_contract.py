import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
E2E_ROOT = ROOT / "tests" / "e2e"
PERFORMANCE_ROOT = ROOT / "tests" / "performance"
PERFORMANCE_ENTRY_ROOT = ROOT / "autoflow_360" / "performance"


class QualityBaselineContractTest(unittest.TestCase):
	def test_playwright_package_is_pinned_and_keeps_secrets_out_of_source(self):
		package_file = E2E_ROOT / "package.json"
		self.assertTrue(package_file.exists())
		package = json.loads(package_file.read_text(encoding="utf-8"))
		version = package["devDependencies"]["@playwright/test"]
		self.assertRegex(version, r"^\d+\.\d+\.\d+$")
		all_source = "\n".join(
			path.read_text(encoding="utf-8")
			for path in E2E_ROOT.glob("*.js")
		)
		self.assertIn("AUTOFLOW_E2E_PASSWORD", all_source)
		self.assertNotIn("admin", all_source.lower().replace("administrator", ""))

	def test_three_browser_scenarios_assert_business_evidence(self):
		expectations = {
			"normal-project.spec.js": ("DEMO-NORMAL-001", "已结项", "Payment Entry"),
			"supplier-delay.spec.js": ("DEMO-DELAY-001", "供应商延期", "已关闭"),
			"resample.spec.js": ("DEMO-RESAMPLE-001", "重新打样", "客户认可"),
		}
		for filename, markers in expectations.items():
			source = (E2E_ROOT / filename).read_text(encoding="utf-8")
			for marker in markers:
				self.assertIn(marker, source)

	def test_scale_generator_has_fixed_targets_and_synthetic_marker(self):
		generator = PERFORMANCE_ROOT / "generate_scale.py"
		self.assertTrue(generator.exists())
		source = generator.read_text(encoding="utf-8")
		ast.parse(source)
		for marker in (
			"PROJECT_TARGET = 200",
			"SAMPLE_TARGET = 1_000",
			"ORDER_TARGET = 500",
			"EVIDENCE_TARGET = 5_000",
			"PERF-",
			"合成性能数据",
		):
			self.assertIn(marker, source)

	def test_measurement_uses_warmup_and_ten_recorded_runs(self):
		measure = PERFORMANCE_ROOT / "measure.py"
		self.assertTrue(measure.exists())
		source = measure.read_text(encoding="utf-8")
		ast.parse(source)
		for marker in (
			"WARMUP_RUNS = 1",
			"MEASURED_RUNS = 10",
			'"p50_ms"',
			'"p95_ms"',
			'"max_ms"',
			"performance.json",
		):
			self.assertIn(marker, source)

	def test_performance_tools_have_installed_app_entry_points(self):
		for filename in ("generate_scale.py", "measure.py"):
			source = (PERFORMANCE_ENTRY_ROOT / filename).read_text(encoding="utf-8")
			ast.parse(source)
			self.assertIn("load_tool", source)
			self.assertIn('"run"', source)

	def test_seed_script_invokes_the_production_seed(self):
		source = (ROOT / "scripts" / "seed-demo.ps1").read_text(encoding="utf-8")
		self.assertIn("autoflow_360.demo.seed.seed_demo_data", source)
		self.assertIn("$ErrorActionPreference = \"Stop\"", source)


if __name__ == "__main__":
	unittest.main()
