from contextlib import contextmanager
from datetime import timedelta

import frappe
from frappe.utils import getdate, now_datetime, nowdate

from autoflow_360.risk_engine.service import evaluate_project, upsert_risks
from autoflow_360.services.deal_conversion import create_project_from_deal
from autoflow_360.services.delivery import confirm_customer_receipt
from autoflow_360.services.exception_workflow import transition_exception
from autoflow_360.services.material_planning import create_material_request
from autoflow_360.services.procurement import (
	make_project_rfq,
	make_purchase_order_from_supplier_quote,
	submit_supplier_quote,
	update_supplier_eta,
)
from autoflow_360.services.project_closure import (
	close_project,
	create_project_closure_request,
)
from autoflow_360.services.project_status import MAIN_STAGE_SEQUENCE, set_project_stage
from autoflow_360.services.sales_conversion import (
	create_quotation_approval_request,
	create_sales_order_from_quotation,
)
from autoflow_360.services.sample_workflow import (
	create_resample,
	dispatch_sample,
	record_customer_feedback,
)


DEMO_CURRENCY = "CNY"
DEMO_COMPANY = "AutoFlow 360 合成演示制造有限公司"
DEMO_COMPANY_ABBR = "AFD"
DEMO_CUSTOMER = "合成客户 · 北方新能源汽车"
DEMO_SUPPLIER = "合成供应商 · 华东精密部件"
DEMO_CONTACT_EMAIL = "autoflow-demo-contact@example.invalid"
DEMO_CUSTOMER_USER = "autoflow-demo-customer@example.invalid"
DEMO_SUPPLIER_USER = "autoflow-demo-supplier@example.invalid"
DEMO_EXECUTIVE_USER = "autoflow-demo-executive@example.invalid"
DEMO_PROCUREMENT_USER = "autoflow-demo-procurement@example.invalid"
RESET_CONFIRMATION = "DELETE AUTOFLOW DEMO DATA"

SCENARIO_KEYS = {
	"normal": "DEMO-NORMAL-001",
	"supplier_delay": "DEMO-DELAY-001",
	"resample": "DEMO-RESAMPLE-001",
}

SCENARIO_TITLES = {
	"normal": "正常交付与回款结项",
	"supplier_delay": "供应商延期与整改关闭",
	"resample": "客户退样与重新打样",
}

SCENARIO_AMOUNTS = {
	"normal": 680_000,
	"supplier_delay": 420_000,
	"resample": 260_000,
}


@contextmanager
def _acting_as(user: str):
	previous_user = frappe.session.user
	try:
		frappe.set_user(user)
		yield
	finally:
		frappe.set_user(previous_user)


def _require_demo_administrator() -> None:
	if frappe.session.user == "Administrator":
		return
	if "AutoFlow Administrator" not in frappe.get_roles():
		raise frappe.PermissionError


def _ensure_currency_settings() -> None:
	if not frappe.db.exists("Currency", DEMO_CURRENCY):
		frappe.throw("CNY currency master is required before seeding demo data.")
	frappe.db.set_value("Currency", DEMO_CURRENCY, "enabled", 1)
	if frappe.db.exists("DocType", "FCRM Settings"):
		frappe.db.set_single_value("FCRM Settings", "currency", DEMO_CURRENCY)
	if frappe.db.exists("DocType", "Global Defaults"):
		frappe.db.set_single_value("Global Defaults", "default_currency", DEMO_CURRENCY)
	frappe.clear_cache()


def _ensure_demo_company() -> str:
	company_name = frappe.db.get_value(
		"Company",
		{"company_name": DEMO_COMPANY},
		"name",
	)
	if not company_name:
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": DEMO_COMPANY,
				"abbr": DEMO_COMPANY_ABBR,
				"default_currency": DEMO_CURRENCY,
				"country": "China",
				"create_chart_of_accounts_based_on": "Standard Template",
				"chart_of_accounts": "Standard",
			}
		)
		company.insert(ignore_permissions=True)
		company_name = company.name
	if frappe.get_cached_value("Company", company_name, "default_currency") != DEMO_CURRENCY:
		frappe.throw("Existing AutoFlow demo company must use CNY.")
	return company_name


