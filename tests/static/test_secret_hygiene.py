import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APPS_FILE = ROOT / "deploy" / "apps.production.json"
FORBIDDEN_SECRET = re.compile(
	r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
TEXT_SUFFIXES = {
	".env",
	".json",
	".md",
	".ps1",
	".py",
	".sh",
	".yaml",
	".yml",
}


def repository_candidate_files() -> list[Path]:
	result = subprocess.run(
		["git", "-C", str(ROOT), "ls-files", "-co", "--exclude-standard", "-z"],
		check=True,
		capture_output=True,
	)
	return [
		ROOT / relative.decode("utf-8")
		for relative in result.stdout.split(b"\0")
		if relative
	]


class SecretHygieneTest(unittest.TestCase):
	def test_production_apps_include_all_required_apps(self):
		apps = json.loads(APPS_FILE.read_text(encoding="utf-8"))
		by_url = {item["url"]: item for item in apps}
		self.assertEqual(by_url["https://github.com/frappe/erpnext"]["branch"], "version-16")
		self.assertEqual(by_url["https://github.com/frappe/crm"]["branch"], "main")
		self.assertEqual(
			by_url["https://github.com/JBX123159/autoflow-360"]["branch"],
			"main",
		)
		for item in apps:
			self.assertNotRegex(item["url"], r"https://[^/]+@github\.com")

	def test_candidate_text_contains_no_common_secret_patterns(self):
		for path in repository_candidate_files():
			if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
				continue
			if path.resolve() == Path(__file__).resolve():
				continue
			content = path.read_text(encoding="utf-8", errors="ignore")
			self.assertIsNone(FORBIDDEN_SECRET.search(content), str(path.relative_to(ROOT)))
			self.assertNotRegex(content, r"[A-Za-z]:\\Users\\", str(path.relative_to(ROOT)))
			self.assertNotRegex(content, r"\b\d{5,}@qq\.com\b", str(path.relative_to(ROOT)))

	def test_build_workflow_uses_buildkit_secret_and_multi_arch(self):
		source = (ROOT / ".github" / "workflows" / "build-image.yml").read_text(encoding="utf-8")
		self.assertIn("linux/amd64,linux/arm64", source)
		self.assertIn("--secret id=apps_json,src=apps.json", source)
		self.assertNotRegex(source, r"--build-arg\s+APPS_JSON")
		self.assertIn("permissions:", source)
		self.assertIn("packages: write", source)

	def test_ci_and_deployment_files_are_present(self):
		required = (
			".github/workflows/static.yml",
			".github/workflows/integration.yml",
			".github/workflows/build-image.yml",
			"deploy/oracle/compose.env.example",
			"deploy/oracle/compose.platform.yaml",
			"deploy/oracle/deploy.sh",
			"deploy/oracle/backup.sh",
			"deploy/oracle/restore-check.sh",
			"scripts/verify-backup.sh",
			"scripts/start-tunnel.ps1",
			"scripts/verify-backup.ps1",
			"docs/deployment/oracle-always-free.md",
			"docs/deployment/cloudflare-tunnel.md",
			"docs/deployment/backup-and-restore.md",
			"docs/security/threat-model.md",
		)
		for relative in required:
			self.assertTrue((ROOT / relative).is_file(), relative)

	def test_backup_scripts_hash_and_restore_into_disposable_site(self):
		backup = (ROOT / "deploy" / "oracle" / "backup.sh").read_text(encoding="utf-8")
		restore = (ROOT / "deploy" / "oracle" / "restore-check.sh").read_text(encoding="utf-8")
		self.assertIn("sha256sum", backup)
		self.assertIn("--with-files", backup)
		self.assertIn("RESTORE_CHECK_PASSED", restore)
		self.assertIn("trap cleanup EXIT", restore)
		self.assertIn("drop-site", restore)
		self.assertNotIn("--force --no-backup", restore)

	def test_environment_example_contains_placeholders_only(self):
		source = (ROOT / "deploy" / "oracle" / "compose.env.example").read_text(encoding="utf-8")
		self.assertIn("CHANGE_ME", source)
		self.assertNotIn("AUTOFLOW_ADMIN_PASSWORD=admin", source)
		self.assertNotRegex(source, FORBIDDEN_SECRET)


if __name__ == "__main__":
	unittest.main()
