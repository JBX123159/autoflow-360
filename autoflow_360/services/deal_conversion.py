import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate, nowdate
from frappe.utils.synchronization import filelock

from autoflow_360.services.idempotency import make_idempotency_key


def _required_value(value, label: str) -> str:
	normalized = cstr(value).strip()
	if not normalized:
		frappe.throw(_("{0} is required.").format(_(label)))
	return normalized


def _parse_delivery_date(value):
	try:
		return getdate(value)
	except (TypeError, ValueError) as error:
		frappe.throw(_("Delivery date must be a valid date."))
		raise error


def _get_project_name(deal) -> str:
	organization_name = cstr(deal.organization_name).strip()
	if not organization_name and deal.organization:
		organization_name = cstr(
			frappe.db.get_value(
				"CRM Organization",
				deal.organization,
				"organization_name",
			)
		).strip()
	return organization_name or cstr(deal.organization).strip() or deal.name


def _get_existing_project(deal_name: str) -> str | None:
	project_name = frappe.db.get_value(
		"Customer Project",
		{"crm_deal": deal_name},
		"name",
	)
	if not project_name:
		return None

	frappe.get_doc("Customer Project", project_name).check_permission("read")
	return project_name


def create_project_from_deal(
	deal_name: str,
	company: str,
	customer: str,
	product_family: str,
	delivery_date: str,
) -> str:
	normalized_deal_name = _required_value(deal_name, "CRM Deal")
	deal = frappe.get_doc("CRM Deal", normalized_deal_name)
	deal.check_permission("read")

	lock_name = "autoflow-deal-" + make_idempotency_key(
		"deal-to-customer-project",
		deal.name,
	)
	with filelock(lock_name, timeout=15):
		if not frappe.db.get_value(
			"CRM Deal",
			deal.name,
			"name",
			for_update=True,
		):
			frappe.throw(_("CRM Deal {0} no longer exists.").format(deal.name))
		deal.reload()

		existing = _get_existing_project(deal.name)
		if existing:
			return existing

		normalized_company = _required_value(company, "Company")
		normalized_customer = _required_value(customer, "Customer")
		normalized_product_family = _required_value(
			product_family,
			"Product Family",
		)
		normalized_delivery_date = _parse_delivery_date(
			_required_value(delivery_date, "Delivery Date")
		)
		target_award_date = getdate(deal.expected_closure_date or nowdate())
		if target_award_date > normalized_delivery_date:
			frappe.throw(
				_("Delivery date cannot be before the target award date.")
			)

		currency = deal.currency or frappe.get_cached_value(
			"Company",
			normalized_company,
			"default_currency",
		)
		if not currency:
			frappe.throw(_("A currency is required on the deal or company."))

		project_manager = deal.deal_owner or frappe.session.user
		project = frappe.get_doc(
			{
				"doctype": "Customer Project",
				"project_name": _get_project_name(deal),
				"company": normalized_company,
				"customer": normalized_customer,
				"crm_deal": deal.name,
				"product_family": normalized_product_family,
				"currency": currency,
				"expected_amount": flt(
					deal.expected_deal_value or deal.deal_value or 0
				),
				"probability": flt(deal.probability),
				"project_manager": project_manager,
				"target_award_date": target_award_date,
				"customer_delivery_date": normalized_delivery_date,
				"stage": "潜在项目",
				"project_members": [
					{
						"user": project_manager,
						"responsibility": "客户项目负责人",
					}
				],
			}
		)
		project.insert()
		return project.name
