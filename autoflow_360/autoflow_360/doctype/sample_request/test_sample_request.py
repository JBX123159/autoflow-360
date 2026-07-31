import frappe
from frappe.tests import IntegrationTestCase

from autoflow_360.services.sample_workflow import (
	create_resample,
	dispatch_sample,
	record_customer_feedback,
)
from autoflow_360.tests.factories import (
	make_customer_portal_user,
	make_dispatched_sample,
	make_sample_request,
)
from autoflow_360.permissions.portal import can_access_customer_project


IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Company",
	"Contact",
	"Currency",
	"Customer",
	"Customer Feedback",
	"Customer Project",
	"Item",
	"Sample Request",
	"UOM",
	"User",
]


class TestSampleRequest(IntegrationTestCase):
	def test_new_sample_advances_customer_project_stage(self):
		sample = make_sample_request()
		project_stage = frappe.db.get_value(
			"Customer Project",
			sample.customer_project,
			"stage",
		)
		self.assertEqual(project_stage, "样品阶段")

	def test_uninspected_sample_cannot_be_dispatched(self):
		sample = make_sample_request(
			status="检验中",
			inspection_status="待检验",
		)
		with self.assertRaises(frappe.ValidationError):
			dispatch_sample(
				sample.name,
				"SYNTHETIC Carrier",
				"SYNTHETIC-TRACK-UNINSPECTED",
			)

	def test_failed_item_cannot_be_dispatched(self):
		sample = make_sample_request(
			status="检验中",
			inspection_status="通过",
		)
		frappe.db.set_value(
			"Sample Item",
			sample.items[0].name,
			"inspection_result",
			"不通过",
			update_modified=False,
		)
		with self.assertRaises(frappe.ValidationError):
			dispatch_sample(
				sample.name,
				"SYNTHETIC Carrier",
				"SYNTHETIC-TRACK-FAILED",
			)

	def test_feedback_is_append_only(self):
		sample = make_dispatched_sample()
		first = record_customer_feedback(
			sample.name,
			"重新打样",
			"SYNTHETIC color mismatch",
		)
		with self.assertRaises(frappe.ValidationError):
			record_customer_feedback(
				sample.name,
				"客户认可",
				"SYNTHETIC attempt to overwrite",
			)
		self.assertTrue(frappe.db.exists("Customer Feedback", first))

		feedback = frappe.get_doc("Customer Feedback", first)
		feedback.comments = "SYNTHETIC changed after submission"
		with self.assertRaises(frappe.ValidationError):
			feedback.save()

	def test_resample_links_previous_round(self):
		sample = make_dispatched_sample()
		record_customer_feedback(
			sample.name,
			"重新打样",
			"SYNTHETIC adjust thickness",
		)

		resample_name = create_resample(sample.name)
		second_call = create_resample(sample.name)
		resample = frappe.get_doc("Sample Request", resample_name)

		self.assertEqual(second_call, resample_name)
		self.assertEqual(resample.previous_sample_request, sample.name)
		self.assertEqual(resample.round_number, sample.round_number + 1)
		self.assertEqual(resample.status, "草稿")
		self.assertEqual(resample.inspection_status, "待检验")
		self.assertEqual(resample.items[0].inspection_result, "待检验")

	def test_guest_cannot_record_feedback(self):
		sample = make_dispatched_sample()
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
				record_customer_feedback(
				sample.name,
				"客户认可",
				"SYNTHETIC unauthorized feedback",
			)

	def test_customer_portal_membership_controls_project_access(self):
		sample = make_dispatched_sample()
		linked_user = make_customer_portal_user()
		unlinked_user = make_customer_portal_user(link_customer=False)
		self.addCleanup(frappe.set_user, "Administrator")

		frappe.set_user(linked_user.name)
		self.assertTrue(can_access_customer_project(sample.customer_project))
		frappe.set_user(unlinked_user.name)
		self.assertFalse(can_access_customer_project(sample.customer_project))

	def test_linked_portal_user_can_record_feedback(self):
		sample = make_dispatched_sample()
		portal_user = make_customer_portal_user()
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(portal_user.name)

		feedback_name = record_customer_feedback(
			sample.name,
			"客户认可",
			"SYNTHETIC portal acceptance",
		)
		feedback = frappe.get_doc("Customer Feedback", feedback_name)
		self.assertEqual(feedback.submitted_by, portal_user.name)

	def test_portal_template_renders_empty_state(self):
		html = frappe.render_template(
			"autoflow_360/templates/pages/customer_samples.html",
			{"samples": []},
		)
		self.assertIn("No samples yet", html)
