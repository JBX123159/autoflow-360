import frappe
from frappe import _
from frappe.utils import cstr


MAIN_STAGE_SEQUENCE = (
	"潜在项目",
	"样品阶段",
	"报价阶段",
	"已定点",
	"订单履约",
	"已交付",
	"待回款",
	"已结项",
)
SIDE_STAGES = frozenset({"暂停", "失败", "取消"})
ALL_STAGES = frozenset((*MAIN_STAGE_SEQUENCE, *SIDE_STAGES))
MAIN_TRANSITIONS = {
	stage: {MAIN_STAGE_SEQUENCE[index + 1]}
	for index, stage in enumerate(MAIN_STAGE_SEQUENCE[:-1])
}
MAIN_TRANSITIONS[MAIN_STAGE_SEQUENCE[-1]] = set()


def validate_stage_transition(previous: str | None, current: str) -> None:
	"""Allow initial potential projects, adjacent progress, or a side exit."""
	if current not in ALL_STAGES:
		frappe.throw(_("Unknown project stage: {0}.").format(current))

	if not previous:
		if current != MAIN_STAGE_SEQUENCE[0]:
			frappe.throw(
				_("A new project must start at stage {0}.").format(
					MAIN_STAGE_SEQUENCE[0]
				)
			)
		return

	if previous not in ALL_STAGES:
		frappe.throw(_("Unknown previous project stage: {0}.").format(previous))
	if previous == current:
		return
	if previous in SIDE_STAGES:
		frappe.throw(
			_("Project stage {0} cannot be changed directly.").format(previous)
		)
	if current in SIDE_STAGES:
		return
	if current not in MAIN_TRANSITIONS.get(previous, set()):
		frappe.throw(
			_("Project stage cannot move from {0} to {1}.").format(
				previous,
				current,
			)
		)


def set_project_stage(
	project_name: str,
	target_stage: str,
	reason: str | None = None,
) -> str:
	if not cstr(project_name).strip():
		frappe.throw(_("Project name is required."))
	if target_stage not in ALL_STAGES:
		frappe.throw(_("Unknown project stage: {0}.").format(target_stage))

	project = frappe.get_doc("Customer Project", project_name)
	project.check_permission("write")
	validate_stage_transition(project.stage, target_stage)

	normalized_reason = cstr(reason).strip()
	if target_stage in SIDE_STAGES and not normalized_reason:
		frappe.throw(
			_("A reason is required for stage {0}.").format(target_stage)
		)
	if target_stage == "暂停":
		project.pause_reason = normalized_reason
	elif target_stage == "失败":
		project.failure_reason = normalized_reason
	elif target_stage == "取消":
		project.cancellation_reason = normalized_reason

	project.stage = target_stage
	project.save()
	return project.name


def _doctype_has_fields(doctype: str, *fieldnames: str) -> bool:
	if not frappe.db.exists("DocType", doctype):
		return False
	meta = frappe.get_meta(doctype)
	return all(meta.has_field(fieldname) for fieldname in fieldnames)


def _has_project_document(doctype: str, filters: dict) -> bool:
	if not _doctype_has_fields(doctype, "custom_customer_project"):
		return False
	return bool(frappe.db.exists(doctype, filters))


def derive_project_stage(project_name: str) -> str:
	project = frappe.get_doc("Customer Project", project_name)
	if project.stage in SIDE_STAGES or project.stage == "已结项":
		return project.stage

	if _has_project_document(
		"Sales Invoice",
		{
			"custom_customer_project": project.name,
			"docstatus": 1,
			"outstanding_amount": [">", 0],
		},
	):
		return "待回款"
	if _has_project_document(
		"Delivery Note",
		{"custom_customer_project": project.name, "docstatus": 1},
	):
		return "已交付"
	if _has_project_document(
		"Sales Order",
		{"custom_customer_project": project.name, "docstatus": 1},
	):
		return "订单履约"

	if _doctype_has_fields(
		"Quotation",
		"custom_customer_project",
		"custom_customer_confirmed",
	) and frappe.db.exists(
		"Quotation",
		{
			"custom_customer_project": project.name,
			"docstatus": 1,
			"custom_customer_confirmed": 1,
		},
	):
		return "已定点"
	if _has_project_document(
		"Quotation",
		{"custom_customer_project": project.name, "docstatus": 1},
	):
		return "报价阶段"
	if _doctype_has_fields(
		"Sample Request",
		"customer_project",
		"status",
	) and frappe.db.exists(
		"Sample Request",
		{
			"customer_project": project.name,
			"status": ["not in", ["客户认可", "拒绝"]],
		},
	):
		return "样品阶段"
	return "潜在项目"


def _next_stage_toward(current: str, derived: str) -> str:
	if current not in MAIN_STAGE_SEQUENCE or derived not in MAIN_STAGE_SEQUENCE:
		return current
	current_index = MAIN_STAGE_SEQUENCE.index(current)
	derived_index = MAIN_STAGE_SEQUENCE.index(derived)
	if derived_index <= current_index:
		return current
	return MAIN_STAGE_SEQUENCE[current_index + 1]


def refresh_project_stage_from_document(doc, method: str | None = None) -> None:
	project_name = getattr(doc, "custom_customer_project", None) or getattr(
		doc,
		"customer_project",
		None,
	)
	if not project_name:
		return
	project = frappe.get_doc("Customer Project", project_name)
	derived = derive_project_stage(project.name)
	next_stage = _next_stage_toward(project.stage, derived)
	if next_stage == project.stage:
		return
	project.stage = next_stage
	project.save(ignore_permissions=True)
