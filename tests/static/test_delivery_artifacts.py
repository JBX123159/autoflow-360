import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DeliveryArtifactTest(unittest.TestCase):
	def test_recruitment_and_user_documents_exist(self):
		required = (
			"docs/architecture/system-context.md",
			"docs/architecture/data-model.md",
			"docs/architecture/business-flow.md",
			"docs/user-guide/sales-and-project.md",
			"docs/user-guide/procurement-and-delivery.md",
			"docs/user-guide/customer-portal.md",
			"docs/user-guide/supplier-portal.md",
			"docs/user-guide/administrator.md",
			"docs/test-report/acceptance.md",
			"docs/test-report/known-limitations.md",
			"docs/interview/resume-project.md",
			"docs/interview/three-minute-pitch.md",
			"docs/interview/questions-and-answers.md",
			"docs/interview/personal-contribution.md",
			"docs/demo-script.md",
			"videos/autoflow-360-launch/RENDER-REPORT.md",
			"CHANGELOG.md",
		)
		for relative_path in required:
			path = ROOT / relative_path
			self.assertTrue(path.is_file(), relative_path)
			self.assertGreater(
				len(path.read_text(encoding="utf-8").strip()),
				100,
				relative_path,
			)

	def test_acceptance_report_uses_measured_performance_values(self):
		performance = json.loads(
			(ROOT / "docs" / "test-report" / "performance.json").read_text(encoding="utf-8")
		)
		acceptance = (ROOT / "docs" / "test-report" / "acceptance.md").read_text(
			encoding="utf-8"
		)
		for key in (
			"workbench_project_list",
			"project_panorama_detail",
			"daily_risk_scan",
		):
			metric = performance["operations"][key]
			self.assertIn(str(metric["p50_ms"]), acceptance)
			self.assertIn(str(metric["p95_ms"]), acceptance)

	def test_interview_material_states_truth_boundaries(self):
		combined = "\n".join(
			(ROOT / "docs" / "interview" / name).read_text(encoding="utf-8")
			for name in (
				"resume-project.md",
				"three-minute-pitch.md",
				"questions-and-answers.md",
				"personal-contribution.md",
			)
		)
		for phrase in ("合成数据", "未上线真实企业", "ERPNext", "Frappe CRM"):
			self.assertIn(phrase, combined)

	def test_readme_links_to_final_delivery_evidence(self):
		readme = (ROOT / "README.md").read_text(encoding="utf-8")
		for link in (
			"docs/test-report/acceptance.md",
			"docs/demo-script.md",
			"docs/interview/resume-project.md",
			"docs/security/threat-model.md",
			"videos/autoflow-360-launch/RENDER-REPORT.md",
		):
			self.assertIn(link, readme)
		for screenshot in (
			"docs/images/01-workbench-overview.png",
			"docs/images/02-normal-project.png",
			"docs/images/03-supplier-delay.png",
			"docs/images/04-resample.png",
			"docs/images/05-management-cockpit.png",
			"docs/images/06-mobile-workbench.png",
			"docs/images/07-project-portfolio.png",
			"docs/images/08-normal-finance-closure.png",
			"docs/images/09-delay-remediation.png",
		):
			path = ROOT / screenshot
			self.assertTrue(path.is_file(), screenshot)
			self.assertGreater(path.stat().st_size, 10_000, screenshot)
			self.assertIn(screenshot, readme)

		video_root = ROOT / "videos" / "autoflow-360-launch"
		for artifact in (
			"STORYBOARD.md",
			"SCRIPT.md",
			"ASSET-AUDIT.md",
			"BRIEF.md",
			"frame.md",
			"hyperframes.json",
		):
			path = video_root / artifact
			self.assertTrue(path.is_file(), artifact)
			self.assertGreater(path.stat().st_size, 100, artifact)

		storyboard = (video_root / "STORYBOARD.md").read_text(encoding="utf-8")
		brief = (video_root / "BRIEF.md").read_text(encoding="utf-8")
		self.assertIn("不得依赖 CDN", brief)
		durations = [
			float(value)
			for value in re.findall(r"^- duration: ([0-9.]+)s$", storyboard, re.MULTILINE)
		]
		self.assertEqual(len(durations), 14)
		self.assertAlmostEqual(sum(durations), 162.624, places=3)

		script = (video_root / "SCRIPT.md").read_text(encoding="utf-8")
		time_ranges = [
			(float(start), float(end))
			for start, end in re.findall(
				r"\*\*Time:\*\* ([0-9.]+) — ([0-9.]+)s",
				script,
			)
		]
		self.assertEqual(len(time_ranges), 14)
		self.assertEqual(time_ranges[0][0], 0.0)
		self.assertEqual(time_ranges[-1][1], 162.624)
		for previous, current in zip(time_ranges, time_ranges[1:]):
			self.assertEqual(previous[1], current[0])

		asset_audit = (video_root / "ASSET-AUDIT.md").read_text(encoding="utf-8")
		for screenshot_path in sorted((ROOT / "docs" / "images").glob("*.png")):
			video_asset = video_root / "assets" / "product" / screenshot_path.name
			self.assertTrue(video_asset.is_file(), video_asset)
			self.assertEqual(video_asset.read_bytes(), screenshot_path.read_bytes())
			self.assertIn(f"assets/product/{screenshot_path.name}", asset_audit)


if __name__ == "__main__":
	unittest.main()
