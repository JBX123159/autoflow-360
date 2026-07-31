import frappe
from frappe import _
from frappe.utils import cstr, now_datetime
from frappe.utils.synchronization import filelock

from autoflow_360.permissions.portal import can_access_customer_project
from autoflow_360.services.idempotency import make_idempotency_key


FEEDBACK_DECISIONS = {"客户认可", "重新打样", "拒绝"}


def _required(value, message: str) -> str:
	normalized = cstr(value).strip()
	if not normalized:
		frappe.throw(_(message))
	return normalized


def _sample_lock_name(operation: str, sample_name: str) -> str:
	return "autoflow-sample-" + make_idempotency_key(operation, sample_name)


def _lock_sample_row(sample_name: str) -> None:
	if not frappe.db.get_value(
		"Sample Request",
		sample_name,
		"name",
		for_update=True,
	):
		frappe.throw(_("Sample Request {0} no longer exists.").format(sample_name))


def dispatch_sample(
	sample_name: str,
	carrier: str,
	tracking_number: str,
) -> str:
	sample_name = _required(sample_name, "Sample request is required.")
	sample = frappe.get_doc("Sample Request", sample_name)
	sample.check_permission("write")
	normalized_carrier = _required(carrier, "Carrier is required.")
	normalized_tracking = _required(
		tracking_number,
		"Tracking number is required.",
	)

	with filelock(_sample_lock_name("dispatch", sample.name), timeout=15):
		_lock_sample_row(sample.name)
		sample.reload()
		if sample.status in {"已发出", "等待反馈"}:
			if (
				cstr(sample.carrier).strip() == normalized_carrier
				and cstr(sample.tracking_number).strip() == normalized_tracking
			):
				return sample.name
			frappe.throw(_("This sample has already been dispatched."))
		if sample.status not in {"制作中", "检验中"}:
			frappe.throw(_("Only prepared samples can be dispatched."))
		if sample.inspection_status != "通过":
			frappe.throw(_("Sample must pass inspection before dispatch."))
		if any(item.inspection_result != "通过" for item in sample.items):
			frappe.throw(_("Every sample item must pass before dispatch."))

		sample.status = "已发出"
		sample.carrier = normalized_carrier
		sample.tracking_number = normalized_tracking
		sample.dispatch_time = now_datetime()
		sample.save()
		return sample.name


def _check_feedback_permission(sample) -> None:
	if frappe.session.user == "Guest":
		raise frappe.PermissionError
	if sample.has_permission("write"):
		return
	if can_access_customer_project(sample.customer_project):
		return
	raise frappe.PermissionError


def record_customer_feedback(
	sample_name: str,
	decision: str,
	comments: str,
	attachment: str | None = None,
) -> str:
	sample_name = _required(sample_name, "Sample request is required.")
	sample = frappe.get_doc("Sample Request", sample_name)
	_check_feedback_permission(sample)
	if decision not in FEEDBACK_DECISIONS:
		frappe.throw(_("Invalid feedback decision."))
	normalized_comments = _required(comments, "Feedback comments are required.")
	normalized_attachment = cstr(attachment).strip() or None

	with filelock(_sample_lock_name("feedback", sample.name), timeout=15):
		_lock_sample_row(sample.name)
		sample.reload()
		if frappe.db.exists(
			"Customer Feedback",
			{"sample_request": sample.name},
		):
			frappe.throw(
				_("Customer feedback already exists and cannot be overwritten.")
			)
		if sample.status not in {"已发出", "等待反馈"}:
			frappe.throw(_("Only dispatched samples can receive feedback."))

		feedback = frappe.get_doc(
			{
				"doctype": "Customer Feedback",
				"sample_request": sample.name,
				"customer": frappe.db.get_value(
					"Customer Project",
					sample.customer_project,
					"customer",
				),
				"contact": sample.customer_contact,
				"decision": decision,
				"comments": normalized_comments,
				"attachment": normalized_attachment,
			}
		)
		feedback.insert()
		sample.db_set(
			{"feedback": feedback.name, "status": decision},
			update_modified=True,
		)
		return feedback.name


def create_resample(sample_name: str) -> str:
	sample_name = _required(sample_name, "Sample request is required.")
	previous = frappe.get_doc("Sample Request", sample_name)
	previous.check_permission("write")

	with filelock(_sample_lock_name("resample", previous.name), timeout=15):
		_lock_sample_row(previous.name)
		previous.reload()
		existing = frappe.db.get_value(
			"Sample Request",
			{"previous_sample_request": previous.name},
			"name",
		)
		if existing:
			frappe.get_doc("Sample Request", existing).check_permission("read")
			return existing
		if previous.status != "重新打样":
			frappe.throw(
				_("Resample is only allowed after a resample decision.")
			)

		new_sample = frappe.get_doc(
			{
				"doctype": "Sample Request",
				"customer_project": previous.customer_project,
				"round_number": int(previous.round_number or 0) + 1,
				"previous_sample_request": previous.name,
				"purpose": previous.purpose,
				"required_date": previous.required_date,
				"customer_contact": previous.customer_contact,
				"status": "草稿",
				"inspection_status": "待检验",
				"items": [
					{
						"item_code": item.item_code,
						"quantity": item.quantity,
						"uom": item.uom,
						"specification": item.specification,
						"inspection_result": "待检验",
					}
					for item in previous.items
				],
			}
		)
		new_sample.insert()
		return new_sample.name
