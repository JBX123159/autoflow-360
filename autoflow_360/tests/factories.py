from datetime import timedelta

import frappe
from frappe.tests.utils import make_test_records
from frappe.utils import flt, getdate, now_datetime, nowdate


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


def make_foreign_customer():
	_ensure_synthetic_master_data()
	identifier = frappe.generate_hash(length=12).lower()
	customer = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": f"SYNTHETIC Customer {identifier}",
			"customer_type": "Company",
			"customer_group": frappe.db.get_value(
				"Customer",
				SYNTHETIC_CUSTOMER,
				"customer_group",
			),
			"territory": frappe.db.get_value(
				"Customer",
				SYNTHETIC_CUSTOMER,
				"territory",
			),
		}
	)
	customer.insert()
	return customer


def make_customer_portal_user(
	*,
	link_customer: bool = True,
	customer: str = SYNTHETIC_CUSTOMER,
):
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
		customer_doc = frappe.get_doc("Customer", customer)
		customer_doc.append("portal_users", {"user": user.name})
		customer_doc.save()
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


def make_supplier_portal_account():
	supplier_group = frappe.db.get_value(
		"Supplier Group",
		{"is_group": 0},
		"name",
		order_by="lft asc",
	)
	if not supplier_group:
		make_test_records("Supplier")
		supplier_group = frappe.db.get_value(
			"Supplier Group",
			{"is_group": 0},
			"name",
			order_by="lft asc",
		)
	if not supplier_group:
		frappe.throw("Synthetic Supplier requires a leaf Supplier Group")

	identifier = frappe.generate_hash(length=12).lower()
	supplier = frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": f"SYNTHETIC Supplier {identifier}",
			"supplier_group": supplier_group,
			"supplier_type": "Company",
		}
	)
	supplier.insert()

	email = f"synthetic-supplier-{identifier}@example.invalid"
	portal_user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": f"SYNTHETIC Supplier {identifier}",
			"enabled": 1,
			"user_type": "Website User",
			"send_welcome_email": 0,
			"roles": [
				{"role": "Supplier"},
				{"role": "AutoFlow Supplier Portal"},
			],
		}
	)
	portal_user.insert()
	supplier.append("portal_users", {"user": portal_user.name})
	supplier.save()
	return frappe._dict(
		{
			"name": supplier.name,
			"portal_user": portal_user.name,
		}
	)


def make_two_suppliers_with_portal_users():
	return make_supplier_portal_account(), make_supplier_portal_account()


def make_project_material_request():
	from autoflow_360.services.material_planning import create_material_request

	order = make_stock_sales_order()
	set_warehouse_stock(
		order.items[0].item_code,
		order.items[0].warehouse,
		actual_qty=0,
	)
	request_name = create_material_request(order.name)
	if not request_name:
		frappe.throw("Synthetic Material Request was not created")
	request = frappe.get_doc("Material Request", request_name)
	request.submit()
	return request


def make_project_request_for_quotation(suppliers: list[str]):
	from autoflow_360.services.procurement import make_project_rfq

	request = make_project_material_request()
	rfq_name = make_project_rfq(request.name, suppliers)
	return frappe.get_doc("Request for Quotation", rfq_name)


def make_supplier_quotation(
	supplier_account=None,
	*,
	rate: float = 25,
):
	from autoflow_360.services.procurement import submit_supplier_quote

	supplier_account = supplier_account or make_supplier_portal_account()
	rfq = make_project_request_for_quotation([supplier_account.name])
	quote_items = [
		{
			"rfq_item": row.name,
			"rate": rate,
			"expected_delivery_date": row.schedule_date,
		}
		for row in rfq.items
	]
	previous_user = frappe.session.user
	try:
		frappe.set_user(supplier_account.portal_user)
		quote_name = submit_supplier_quote(
			rfq.name,
			quote_items,
			str(getdate(nowdate()) + timedelta(days=30)),
		)
	finally:
		frappe.set_user(previous_user)
	return frappe.get_doc("Supplier Quotation", quote_name)


def make_purchase_order(*, submit: bool = False):
	from autoflow_360.services.procurement import (
		make_purchase_order_from_supplier_quote,
	)

	quote = make_supplier_quotation()
	order_name = make_purchase_order_from_supplier_quote(quote.name)
	order = frappe.get_doc("Purchase Order", order_name)
	if submit:
		order.submit()
	return order


