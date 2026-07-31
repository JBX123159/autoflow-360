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


def _get_open_crm_deal_status() -> str:
	status = frappe.db.get_value(
		"CRM Deal Status",
		{"type": ["in", ["Open", "Ongoing"]]},
		"name",
		order_by="position asc",
	)
	if status:
		return status

	status_doc = frappe.get_doc(
		{
			"doctype": "CRM Deal Status",
			"deal_status": "SYNTHETIC Qualification",
			"type": "Open",
			"probability": 10,
			"color": "blue",
		}
	)
	status_doc.insert()
	return status_doc.name


def make_crm_deal(organization_name: str, **overrides):
	_ensure_synthetic_master_data()
	today = getdate(nowdate())
	values = {
		"doctype": "CRM Deal",
		"naming_series": "CRM-DEAL-.YYYY.-",
		"organization_name": organization_name,
		"status": _get_open_crm_deal_status(),
		"deal_owner": SYNTHETIC_USER,
		"currency": frappe.get_cached_value(
			"Company",
			SYNTHETIC_COMPANY,
			"default_currency",
		)
		or "INR",
		"probability": 40,
		"deal_value": 200000,
		"expected_deal_value": 80000,
		"expected_closure_date": today + timedelta(days=30),
	}
	values.update(overrides)
	deal = frappe.get_doc(values)
	deal.insert()
	return deal


def _make_synthetic_item():
	item_group = frappe.db.get_value(
		"Item Group",
		{"is_group": 0},
		"name",
		order_by="lft asc",
	)
	uom = "Nos" if frappe.db.exists("UOM", "Nos") else frappe.db.get_value(
		"UOM",
		{},
		"name",
	)
	if not item_group or not uom:
		frappe.throw("Synthetic Item requires an existing leaf Item Group and UOM")

	item_code = f"SYNTHETIC-ITEM-{frappe.generate_hash(length=12)}"
	item = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_code,
			"item_name": item_code,
			"item_group": item_group,
			"stock_uom": uom,
			"is_stock_item": 0,
		}
	)
	item.insert()
	return item


def _make_synthetic_customer_contact():
	identifier = frappe.generate_hash(length=12).lower()
	contact = frappe.get_doc(
		{
			"doctype": "Contact",
			"first_name": f"SYNTHETIC Contact {identifier}",
			"email_ids": [
				{
					"email_id": f"synthetic-{identifier}@example.invalid",
					"is_primary": 1,
				}
			],
			"links": [
				{
					"link_doctype": "Customer",
					"link_name": SYNTHETIC_CUSTOMER,
				}
			],
		}
	)
	contact.insert()
	return contact


def make_sample_request(**overrides):
	project_name = overrides.pop("customer_project", None)
	if not project_name:
		project_name = make_customer_project(
			"SYNTHETIC Sample Project"
		).name
	item = _make_synthetic_item()
	contact = _make_synthetic_customer_contact()
	inspection_status = overrides.get("inspection_status", "待检验")
	item_inspection = "通过" if inspection_status == "通过" else "待检验"
	today = getdate(nowdate())
	values = {
		"doctype": "Sample Request",
		"customer_project": project_name,
		"round_number": 1,
		"purpose": "SYNTHETIC customer approval sample",
		"required_date": today + timedelta(days=10),
		"customer_contact": contact.name,
		"status": "草稿",
		"inspection_status": "待检验",
		"items": [
			{
				"item_code": item.name,
				"quantity": 1,
				"uom": item.stock_uom,
				"specification": "SYNTHETIC color and thickness specification",
				"inspection_result": item_inspection,
			}
		],
	}
	values.update(overrides)
	sample = frappe.get_doc(values)
	sample.insert()
	return sample


def make_dispatched_sample():
	from autoflow_360.services.sample_workflow import dispatch_sample

	sample = make_sample_request(
		status="检验中",
		inspection_status="通过",
	)
	dispatch_sample(
		sample.name,
		"SYNTHETIC Carrier",
		f"SYNTHETIC-TRACK-{frappe.generate_hash(length=12)}",
	)
	return frappe.get_doc("Sample Request", sample.name)


def make_customer_portal_user(*, link_customer: bool = True):
	identifier = frappe.generate_hash(length=12).lower()
	email = f"synthetic-portal-{identifier}@example.invalid"
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": f"SYNTHETIC Portal {identifier}",
			"enabled": 1,
			"user_type": "Website User",
			"send_welcome_email": 0,
			"roles": [{"role": "AutoFlow Customer Portal"}],
		}
	)
	user.insert()
	if link_customer:
		customer = frappe.get_doc("Customer", SYNTHETIC_CUSTOMER)
		customer.append("portal_users", {"user": user.name})
		customer.save()
	return user


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
