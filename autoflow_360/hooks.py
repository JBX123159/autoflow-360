from . import __version__ as app_version


app_name = "autoflow_360"
app_title = "AutoFlow 360"
app_publisher = "JBX123159"
app_description = "汽车零部件客户项目与供应链协同智能平台"
app_email = "294367704+JBX123159@users.noreply.github.com"
app_license = "AGPL-3.0-only"
required_apps = ["erpnext", "crm"]

add_to_apps_screen = [
	{
		"name": "autoflow_360",
		"logo": "/assets/autoflow_360/images/autoflow-360-logo.svg",
		"title": "AutoFlow 360",
		"route": "/desk",
	}
]

export_python_type_annotations = True
require_type_annotated_api_methods = True

after_install = "autoflow_360.install.after_install"
after_migrate = "autoflow_360.install.after_migrate"

doctype_js = {
	"CRM Deal": "public/js/crm_deal.js",
}

doc_events = {
	"Sample Request": {
		"after_insert": "autoflow_360.services.project_status.refresh_project_stage_from_document",
		"on_update": "autoflow_360.services.project_status.refresh_project_stage_from_document",
	},
}

portal_menu_items = [
	{
		"title": "我的样品",
		"route": "/customer-samples",
		"role": "AutoFlow Customer Portal",
	},
]

permission_query_conditions = {
	"Customer Feedback": "autoflow_360.permissions.portal.customer_feedback_query",
}

has_permission = {
	"Customer Feedback": "autoflow_360.permissions.portal.customer_feedback_has_permission",
}
