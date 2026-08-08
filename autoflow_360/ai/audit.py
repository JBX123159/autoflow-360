import frappe

from autoflow_360.permissions.project import (
	customer_project_has_permission,
	customer_project_query,
)


SAFE_ERROR_MESSAGE = "AI 暂时不可用，确定性业务规则和原始单据仍然有效。"


def ai_analysis_query(user: str | None = None) -> str:
	project_condition = customer_project_query(user)
	if not project_condition:
		return ""
	if project_condition == "1=0":
		return project_condition
	return (
		"exists (select 1 from `tabCustomer Project` "
		"where `tabCustomer Project`.`name` = `tabAI Analysis`.`customer_project` "
		f"and ({project_condition}))"
	)


def ai_analysis_has_permission(
	doc,
	user: str | None = None,
	ptype: str | None = None,
	debug: bool = False,
) -> bool:
	if not doc.customer_project:
		return False
	project = frappe.get_doc("Customer Project", doc.customer_project)
	return bool(
		customer_project_has_permission(
			project,
			user=user,
			ptype="read",
		)
	)


def safe_error_code(error: Exception) -> str:
	from autoflow_360.ai.providers.base import ProviderError
	from autoflow_360.ai.schemas import AIResponseError

	if isinstance(error, ProviderError | AIResponseError):
		return error.code
	if isinstance(error, TimeoutError):
		return "provider_timeout"
	return "analysis_failed"


def validate_result_sources(result, allowed_sources: set[tuple[str, str]]):
	from autoflow_360.ai.schemas import AIResponseError

	pairs = {(source.doctype, source.name) for source in result.sources}
	if not pairs or not pairs.issubset(allowed_sources):
		raise AIResponseError("unauthorized_source")
	return tuple(sorted(pairs))


def build_display_text(result) -> str:
	lines = [result.summary, f"风险等级：{result.risk_level}"]
	if result.actions:
		lines.append("建议行动：")
		lines.extend(f"- {action['text']}" for action in result.actions)
	if result.uncertainties:
		lines.append("待人工确认：")
		lines.extend(f"- {item}" for item in result.uncertainties)
	return "\n".join(lines)
