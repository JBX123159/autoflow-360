import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SEED_FILE = ROOT / "autoflow_360" / "demo" / "seed.py"
PROJECT_SCHEMA = (
	ROOT
	/ "autoflow_360"
	/ "autoflow_360"
	/ "doctype"
	/ "customer_project"
	/ "customer_project.json"
)


class DemoContractTest(unittest.TestCase):
	def test_demo_seed_is_production_code_and_parses(self):
		self.assertTrue(SEED_FILE.exists())
		ast.parse(SEED_FILE.read_text(encoding="utf-8"))

	def test_demo_seed_uses_cny_and_fixed_scenario_keys(self):
		source = SEED_FILE.read_text(encoding="utf-8")
		self.assertIn('DEMO_CURRENCY = "CNY"', source)
		for value in ("DEMO-NORMAL-001", "DEMO-DELAY-001", "DEMO-RESAMPLE-001"):
			self.assertIn(value, source)

	def test_demo_seed_does_not_import_test_factories(self):
		source = SEED_FILE.read_text(encoding="utf-8")
		self.assertNotIn("autoflow_360.tests", source)
		self.assertNotIn("make_test_records", source)

	def test_demo_seed_calls_formal_business_services(self):
		source = SEED_FILE.read_text(encoding="utf-8")
		for symbol in (
			"create_project_from_deal",
			"record_customer_feedback",
			"create_resample",
			"create_sales_order_from_quotation",
			"create_material_request",
			"make_project_rfq",
			"make_purchase_order_from_supplier_quote",
			"update_supplier_eta",
			"confirm_customer_receipt",
			"transition_exception",
			"close_project",
		):
			self.assertIn(symbol, source)

	def test_customer_project_schema_has_demo_scenario_marker(self):
		payload = json.loads(PROJECT_SCHEMA.read_text(encoding="utf-8"))
		fields = {field["fieldname"]: field for field in payload["fields"]}
		self.assertEqual(
			fields["demo_scenario"]["options"],
			"normal\nsupplier_delay\nresample",
		)
		self.assertEqual(fields["demo_scenario"]["read_only"], 1)


if __name__ == "__main__":
	unittest.main()