def _first_leaf(doctype: str) -> str:
	name = frappe.db.get_value(
		doctype,
		{"is_group": 0},
		"name",
		order_by="creation asc",
	)
	if not name:
		frappe.throw(f"A leaf {doctype} is required before seeding demo data.")
	return name


def _ensure_demo_customer() -> str:
	name = frappe.db.get_value(
		"Customer",
		{"customer_name": DEMO_CUSTOMER},
		"name",
	)
	if name:
		return name
	customer = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": DEMO_CUSTOMER,
			"customer_type": "Company",
			"customer_group": _first_leaf("Customer Group"),
			"territory": _first_leaf("Territory"),
		}
	)
	customer.insert(ignore_permissions=True)
	return customer.name


def _ensure_demo_supplier() -> str:
	name = frappe.db.get_value(
		"Supplier",
		{"supplier_name": DEMO_SUPPLIER},
		"name",
	)
	if name:
		return name
	supplier = frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": DEMO_SUPPLIER,
			"supplier_group": _first_leaf("Supplier Group"),
			"supplier_type": "Company",
		}
	)
	supplier.insert(ignore_permissions=True)
	return supplier.name


def _ensure_user(email: str, first_name: str, roles: tuple[str, ...], user_type: str) -> str:
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"enabled": 1,
				"user_type": user_type,
				"send_welcome_email": 0,
			}
		)
	existing_roles = {row.role for row in user.roles}
	roles_changed = False
	for role in roles:
		if not frappe.db.exists("Role", role):
			frappe.throw(f"Required demo role is missing: {role}")
		if role not in existing_roles:
			user.append("roles", {"role": role})
			roles_changed = True
	if user.is_new():
		user.insert(ignore_permissions=True)
	elif roles_changed:
		user.save(ignore_permissions=True)
	return user.name


def _ensure_portal_link(doctype: str, party_name: str, user: str) -> None:
	if frappe.db.exists(
		"Portal User",
		{
			"parenttype": doctype,
			"parent": party_name,
			"user": user,
		},
	):
		return
	party = frappe.get_doc(doctype, party_name)
	party.append("portal_users", {"user": user})
	party.save(ignore_permissions=True)


def _ensure_demo_contact(customer: str) -> str:
	name = frappe.db.get_value(
		"Contact",
		{"first_name": "合成客户联系人"},
		"name",
	)
	if name:
		return name
	contact = frappe.get_doc(
		{
			"doctype": "Contact",
			"first_name": "合成客户联系人",
			"email_ids": [
				{"email_id": DEMO_CONTACT_EMAIL, "is_primary": 1},
			],
			"links": [
				{"link_doctype": "Customer", "link_name": customer},
			],
		}
	)
	contact.insert(ignore_permissions=True)
	return contact.name


def _ensure_demo_warehouse(company: str) -> str:
	warehouse = frappe.db.get_value(
		"Warehouse",
		{"company": company, "is_group": 0, "disabled": 0},
		"name",
		order_by="creation asc",
	)
	if not warehouse:
		frappe.throw("AutoFlow demo company requires a non-group warehouse.")
	return warehouse


def _ensure_demo_item(scenario: str) -> str:
	item_code = f"AFD-{scenario.upper()}-COMPONENT"
	if frappe.db.exists("Item", item_code):
		return item_code
	uom = "Nos" if frappe.db.exists("UOM", "Nos") else frappe.db.get_value("UOM", {}, "name")
	if not uom:
		frappe.throw("A stock UOM is required before seeding demo data.")
	item = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_code,
			"item_name": f"合成汽车部件 · {SCENARIO_KEYS[scenario]}",
			"item_group": _first_leaf("Item Group"),
			"stock_uom": uom,
			"is_stock_item": 1,
			"is_sales_item": 1,
			"is_purchase_item": 1,
		}
	)
	item.insert(ignore_permissions=True)
	return item.name


