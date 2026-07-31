import hashlib
import json
from collections.abc import Iterable

import frappe
from frappe import _
from frappe.utils import cstr
from frappe.utils.synchronization import filelock

from autoflow_360.risk_engine.rules import RULES
from autoflow_360.risk_engine.types import RiskFinding
from autoflow_360.services.idempotency import make_idempotency_key


RISK_LEVEL_RANK = {"低": 1, "中": 2, "高": 3}
TERMINAL_PROJECT_STAGES = {"已结项", "失败", "取消"}


def _project_name(project_name: str) -> str:
	project_name = cstr(project_name).strip()
	if not project_name:
		frappe.throw(_("Customer Project is required."))
	return project_name


def evaluate_project(project_name: str) -> list[RiskFinding]:
	project = frappe.get_doc("Customer Project", _project_name(project_name))
	project.check_permission("read")
	if project.stage in TERMINAL_PROJECT_STAGES:
		return []
	findings: list[RiskFinding] = []
	for rule in RULES:
		findings.extend(rule(project))
	return sorted(
		findings,
		key=lambda finding: (
			finding.rule_code,
			finding.reference_doctype,
			finding.reference_name,
		),
	)


def make_risk_key(project_name: str, finding: RiskFinding) -> str:
	raw = "|".join(
		(
			_project_name(project_name),
			cstr(finding.rule_code).strip(),
			cstr(finding.reference_doctype).strip(),
			cstr(finding.reference_name).strip(),
		)
	)
	return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate_finding(finding: RiskFinding) -> None:
	if not isinstance(finding, RiskFinding):
		frappe.throw(_("Risk engine received an invalid finding."))
	if finding.level not in RISK_LEVEL_RANK:
		frappe.throw(_("Risk finding has an invalid level."))
	for value in (
		finding.rule_code,
		finding.risk_type,
		finding.title,
		finding.description,
		finding.reference_doctype,
		finding.reference_name,
	):
		if not cstr(value).strip():
			frappe.throw(_("Risk finding is missing required evidence."))
	if not isinstance(finding.inputs, dict):
		frappe.throw(_("Risk finding inputs must be a dictionary."))
	if not frappe.db.exists(finding.reference_doctype, finding.reference_name):
		frappe.throw(_("Risk finding reference no longer exists."))


def _risk_values(project_name: str, finding: RiskFinding, key: str) -> dict:
	return {
		"customer_project": project_name,
		"risk_type": finding.risk_type,
		"risk_level": finding.level,
		"title": finding.title,
		"description": finding.description,
		"rule_code": finding.rule_code,
		"reference_doctype": finding.reference_doctype,
		"reference_name": finding.reference_name,
		"rule_inputs": json.dumps(
			finding.inputs,
			ensure_ascii=False,
			sort_keys=True,
			separators=(",", ":"),
			default=str,
		),
		"deduplication_key": key,
		"owner_user": finding.owner_user,
		"due_date": finding.due_date,
	}


def _project_lock_name(project_name: str) -> str:
	return "autoflow-risk-scan-" + make_idempotency_key("risk", project_name)


def _lock_project(project_name: str) -> None:
	if not frappe.db.get_value(
		"Customer Project",
		project_name,
		"name",
		for_update=True,
	):
		frappe.throw(_("Customer Project no longer exists."))


def _update_overall_risk(project_name: str) -> None:
	levels = frappe.get_all(
		"Project Risk",
		filters={
			"customer_project": project_name,
			"status": ["!=", "已关闭"],
		},
		pluck="risk_level",
	)
	overall = max(
		levels,
		key=lambda level: RISK_LEVEL_RANK.get(level, 0),
		default="低",
	)
	frappe.db.set_value(
		"Customer Project",
		project_name,
		"overall_risk_level",
		overall,
		update_modified=False,
	)


def upsert_risks(
	project_name: str,
	findings: Iterable[RiskFinding],
) -> list[str]:
	project_name = _project_name(project_name)
	project = frappe.get_doc("Customer Project", project_name)
	project.check_permission("write")
	findings = list(findings)
	for finding in findings:
		_validate_finding(finding)

	with filelock(_project_lock_name(project_name), timeout=15):
		_lock_project(project_name)
		project.reload()
		project.check_permission("write")
		names: list[str] = []
		active_keys: set[str] = set()
		for finding in findings:
			key = make_risk_key(project_name, finding)
			active_keys.add(key)
			risk_name = frappe.db.get_value(
				"Project Risk",
				{"deduplication_key": key},
				"name",
				for_update=True,
			)
			values = _risk_values(project_name, finding, key)
			if risk_name:
				risk = frappe.get_doc("Project Risk", risk_name)
				risk.update(values)
				if risk.status in {"待验证", "已关闭"}:
					risk.status = "已发现"
					risk.resolved_at = None
					risk.verified_by = None
				risk.flags.from_risk_engine = True
				risk.save(ignore_permissions=True)
			else:
				risk = frappe.get_doc({"doctype": "Project Risk", **values})
				risk.status = "已发现"
				risk.flags.from_risk_engine = True
				try:
					risk.insert(ignore_permissions=True)
				except frappe.DuplicateEntryError:
					risk_name = frappe.db.get_value(
						"Project Risk",
						{"deduplication_key": key},
						"name",
					)
					if not risk_name:
						raise
					risk = frappe.get_doc("Project Risk", risk_name)
			names.append(risk.name)

		for stale in frappe.get_all(
			"Project Risk",
			filters={
				"customer_project": project_name,
				"rule_code": ["is", "set"],
				"status": ["in", ["已发现", "处理中"]],
			},
			fields=["name", "deduplication_key"],
		):
			if stale.deduplication_key in active_keys:
				continue
			risk = frappe.get_doc("Project Risk", stale.name)
			risk.status = "待验证"
			risk.flags.from_risk_engine = True
			risk.save(ignore_permissions=True)

		_update_overall_risk(project_name)
		return names
