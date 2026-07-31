import frappe
from frappe import _

from autoflow_360.permissions.portal import (
	CUSTOMER_PORTAL_ROLE,
	get_customer_names_for_user,
)


def get_context(context):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Please sign in to view customer samples."), frappe.PermissionError)
	if user != "Administrator" and CUSTOMER_PORTAL_ROLE not in frappe.get_roles(user):
		raise frappe.PermissionError

	context.no_cache = 1
	context.title = _("My Samples")
	customers = get_customer_names_for_user(user)
	if not customers:
		context.samples = []
		return context

	projects = frappe.get_all(
		"Customer Project",
		filters={"customer": ["in", customers]},
		fields=["name", "project_name", "customer"],
	)
	if not projects:
		context.samples = []
		return context

	project_by_name = {project.name: project for project in projects}
	samples = frappe.get_all(
		"Sample Request",
		filters={"customer_project": ["in", list(project_by_name)]},
		fields=[
			"name",
			"customer_project",
			"round_number",
			"purpose",
			"required_date",
			"status",
			"inspection_status",
			"carrier",
			"tracking_number",
			"dispatch_time",
			"feedback",
		],
		order_by="modified desc",
	)
	for sample in samples:
		project = project_by_name[sample.customer_project]
		sample.project_title = project.project_name
		sample.customer = project.customer
	context.samples = samples
	return context