def _ensure_demo_roles_and_links(customer: str, supplier: str) -> dict[str, str]:
	users = {
		"customer": _ensure_user(
			DEMO_CUSTOMER_USER,
			"合成客户门户",
			("AutoFlow Customer Portal",),
			"Website User",
		),
		"supplier": _ensure_user(
			DEMO_SUPPLIER_USER,
			"合成供应商门户",
			("Supplier", "AutoFlow Supplier Portal"),
			"Website User",
		),
		"executive": _ensure_user(
			DEMO_EXECUTIVE_USER,
			"合成管理审批人",
			("Sales User", "Purchase User", "AutoFlow Executive"),
			"System User",
		),
		"procurement": _ensure_user(
			DEMO_PROCUREMENT_USER,
			"合成采购负责人",
			("Purchase User", "AutoFlow Procurement"),
			"System User",
		),
	}
	_ensure_portal_link("Customer", customer, users["customer"])
	_ensure_portal_link("Supplier", supplier, users["supplier"])
	return users


def _ensure_approval_rule(company: str, document_type: str) -> str:
	existing = frappe.db.get_value(
		"AutoFlow Approval Rule",
		{
			"company": company,
			"document_type": document_type,
			"role": "AutoFlow Executive",
			"active": 1,
		},
		"name",
	)
	if existing:
		return existing
	rule = frappe.get_doc(
		{
			"doctype": "AutoFlow Approval Rule",
			"company": company,
			"document_type": document_type,
			"role": "AutoFlow Executive",
			"amount_limit": 10_000_000,
			"discount_limit": 100,
			"risk_level": "高",
			"active": 1,
		}
	)
	rule.insert(ignore_permissions=True)
	return rule.name


def _ensure_open_deal_status() -> str:
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
			"deal_status": "合成演示 · 需求确认",
			"type": "Open",
			"probability": 25,
			"color": "blue",
		}
	)
	status_doc.insert(ignore_permissions=True)
	return status_doc.name


def _ensure_demo_project(scenario: str, company: str, customer: str) -> str:
	key = SCENARIO_KEYS[scenario]
	existing = frappe.db.get_value("Customer Project", {"demo_key": key}, "name")
	if existing:
		return existing
	today = getdate(nowdate())
	organization_name = f"{key} · {SCENARIO_TITLES[scenario]}"
	deal_name = frappe.db.get_value(
		"CRM Deal",
		{"organization_name": organization_name},
		"name",
	)
	if not deal_name:
		deal = frappe.get_doc(
			{
				"doctype": "CRM Deal",
				"naming_series": "CRM-DEAL-.YYYY.-",
				"organization_name": organization_name,
				"status": _ensure_open_deal_status(),
				"deal_owner": "Administrator",
				"currency": DEMO_CURRENCY,
				"probability": 65,
				"deal_value": SCENARIO_AMOUNTS[scenario],
				"expected_deal_value": SCENARIO_AMOUNTS[scenario],
				"expected_closure_date": today + timedelta(days=30),
			}
		)
		deal.insert(ignore_permissions=True)
		deal_name = deal.name
	project_name = create_project_from_deal(
		deal_name,
		company,
		customer,
		"汽车轻量化结构件",
		str(today + timedelta(days=90)),
	)
	project = frappe.get_doc("Customer Project", project_name)
	project.is_demo = 1
	project.demo_key = key
	project.demo_scenario = scenario
	project.data_classification = "合成演示数据 · 不代表真实客户或经营结果"
	project.next_action = "查看演示场景证据链"
	project.next_action_owner = "Administrator"
	project.next_action_due_date = today + timedelta(days=7)
	project.save(ignore_permissions=True)
	return project.name


def _ensure_project_member(project_name: str, user: str, responsibility: str) -> None:
	project = frappe.get_doc("Customer Project", project_name)
	if any(row.user == user for row in project.project_members):
		return
	project.append(
		"project_members",
		{"user": user, "responsibility": responsibility},
	)
	project.save(ignore_permissions=True)