def make_submitted_project_purchase_order():
	return make_purchase_order(submit=True)


def make_purchase_receipt_from_order(purchase_order: str):
	from erpnext.buying.doctype.purchase_order.purchase_order import (
		make_purchase_receipt,
	)

	return make_purchase_receipt(purchase_order)


def make_purchase_invoice_from_order(purchase_order: str):
	from erpnext.buying.doctype.purchase_order.purchase_order import (
		make_purchase_invoice,
	)

	return make_purchase_invoice(purchase_order)


def make_delivery_note(
	*,
	quantity: float = 10,
	available_stock: float = 20,
):
	from erpnext.selling.doctype.sales_order.sales_order import (
		make_delivery_note as make_erpnext_delivery_note,
	)
	from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

	order = make_stock_sales_order(quantity=quantity)
	if available_stock < 0:
		frappe.throw("Synthetic Delivery Note stock cannot be negative")
	if available_stock:
		make_stock_entry(
			item_code=order.items[0].item_code,
			to_warehouse=order.items[0].warehouse,
			qty=available_stock,
			company=order.company,
			rate=100,
		)
	delivery = make_erpnext_delivery_note(order.name)
	delivery.custom_customer_project = order.custom_customer_project
	if not delivery.items:
		frappe.throw("Synthetic Delivery Note requires at least one item")
	return delivery


def make_submitted_delivery_note(**kwargs):
	delivery = make_delivery_note(**kwargs)
	delivery.insert()
	delivery.submit()
	return delivery


def _advance_project_to_closure_ready(project_name: str):
	from autoflow_360.services.project_status import MAIN_STAGE_SEQUENCE

	project = frappe.get_doc("Customer Project", project_name)
	target_index = MAIN_STAGE_SEQUENCE.index("待回款")
	while MAIN_STAGE_SEQUENCE.index(project.stage) < target_index:
		current_index = MAIN_STAGE_SEQUENCE.index(project.stage)
		project.stage = MAIN_STAGE_SEQUENCE[current_index + 1]
		project.save(ignore_permissions=True)
		project.reload()
	return project


def make_fulfilled_project(
	*,
	outstanding_amount: float = 0,
	confirm_receipt: bool = True,
):
	from erpnext.accounts.doctype.payment_entry.payment_entry import (
		get_payment_entry,
	)
	from erpnext.selling.doctype.sales_order.sales_order import (
		make_delivery_note as make_erpnext_delivery_note,
	)
	from erpnext.selling.doctype.sales_order.sales_order import (
		make_sales_invoice,
	)
	from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

	from autoflow_360.services.delivery import confirm_customer_receipt

	if outstanding_amount < 0:
		frappe.throw("Synthetic outstanding amount cannot be negative")
	project = make_customer_project("SYNTHETIC Fulfilled Customer Project")
	order = make_stock_sales_order(
		quantity=1,
		customer_project=project.name,
	)
	make_stock_entry(
		item_code=order.items[0].item_code,
		to_warehouse=order.items[0].warehouse,
		qty=1,
		company=order.company,
		rate=100,
	)
	delivery = make_erpnext_delivery_note(order.name)
	delivery.custom_customer_project = project.name
	delivery.insert()
	delivery.submit()

	if confirm_receipt:
		portal_user = make_customer_portal_user(customer=project.customer)
		previous_user = frappe.session.user
		try:
			frappe.set_user(portal_user.name)
			confirm_customer_receipt(delivery.name)
		finally:
			frappe.set_user(previous_user)

	invoice = make_sales_invoice(order.name)
	invoice.custom_customer_project = project.name
	invoice.insert()
	invoice.submit()
	invoice.reload()
	if outstanding_amount > flt(invoice.outstanding_amount):
		frappe.throw("Synthetic outstanding amount exceeds invoice total")

	amount_to_pay = flt(invoice.outstanding_amount) - outstanding_amount
	if amount_to_pay > 0:
		payment = get_payment_entry("Sales Invoice", invoice.name)
		payment.custom_customer_project = project.name
		payment.paid_amount = amount_to_pay
		payment.received_amount = amount_to_pay
		for reference in payment.references:
			if (
				reference.reference_doctype == "Sales Invoice"
				and reference.reference_name == invoice.name
			):
				reference.allocated_amount = amount_to_pay
		payment.insert()
		payment.submit()

	return _advance_project_to_closure_ready(project.name)


