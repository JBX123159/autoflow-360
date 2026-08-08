#!/usr/bin/env bash

set -euo pipefail

SITE="${AUTOFLOW_SITE}"
BENCH_PATH="/workspace/development/frappe-bench"
LOCK_FILE="/workspace/autoflow_360/deploy/upstream-lock.json"
CACHE_ROOT="/workspace/development/autoflow-upstreams"
LOCKED_APPS_JSON="/workspace/development/apps.autoflow-lock.json"
INITIAL_ADMIN_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(36))')"

redact_bench_log() {
  python - "${BENCH_PATH}/logs/bench.log" <<'PY' || true
import pathlib
import re
import sys

log_path = pathlib.Path(sys.argv[1])
if log_path.is_file():
    content = log_path.read_text(encoding="utf-8", errors="replace")
    redacted = re.sub(
        r"(--admin-password(?:=|\s+))\S+",
        r"\1<redacted>",
        content,
    )
    if redacted != content:
        log_path.write_text(redacted, encoding="utf-8")
PY
}

trap redact_bench_log EXIT

read_lock_value() {
  local app_name="$1"
  local field_name="$2"
  python - "${LOCK_FILE}" "${app_name}" "${field_name}" <<'PY'
import json
import pathlib
import sys

lock_path = pathlib.Path(sys.argv[1])
app_name = sys.argv[2]
field_name = sys.argv[3]
try:
    lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
    value = lock_data[app_name][field_name]
except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
    raise SystemExit(f"无法读取上游锁 {app_name}.{field_name}: {error}")
if not isinstance(value, str) or not value:
    raise SystemExit(f"上游锁 {app_name}.{field_name} 必须是非空字符串")
print(value)
PY
}

normalize_repository() {
  local repository="$1"
  repository="${repository%.git}"
  repository="${repository%/}"
  printf '%s\n' "${repository}"
}

prepare_locked_source() {
  local app_name="$1"
  local expected_repository="$2"
  local expected_branch="$3"
  local source_path="${CACHE_ROOT}/${app_name}"
  local locked_repository
  local locked_branch
  local locked_commit
  local actual_repository

  locked_repository="$(read_lock_value "${app_name}" repository)"
  locked_branch="$(read_lock_value "${app_name}" branch)"
  locked_commit="$(read_lock_value "${app_name}" commit)"
  if [ "$(normalize_repository "${locked_repository}")" != "${expected_repository}" ]; then
    echo "上游锁中的 ${app_name}.repository 不是预期官方地址。" >&2
    exit 24
  fi
  if [ "${locked_branch}" != "${expected_branch}" ]; then
    echo "上游锁中的 ${app_name}.branch 必须为 ${expected_branch}。" >&2
    exit 25
  fi
  if ! printf '%s\n' "${locked_commit}" | grep -Eq '^[0-9a-f]{40}$'; then
    echo "上游锁中的 ${app_name}.commit 必须是 40 位小写 Git 哈希。" >&2
    exit 26
  fi

  if [ -e "${source_path}" ] && [ ! -d "${source_path}/.git" ]; then
    echo "上游缓存路径已存在但不是 Git 仓库：${source_path}" >&2
    exit 27
  fi
  if [ ! -d "${source_path}/.git" ]; then
    mkdir -p "${source_path}"
    git -C "${source_path}" init
    git -C "${source_path}" remote add origin "${expected_repository}"
  fi

  actual_repository="$(normalize_repository "$(git -C "${source_path}" remote get-url origin)")"
  if [ "${actual_repository}" != "${expected_repository}" ]; then
    echo "上游缓存 ${app_name} 的 origin 不是预期官方地址：${actual_repository}" >&2
    exit 28
  fi
  if [ -n "$(git -C "${source_path}" status --porcelain --untracked-files=no)" ]; then
    echo "上游缓存存在未提交改动，拒绝覆盖：${app_name}" >&2
    exit 29
  fi

  if ! git -C "${source_path}" cat-file -e "${locked_commit}^{commit}" 2>/dev/null; then
    if ! git -C "${source_path}" fetch --depth 1 origin "${locked_commit}"; then
      if [ "$(git -C "${source_path}" rev-parse --is-shallow-repository)" = "true" ]; then
        git -C "${source_path}" fetch --unshallow origin "${locked_branch}"
      else
        git -C "${source_path}" fetch origin "${locked_branch}"
      fi
    fi
  fi
  if ! git -C "${source_path}" cat-file -e "${locked_commit}^{commit}" 2>/dev/null; then
    echo "无法从官方仓库取得锁定提交：${app_name} ${locked_commit}" >&2
    exit 30
  fi

  git -C "${source_path}" checkout --detach "${locked_commit}"
  git -C "${source_path}" branch --force autoflow-lock "${locked_commit}"
  if [ "$(git -C "${source_path}" rev-parse HEAD)" != "${locked_commit}" ]; then
    echo "上游缓存 ${app_name} 提交校验失败。" >&2
    exit 31
  fi
}