def _ensure_sample(
	project_name: str,
	item_code: str,
	contact: str,
	round_number: int,
) -> str:
	existing = frappe.db.get_value(
		"Sample Request",
		{"customer_project": project_name, "round_number": round_number},
		"name",
	)
	if existing:
		return existing
	project = frappe.get_doc("Customer Project", project_name)
	today = getdate(nowdate())
	sample = frappe.get_doc(
		{
			"doctype": "Sample Request",
			"customer_project": project.name,
			"round_number": round_number,
			"purpose": f"{project.demo_key} 客户认可样件",
			"required_date": today + timedelta(days=10 + round_number),
			"customer_contact": contact,
			"status": "检验中",
			"inspection_status": "通过",
			"items": [
				{
					"item_code": item_code,
					"quantity": 1,
					"uom": frappe.get_cached_value("Item", item_code, "stock_uom"),
					"specification": "合成规格：尺寸、外观与材料性能确认",
					"inspection_result": "通过",
				},
			],
		}
	)
	sample.insert(ignore_permissions=True)
	return sample.name


def _dispatch_and_record_feedback(
	sample_name: str,
	scenario: str,
	decision: str,
	comments: str,
	customer_user: str,
) -> str:
	sample = frappe.get_doc("Sample Request", sample_name)
	if sample.status not in {"已发出", "等待反馈", "客户认可", "重新打样", "拒绝"}:
		dispatch_sample(
			sample.name,
			"合成演示物流",
			f"AF360-{scenario.upper()}-R{sample.round_number}",
		)
	if frappe.db.exists("Customer Feedback", {"sample_request": sample.name}):
		return frappe.db.get_value("Customer Feedback", {"sample_request": sample.name}, "name")
	with _acting_as(customer_user):
		return record_customer_feedback(sample.name, decision, comments)


def _ensure_customer_approved_sample(
	project_name: str,
	item_code: str,
	contact: str,
	customer_user: str,
	scenario: str,
) -> str:
	sample_name = _ensure_sample(project_name, item_code, contact, 1)
	_dispatch_and_record_feedback(
		sample_name,
		scenario,
		"客户认可",
		"合成客户确认样件满足尺寸、外观和材料性能要求。",
		customer_user,
	)
	return sample_name


def _ensure_submitted_quotation(
	project_name: str,
	item_code: str,
	executive: str,
	warehouse: str,
) -> str:
	existing = frappe.db.get_value(
		"Quotation",
		{"custom_customer_project": project_name, "docstatus": ["<", 2]},
		"name",
	)
	if existing and frappe.db.get_value("Quotation", existing, "docstatus") == 1:
		return existing
	project = frappe.get_doc("Customer Project", project_name)
	today = getdate(nowdate())
	quotation = frappe.get_doc("Quotation", existing) if existing else frappe.new_doc("Quotation")
	if not existing:
		quotation.company = project.company
		quotation.quotation_to = "Customer"
		quotation.party_name = project.customer
		quotation.currency = DEMO_CURRENCY
		quotation.transaction_date = today
		quotation.valid_till = today + timedelta(days=45)
		quotation.custom_customer_project = project.name
		quotation.custom_customer_confirmed = 1
		quotation.append(
			"items",
			{
				"item_code": item_code,
				"qty": 10,
				"uom": frappe.get_cached_value("Item", item_code, "stock_uom"),
				"rate": 1_200,
				"custom_floor_rate": 1_300,
				"warehouse": warehouse,
			},
		)
		quotation.insert(ignore_permissions=True)
	request_name = create_quotation_approval_request(quotation.name)
	with _acting_as(executive):
		request = frappe.get_doc("AutoFlow Approval Request", request_name)
		if request.docstatus == 0:
			request.approve("合成演示：价格与项目风险在授权范围内。")
	quotation.reload()
	if quotation.docstatus == 0:
		quotation.submit()
	return quotation.name


def _ensure_submitted_sales_order(
	quotation_name: str,
	warehouse: str,
) -> str:
	order_name = create_sales_order_from_quotation(quotation_name)
	order = frappe.get_doc("Sales Order", order_name)
	if order.docstatus == 0:
		for row in order.items:
			row.warehouse = warehouse
		order.submit()
	return order.name