def make_overdue_project(*, days_overdue: int = 3):
	if days_overdue <= 0:
		frappe.throw("Synthetic overdue days must be positive")
	return make_customer_project(
		"SYNTHETIC Overdue Milestone Project",
		milestones=[
			{
				"milestone_name": "SYNTHETIC PPAP approval",
				"planned_date": getdate(nowdate()) - timedelta(days=days_overdue),
				"owner_user": "Administrator",
				"status": "进行中",
			}
		],
	)


def make_pending_feedback_project(*, days_waiting: int = 5):
	if days_waiting <= 0:
		frappe.throw("Synthetic feedback waiting days must be positive")
	frappe.db.set_single_value("AutoFlow Settings", "feedback_warning_days", 3)
	sample = make_dispatched_sample()
	frappe.db.set_value(
		"Sample Request",
		sample.name,
		"dispatch_time",
		now_datetime() - timedelta(days=days_waiting),
		update_modified=False,
	)
	return frappe.get_doc("Customer Project", sample.customer_project)


def make_expiring_quotation_project(*, days_until_expiry: int = 2):
	if days_until_expiry < 0:
		frappe.throw("Synthetic quotation expiry days cannot be negative")
	frappe.db.set_single_value(
		"AutoFlow Settings",
		"quotation_expiry_warning_days",
		7,
	)
	project = make_customer_project("SYNTHETIC Expiring Quotation Project")
	make_customer_approved_sample(project.name)
	make_approval_rule(role="System Manager", document_type="Quotation")
	quotation = make_quotation(
		customer_project=project.name,
		valid_till=getdate(nowdate()) + timedelta(days=days_until_expiry),
	)
	quotation.submit()
	return frappe.get_doc("Customer Project", project.name)


def make_project_with_stock_gap():
	project = make_customer_project("SYNTHETIC Stock Gap Project")
	make_stock_sales_order(
		quantity=10,
		customer_project=project.name,
	)
	return frappe.get_doc("Customer Project", project.name)


def make_project_with_supplier_eta_after_delivery():
	from autoflow_360.services.procurement import update_supplier_eta

	order = make_purchase_order(submit=True)
	project = frappe.get_doc("Customer Project", order.custom_customer_project)
	portal_user = frappe.db.get_value(
		"Portal User",
		{
			"parenttype": "Supplier",
			"parent": order.supplier,
		},
		"user",
	)
	if not portal_user:
		frappe.throw("Synthetic supplier portal user is missing")
	previous_user = frappe.session.user
	try:
		frappe.set_user(portal_user)
		update_supplier_eta(
			order.name,
			str(getdate(project.customer_delivery_date) + timedelta(days=5)),
			"SYNTHETIC supplier capacity delay",
		)
	finally:
		frappe.set_user(previous_user)
	return frappe.get_doc("Customer Project", project.name)


def make_unpaid_project(*, days_overdue: int = 8):
	if days_overdue <= 0:
		frappe.throw("Synthetic receivable overdue days must be positive")
	project = make_fulfilled_project(outstanding_amount=100)
	invoice_name = frappe.db.get_value(
		"Sales Invoice",
		{"custom_customer_project": project.name, "docstatus": 1},
		"name",
	)
	frappe.db.set_value(
		"Sales Invoice",
		invoice_name,
		"due_date",
		getdate(nowdate()) - timedelta(days=days_overdue),
		update_modified=False,
	)
	return frappe.get_doc("Customer Project", project.name)


def make_inactive_project(*, days_inactive: int = 10):
	if days_inactive <= 0:
		frappe.throw("Synthetic inactive days must be positive")
	frappe.db.set_single_value("AutoFlow Settings", "project_inactive_days", 7)
	return make_customer_project(
		"SYNTHETIC Inactive Customer Project",
		last_meaningful_activity=now_datetime() - timedelta(days=days_inactive),
	)