adopt_official_origin() {
  local app_name="$1"
  local expected_repository="$2"
  local app_path="${BENCH_PATH}/apps/${app_name}"
  local source_path="${CACHE_ROOT}/${app_name}"
  local actual_repository
  local remote_name

  if git -C "${app_path}" remote get-url origin >/dev/null 2>&1; then
    remote_name="origin"
  elif git -C "${app_path}" remote get-url upstream >/dev/null 2>&1; then
    remote_name="upstream"
  else
    echo "上游应用 ${app_name} 缺少 origin 或 upstream 远程。" >&2
    exit 32
  fi

  actual_repository="$(
    normalize_repository "$(git -C "${app_path}" remote get-url "${remote_name}")"
  )"
  if [ "${actual_repository}" = "$(normalize_repository "${source_path}")" ] ||
    [ "${actual_repository}" = "$(normalize_repository "file://${source_path}")" ]; then
    git -C "${app_path}" remote set-url "${remote_name}" "${expected_repository}"
    actual_repository="${expected_repository}"
  fi
  if [ "${actual_repository}" != "${expected_repository}" ]; then
    echo "上游应用 ${app_name} 的 origin 不是预期官方地址：${actual_repository}" >&2
    exit 32
  fi
  if [ "${remote_name}" = "upstream" ]; then
    git -C "${app_path}" remote rename upstream origin
  fi
}

restore_generated_files_for_app() {
  local app_name="$1"
  local app_path="${BENCH_PATH}/apps/${app_name}"
  local generated_files=()

  if [ "${app_name}" = "erpnext" ]; then
    generated_files=("banking/yarn.lock")
  elif [ "${app_name}" = "crm" ]; then
    generated_files=("frontend/auto-imports.d.ts" "yarn.lock")
  fi

  for generated_file in "${generated_files[@]}"; do
    if ! git -C "${app_path}" diff --cached --quiet -- "${generated_file}"; then
      echo "生成文件存在已暂存改动，拒绝自动恢复：${app_name}/${generated_file}" >&2
      exit 33
    fi
    if ! git -C "${app_path}" diff --quiet -- "${generated_file}"; then
      git -C "${app_path}" restore --worktree -- "${generated_file}"
    fi
  done
}