def _ensure_purchase_path(
	project_name: str,
	order_name: str,
	supplier: str,
	supplier_user: str,
) -> str:
	request_name = create_material_request(order_name)
	if not request_name:
		frappe.throw("Demo sales order must produce a material shortage.")
	request = frappe.get_doc("Material Request", request_name)
	if request.docstatus == 0:
		request.submit()
	rfq_name = make_project_rfq(request.name, [supplier])
	rfq = frappe.get_doc("Request for Quotation", rfq_name)
	quote_items = [
		{
			"rfq_item": row.name,
			"rate": 700,
			"expected_delivery_date": row.schedule_date,
		}
		for row in rfq.items
	]
	with _acting_as(supplier_user):
		supplier_quote_name = submit_supplier_quote(
			rfq.name,
			quote_items,
			str(getdate(nowdate()) + timedelta(days=120)),
		)
	order_name = make_purchase_order_from_supplier_quote(supplier_quote_name)
	order = frappe.get_doc("Purchase Order", order_name)
	if order.docstatus == 0:
		order.submit()
	if order.custom_customer_project != project_name:
		frappe.throw("Demo purchase order lost its customer-project trace.")
	return order.name


def _ensure_purchase_receipt(project_name: str, purchase_order: str) -> str:
	existing = frappe.db.get_value(
		"Purchase Receipt",
		{"custom_customer_project": project_name, "docstatus": 1},
		"name",
	)
	if existing:
		return existing
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

	receipt = make_purchase_receipt(purchase_order)
	receipt.insert()
	receipt.submit()
	return receipt.name


def _ensure_delivery_and_receipt(
	project_name: str,
	sales_order: str,
	customer_user: str,
) -> str:
	existing = frappe.db.get_value(
		"Delivery Note",
		{"custom_customer_project": project_name, "docstatus": 1},
		"name",
	)
	if not existing:
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

		delivery = make_delivery_note(sales_order)
		delivery.custom_customer_project = project_name
		delivery.insert()
		delivery.submit()
		existing = delivery.name
	with _acting_as(customer_user):
		confirm_customer_receipt(existing)
	return existing


def _ensure_invoice_and_payment(project_name: str, sales_order: str) -> tuple[str, str]:
	invoice_name = frappe.db.get_value(
		"Sales Invoice",
		{"custom_customer_project": project_name, "docstatus": 1},
		"name",
	)
	if not invoice_name:
		from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

		invoice = make_sales_invoice(sales_order)
		invoice.custom_customer_project = project_name
		invoice.insert()
		invoice.submit()
		invoice_name = invoice.name
	payment_name = frappe.db.get_value(
		"Payment Entry",
		{"custom_customer_project": project_name, "docstatus": 1},
		"name",
	)
	if not payment_name:
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

		payment = get_payment_entry("Sales Invoice", invoice_name)
		payment.custom_customer_project = project_name
		payment.insert()
		payment.submit()
		payment_name = payment.name
	return invoice_name, payment_name


def _advance_to_payment_pending(project_name: str) -> None:
	project = frappe.get_doc("Customer Project", project_name)
	target_index = MAIN_STAGE_SEQUENCE.index("待回款")
	while MAIN_STAGE_SEQUENCE.index(project.stage) < target_index:
		current_index = MAIN_STAGE_SEQUENCE.index(project.stage)
		set_project_stage(project.name, MAIN_STAGE_SEQUENCE[current_index + 1])
		project.reload()


def _approve_and_close_project(project_name: str, executive: str) -> None:
	project = frappe.get_doc("Customer Project", project_name)
	if project.stage == "已结项":
		return
	request_name = create_project_closure_request(project.name)
	with _acting_as(executive):
		request = frappe.get_doc("AutoFlow Approval Request", request_name)
		if request.docstatus == 0:
			request.approve("合成演示：交付、签收、开票和回款证据齐全。")
	close_project(
		project.name,
		"合成演示项目已完成采购、收货、交付、客户签收、开票、回款和审批结项。",
	)


