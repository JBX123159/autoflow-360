import locale
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-environment.ps1"
POWERSHELL = (
    shutil.which("powershell.exe")
    or shutil.which("powershell")
    or shutil.which("pwsh")
)


@unittest.skipUnless(os.name == "nt" and POWERSHELL, "需要 Windows PowerShell")
class EnvironmentCheckTest(unittest.TestCase):
    def _write_command(self, directory: Path, name: str, lines: list[str]) -> None:
        (directory / f"{name}.cmd").write_text(
            "\r\n".join(("@echo off", *lines, "")),
            encoding="ascii",
        )

    def _write_git(self, directory: Path) -> None:
        self._write_command(
            directory,
            "git",
            (
                'if "%1"=="--version" echo git version 2.54.0.windows.1',
                'if "%1"=="--version" exit /b 0',
                "exit /b 1",
            ),
        )

    def _write_docker(
        self,
        directory: Path,
        *,
        major: int = 28,
        daemon_available: bool = True,
        compose_available: bool = True,
        compose_output: str = "Docker Compose version v2.39.1",
    ) -> None:
        lines = [
            f'if "%1"=="--version" echo Docker version {major}.0.0, build synthetic',
            'if "%1"=="--version" exit /b 0',
            (
                f'if "%1"=="info" echo {major}.0.0'
                if daemon_available
                else 'if "%1"=="info" exit /b 1'
            ),
            'if "%1"=="info" exit /b 0',
        ]
        if compose_available:
            lines.extend(
                (
                    f'if "%1"=="compose" echo {compose_output}',
                    'if "%1"=="compose" exit /b 0',
                )
            )
        lines.append("exit /b 1")
        self._write_command(directory, "docker", lines)

    def _write_wsl(
        self,
        directory: Path,
        *,
        distro: str = "Ubuntu-24.04",
        distro_version: int = 2,
        rows: tuple[str, ...] | None = None,
        nul_characters: bool = False,
        docker_available: bool = False,
        docker_major: int = 29,
        compose_output: str = "Docker Compose version v5.3.1",
    ) -> None:
        distribution_rows = rows or (f"{distro} Stopped {distro_version}",)
        payload_lines = ("NAME STATE VERSION", *distribution_rows)
        payload = bytearray()
        for line in payload_lines:
            encoded_line = line.encode("ascii")
            if nul_characters:
                encoded_line = b"\x00".join(
                    bytes((character,)) for character in encoded_line
                )
            payload.extend(encoded_line)
            payload.extend(b"\r\n")
        (directory / "wsl-list.bin").write_bytes(payload)

        command_lines = [
            'if "%1"=="--version" goto version',
            'if "%1"=="--list" goto list',
        ]
        if docker_available:
            command_lines.extend(
                (
                    'if "%1"=="-d" if "%4"=="git" if "%5"=="--version" goto git_version',
                    'if "%1"=="-d" if "%4"=="docker" if "%5"=="--version" goto docker_version',
                    'if "%1"=="-d" if "%4"=="docker" if "%5"=="compose" goto compose_version',
                    'if "%1"=="-d" if "%4"=="docker" if "%5"=="info" goto docker_info',
                )
            )
        command_lines.extend(
            (
                "exit /b 1",
                ":version",
                "echo WSL version: 2.7.10.0",
                "exit /b 0",
                ":list",
                'type "%~dp0wsl-list.bin"',
                "exit /b 0",
            )
        )
        if docker_available:
            command_lines.extend(
                (
                    ":git_version",
                    "echo git version 2.54.0.synthetic-wsl",
                    "exit /b 0",
                    ":docker_version",
                    f"echo Docker version {docker_major}.0.0, build synthetic-wsl",
                    "exit /b 0",
                    ":docker_info",
                    f"echo {docker_major}.0.0",
                    "exit /b 0",
                    ":compose_version",
                    f"echo {compose_output}",
                    "exit /b 0",
                )
            )
        self._write_command(directory, "wsl", command_lines)

    def _run_check(
        self,
        *,
        docker_major: int | None = 28,
        docker_daemon_available: bool = True,
        compose_available: bool = True,
        include_wsl: bool = True,
        distro: str = "Ubuntu-24.04",
        distro_version: int = 2,
        compose_output: str = "Docker Compose version v2.39.1",
        wsl_rows: tuple[str, ...] | None = None,
        nul_characters: bool = False,
        docker_in_wsl: bool = False,
        wsl_docker_major: int = 29,
        wsl_compose_output: str = "Docker Compose version v5.3.1",
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fake_bin = Path(temporary_directory)
            self._write_git(fake_bin)
            if docker_major is not None:
                self._write_docker(
                    fake_bin,
                    major=docker_major,
                    daemon_available=docker_daemon_available,
                    compose_available=compose_available,
                    compose_output=compose_output,
                )
            if include_wsl:
                self._write_wsl(
                    fake_bin,
                    distro=distro,
                    distro_version=distro_version,
                    rows=wsl_rows,
                    nul_characters=nul_characters,
                    docker_available=docker_in_wsl,
                    docker_major=wsl_docker_major,
                    compose_output=wsl_compose_output,
                )

            environment = os.environ.copy()
            environment["PATH"] = str(fake_bin)
            environment["PATHEXT"] = ".COM;.EXE;.BAT;.CMD"
            return subprocess.run(
                (
                    str(POWERSHELL),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(SCRIPT),
                ),
                check=False,
                capture_output=True,
                text=True,
                encoding=locale.getpreferredencoding(False),
                errors="replace",
                env=environment,
            )

    def test_supported_environment_passes(self):
        result = self._run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("环境体检通过", result.stdout)

    def test_wsl_docker_backend_passes_without_windows_docker(self):
        result = self._run_check(
            docker_major=None,
            docker_in_wsl=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("backend    WSL2", result.stdout)
        self.assertIn("git version 2.54.0.synthetic-wsl", result.stdout)
        self.assertIn("Docker version 29.0.0", result.stdout)
        self.assertIn("Docker Compose version v5.3.1", result.stdout)

    def test_windows_docker_cli_without_daemon_falls_back_to_wsl(self):
        result = self._run_check(
            docker_daemon_available=False,
            docker_in_wsl=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("backend    WSL2", result.stdout)
        self.assertIn("Docker version 29.0.0", result.stdout)

    def test_missing_docker_reports_docker_and_compose(self):
        result = self._run_check(docker_major=None)
        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("缺少运行环境", output)
        self.assertIn("Docker Engine", output)
        self.assertIn("Docker Compose", output)
        self.assertIn("README.md", output)

    def test_missing_compose_is_clear(self):
        result = self._run_check(compose_available=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Docker Compose 版本检查失败", result.stdout + result.stderr)

    def test_compose_v1_is_rejected(self):
        result = self._run_check(compose_output="docker-compose version 1.29.2")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "Docker Compose 需要 v2 或更高版本",
            result.stdout + result.stderr,
        )

    def test_unparseable_compose_version_is_rejected(self):
        result = self._run_check(compose_output="Docker Compose version unknown")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "无法识别 Docker Compose 版本",
            result.stdout + result.stderr,
        )

    def test_docker_below_23_is_rejected(self):
        result = self._run_check(docker_major=22)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "Docker Engine 需要 23 或更高版本",
            result.stdout + result.stderr,
        )

    def test_missing_wsl_is_clear(self):
        result = self._run_check(include_wsl=False)
        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("缺少运行环境", output)
        self.assertIn("WSL", output)
        self.assertIn("README.md", output)

    def test_no_ubuntu_distribution_is_rejected(self):
        result = self._run_check(distro="Debian")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未安装 Ubuntu 发行版", result.stdout + result.stderr)

    def test_ubuntu_on_wsl1_is_rejected(self):
        result = self._run_check(distro_version=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Ubuntu 发行版必须使用 WSL2", result.stdout + result.stderr)

    def test_indented_starred_ubuntu_row_passes(self):
        result = self._run_check(
            wsl_rows=("   *   Ubuntu-24.04 Running 2",),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unstarred_ubuntu_row_passes(self):
        result = self._run_check(
            wsl_rows=("Ubuntu-24.04 Stopped 2",),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_multiple_distributions_with_one_ubuntu_wsl2_pass(self):
        result = self._run_check(
            wsl_rows=(
                "* Debian Stopped 2",
                "Ubuntu-22.04 Stopped 1",
                "Ubuntu-24.04 Running 2",
            ),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_nul_characters_in_wsl_output_are_removed(self):
        result = self._run_check(nul_characters=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
