import json
import hashlib
import locale
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = (
    shutil.which("powershell.exe")
    or shutil.which("powershell")
    or shutil.which("pwsh")
)


class DeploymentContractTest(unittest.TestCase):
    def test_integration_workflow_prepares_writable_bench_workspace(self):
        workflow = (
            ROOT / ".github" / "workflows" / "integration.yml"
        ).read_text(encoding="utf-8")
        compose_override = (
            ROOT / "deploy" / "ci" / "compose.autoflow.yaml"
        ).read_text(encoding="utf-8")
        required_text = (
            "exec -T --user root frappe sh -ceu",
            "mkdir -p /workspace/development",
            "chown -R frappe:frappe /workspace/development",
        )
        for text in required_text:
            self.assertIn(text, workflow)

        prepare_index = workflow.index("Prepare writable development workspace")
        bootstrap_index = workflow.index("Bootstrap the locked application stack")
        self.assertLess(prepare_index, bootstrap_index)
        self.assertIn(
            "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
            "/.runtime/frappe_docker:/workspace/frappe_docker",
            compose_override,
        )

    def test_required_development_files_exist(self):
        for relative_path in (
            "deploy/apps.dev.json",
            "deploy/container-lock.json",
            "deploy/env.example",
            "deploy/upstream-lock.json",
            "scripts/bootstrap-dev.ps1",
            "scripts/bootstrap-container.sh",
            "scripts/bench.ps1",
            "scripts/run-tests.ps1",
            "autoflow_360/development.py",
            "autoflow_360/tests/test_installation.py",
            "docs/deployment/local-development.md",
        ):
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)

    def test_dev_apps_are_exactly_the_compatible_upstreams(self):
        apps = json.loads(
            (ROOT / "deploy" / "apps.dev.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            apps,
            [
                {
                    "url": "https://github.com/frappe/erpnext",
                    "branch": "version-16",
                },
                {
                    "url": "https://github.com/frappe/crm",
                    "branch": "main",
                },
            ],
        )

    def test_machine_readable_lock_matches_documented_upstreams(self):
        lock_data = json.loads(
            (ROOT / "deploy" / "upstream-lock.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            lock_data,
            {
                "frappe_docker": {
                    "repository": "https://github.com/frappe/frappe_docker",
                    "branch": "main",
                    "commit": "f137f05d799a6a00d203b4c0d316a8f475e51778",
                },
                "frappe": {
                    "repository": "https://github.com/frappe/frappe",
                    "branch": "version-16",
                    "commit": "06613fc60b44d5736007ae3107cdab029b2ae045",
                },
                "erpnext": {
                    "repository": "https://github.com/frappe/erpnext",
                    "branch": "version-16",
                    "commit": "8378b6e203841c056925420cc44e6d631c915cf1",
                },
                "crm": {
                    "repository": "https://github.com/frappe/crm",
                    "branch": "main",
                    "commit": "966705a95dbc6e66a8c3342bec6e78a3b397b402",
                },
            },
        )
        baseline = (
            ROOT / "docs" / "research" / "upstream-baseline.md"
        ).read_text(encoding="utf-8")
        for entry in lock_data.values():
            self.assertIn(entry["repository"], baseline)
            self.assertIn(entry["branch"], baseline)
            self.assertIn(entry["commit"], baseline)

    def test_container_images_are_locked_by_digest(self):
        lock_data = json.loads(
            (ROOT / "deploy" / "container-lock.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            lock_data,
            {
                "frappe_bench": (
                    "docker.io/frappe/bench@sha256:"
                    "c66af151b8b220312c2bb9ea831416299c08af2d7d344bc432252f89c39cc622"
                ),
                "mariadb": (
                    "docker.io/mariadb@sha256:"
                    "efb4959ef2c835cd735dbc388eb9ad6aab0c78dd64febcd51bc17481111890c4"
                ),
                "redis": (
                    "docker.io/redis@sha256:"
                    "8096655e437712b07503796fb64d81359256cfcff0ab29d95a7da72863786efb"
                ),
            },
        )
        for image in lock_data.values():
            self.assertRegex(image, r"^docker\.io/.+@sha256:[0-9a-f]{64}$")

    def test_example_environment_has_no_database_root_setting_or_real_secret(self):
        content = (ROOT / "deploy" / "env.example").read_text(encoding="utf-8")
        self.assertIn("AUTOFLOW_SITE=autoflow.localhost", content)
        self.assertIn("AUTOFLOW_ADMIN_PASSWORD=change-me-locally", content)
        self.assertIn("AUTOFLOW_RUNTIME=.runtime/frappe_docker", content)
        self.assertIn("AUTOFLOW_WSL_DISTRO=Ubuntu", content)
        self.assertNotIn("AUTOFLOW_DB_ROOT_PASSWORD", content)
        self.assertNotIn("@qq.com", content)
        self.assertNotIn("MYSQL_ROOT_PASSWORD", content)

    def test_bootstrap_uses_safe_config_and_current_toolchain(self):
        content = (ROOT / "scripts" / "bootstrap-dev.ps1").read_text(
            encoding="utf-8-sig"
        )
        for required_text in (
            "AUTOFLOW_SITE",
            "AUTOFLOW_ADMIN_PASSWORD",
            "AUTOFLOW_RUNTIME",
            "AUTOFLOW_WSL_DISTRO",
            "upstream-lock.json",
            "Read-UpstreamLock",
            "container-lock.json",
            "Read-ContainerImageLock",
            "image: '${mariaDbImage}'",
            "image: '${redisImage}'",
            "image: '${frappeBenchImage}'",
            '"checkout", "--detach", $frappeDockerCommit',
            '"status",',
            '"--untracked-files=no"',
            "Remove-Item -Recurse -Force -LiteralPath $actualTargetPath",
            '@("info", "--format", "{{.ServerVersion}}")',
            '"AUTOFLOW_SITE=$siteName"',
            '"AUTOFLOW_ADMIN_PASSWORD=$adminPassword"',
            "Get-DockerBackend",
            "wslpath",
            '$normalizedWindowsPath = $WindowsPath.Replace("\\", "/")',
            '$gitPrefix = @("-d", $wslDistro, "--", "git")',
            "$runtimePathForGit",
            "-Command $gitCommand",
            '$ErrorActionPreference = "Continue"',
            "- '${projectRootForYaml}:/workspace/autoflow_360'",
            "- '${runtimeRootForYaml}:/workspace/frappe_docker'",
            "autoflow-bench-data:/workspace/development",
            'name: autoflow-360-bench-data',
            "external: true",
            ".autoflow-volume-owner",
            ".autoflow-volume-ready",
            "Read-BenchVolumeOwner",
            "target=/source/volume-owner,readonly",
            "Bench 原生卷所有权标记写后校验失败",
            "Bench 原生卷属于其他项目或站点",
            "未标记的非空卷只能先确认来源，再重新覆盖复制以恢复中断迁移",
            "find /target -mindepth 1 -maxdepth 1",
            "tar -C /source -cf - . | tar -C /target -xpf -",
            ":/workspace/autoflow_360",
            ":/workspace/frappe_docker",
            "/workspace/autoflow_360/scripts/bootstrap-container.sh",
        ):
            self.assertIn(required_text, content)

        for forbidden_text in (
            "AUTOFLOW_DB_ROOT_PASSWORD",
            "--admin-password admin",
            "Invoke-Expression",
            "Copy-Item apps/autoflow_360",
            r"- \'${projectRootForYaml}",
            r"- \'${runtimeRootForYaml}",
            "bash -lc",
            'printf "%s\\n" "$1" > /target/.autoflow-volume-owner',
        ):
            self.assertNotIn(forbidden_text, content)

        container_script = (
            ROOT / "scripts" / "bootstrap-container.sh"
        ).read_text(encoding="utf-8")
        for required_text in (
            "version-16",
            "--py-version 3.14",
            "--node-version 24",
            'prepare_locked_source frappe',
            'prepare_locked_source erpnext',
            'prepare_locked_source crm',
            '--apps-json "${LOCKED_APPS_JSON}"',
            '--frappe-repo "${CACHE_ROOT}/frappe"',
            "--frappe-branch autoflow-lock",
            "adopt_official_origin frappe",
            "adopt_official_origin erpnext",
            "adopt_official_origin crm",
            "ln -s /workspace/autoflow_360 apps/autoflow_360",
            "pin_upstream_app frappe",
            "pin_upstream_app erpnext",
            "pin_upstream_app crm",
            'git -C "${app_path}" checkout --detach "${locked_commit}"',
            "bench setup requirements --python --node",
            "bench build",
            "INITIAL_ADMIN_PASSWORD",
            "autoflow_360.development.sync_local_admin_password",
            "<redacted>",
            'tail -c 1 "${APPS_TXT}" | wc -l',
            'grep -qx autoflow_360 "${APPS_TXT}"',
            "printf '%s\\n' autoflow_360",
            'bench --site "${SITE}" execute frappe.cache_manager.clear_global_cache',
            'set-config allow_tests true',
        ):
            self.assertIn(required_text, container_script)
        pip_install_index = container_script.index(
            "./env/bin/pip install -e apps/autoflow_360"
        )
        cache_refresh_index = container_script.index(
            'bench --site "${SITE}" execute frappe.cache_manager.clear_global_cache'
        )
        app_install_index = container_script.index(
            'bench --site "${SITE}" install-app autoflow_360'
        )
        self.assertLess(pip_install_index, cache_refresh_index)
        self.assertLess(cache_refresh_index, app_install_index)
        self.assertNotIn("\r", container_script)
        self.assertNotIn('set-admin-password "${AUTOFLOW_ADMIN_PASSWORD}"', container_script)

        development_module = (
            ROOT / "autoflow_360" / "development.py"
        ).read_text(encoding="utf-8")
        for required_text in (
            'site_name.endswith(".localhost")',
            "frappe.conf.developer_mode",
            'os.environ.get("AUTOFLOW_ADMIN_PASSWORD", "")',
            "logout_all_sessions=True",
        ):
            self.assertIn(required_text, development_module)

        test_script = (
            ROOT / "scripts" / "run-tests.ps1"
        ).read_text(encoding="utf-8-sig")
        self.assertIn("--site $siteName set-config allow_tests true", test_script)
        self.assertIn("--site $siteName run-tests --app autoflow_360", test_script)

    def test_bench_wrapper_passes_arguments_without_a_shell_command_string(self):
        content = (ROOT / "scripts" / "bench.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("Get-DockerBackend", content)
        self.assertIn("Test-DockerDaemon", content)
        self.assertIn('"info", "--format", "{{.ServerVersion}}"', content)
        self.assertIn("wslpath", content)
        self.assertRegex(content, r"@dockerPrefix exec\s+`")
        self.assertIn("--workdir", content)
        self.assertIn("bench @args", content)
        self.assertNotIn("bash -lc", content)
        self.assertNotIn("Invoke-Expression", content)

    def test_documentation_states_local_database_boundary_and_start_command(self):
        content = (
            ROOT / "docs" / "deployment" / "local-development.md"
        ).read_text(encoding="utf-8")
        for required_text in (
            "仅限本机隔离开发",
            "MariaDB",
            "`123`",
            "生产环境禁止",
            "Python 3.14",
            "Node 24",
            r".\scripts\bench.ps1 start",
            "autoflow-lock",
            "每次运行 `bootstrap-dev.ps1` 都会",
        ):
            self.assertIn(required_text, content)

    def test_upstream_rows_are_present_without_fabricated_revisions(self):
        content = (ROOT / "docs" / "research" / "upstream-baseline.md").read_text(
            encoding="utf-8"
        )
        expected_projects = {
            "Frappe Framework",
            "ERPNext",
            "Frappe CRM",
            "frappe_docker",
        }
        rows = {}
        for line in content.splitlines():
            if not line.lstrip().startswith("|"):
                continue
            columns = [column.strip() for column in line.strip().strip("|").split("|")]
            if columns and columns[0] in expected_projects:
                self.assertNotIn(columns[0], rows, f"重复上游行：{columns[0]}")
                rows[columns[0]] = columns

        self.assertEqual(set(rows), expected_projects)
        revision_counts = []
        for project, columns in rows.items():
            self.assertGreaterEqual(len(columns), 5, project)
            revisions = re.findall(r"`([0-9a-f]{40})`", columns[4])
            self.assertLessEqual(len(revisions), 1, project)
            revision_counts.append(len(revisions))

        self.assertIn(sum(revision_counts), (0, 4))
        if sum(revision_counts) == 0:
            self.assertIn("首次成功拉取并安装后回填", content)
        else:
            dates = re.findall(r"获取日期：(\d{4}-\d{2}-\d{2})", content)
            self.assertGreaterEqual(len(dates), 1)
            self.assertEqual(len(set(dates)), 1)

    def test_task_three_matches_current_frappe_docker_contract(self):
        plan = (
            ROOT
            / "docs"
            / "superpowers"
            / "plans"
            / "2026-07-29-autoflow-360-implementation.md"
        ).read_text(encoding="utf-8")
        task_three = plan.split("### Task 3:", 1)[1].split("\n---", 1)[0]

        self.assertNotIn("AUTOFLOW_DB_ROOT_PASSWORD", task_three)
        self.assertNotIn("--admin-password admin", task_three)
        for required_text in (
            "仅限本机隔离开发",
            "生产环境禁止",
            "installer.py",
            "MariaDB root 密码固定为 `123`",
            "Python 3.14",
            "Node 24",
            "允许名单",
            "Invoke-Expression",
            "当前基线已于 2026-07-30 完成回填",
        ):
            self.assertIn(required_text, task_three)


@unittest.skipUnless(os.name == "nt" and POWERSHELL, "需要 Windows PowerShell")
class DeploymentConfigValidationTest(unittest.TestCase):
    def _run_bootstrap_with_env_text(
        self, env_text: str
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            scripts_directory = project_root / "scripts"
            scripts_directory.mkdir()
            shutil.copy2(
                ROOT / "scripts" / "bootstrap-dev.ps1",
                scripts_directory / "bootstrap-dev.ps1",
            )
            (scripts_directory / "check-environment.ps1").write_text(
                'throw "不应执行环境体检"\n',
                encoding="utf-8-sig",
            )
            (project_root / ".env").write_text(env_text, encoding="utf-8")

            environment = os.environ.copy()
            for key in (
                "AUTOFLOW_SITE",
                "AUTOFLOW_ADMIN_PASSWORD",
                "AUTOFLOW_RUNTIME",
                "AUTOFLOW_WSL_DISTRO",
            ):
                environment.pop(key, None)

            return subprocess.run(
                (
                    str(POWERSHELL),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(scripts_directory / "bootstrap-dev.ps1"),
                ),
                check=False,
                capture_output=True,
                text=True,
                encoding=locale.getpreferredencoding(False),
                errors="replace",
                env=environment,
            )

    def test_unknown_environment_key_is_rejected_before_any_command(self):
        result = self._run_bootstrap_with_env_text(
            "AUTOFLOW_SITE=autoflow.localhost\n"
            "AUTOFLOW_ADMIN_PASSWORD=synthetic-only\n"
            "UNEXPECTED_KEY=value\n"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不支持的配置项", result.stdout + result.stderr)
        self.assertNotIn("不应执行环境体检", result.stdout + result.stderr)

    def test_invalid_site_is_rejected_before_any_command(self):
        result = self._run_bootstrap_with_env_text(
            "AUTOFLOW_SITE=autoflow.localhost;echo-bad\n"
            "AUTOFLOW_ADMIN_PASSWORD=synthetic-only\n"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("站点名不合法", result.stdout + result.stderr)
        self.assertNotIn("不应执行环境体检", result.stdout + result.stderr)

    def test_nul_character_is_rejected_before_any_command(self):
        result = self._run_bootstrap_with_env_text(
            "AUTOFLOW_SITE=autoflow.localhost\n"
            "AUTOFLOW_ADMIN_PASSWORD=safe\x00suffix\n"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("NUL", result.stdout + result.stderr)
        self.assertNotIn("不应执行环境体检", result.stdout + result.stderr)

    def test_wsl_backend_normalizes_paths_and_writes_valid_yaml_quotes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory) / "中文 项目"
            scripts_directory = project_root / "scripts"
            deploy_directory = project_root / "deploy"
            runtime_root = project_root / ".runtime" / "frappe_docker"
            devcontainer_source = runtime_root / "devcontainer-example"
            scripts_directory.mkdir(parents=True)
            deploy_directory.mkdir()
            (runtime_root / ".git").mkdir(parents=True)
            devcontainer_source.mkdir()
            (devcontainer_source / "docker-compose.yml").write_text(
                "services:\n  frappe:\n    image: synthetic\n",
                encoding="utf-8",
            )

            shutil.copy2(
                ROOT / "scripts" / "bootstrap-dev.ps1",
                scripts_directory / "bootstrap-dev.ps1",
            )
            shutil.copy2(
                ROOT / "deploy" / "upstream-lock.json",
                deploy_directory / "upstream-lock.json",
            )
            shutil.copy2(
                ROOT / "deploy" / "container-lock.json",
                deploy_directory / "container-lock.json",
            )
            (scripts_directory / "check-environment.ps1").write_text(
                "param([string]$WslDistro)\n",
                encoding="utf-8-sig",
            )
            (project_root / ".env").write_text(
                "AUTOFLOW_SITE=autoflow.localhost\n"
                "AUTOFLOW_ADMIN_PASSWORD=synthetic-only\n"
                "AUTOFLOW_RUNTIME=.runtime/frappe_docker\n"
                "AUTOFLOW_WSL_DISTRO=Ubuntu\n",
                encoding="utf-8",
            )

            fake_bin = project_root / "fake-bin"
            fake_bin.mkdir()
            project_identity = hashlib.sha256(
                str(project_root).lower().encode("utf-8")
            ).hexdigest()
            expected_volume_owner = (
                f"autoflow-360:v1:{project_identity}:autoflow.localhost"
            )
            self._write_fake_wsl(fake_bin, expected_volume_owner)
            environment = os.environ.copy()
            environment["PATH"] = str(fake_bin)
            environment["PATHEXT"] = ".COM;.EXE;.BAT;.CMD"
            for key in (
                "AUTOFLOW_SITE",
                "AUTOFLOW_ADMIN_PASSWORD",
                "AUTOFLOW_RUNTIME",
                "AUTOFLOW_WSL_DISTRO",
            ):
                environment.pop(key, None)

            result = subprocess.run(
                (
                    str(POWERSHELL),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(scripts_directory / "bootstrap-dev.ps1"),
                ),
                check=False,
                capture_output=True,
                text=True,
                encoding=locale.getpreferredencoding(False),
                errors="replace",
                env=environment,
            )
            fake_wsl_log = (fake_bin / "wsl-args.log").read_text(
                encoding=locale.getpreferredencoding(False),
                errors="replace",
            )
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + result.stderr + "\nWSL 参数日志：\n" + fake_wsl_log,
            )

            override = (
                runtime_root / ".devcontainer" / "compose.autoflow.yaml"
            ).read_text(encoding="utf-8-sig")
            self.assertIn(
                "- '/mnt/c/synthetic 中文 path:/workspace/autoflow_360'",
                override,
            )
            self.assertIn(
                "- '/mnt/c/synthetic 中文 path:/workspace/frappe_docker'",
                override,
            )
            self.assertNotIn(r"\'", override)

            wsl_arguments = fake_wsl_log
            owner_source_bytes = (
                runtime_root / ".devcontainer" / "volume-owner.txt"
            ).read_bytes()
            self.assertEqual(
                owner_source_bytes,
                (expected_volume_owner + "\n").encode("utf-8"),
            )
            self.assertFalse(owner_source_bytes.startswith(b"\xef\xbb\xbf"))

            copy_fragment = (
                'target=/source/volume-owner,readonly"'
                " --mount type=volume,source=autoflow-360-bench-data,target=/target"
                " docker.io/frappe/bench@sha256:"
                "c66af151b8b220312c2bb9ea831416299c08af2d7d344bc432252f89c39cc622"
                " cp /source/volume-owner /target/.autoflow-volume-owner"
            )
            touch_fragment = (
                "docker.io/frappe/bench@sha256:"
                "c66af151b8b220312c2bb9ea831416299c08af2d7d344bc432252f89c39cc622"
                " touch /target/.autoflow-volume-ready"
            )
            read_fragment = (
                "docker.io/frappe/bench@sha256:"
                "c66af151b8b220312c2bb9ea831416299c08af2d7d344bc432252f89c39cc622"
                " cat /target/.autoflow-volume-owner"
            )
            for required_fragment in (
                copy_fragment,
                touch_fragment,
                read_fragment,
            ):
                self.assertIn(required_fragment, wsl_arguments)
            self.assertLess(
                wsl_arguments.index(copy_fragment),
                wsl_arguments.index(touch_fragment),
            )
            self.assertLess(
                wsl_arguments.index(touch_fragment),
                wsl_arguments.index(read_fragment),
            )
            self.assertNotIn('sh -c "printf', wsl_arguments)
            self.assertIn("wslpath -a", wsl_arguments)
            self.assertIn("中文 项目", wsl_arguments)
            self.assertNotRegex(wsl_arguments, r"[A-Za-z]:\\")

    def _write_fake_wsl(
        self, directory: Path, expected_volume_owner: str
    ) -> None:
        (directory / "wsl.cmd").write_text(
            "\r\n".join(
                (
                    "@echo off",
                    'echo %*>>"%~dp0wsl-args.log"',
                    'if "%4"=="wslpath" goto wslpath',
                    'if "%4"=="git" goto git',
                    'if "%4"=="docker" goto docker',
                    "exit /b 1",
                    ":wslpath",
                    "echo /mnt/c/synthetic 中文 path",
                    "exit /b 0",
                    ":git",
                    'if "%7"=="status" exit /b 0',
                    "echo synthetic git progress 1>&2",
                    'if "%7"=="remote" echo https://github.com/frappe/frappe_docker',
                    'if "%7"=="rev-parse" echo f137f05d799a6a00d203b4c0d316a8f475e51778',
                    "exit /b 0",
                    ":docker",
                    'if "%5"=="compose" echo aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                    'if not "%5"=="run" exit /b 0',
                    'if not exist "%~dp0docker-run-1" goto first_docker_run',
                    'if not exist "%~dp0docker-run-2" goto second_docker_run',
                    'if not exist "%~dp0docker-run-3" goto third_docker_run',
                    'if not exist "%~dp0docker-run-4" goto fourth_docker_run',
                    'if not exist "%~dp0docker-run-5" goto fifth_docker_run',
                    'if not exist "%~dp0docker-run-6" goto sixth_docker_run',
                    "exit /b 0",
                    ":first_docker_run",
                    'type nul > "%~dp0docker-run-1"',
                    "exit /b 1",
                    ":second_docker_run",
                    'type nul > "%~dp0docker-run-2"',
                    "exit /b 1",
                    ":third_docker_run",
                    'type nul > "%~dp0docker-run-3"',
                    "exit /b 0",
                    ":fourth_docker_run",
                    'type nul > "%~dp0docker-run-4"',
                    "exit /b 0",
                    ":fifth_docker_run",
                    'type nul > "%~dp0docker-run-5"',
                    "exit /b 0",
                    ":sixth_docker_run",
                    'type nul > "%~dp0docker-run-6"',
                    f"echo {expected_volume_owner}",
                    "exit /b 0",
                    "",
                )
            ),
            encoding=locale.getpreferredencoding(False),
        )


if __name__ == "__main__":
    unittest.main()