def _save_private_evidence(filename: str, owner: str, content: str) -> str:
	from frappe.utils.file_manager import save_file

	with _acting_as(owner):
		return save_file(
			filename,
			content.encode("utf-8"),
			None,
			None,
			is_private=1,
		).file_url


def _ensure_closed_supplier_exception(
	project_name: str,
	purchase_order: str,
	procurement: str,
	executive: str,
) -> str:
	existing = frappe.db.get_value(
		"Business Exception",
		{
			"customer_project": project_name,
			"reference_doctype": "Purchase Order",
			"reference_name": purchase_order,
		},
		"name",
	)
	if existing:
		return existing
	exception = frappe.get_doc(
		{
			"doctype": "Business Exception",
			"customer_project": project_name,
			"exception_type": "供应商延期",
			"risk_level": "高",
			"reference_doctype": "Purchase Order",
			"reference_name": purchase_order,
			"description": "合成演示：供应商产能波动导致承诺交期晚于客户交期。",
			"impact": "若不纠偏，客户试装和量产准备节点将受到影响。",
		}
	)
	exception.insert()
	transition_exception(exception.name, "已分级")
	exception.reload()
	exception.responsible_department = "采购与供应链"
	exception.responsible_user = procurement
	exception.target_close_date = getdate(nowdate()) + timedelta(days=7)
	exception.save()
	transition_exception(exception.name, "已分派")
	transition_exception(exception.name, "根因分析中")
	action_evidence = _save_private_evidence(
		"DEMO-DELAY-ACTION.txt",
		procurement,
		"合成证据：供应商完成产能重排，并确认加急批次与每日跟踪机制。",
	)
	exception.reload()
	exception.root_cause = "供应商产能排程未预留设备切换与来料波动缓冲，导致原交期承诺失真。"
	exception.append(
		"actions",
		{
			"action": "锁定加急产能并建立每日交期确认",
			"owner_user": procurement,
			"due_date": getdate(nowdate()) + timedelta(days=3),
			"status": "已完成",
			"evidence": action_evidence,
			"verification_result": "加急批次和跟踪节奏已由采购复核。",
		},
	)
	exception.save()
	transition_exception(exception.name, "整改中")
	transition_exception(exception.name, "待验证")
	verification_evidence = _save_private_evidence(
		"DEMO-DELAY-VERIFICATION.txt",
		executive,
		"合成证据：独立验证人复核整改记录和恢复交期，确认异常可关闭。",
	)
	with _acting_as(executive):
		transition_exception(
			exception.name,
			"已关闭",
			evidence=verification_evidence,
		)
	return exception.name


def _create_normal_project(context: dict[str, str]) -> str:
	project_name = _ensure_demo_project("normal", context["company"], context["customer"])
	item_code = _ensure_demo_item("normal")
	_ensure_customer_approved_sample(
		project_name,
		item_code,
		context["contact"],
		context["customer_user"],
		"normal",
	)
	quotation = _ensure_submitted_quotation(
		project_name,
		item_code,
		context["executive"],
		context["warehouse"],
	)
	sales_order = _ensure_submitted_sales_order(quotation, context["warehouse"])
	purchase_order = _ensure_purchase_path(
		project_name,
		sales_order,
		context["supplier"],
		context["supplier_user"],
	)
	_ensure_purchase_receipt(project_name, purchase_order)
	_ensure_delivery_and_receipt(project_name, sales_order, context["customer_user"])
	_ensure_invoice_and_payment(project_name, sales_order)
	_advance_to_payment_pending(project_name)
	_approve_and_close_project(project_name, context["executive"])
	return project_name


