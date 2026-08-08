from dataclasses import dataclass


RISK_LEVELS = {"低", "中", "高", "未知"}
MAX_SUMMARY_LENGTH = 4000
MAX_ACTIONS = 20
MAX_UNCERTAINTIES = 20
MAX_ITEM_LENGTH = 500
MAX_SOURCES = 50


class AIResponseError(ValueError):
	def __init__(self, code: str):
		super().__init__(code)
		self.code = code


@dataclass(frozen=True, slots=True)
class SourceReference:
	doctype: str
	name: str


@dataclass(frozen=True, slots=True)
class AIResult:
	summary: str
	risk_level: str
	actions: tuple[dict[str, str], ...]
	sources: tuple[SourceReference, ...]
	uncertainties: tuple[str, ...]


def _required_text(value, *, maximum: int = MAX_ITEM_LENGTH) -> str:
	if not isinstance(value, str):
		raise AIResponseError("invalid_schema")
	value = value.strip()
	if not value or len(value) > maximum:
		raise AIResponseError("invalid_schema")
	return value


def parse_ai_result(payload) -> AIResult:
	if not isinstance(payload, dict):
		raise AIResponseError("invalid_schema")
	required = {"summary", "risk_level", "actions", "sources", "uncertainties"}
	if not required.issubset(payload):
		raise AIResponseError("invalid_schema")

	summary = _required_text(payload["summary"], maximum=MAX_SUMMARY_LENGTH)
	risk_level = _required_text(payload["risk_level"], maximum=10)
	if risk_level not in RISK_LEVELS:
		raise AIResponseError("invalid_schema")

	action_rows = payload["actions"]
	if not isinstance(action_rows, list) or len(action_rows) > MAX_ACTIONS:
		raise AIResponseError("invalid_schema")
	actions: list[dict[str, str]] = []
	for row in action_rows:
		if not isinstance(row, dict):
			raise AIResponseError("invalid_schema")
		action = {"text": _required_text(row.get("text"))}
		owner_role = row.get("owner_role")
		if owner_role not in (None, ""):
			action["owner_role"] = _required_text(owner_role, maximum=100)
		actions.append(action)

	source_rows = payload["sources"]
	if (
		not isinstance(source_rows, list)
		or not source_rows
		or len(source_rows) > MAX_SOURCES
	):
		raise AIResponseError("invalid_schema")
	sources: list[SourceReference] = []
	seen_sources: set[tuple[str, str]] = set()
	for row in source_rows:
		if not isinstance(row, dict):
			raise AIResponseError("invalid_schema")
		pair = (
			_required_text(row.get("doctype"), maximum=140),
			_required_text(row.get("name"), maximum=140),
		)
		if pair not in seen_sources:
			sources.append(SourceReference(*pair))
			seen_sources.add(pair)

	uncertainty_rows = payload["uncertainties"]
	if not isinstance(uncertainty_rows, list) or len(uncertainty_rows) > MAX_UNCERTAINTIES:
		raise AIResponseError("invalid_schema")
	uncertainties = tuple(_required_text(item) for item in uncertainty_rows)
	return AIResult(
		summary=summary,
		risk_level=risk_level,
		actions=tuple(actions),
		sources=tuple(sources),
		uncertainties=uncertainties,
	)


def result_to_dict(result: AIResult) -> dict:
	return {
		"summary": result.summary,
		"risk_level": result.risk_level,
		"actions": list(result.actions),
		"sources": [
			{"doctype": source.doctype, "name": source.name}
			for source in result.sources
		],
		"uncertainties": list(result.uncertainties),
	}
