import importlib
import json
import math
import os
import platform
from pathlib import Path
from time import perf_counter_ns

import frappe
from frappe.utils import now_datetime

from autoflow_360.ai.service import generate_weekly_drafts
from autoflow_360.api.analytics import get_project_panorama, get_workbench_data
from autoflow_360.risk_engine.scheduled import scan_daily_risks
from autoflow_360.performance.generate_scale import (
	EVIDENCE_TARGET,
	ORDER_TARGET,
	PROJECT_TARGET,
	SAMPLE_TARGET,
	_record_counts,
)


WARMUP_RUNS = 1
MEASURED_RUNS = 10
REPORT_PATH = Path(__file__).resolve().parents[2] / "docs" / "test-report" / "performance.json"


def _percentile(values: list[float], percentile: float) -> float:
	ordered = sorted(values)
	index = max(0, math.ceil(percentile * len(ordered)) - 1)
	return ordered[index]


def _measure(operation) -> dict:
	last_result = None
	for _ in range(WARMUP_RUNS):
		last_result = operation()
	durations = []
	for _ in range(MEASURED_RUNS):
		started = perf_counter_ns()
		last_result = operation()
		durations.append((perf_counter_ns() - started) / 1_000_000)
	return {
		"runs": MEASURED_RUNS,
		"p50_ms": round(_percentile(durations, 0.50), 3),
		"p95_ms": round(_percentile(durations, 0.95), 3),
		"max_ms": round(max(durations), 3),
		"last_result": last_result if isinstance(last_result, (str, int, float, bool, type(None))) else None,
	}


def _module_version(module_name: str) -> str:
	try:
		module = importlib.import_module(module_name)
		return str(getattr(module, "__version__", "unknown"))
	except (ImportError, AttributeError):
		return "unknown"


def _memory_total_mb() -> int | None:
	try:
		for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
			if line.startswith("MemTotal:"):
				return round(int(line.split()[1]) / 1024)
	except (OSError, ValueError, IndexError):
		return None
	return None


def _environment() -> dict:
	database_version = frappe.db.sql("SELECT VERSION()", pluck=True)[0]
	return {
		"site": frappe.local.site,
		"python": platform.python_version(),
		"node_requirement": "24+",
		"frappe": _module_version("frappe"),
		"erpnext": _module_version("erpnext"),
		"crm": _module_version("crm"),
		"database": str(database_version),
		"platform": platform.platform(),
		"cpu_count": os.cpu_count(),
		"memory_total_mb": _memory_total_mb(),
	}


def _project_list() -> int:
	return len(get_workbench_data()["projects"])


def _project_detail() -> str:
	return get_project_panorama("PERF-PROJECT-0001")["project"]["name"]


def _risk_scan() -> str:
	scan_daily_risks()
	return "completed"


def _weekly_drafts() -> int:
	return generate_weekly_drafts()


def _validate_scale(counts: dict[str, int]) -> None:
	required = {
		"customer_projects": PROJECT_TARGET,
		"sample_requests": SAMPLE_TARGET,
		"customer_feedback": SAMPLE_TARGET,
		"sales_orders": ORDER_TARGET,
		"purchase_orders": ORDER_TARGET,
		"risk_exception_version_total": EVIDENCE_TARGET,
	}
	missing = {
		name: {"required": target, "actual": counts.get(name, 0)}
		for name, target in required.items()
		if counts.get(name, 0) < target
	}
	if missing:
		frappe.throw(f"性能测量前必须先生成完整合成规模数据：{missing}")


def run() -> dict:
	counts = _record_counts()
	_validate_scale(counts)
	settings = frappe.get_single("AutoFlow Settings")
	report = {
		"generated_at": str(now_datetime()),
		"classification": "合成性能数据；结果仅代表本次本机容器环境。",
		"measurement_policy": {
			"warmup_runs": WARMUP_RUNS,
			"measured_runs": MEASURED_RUNS,
			"percentile_method": "nearest-rank",
			"ai_enabled_during_weekly_task": bool(settings.ai_enabled),
		},
		"environment": _environment(),
		"record_counts": counts,
		"operations": {
			"workbench_project_list": _measure(_project_list),
			"project_panorama_detail": _measure(_project_detail),
			"daily_risk_scan": _measure(_risk_scan),
			"weekly_draft_scheduler": _measure(_weekly_drafts),
		},
	}
	REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
	REPORT_PATH.write_text(
		json.dumps(report, ensure_ascii=False, indent=2) + "\n",
		encoding="utf-8",
	)
	frappe.db.commit()
	return report
