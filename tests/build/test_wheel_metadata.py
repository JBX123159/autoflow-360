from email.parser import BytesParser
from email.policy import default
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def _format_process_output(output: bytes | str | None) -> str:
    if output is None:
        return "<无输出>"
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def build_wheel(wheel_directory: Path, timeout: int = 180) -> subprocess.CompletedProcess:
    command = [
        sys.executable,
        "-m",
        "pip",
        "wheel",
        ".",
        "--no-deps",
        "--wheel-dir",
        str(wheel_directory),
    ]
    try:
        return subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        stdout = _format_process_output(error.stdout)
        stderr = _format_process_output(error.stderr)
        raise AssertionError(
            f"wheel 构建超时（timeout={timeout} 秒）。"
            f"\nstdout:\n{stdout}\nstderr:\n{stderr}"
        ) from error


class WheelMetadataTest(unittest.TestCase):
    def test_timeout_diagnostic_preserves_process_output_and_context(self):
        cases = (
            (b"partial stdout", "partial stderr", ("partial stdout", "partial stderr")),
            (None, None, ("<无输出>",)),
        )
        for output, stderr, expected_outputs in cases:
            with self.subTest(output=output, stderr=stderr):
                timeout_error = subprocess.TimeoutExpired(
                    cmd=["python", "-m", "pip", "wheel"],
                    timeout=7,
                    output=output,
                    stderr=stderr,
                )

                with tempfile.TemporaryDirectory() as temporary_directory:
                    with patch(
                        "tests.build.test_wheel_metadata.subprocess.run",
                        side_effect=timeout_error,
                    ):
                        with self.assertRaises(AssertionError) as caught:
                            build_wheel(Path(temporary_directory), timeout=7)

                diagnostic = str(caught.exception)
                for expected_text in (
                    "wheel 构建超时",
                    "timeout=7",
                    "stdout",
                    "stderr",
                    *expected_outputs,
                ):
                    self.assertIn(expected_text, diagnostic)
                self.assertIs(caught.exception.__cause__, timeout_error)

    def test_built_wheel_contains_runtime_files_and_complete_metadata(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            wheel_directory = Path(temporary_directory)
            result = build_wheel(wheel_directory)
            self.assertEqual(
                result.returncode,
                0,
                f"wheel 构建失败。\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )

            wheels = list(wheel_directory.glob("*.whl"))
            self.assertEqual(
                len(wheels),
                1,
                f"预期生成一个 wheel，实际为：{[path.name for path in wheels]}",
            )

            with zipfile.ZipFile(wheels[0]) as wheel:
                members = set(wheel.namelist())
                self.assertIn("autoflow_360/hooks.py", members)
                self.assertIn(
                    "autoflow_360/public/images/autoflow-360-logo.svg",
                    members,
                )

                license_members = [
                    member for member in members if member.endswith("/LICENSE")
                ]
                self.assertEqual(len(license_members), 1, sorted(license_members))

                metadata_members = [
                    member for member in members if member.endswith(".dist-info/METADATA")
                ]
                self.assertEqual(len(metadata_members), 1, sorted(metadata_members))
                metadata = BytesParser(policy=default).parsebytes(
                    wheel.read(metadata_members[0])
                )

            self.assertEqual(metadata["Name"], "autoflow-360")
            self.assertEqual(metadata["Version"], "0.1.0")
            self.assertEqual(metadata["Requires-Python"], ">=3.14,<3.15")
            self.assertEqual(metadata["License-Expression"], "AGPL-3.0-only")
            self.assertEqual(metadata.get_all("License-File"), ["LICENSE"])


if __name__ == "__main__":
    unittest.main()
