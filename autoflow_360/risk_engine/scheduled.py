import frappe

from autoflow_360.risk_engine.service import evaluate_project, upsert_risks


TERMINAL_STAGES = ["已结项", "失败", "取消"]


def _scan_active_projects() -> None:
	for project_name in frappe.get_all(
		"Customer Project",
		filters={"stage": ["not in", TERMINAL_STAGES]},
		pluck="name",
	):
		savepoint = f"risk_scan_{frappe.generate_hash(length=10)}"
		frappe.db.savepoint(savepoint)
		try:
			upsert_risks(project_name, evaluate_project(project_name))
		except Exception:
			frappe.db.rollback(save_point=savepoint)
			frappe.log_error(
				title=f"AutoFlow risk scan failed for {project_name}",
				message=frappe.get_traceback(),
			)


def scan_delivery_risks() -> None:
	_scan_active_projects()


def scan_daily_risks() -> None:
	_scan_active_projects()
