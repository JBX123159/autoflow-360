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
	"Customer Project": "public/js/customer_project.js",
	"Material Request": "public/js/material_request.js",
	"Purchase Order": "public/js/purchase_order.js",
	"Quotation": "public/js/quotation.js",
	"Sales Order": "public/js/sales_order.js",
	"Supplier Quotation": "public/js/supplier_quotation.js",
}

doc_events = {
	"Sample Request": {
		"after_insert": "autoflow_360.services.project_status.refresh_project_stage_from_document",
		"on_update": "autoflow_360.services.project_status.refresh_project_stage_from_document",
	},
	"Quotation": {
		"before_submit": "autoflow_360.services.sales_conversion.validate_quotation_submission",
		"on_submit": "autoflow_360.services.project_status.refresh_project_stage_from_document",
		"on_update_after_submit": "autoflow_360.services.project_status.refresh_project_stage_from_document",
	},
	"Sales Order": {
		"before_cancel": "autoflow_360.services.project_closure.prevent_closed_project_evidence_change",
		"on_submit": "autoflow_360.services.project_status.refresh_project_stage_from_document",
	},
	"Delivery Note": {
		"before_cancel": "autoflow_360.services.project_closure.prevent_closed_project_evidence_change",
		"before_validate": "autoflow_360.services.project_linking.propagate_project_link",
		"before_submit": "autoflow_360.services.delivery.validate_delivery_stock",
		"on_submit": "autoflow_360.services.project_status.refresh_project_stage_from_document",
	},
	"Sales Invoice": {
		"before_cancel": "autoflow_360.services.project_closure.prevent_closed_project_evidence_change",
		"before_validate": "autoflow_360.services.project_linking.propagate_project_link",
		"on_submit": "autoflow_360.services.project_status.refresh_project_stage_from_document",
		"on_update_after_submit": "autoflow_360.services.project_status.refresh_project_stage_from_document",
	},
	"Purchase Receipt": {
		"before_validate": "autoflow_360.services.project_linking.propagate_project_link",
	},
	"Purchase Invoice": {
		"before_validate": "autoflow_360.services.project_linking.propagate_project_link",
	},
	"Payment Entry": {
		"before_cancel": "autoflow_360.services.project_closure.prevent_closed_project_evidence_change",
		"before_validate": "autoflow_360.services.project_linking.propagate_project_link",
		"on_submit": "autoflow_360.services.project_status.refresh_project_stage_from_document",
	},
}

portal_menu_items = [
	{
		"title": "我的样品",
		"route": "/customer-samples",
		"role": "AutoFlow Customer Portal",
	},
	{
		"title": "我的交付",
		"route": "/customer-deliveries",
		"role": "AutoFlow Customer Portal",
	},
	{
		"title": "询价",
		"route": "/supplier-rfqs",
		"role": "AutoFlow Supplier Portal",
	},
	{
		"title": "采购订单",
		"route": "/supplier-orders",
		"role": "AutoFlow Supplier Portal",
	},
]

permission_query_conditions = {
	"Account": "autoflow_360.permissions.portal.supplier_account_query",
	"Customer Feedback": "autoflow_360.permissions.portal.customer_feedback_query",
	"Customer Receipt": "autoflow_360.permissions.portal.customer_receipt_query",
	"Delivery Note": "autoflow_360.permissions.portal.customer_delivery_query",
	"Item": "autoflow_360.permissions.portal.supplier_item_query",
	"Request for Quotation": "autoflow_360.permissions.portal.request_for_quotation_query",
	"Supplier Quotation": "autoflow_360.permissions.portal.supplier_quotation_query",
	"Purchase Order": "autoflow_360.permissions.portal.purchase_order_query",
}

has_permission = {
	"Account": "autoflow_360.permissions.portal.supplier_account_has_permission",
	"Customer Feedback": "autoflow_360.permissions.portal.customer_feedback_has_permission",
	"Customer Receipt": "autoflow_360.permissions.portal.customer_receipt_has_permission",
	"Delivery Note": "autoflow_360.permissions.portal.customer_delivery_has_permission",
	"Item": "autoflow_360.permissions.portal.supplier_item_has_permission",
	"Request for Quotation": "autoflow_360.permissions.portal.supplier_rfq_has_permission",
	"Supplier Quotation": "autoflow_360.permissions.portal.supplier_document_has_permission",
	"Purchase Order": "autoflow_360.permissions.portal.supplier_document_has_permission",
}