pin_upstream_app() {
  local app_name="$1"
  local expected_repository="$2"
  local expected_branch="$3"
  local app_path="${BENCH_PATH}/apps/${app_name}"
  local locked_repository
  local locked_branch
  local locked_commit
  local actual_repository
  local current_commit

  locked_repository="$(read_lock_value "${app_name}" repository)"
  locked_branch="$(read_lock_value "${app_name}" branch)"
  locked_commit="$(read_lock_value "${app_name}" commit)"

  if [ "$(normalize_repository "${locked_repository}")" != "${expected_repository}" ]; then
    echo "上游锁中的 ${app_name}.repository 不是预期官方地址。" >&2
    exit 34
  fi
  if [ "${locked_branch}" != "${expected_branch}" ]; then
    echo "上游锁中的 ${app_name}.branch 必须为 ${expected_branch}。" >&2
    exit 35
  fi
  if ! printf '%s\n' "${locked_commit}" | grep -Eq '^[0-9a-f]{40}$'; then
    echo "上游锁中的 ${app_name}.commit 必须是 40 位小写 Git 哈希。" >&2
    exit 36
  fi
  if [ ! -d "${app_path}/.git" ]; then
    echo "上游应用不是 Git 仓库：${app_path}" >&2
    exit 37
  fi
  if [ -n "$(git -C "${app_path}" status --porcelain --untracked-files=no)" ]; then
    echo "上游应用存在未提交改动，拒绝覆盖：${app_name}" >&2
    exit 38
  fi

  actual_repository="$(normalize_repository "$(git -C "${app_path}" remote get-url origin)")"
  if [ "${actual_repository}" != "${expected_repository}" ]; then
    echo "上游应用 ${app_name} 的 origin 不是预期官方地址：${actual_repository}" >&2
    exit 39
  fi

  current_commit="$(git -C "${app_path}" rev-parse HEAD)"
  if [ "${current_commit}" != "${locked_commit}" ]; then
    if ! git -C "${app_path}" cat-file -e "${locked_commit}^{commit}" 2>/dev/null; then
      if [ "$(git -C "${app_path}" rev-parse --is-shallow-repository)" = "true" ]; then
        git -C "${app_path}" fetch --unshallow origin "${locked_branch}"
      else
        git -C "${app_path}" fetch origin "${locked_branch}"
      fi
    fi
    git -C "${app_path}" checkout --detach "${locked_commit}"
    UPSTREAM_DEPENDENCIES_CHANGED=1
  fi

  current_commit="$(git -C "${app_path}" rev-parse HEAD)"
  if [ "${current_commit}" != "${locked_commit}" ]; then
    echo "上游应用 ${app_name} 提交校验失败：期望 ${locked_commit}，实际 ${current_commit}。" >&2
    exit 40
  fi
}

cd /workspace/development
if [ -e "${BENCH_PATH}" ] && [ ! -d "${BENCH_PATH}/apps/frappe" ]; then
  echo "检测到不完整的 Frappe Bench，脚本拒绝覆盖：${BENCH_PATH}" >&2
  echo "请先保留现场并按本地开发文档的“中断恢复”处理。" >&2
  exit 20
fi
if [ ! -d "${BENCH_PATH}/apps/frappe" ]; then
  prepare_locked_source frappe "https://github.com/frappe/frappe" "version-16"
  prepare_locked_source erpnext "https://github.com/frappe/erpnext" "version-16"
  prepare_locked_source crm "https://github.com/frappe/crm" "main"
  python - "${LOCKED_APPS_JSON}" "${CACHE_ROOT}" <<'PY'
import json
import pathlib
import sys

