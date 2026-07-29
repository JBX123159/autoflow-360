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
