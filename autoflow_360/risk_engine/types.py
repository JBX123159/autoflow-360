from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True, slots=True)
class RiskFinding:
	rule_code: str
	risk_type: str
	level: str
	title: str
	description: str
	reference_doctype: str
	reference_name: str
	inputs: dict[str, Any]
	owner_user: str | None = None
	due_date: date | None = None
