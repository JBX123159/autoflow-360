import frappe

from autoflow_360.services.exception_workflow import transition_exception


@frappe.whitelist(methods=["POST"])
def change_exception_status(
	exception_name: str,
	target_status: str,
	evidence: str | None = None,
	reason: str | None = None,
) -> str:
	return transition_exception(
		exception_name,
		target_status,
		evidence=evidence,
		reason=reason,
	)
