from datetime import timedelta

import frappe
from frappe.tests.utils import make_test_records
from frappe.utils import flt, getdate, nowdate


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


def _make_synthetic_item(
	*,
	is_stock_item: bool = False,
	safety_stock: float = 0,
):
	if safety_stock < 0:
		frappe.throw("Synthetic Item safety stock cannot be negative")
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
			"is_stock_item": int(is_stock_item),
			"safety_stock": safety_stock,
		}
	)
	item.insert()
	return item


def make_stock_sales_order(
	*,
	quantity: float = 10,
	submit: bool = True,
	warehouse: str | None = "_Test Warehouse - _TC",
	customer_project: str | None = None,
	safety_stock: float = 0,
):
	if quantity <= 0:
		frappe.throw("Synthetic Sales Order quantity must be positive")
	_ensure_synthetic_master_data()
	if warehouse and not frappe.db.exists("Warehouse", warehouse):
		make_test_records("Warehouse")
	if warehouse and not frappe.db.exists("Warehouse", warehouse):
		frappe.throw(f"Synthetic fixture is missing: Warehouse {warehouse}")
	if not customer_project:
		customer_project = make_customer_project(
			"SYNTHETIC Material Planning Project"
		).name

	item = _make_synthetic_item(
		is_stock_item=True,
		safety_stock=safety_stock,
	)
	today = getdate(nowdate())
	order = frappe.new_doc("Sales Order")
	order.company = SYNTHETIC_COMPANY
	order.customer = SYNTHETIC_CUSTOMER
	order.order_type = "Sales"
	order.transaction_date = today
	order.delivery_date = today + timedelta(days=30)
	order.currency = (
		frappe.get_cached_value(
			"Company",
			SYNTHETIC_COMPANY,
			"default_currency",
		)
		or "INR"
	)
	order.custom_customer_project = customer_project
	order.append(
		"items",
		{
			"item_code": item.name,
			"qty": quantity,
			"uom": item.stock_uom,
			"warehouse": warehouse,
			"delivery_date": order.delivery_date,
			"rate": 100,
		},
	)
	order.insert()
	if submit:
		order.submit()
	return order


def set_warehouse_stock(
	item_code: str,
	warehouse: str,
	*,
	actual_qty: float,
	incoming_qty: float = 0,
	extra_reserved_qty: float = 0,
):
	if incoming_qty < 0 or extra_reserved_qty < 0:
		frappe.throw("Synthetic incoming and extra reserved quantities cannot be negative")
	if not frappe.db.exists("Item", item_code):
		frappe.throw(f"Synthetic fixture is missing: Item {item_code}")
	if not frappe.db.exists("Warehouse", warehouse):
		frappe.throw(f"Synthetic fixture is missing: Warehouse {warehouse}")

	from erpnext.stock.utils import get_bin

	bin_doc = get_bin(item_code, warehouse)
	bin_doc.reload()
	frappe.db.set_value(
		"Bin",
		bin_doc.name,
		{
			"actual_qty": actual_qty,
			"ordered_qty": incoming_qty,
			"reserved_qty": flt(bin_doc.reserved_qty) + extra_reserved_qty,
		},
		update_modified=False,
	)
	return frappe.get_doc("Bin", bin_doc.name)


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


def make_customer_approved_sample(customer_project: str):
	from autoflow_360.services.sample_workflow import (
		dispatch_sample,
		record_customer_feedback,
	)

	sample = make_sample_request(
		customer_project=customer_project,
		status="检验中",
		inspection_status="通过",
	)
	dispatch_sample(
		sample.name,
		"SYNTHETIC Carrier",
		f"SYNTHETIC-TRACK-{frappe.generate_hash(length=12)}",
	)
	record_customer_feedback(
		sample.name,
		"客户认可",
		"SYNTHETIC customer accepted the sample",
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


def make_internal_user(*roles: str):
	identifier = frappe.generate_hash(length=12).lower()
	email = f"synthetic-internal-{identifier}@example.invalid"
	role_names = list(dict.fromkeys(("Sales User", *roles)))
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": f"SYNTHETIC Internal {identifier}",
			"enabled": 1,
			"user_type": "System User",
			"send_welcome_email": 0,
			"roles": [{"role": role} for role in role_names],
		}
	)
	user.insert()
	return user


def make_approval_rule(
	*,
	role: str = "System Manager",
	document_type: str = "Quotation",
	amount_limit: float = 1_000_000,
	discount_limit: float = 100,
	risk_level: str = "高",
):
	_ensure_synthetic_master_data()
	rule = frappe.get_doc(
		{
			"doctype": "AutoFlow Approval Rule",
			"company": SYNTHETIC_COMPANY,
			"document_type": document_type,
			"role": role,
			"amount_limit": amount_limit,
			"discount_limit": discount_limit,
			"risk_level": risk_level,
			"active": 1,
		}
	)
	rule.insert()
	return rule


def make_quotation(
	*,
	customer_project: str,
	valid_till=None,
	customer_confirmed: bool = False,
	rate: float = 100,
	floor_rate: float = 0,
	discount_percentage: float = 0,
	insert: bool = True,
):
	_ensure_synthetic_master_data()
	item = _make_synthetic_item()
	today = getdate(nowdate())
	quotation = frappe.new_doc("Quotation")
	quotation.company = SYNTHETIC_COMPANY
	quotation.quotation_to = "Customer"
	quotation.party_name = SYNTHETIC_CUSTOMER
	quotation.currency = (
		frappe.get_cached_value(
			"Company",
			SYNTHETIC_COMPANY,
			"default_currency",
		)
		or "INR"
	)
	quotation.transaction_date = today
	quotation.valid_till = valid_till or today + timedelta(days=30)
	quotation.custom_customer_project = customer_project
	quotation.custom_customer_confirmed = int(customer_confirmed)
	quotation.append(
		"items",
		{
			"item_code": item.name,
			"qty": 10,
			"uom": item.stock_uom,
			"rate": rate,
			"discount_percentage": discount_percentage,
			"custom_floor_rate": floor_rate,
		},
	)
	if insert:
		quotation.insert()
	return quotation


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
