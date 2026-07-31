from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.model.document import Document


POSITIVE_DAY_FIELDS = (
	("feedback_warning_days", "Feedback Warning Days"),
	("quotation_expiry_warning_days", "Quotation Expiry Warning Days"),
	("project_inactive_days", "Project Inactive Days"),
)


def _require_integer(value, label: str) -> int:
	if isinstance(value, bool):
		frappe.throw(_("{0} must be a whole number.").format(label))

	if isinstance(value, int):
		return value

	if isinstance(value, str):
		normalized = value.strip()
		if normalized and normalized.lstrip("+-").isdigit():
			return int(normalized)

	frappe.throw(_("{0} must be a whole number.").format(label))
	raise AssertionError("frappe.throw must stop validation")


def _get_check_value(value, label: str) -> int:
	if value in (0, "0", False, None, ""):
		return 0
	if value in (1, "1", True):
		return 1
	frappe.throw(_("{0} must be either 0 or 1.").format(label))
	raise AssertionError("frappe.throw must stop validation")


def _get_text(value, label: str) -> str:
	if value is None:
		return ""
	if not isinstance(value, str):
		frappe.throw(_("{0} must be text.").format(label))
	return value.strip()


class AutoFlowSettings(Document):
	def validate(self) -> None:
		for fieldname, label in POSITIVE_DAY_FIELDS:
			value = _require_integer(getattr(self, fieldname, None), label)
			if value <= 0:
				frappe.throw(_("{0} must be greater than zero.").format(label))

		risk_score = _require_integer(
			getattr(self, "high_risk_score", None),
			"High Risk Score",
		)
		if not 1 <= risk_score <= 100:
			frappe.throw(_("High Risk Score must be between 1 and 100."))

		if not _get_check_value(getattr(self, "ai_enabled", 0), "AI Enabled"):
			return

		provider = _get_text(
			getattr(self, "ai_provider", ""),
			"AI Provider",
		)
		if provider != "OpenAI Compatible":
			frappe.throw(
				_("AI Provider must be OpenAI Compatible when AI is enabled.")
			)

		model = _get_text(getattr(self, "ai_model", ""), "AI Model")
		if not model:
			frappe.throw(_("AI Model is required when AI is enabled."))

		base_url = _get_text(getattr(self, "ai_base_url", ""), "AI Base URL")
		if not base_url:
			frappe.throw(_("AI Base URL is required when AI is enabled."))

		parsed_url = urlparse(base_url)
		if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
			frappe.throw(_("AI Base URL must use http or https and include a host."))