output_path = pathlib.Path(sys.argv[1])
cache_root = pathlib.Path(sys.argv[2])
apps = [
    {"url": str(cache_root / "erpnext"), "branch": "autoflow-lock"},
    {"url": str(cache_root / "crm"), "branch": "autoflow-lock"},
]
output_path.write_text(
    json.dumps(apps, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
  python /workspace/frappe_docker/development/installer.py \
    --apps-json "${LOCKED_APPS_JSON}" \
    --bench-name frappe-bench \
    --site-name "${SITE}" \
    --frappe-repo "${CACHE_ROOT}/frappe" \
    --frappe-branch autoflow-lock \
    --py-version 3.14 \
    --node-version 24 \
    --admin-password "${INITIAL_ADMIN_PASSWORD}"
  restore_generated_files_for_app erpnext
  restore_generated_files_for_app crm
fi

if [ ! -x "${BENCH_PATH}/env/bin/python" ] ||
  [ ! -f "${BENCH_PATH}/sites/apps.txt" ] ||
  [ ! -d "${BENCH_PATH}/apps/frappe" ]; then
  echo "Frappe Bench 初始化未完成。" >&2
  exit 21
fi

cd "${BENCH_PATH}"
UPSTREAM_DEPENDENCIES_CHANGED=0
for required_app in erpnext crm; do
  if [ ! -d "${BENCH_PATH}/apps/${required_app}" ]; then
    if [ "${required_app}" = "erpnext" ]; then
      required_branch="version-16"
    else
      required_branch="main"
    fi
    prepare_locked_source "${required_app}" \
      "https://github.com/frappe/${required_app}" \
      "${required_branch}"
    bench get-app \
      --branch autoflow-lock \
      --skip-assets \
      "${CACHE_ROOT}/${required_app}"
    restore_generated_files_for_app "${required_app}"
    UPSTREAM_DEPENDENCIES_CHANGED=1
  fi
done

adopt_official_origin frappe "https://github.com/frappe/frappe"
adopt_official_origin erpnext "https://github.com/frappe/erpnext"
adopt_official_origin crm "https://github.com/frappe/crm"
pin_upstream_app frappe "https://github.com/frappe/frappe" "version-16"
pin_upstream_app erpnext "https://github.com/frappe/erpnext" "version-16"
pin_upstream_app crm "https://github.com/frappe/crm" "main"
if [ "${UPSTREAM_DEPENDENCIES_CHANGED}" -eq 1 ]; then
  bench setup requirements --python --node
  bench build
  restore_generated_files_for_app erpnext
  restore_generated_files_for_app crm
fi

if [ ! -d "${BENCH_PATH}/sites/${SITE}" ]; then
  bench set-config -g db_type mariadb
  bench set-config -g db_host mariadb
  bench set-config -g redis_cache redis://redis-cache:6379
  bench set-config -g redis_queue redis://redis-queue:6379
  bench set-config -g redis_socketio redis://redis-queue:6379
  bench set-config -gp developer_mode 1
  bench new-site \
    --db-root-username root \
    --db-host mariadb \
    --db-type mariadb \
    --mariadb-user-host-login-scope '%' \
    --db-root-password 123 \
    --admin-password "${INITIAL_ADMIN_PASSWORD}" \
    --install-app erpnext \
    --install-app crm \
    "${SITE}"
fi

installed_apps="$(bench --site "${SITE}" list-apps)"
for required_app in erpnext crm; do
  if ! printf '%s\n' "${installed_apps}" | awk '{print $1}' | grep -qx "${required_app}"; then
    echo "站点缺少上游应用：${required_app}" >&2
    exit 21
  fi
done

if [ -L apps/autoflow_360 ]; then
  if [ "$(readlink -f apps/autoflow_360)" != "/workspace/autoflow_360" ]; then
    echo "apps/autoflow_360 已链接到其他目录，拒绝覆盖。" >&2
    exit 22
  fi
elif [ -e apps/autoflow_360 ]; then
  echo "apps/autoflow_360 已存在且不是符号链接，拒绝覆盖。" >&2
  exit 23
else
  ln -s /workspace/autoflow_360 apps/autoflow_360
fi

APPS_TXT="${BENCH_PATH}/sites/apps.txt"
if [ -s "${APPS_TXT}" ] && [ "$(tail -c 1 "${APPS_TXT}" | wc -l)" -eq 0 ]; then
  printf '\n' >> "${APPS_TXT}"
fi
if ! grep -qx autoflow_360 "${APPS_TXT}"; then
  printf '%s\n' autoflow_360 >> "${APPS_TXT}"
fi

./env/bin/pip install -e apps/autoflow_360
bench --site "${SITE}" execute frappe.cache_manager.clear_global_cache
if ! bench --site "${SITE}" list-apps | awk '{print $1}' | grep -qx autoflow_360; then
  bench --site "${SITE}" install-app autoflow_360
fi
bench --site "${SITE}" migrate
bench --site "${SITE}" set-config allow_tests true
bench --site "${SITE}" execute \
  autoflow_360.development.sync_local_admin_password
bench --site "${SITE}" enable-scheduler
