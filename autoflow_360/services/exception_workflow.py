import frappe
from frappe import _
from frappe.utils import cstr, now_datetime
from frappe.utils.synchronization import filelock

from autoflow_360.services.idempotency import make_idempotency_key


TRANSITIONS = {
	"已发现": {"已分级", "已取消"},
	"已分级": {"已分派", "已取消"},
	"已分派": {"根因分析中", "已取消"},
	"根因分析中": {"整改中", "已取消"},
	"整改中": {"待验证", "已取消"},
	"待验证": {"已关闭", "整改中"},
}


def _required(value: str | None, message: str) -> str:
	value = cstr(value).strip()
	if not value:
		frappe.throw(_(message))
	return value


def _lock_name(exception_name: str) -> str:
	return "autoflow-exception-" + make_idempotency_key(
		"transition",
		exception_name,
	)


def _lock_exception(exception_name: str) -> None:
	if not frappe.db.get_value(
		"Business Exception",
		exception_name,
		"name",
		for_update=True,
	):
		frappe.throw(_("Business Exception no longer exists."))


def _validate_owned_private_file(file_url: str | None) -> str:
	file_url = _required(file_url, "Verification evidence is required.")
	if not frappe.db.exists(
		"File",
		{
			"file_url": file_url,
			"owner": frappe.session.user,
			"is_private": 1,
		},
	):
		raise frappe.PermissionError
	return file_url


def _validate_action_evidence(doc) -> None:
	if not doc.actions:
		frappe.throw(_("At least one corrective action is required."))
	for action in doc.actions:
		if action.status != "已完成" or not action.evidence or not action.completed_at:
			frappe.throw(_("All corrective actions require completion evidence."))
		if not frappe.db.exists(
			"File",
			{
				"file_url": action.evidence,
				"owner": action.owner_user,
				"is_private": 1,
			},
		):
			frappe.throw(_("Corrective action evidence must belong to its owner."))


def _validate_independent_verifier(doc) -> None:
	if doc.risk_level != "高":
		return
	conflicted_users = {
		cstr(doc.raised_by).strip(),
		cstr(doc.responsible_user).strip(),
		*(cstr(action.owner_user).strip() for action in doc.actions),
	}
	conflicted_users.discard("")
	if frappe.session.user in conflicted_users:
		frappe.throw(
			_("Independent verification requires a different user."),
			frappe.PermissionError,
		)


def transition_exception(
	exception_name: str,
	target_status: str,
	evidence: str | None = None,
	reason: str | None = None,
) -> str:
	if frappe.session.user == "Guest":
		raise frappe.PermissionError
	exception_name = _required(exception_name, "Business Exception is required.")
	target_status = _required(target_status, "Target status is required.")
	doc = frappe.get_doc("Business Exception", exception_name)
	doc.check_permission("write")

	with filelock(_lock_name(doc.name), timeout=15):
		_lock_exception(doc.name)
		doc.reload()
		doc.check_permission("write")
		if doc.status == target_status:
			if target_status == "已关闭" and evidence and evidence != doc.verification_evidence:
				frappe.throw(_("Closed exception evidence cannot be changed."))
			if target_status == "已取消" and reason and cstr(reason).strip() != cstr(doc.cancellation_reason).strip():
				frappe.throw(_("Cancellation reason cannot be changed."))
			return doc.name
		if target_status not in TRANSITIONS.get(doc.status, set()):
			frappe.throw(
				_("Invalid exception transition from {0} to {1}.").format(
					doc.status,
					target_status,
				)
			)

		if target_status == "已分派":
			_required(doc.responsible_department, "Responsible department is required.")
			_required(doc.responsible_user, "Responsible user is required.")
			_required(doc.target_close_date, "Target close date is required.")
		if target_status == "整改中":
			root_cause = _required(doc.root_cause, "Root cause is required before corrective action.")
			if len(root_cause) < 10:
				frappe.throw(_("Root cause must contain at least 10 characters."))
			if not doc.actions:
				frappe.throw(_("At least one corrective action is required."))
			doc.verification_evidence = None
			doc.verified_by = None
			doc.verified_at = None
		if target_status == "待验证":
			_validate_action_evidence(doc)
		if target_status == "已关闭":
			_validate_action_evidence(doc)
			validated_evidence = _validate_owned_private_file(evidence)
			_validate_independent_verifier(doc)
			doc.verification_evidence = validated_evidence
			doc.verified_by = frappe.session.user
			doc.verified_at = now_datetime()
		if target_status == "已取消":
			cancellation_reason = _required(reason, "Cancellation reason is required.")
			if len(cancellation_reason) < 10:
				frappe.throw(_("Cancellation reason must contain at least 10 characters."))
			doc.cancellation_reason = cancellation_reason

		doc.status = target_status
		doc.flags.from_exception_workflow = True
		doc.save()
		return doc.name
