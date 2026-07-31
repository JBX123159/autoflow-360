import frappe
from frappe.tests import IntegrationTestCase

from autoflow_360 import __version__


class TestInstallation(IntegrationTestCase):
	def test_required_apps_are_installed(self):
		installed_apps = set(frappe.get_installed_apps())

		for app_name in ("frappe", "erpnext", "crm", "autoflow_360"):
			self.assertIn(app_name, installed_apps)

	def test_app_metadata_matches_runtime(self):
		self.assertEqual(__version__, "0.1.0")
		self.assertTrue(frappe.local.site.endswith(".localhost"))
