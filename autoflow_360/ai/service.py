import hashlib
import json
from time import perf_counter

import frappe
from frappe.utils import add_days, cstr, now_datetime

from autoflow_360.ai.audit import (
	SAFE_ERROR_MESSAGE,
	build_display_text,
	safe_error_code,
	validate_result_sources,
)
from autoflow_360.ai.context_builder import build_project_context
from autoflow_360.ai.providers.disabled import DisabledProvider
from autoflow_360.ai.providers.openai_compatible import OpenAICompatibleProvider
from autoflow_360.ai.schemas import parse_ai_result, result_to_dict


PROMPT_VERSION = "project-analysis-v1"
PROVIDER_TIMEOUT_SECONDS = 30
ANALYSIS_TYPES = {
	"风险摘要",
	"下一步行动",
	"管理周报",
	"根因草稿",
	"供应商报价总结",
	"结项复盘",
}
AI_INTERNAL_ROLES = {
	"AutoFlow Administrator",
	"AutoFlow Sales Operations",
	"AutoFlow Project Manager",
	"AutoFlow Procurement",
	"AutoFlow Warehouse",
	"AutoFlow Finance",
	"AutoFlow Executive",
}
TERMINAL_PROJECT_STAGES = {"已结项", "失败", "取消"}


def _require_internal_ai_user() -> None:
	user = frappe.session.user
	if user == "Administrator":
		return
	roles = set(
		frappe.get_all(
			"Has Role",
			filters={"parent": user, "parenttype": "User"},
			pluck="role",
		)
	)
	if not roles.intersection(AI_INTERNAL_ROLES):
		raise frappe.PermissionError


def get_provider(settings):
	if not settings.ai_enabled or settings.ai_provider == "Disabled":
		return DisabledProvider()
	if settings.ai_provider == "OpenAI Compatible":
		return OpenAICompatibleProvider(
			cstr(settings.ai_base_url).strip(),
			cstr(settings.get_password("ai_api_key", raise_exception=False)).strip(),
		)
	raise ValueError("Unsupported AI provider")


def _messages(input_json: str, analysis_type: str) -> list[dict]:
	return [
		{
			"role": "system",
			"content": (
				"你是汽车零部件客户项目与供应链协同助手。"
				"只能依据用户提供的业务 JSON，不得虚构金额、日期、客户、供应商或单据。"
				"只输出 JSON，字段必须是 summary、risk_level、actions、sources、uncertainties。"
				"sources 中每项只包含 doctype 和 name，且必须来自输入 JSON。"
				"actions 只是人工建议，不能声称已执行任何业务动作。"
			),
		},
		{
			"role": "user",
			"content": json.dumps(
				{"analysis_type": analysis_type, "context": json.loads(input_json)},
				ensure_ascii=False,
				sort_keys=True,
				default=str,
			),
		},
	]


def analyze_project(project_name: str, analysis_type: str) -> str:
	_require_internal_ai_user()
	project_name = cstr(project_name).strip()
	analysis_type = cstr(analysis_type).strip()
	if not project_name:
		frappe.throw("Customer Project is required.")
	if analysis_type not in ANALYSIS_TYPES:
		frappe.throw("Unsupported AI analysis type.")

	context, allowed_sources = build_project_context(project_name)
	input_json = json.dumps(
		context,
		ensure_ascii=False,
		sort_keys=True,
		separators=(",", ":"),
		default=str,
	)
	settings = frappe.get_single("AutoFlow Settings")
	analysis = frappe.get_doc(
		{
			"doctype": "AI Analysis",
			"customer_project": project_name,
			"analysis_type": analysis_type,
			"provider": cstr(settings.ai_provider).strip() or "Disabled",
			"model": cstr(settings.ai_model).strip() or None,
			"prompt_version": PROMPT_VERSION,
			"input_hash": hashlib.sha256(input_json.encode("utf-8")).hexdigest(),
		}
	)
	analysis.flags.from_ai_service = True
	analysis.insert()

	started = perf_counter()
	try:
		payload = get_provider(settings).generate(
			model=cstr(settings.ai_model).strip(),
			messages=_messages(input_json, analysis_type),
			timeout_seconds=PROVIDER_TIMEOUT_SECONDS,
		)
		result = parse_ai_result(payload)
		source_pairs = validate_result_sources(result, allowed_sources)
		analysis.output_json = json.dumps(
			result_to_dict(result),
			ensure_ascii=False,
			sort_keys=True,
			separators=(",", ":"),
		)
		analysis.display_text = build_display_text(result)
		for doctype, name in source_pairs:
			analysis.append(
				"sources",
				{
					"reference_doctype": doctype,
					"reference_name": name,
					"label": f"{doctype} {name}",
				},
			)
		analysis.status = "成功"
	except Exception as error:
		analysis.status = "降级"
		analysis.output_json = None
		analysis.display_text = None
		analysis.set("sources", [])
		analysis.error_code = safe_error_code(error)
		analysis.error_message = SAFE_ERROR_MESSAGE
	finally:
		analysis.latency_ms = max(0, int((perf_counter() - started) * 1000))
		analysis.flags.from_ai_service = True
		analysis.save()
	return analysis.name


def generate_weekly_drafts() -> int:
	settings = frappe.get_single("AutoFlow Settings")
	if not settings.ai_enabled:
		return 0
	cutoff = add_days(now_datetime(), -6)
	project_names = frappe.get_all(
		"Customer Project",
		filters={"stage": ["not in", list(TERMINAL_PROJECT_STAGES)]},
		pluck="name",
		order_by="name asc",
		limit_page_length=50,
	)
	queued = 0
	for project_name in project_names:
		if frappe.db.exists(
			"AI Analysis",
			{
				"customer_project": project_name,
				"analysis_type": "管理周报",
				"requested_at": [">=", cutoff],
				"status": ["in", ["处理中", "成功"]],
			},
		):
			continue
		frappe.enqueue(
			"autoflow_360.ai.service.analyze_project",
			queue="long",
			project_name=project_name,
			analysis_type="管理周报",
			enqueue_after_commit=True,
		)
		queued += 1
	return queued
