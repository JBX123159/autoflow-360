import frappe
from frappe.tests import IntegrationTestCase

from autoflow_360.permissions.portal import (
	customer_delivery_has_permission,
	supplier_document_has_permission,
)
from autoflow_360.tests.factories import (
	SYNTHETIC_COMPANY,
	add_company_user_permission,
	get_foreign_company,
	make_approval_rule,
	make_customer_portal_user,
	make_customer_project,
	make_customer_project_with_member,
	make_foreign_customer,
	make_internal_user,
	make_over_limit_approval_request,
	make_project_for_company,
	make_supplier_portal_account,
)


SCOPED_INTERNAL_ROLES = (
	"AutoFlow Sales Operations",
	"AutoFlow Project Manager",
	"AutoFlow Procurement",
	"AutoFlow Warehouse",
	"AutoFlow Finance",
)
GLOBAL_INTERNAL_ROLES = (
	"AutoFlow Administrator",
	"AutoFlow Executive",
)
PORTAL_ROLES = (
	"AutoFlow Customer Portal",
	"AutoFlow Supplier Portal",
)


class TestPermissions(IntegrationTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")

	def _visible_project_names(self, user: str) -> set[str]:
		frappe.set_user(user)
		return {
			row.name
			for row in frappe.get_list("Customer Project", fields=["name"])
		}

	def test_five_scoped_roles_read_assigned_projects_only(self):
		blocked = make_customer_project("SYNTHETIC Unassigned Permission Project")
		for role in SCOPED_INTERNAL_ROLES:
			with self.subTest(role=role):
				frappe.set_user("Administrator")
				user = make_internal_user(role)
				allowed = make_customer_project_with_member(user.name)
				names = self._visible_project_names(user.name)
				self.assertIn(allowed.name, names)
				self.assertNotIn(blocked.name, names)
				self.assertFalse(
					frappe.has_permission(
						"Customer Project",
						"read",
						doc=blocked.name,
					)
				)

	def test_two_global_business_roles_read_unassigned_projects(self):
		project = make_customer_project("SYNTHETIC Global Permission Project")
		for role in GLOBAL_INTERNAL_ROLES:
			with self.subTest(role=role):
				frappe.set_user("Administrator")
				user = make_internal_user(role)
				names = self._visible_project_names(user.name)
				self.assertIn(project.name, names)

	def test_company_user_permission_blocks_other_company(self):
		foreign_company = get_foreign_company()
		allowed = make_project_for_company(SYNTHETIC_COMPANY)
		blocked = make_project_for_company(foreign_company)
		user = make_internal_user("AutoFlow Executive")
		add_company_user_permission(user.name, SYNTHETIC_COMPANY)

		names = self._visible_project_names(user.name)

		self.assertIn(allowed.name, names)
		self.assertNotIn(blocked.name, names)
		self.assertFalse(
			frappe.has_permission(
				"Customer Project",
				"read",
				doc=blocked.name,
			)
		)

	def test_customer_portal_reads_own_customer_project_only(self):
		own = make_customer_project("SYNTHETIC Portal Own Project")
		foreign_customer = make_foreign_customer()
		blocked = make_customer_project(
			"SYNTHETIC Portal Foreign Project",
			customer=foreign_customer.name,
		)
		user = make_customer_portal_user()
		self.assertIn(PORTAL_ROLES[0], frappe.get_roles(user.name))

		names = self._visible_project_names(user.name)

		self.assertIn(own.name, names)
		self.assertNotIn(blocked.name, names)
		self.assertTrue(
			frappe.has_permission("Customer Project", "read", doc=own.name)
		)
		self.assertFalse(
			frappe.has_permission("Customer Project", "write", doc=own.name)
		)

	def test_supplier_portal_cannot_read_customer_projects(self):
		project = make_customer_project("SYNTHETIC Supplier Blocked Project")
		supplier = make_supplier_portal_account()
		self.assertIn(PORTAL_ROLES[1], frappe.get_roles(supplier.portal_user))
		frappe.set_user(supplier.portal_user)

		self.assertFalse(
			frappe.has_permission(
				"Customer Project",
				"read",
				doc=project.name,
			)
		)

	def test_read_only_member_role_is_not_promoted_to_writer(self):
		user = make_internal_user("AutoFlow Procurement")
		project = make_customer_project_with_member(user.name)
		frappe.set_user(user.name)

		self.assertTrue(
			frappe.has_permission("Customer Project", "read", doc=project.name)
		)
		self.assertFalse(
			frappe.has_permission("Customer Project", "write", doc=project.name)
		)

	def test_portal_guards_do_not_deny_internal_role_permissions(self):
		user = make_internal_user("AutoFlow Procurement")
		frappe.set_user(user.name)

		self.assertTrue(
			customer_delivery_has_permission(
				frappe._dict(customer="SYNTHETIC"),
				ptype="read",
			)
		)
		self.assertTrue(
			supplier_document_has_permission(
				frappe._dict(supplier="SYNTHETIC"),
				ptype="read",
			)
		)

	def test_guest_cannot_read_customer_project(self):
		project = make_customer_project("SYNTHETIC Guest Blocked Project")
		frappe.set_user("Guest")

		self.assertFalse(
			frappe.has_permission("Customer Project", "read", doc=project.name)
		)

	def test_system_manager_is_not_automatic_business_approver(self):
		requester = make_internal_user("AutoFlow Project Manager")
		make_approval_rule(role="AutoFlow Executive")
		request = make_over_limit_approval_request(requester.name)
		frappe.set_user("Administrator")

		with self.assertRaises(frappe.PermissionError):
			request.approve("SYNTHETIC system access is not business authority")
