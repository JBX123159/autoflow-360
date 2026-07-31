from datetime import timedelta

import frappe
from frappe.tests.utils import make_test_records
from frappe.utils import getdate, nowdate


SYNTHETIC_COMPANY = "_Test Company"
SYNTHETIC_CUSTOMER = "_Test Customer"
SYNTHETIC_USER = "Administrator"


def _ensure_synthetic_master_data() -> None:
	if not frappe.db.exists("Company", SYNTHETIC_COMPANY):
		make_test_records("Company")
	if not frappe.db.exists("Customer", SYNTHETIC_CUSTOMER):
		make_test_records("Customer")

	for doctype, name in (
		("Company", SYNTHETIC_COMPANY),
		("Customer", SYNTHETIC_CUSTOMER),
		("User", SYNTHETIC_USER),
	):
		if not frappe.db.exists(doctype, name):
			frappe.throw(f"Synthetic fixture is missing: {doctype} {name}")


def make_customer_project(
	project_name: str,
	*,
	insert: bool = True,
	**overrides,
):
	_ensure_synthetic_master_data()
	today = getdate(nowdate())
	values = {
		"doctype": "Customer Project",
		"project_name": project_name,
		"company": SYNTHETIC_COMPANY,
		"customer": SYNTHETIC_CUSTOMER,
		"product_family": "SYNTHETIC Automotive Material",
		"currency": frappe.get_cached_value(
			"Company",
			SYNTHETIC_COMPANY,
			"default_currency",
		)
		or "INR",
		"expected_amount": 1000,
		"probability": 10,
		"project_manager": SYNTHETIC_USER,
		"target_award_date": today + timedelta(days=30),
		"customer_delivery_date": today + timedelta(days=60),
		"stage": "潜在项目",
		"is_demo": 1,
		"demo_key": f"SYNTHETIC-{frappe.generate_hash(length=20)}",
		"data_classification": "合成测试数据",
		"project_members": [
			{
				"user": SYNTHETIC_USER,
				"responsibility": "SYNTHETIC project owner",
			}
		],
	}
	values.update(overrides)
	project = frappe.get_doc(values)
	if insert:
		project.insert()
	return project
