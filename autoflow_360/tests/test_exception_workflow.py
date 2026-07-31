import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.file_manager import save_file

from autoflow_360.risk_engine.service import evaluate_project
from autoflow_360.services.exception_workflow import transition_exception
from autoflow_360.services.project_closure import get_closure_gaps
from autoflow_360.tests.factories import (
	make_business_exception,
	make_fulfilled_project,
	make_internal_user,
)


def _private_evidence(filename: str) -> str:
	return save_file(
		filename,
		f"SYNTHETIC auditable exception evidence: {frappe.session.user}: {filename}".encode(),
		None,
		None,
		is_private=1,
	).file_url


class TestExceptionWorkflow(IntegrationTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")

	def test_status_cannot_be_changed_directly(self):
		exception = make_business_exception(status="已发现")
		exception.status = "已分级"

		with self.assertRaises(frappe.ValidationError):
			exception.save(ignore_permissions=True)

	def test_exception_cannot_skip_root_cause(self):
		exception = make_business_exception(status="根因分析中", include_root_cause=False)

		with self.assertRaises(frappe.ValidationError):
			transition_exception(exception.name, "整改中")

	def test_assignment_requires_responsible_owner(self):
		exception = make_business_exception(status="已分级")
		exception.responsible_department = None
		exception.responsible_user = None
		exception.target_close_date = None
		exception.save()

		with self.assertRaises(frappe.ValidationError):
			transition_exception(exception.name, "已分派")

	def test_pending_verification_requires_completed_actions_and_evidence(self):
		exception = make_business_exception(
			status="整改中",
			all_actions_complete=False,
		)

		with self.assertRaises(frappe.ValidationError):
			transition_exception(exception.name, "待验证")

	def test_high_risk_creator_cannot_verify_own_exception(self):
		creator = make_internal_user("AutoFlow Project Manager")
		exception = make_business_exception(
			status="待验证",
			risk_level="高",
			raised_by=creator.name,
		)
		frappe.set_user(creator.name)
		evidence = _private_evidence("SYNTHETIC-creator-verification.txt")

		with self.assertRaises(frappe.PermissionError):
			transition_exception(exception.name, "已关闭", evidence)

	def test_high_risk_responsible_user_cannot_verify_own_work(self):
		creator = make_internal_user("AutoFlow Project Manager")
		responsible = make_internal_user("AutoFlow Procurement")
		exception = make_business_exception(
			status="待验证",
			risk_level="高",
			raised_by=creator.name,
			responsible_user=responsible.name,
			action_owner=responsible.name,
		)
		frappe.set_user(responsible.name)
		evidence = _private_evidence("SYNTHETIC-responsible-verification.txt")

		with self.assertRaises(frappe.PermissionError):
			transition_exception(exception.name, "已关闭", evidence)

	def test_foreign_verification_file_is_rejected(self):
		creator = make_internal_user("AutoFlow Project Manager")
		verifier = make_internal_user("AutoFlow Executive")
		exception = make_business_exception(
			status="待验证",
			risk_level="高",
			raised_by=creator.name,
		)
		foreign_evidence = _private_evidence("SYNTHETIC-foreign-verification.txt")
		frappe.set_user(verifier.name)

		with self.assertRaises(frappe.PermissionError):
			transition_exception(exception.name, "已关闭", foreign_evidence)

	def test_independent_verifier_closes_with_audit_evidence(self):
		creator = make_internal_user("AutoFlow Project Manager")
		verifier = make_internal_user("AutoFlow Executive")
		exception = make_business_exception(
			status="待验证",
			risk_level="高",
			raised_by=creator.name,
		)
		frappe.set_user(verifier.name)
		evidence = _private_evidence("SYNTHETIC-independent-verification.txt")

		first = transition_exception(exception.name, "已关闭", evidence)
		second = transition_exception(exception.name, "已关闭", evidence)
		exception.reload()

		self.assertEqual(first, second)
		self.assertEqual(exception.status, "已关闭")
		self.assertEqual(exception.verification_evidence, evidence)
		self.assertEqual(exception.verified_by, verifier.name)
		self.assertTrue(exception.verified_at)

	def test_cancellation_requires_reason_and_is_idempotent(self):
		exception = make_business_exception(status="已发现")

		with self.assertRaises(frappe.ValidationError):
			transition_exception(exception.name, "已取消")
		first = transition_exception(
			exception.name,
			"已取消",
			reason="SYNTHETIC customer program cancelled",
		)
		second = transition_exception(
			exception.name,
			"已取消",
			reason="SYNTHETIC customer program cancelled",
		)

		self.assertEqual(first, second)

	def test_guest_cannot_transition_exception(self):
		exception = make_business_exception(status="已发现")
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			transition_exception(exception.name, "已分级")

	def test_open_high_exception_blocks_project_and_creates_risk(self):
		project = make_fulfilled_project()
		make_business_exception(
			project.name,
			risk_level="高",
			status="整改中",
		)

		gap_codes = {gap.code for gap in get_closure_gaps(project.name)}
		finding_codes = {
			finding.rule_code for finding in evaluate_project(project.name)
		}

		self.assertIn("OPEN_HIGH_EXCEPTION", gap_codes)
		self.assertIn("HIGH_EXCEPTION_OPEN", finding_codes)

	def test_closed_high_exception_no_longer_blocks_project(self):
		project = make_fulfilled_project()
		creator = make_internal_user("AutoFlow Project Manager")
		verifier = make_internal_user("AutoFlow Executive")
		exception = make_business_exception(
			project.name,
			risk_level="高",
			status="待验证",
			raised_by=creator.name,
		)
		frappe.set_user(verifier.name)
		evidence = _private_evidence("SYNTHETIC-closed-exception.txt")
		transition_exception(exception.name, "已关闭", evidence)

		gap_codes = {gap.code for gap in get_closure_gaps(project.name)}
		finding_codes = {
			finding.rule_code for finding in evaluate_project(project.name)
		}

		self.assertNotIn("OPEN_HIGH_EXCEPTION", gap_codes)
		self.assertNotIn("HIGH_EXCEPTION_OPEN", finding_codes)
