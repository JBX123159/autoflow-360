import frappe


WORKFLOW_STATES = {
	"草稿": "Primary",
	"待审批": "Warning",
	"已通过": "Success",
	"已退回": "Warning",
	"已拒绝": "Danger",
}
WORKFLOW_ACTIONS = ("提交审批", "通过", "退回", "拒绝")


def _ensure_workflow_state(state: str, style: str) -> None:
	if frappe.db.exists("Workflow State", state):
		return
	frappe.get_doc(
		{
			"doctype": "Workflow State",
			"workflow_state_name": state,
			"style": style,
		}
	).insert(ignore_permissions=True)


def _ensure_workflow_action(action: str) -> None:
	if frappe.db.exists("Workflow Action Master", action):
		return
	frappe.get_doc(
		{
			"doctype": "Workflow Action Master",
			"workflow_action_name": action,
		}
	).insert(ignore_permissions=True)


def _reconcile_workflow(
	name: str,
	document_type: str,
	workflow_state_field: str,
	states: list[dict],
	transitions: list[dict],
) -> None:
	existing = frappe.db.exists("Workflow", name)
	workflow = (
		frappe.get_doc("Workflow", existing)
		if existing
		else frappe.new_doc("Workflow")
	)
	workflow.workflow_name = name
	workflow.document_type = document_type
	workflow.workflow_state_field = workflow_state_field
	workflow.is_active = 1
	workflow.override_status = 1
	workflow.send_email_alert = 0
	workflow.set("states", states)
	workflow.set("transitions", transitions)
	if existing:
		workflow.save(ignore_permissions=True)
	else:
		workflow.insert(ignore_permissions=True)


def ensure_sample_workflow() -> None:
	_reconcile_workflow(
		"AutoFlow Sample Approval",
		"Sample Request",
		"approval_status",
		[
			{"state": "草稿", "doc_status": "0", "allow_edit": "AutoFlow Project Manager"},
			{"state": "待审批", "doc_status": "0", "allow_edit": "AutoFlow Sales Operations"},
			{
				"state": "已通过",
				"doc_status": "0",
				"allow_edit": "AutoFlow Project Manager",
				"update_field": "status",
				"update_value": "制作中",
			},
			{
				"state": "已退回",
				"doc_status": "0",
				"allow_edit": "AutoFlow Project Manager",
				"update_field": "status",
				"update_value": "草稿",
			},
		],
		[
			{
				"state": "草稿",
				"action": "提交审批",
				"next_state": "待审批",
				"allowed": "AutoFlow Project Manager",
				"allow_self_approval": 1,
			},
			{
				"state": "待审批",
				"action": "通过",
				"next_state": "已通过",
				"allowed": "AutoFlow Sales Operations",
				"allow_self_approval": 0,
			},
			{
				"state": "待审批",
				"action": "退回",
				"next_state": "已退回",
				"allowed": "AutoFlow Sales Operations",
				"allow_self_approval": 0,
			},
			{
				"state": "已退回",
				"action": "提交审批",
				"next_state": "待审批",
				"allowed": "AutoFlow Project Manager",
				"allow_self_approval": 1,
			},
		],
	)


def ensure_approval_workflow() -> None:
	_reconcile_workflow(
		"AutoFlow Business Approval",
		"AutoFlow Approval Request",
		"status",
		[
			{"state": "待审批", "doc_status": "0", "allow_edit": "All"},
			{"state": "已通过", "doc_status": "1", "allow_edit": "All"},
			{"state": "已退回", "doc_status": "1", "allow_edit": "All"},
			{"state": "已拒绝", "doc_status": "1", "allow_edit": "All"},
		],
		[
			{
				"state": "待审批",
				"action": "通过",
				"next_state": "已通过",
				"allowed": "All",
				"allow_self_approval": 0,
			},
			{
				"state": "待审批",
				"action": "退回",
				"next_state": "已退回",
				"allowed": "All",
				"allow_self_approval": 0,
			},
			{
				"state": "待审批",
				"action": "拒绝",
				"next_state": "已拒绝",
				"allowed": "All",
				"allow_self_approval": 0,
			},
		],
	)


def ensure_workflows() -> None:
	for state, style in WORKFLOW_STATES.items():
		_ensure_workflow_state(state, style)
	for action in WORKFLOW_ACTIONS:
		_ensure_workflow_action(action)
	if frappe.db.exists("DocType", "Sample Request"):
		ensure_sample_workflow()
	if frappe.db.exists("DocType", "AutoFlow Approval Request"):
		ensure_approval_workflow()