def _create_supplier_delay_project(context: dict[str, str]) -> str:
	project_name = _ensure_demo_project(
		"supplier_delay",
		context["company"],
		context["customer"],
	)
	_ensure_project_member(project_name, context["procurement"], "采购交付与异常整改负责人")
	item_code = _ensure_demo_item("supplier_delay")
	_ensure_customer_approved_sample(
		project_name,
		item_code,
		context["contact"],
		context["customer_user"],
		"supplier_delay",
	)
	quotation = _ensure_submitted_quotation(
		project_name,
		item_code,
		context["executive"],
		context["warehouse"],
	)
	sales_order = _ensure_submitted_sales_order(quotation, context["warehouse"])
	purchase_order = _ensure_purchase_path(
		project_name,
		sales_order,
		context["supplier"],
		context["supplier_user"],
	)
	project = frappe.get_doc("Customer Project", project_name)
	target_eta = getdate(project.customer_delivery_date) + timedelta(days=7)
	current_eta = frappe.db.get_value("Purchase Order", purchase_order, "custom_supplier_eta")
	if not current_eta or getdate(current_eta) != target_eta:
		with _acting_as(context["supplier_user"]):
			update_supplier_eta(
				purchase_order,
				str(target_eta),
				"合成演示：设备切换和来料波动造成产能延期。",
			)
	upsert_risks(project.name, evaluate_project(project.name))
	_ensure_closed_supplier_exception(
		project.name,
		purchase_order,
		context["procurement"],
		context["executive"],
	)
	return project.name


def _create_resample_project(context: dict[str, str]) -> str:
	project_name = _ensure_demo_project("resample", context["company"], context["customer"])
	item_code = _ensure_demo_item("resample")
	first_sample = _ensure_sample(project_name, item_code, context["contact"], 1)
	_dispatch_and_record_feedback(
		first_sample,
		"resample",
		"重新打样",
		"合成客户反馈：首轮样件边缘色差超出确认标准，需要调整工艺后重新送样。",
		context["customer_user"],
	)
	second_sample = create_resample(first_sample)
	second = frappe.get_doc("Sample Request", second_sample)
	if second.status == "草稿":
		second.status = "检验中"
		second.inspection_status = "通过"
		for row in second.items:
			row.inspection_result = "通过"
		second.save()
	_dispatch_and_record_feedback(
		second.name,
		"resample",
		"客户认可",
		"合成客户确认：第二轮样件已消除色差并满足装配要求。",
		context["customer_user"],
	)
	_ensure_submitted_quotation(
		project_name,
		item_code,
		context["executive"],
		context["warehouse"],
	)
	return project_name


def _build_context() -> dict[str, str]:
	_ensure_currency_settings()
	company = _ensure_demo_company()
	customer = _ensure_demo_customer()
	supplier = _ensure_demo_supplier()
	users = _ensure_demo_roles_and_links(customer, supplier)
	_ensure_approval_rule(company, "Quotation")
	_ensure_approval_rule(company, "Customer Project")
	return {
		"company": company,
		"customer": customer,
		"supplier": supplier,
		"contact": _ensure_demo_contact(customer),
		"warehouse": _ensure_demo_warehouse(company),
		"customer_user": users["customer"],
		"supplier_user": users["supplier"],
		"executive": users["executive"],
		"procurement": users["procurement"],
	}


def _validate_reset_request(confirmation: str | None) -> None:
	if confirmation != RESET_CONFIRMATION:
		frappe.throw(
			f"Demo reset requires exact confirmation: {RESET_CONFIRMATION}"
		)
	frappe.throw(
		"Demo reset is intentionally unavailable until an operator reviews the exact immutable audit records."
	)


def seed_demo_data(
	reset: bool = False,
	confirmation: str | None = None,
) -> dict[str, str]:
	"""Create three idempotent CNY scenarios using the real business services."""
	_require_demo_administrator()
	if reset:
		_validate_reset_request(confirmation)
	with _acting_as("Administrator"):
		context = _build_context()
		builders = {
			"normal": _create_normal_project,
			"supplier_delay": _create_supplier_delay_project,
			"resample": _create_resample_project,
		}
		projects = {
			scenario: builders[scenario](context)
			for scenario in SCENARIO_KEYS
		}
		refreshed_at = now_datetime()
		for project_name in projects.values():
			frappe.db.set_value(
				"Customer Project",
				project_name,
				"modified",
				refreshed_at,
				update_modified=False,
			)
		return projects
