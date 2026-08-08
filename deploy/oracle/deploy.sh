#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_command docker
require_command git
require_command python3
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required."
docker info >/dev/null 2>&1 || fail "Docker daemon is not available."

load_compose_env
validate_deployment_config
require_private_env_file

read_locked_commit() {
  python3 - "${PROJECT_DIR}/deploy/upstream-lock.json" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
entry = data.get("frappe_docker")
if not isinstance(entry, dict):
    raise SystemExit("frappe_docker lock entry is missing")
if entry.get("repository") != "https://github.com/frappe/frappe_docker":
    raise SystemExit("frappe_docker repository lock is not the official URL")
commit = entry.get("commit", "")
if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
    raise SystemExit("frappe_docker commit lock is invalid")
print(commit)
PY
}

locked_commit="$(read_locked_commit)"
expected_origin="https://github.com/frappe/frappe_docker"
mkdir -p "$(dirname "${RUNTIME_DIR}")"
if [ ! -d "${RUNTIME_DIR}/.git" ]; then
  [ ! -e "${RUNTIME_DIR}" ] || fail "Runtime path exists but is not a Git checkout: ${RUNTIME_DIR}"
  git clone --filter=blob:none --no-checkout "${expected_origin}" "${RUNTIME_DIR}"
fi

actual_origin="$(git -C "${RUNTIME_DIR}" remote get-url origin | sed -E 's#\.git$##; s#/$##')"
[ "${actual_origin}" = "${expected_origin}" ] || fail "Runtime origin is not the official frappe_docker repository."
[ -z "$(git -C "${RUNTIME_DIR}" status --porcelain)" ] || fail "Runtime frappe_docker checkout has local changes; refusing to overwrite it."
if ! git -C "${RUNTIME_DIR}" cat-file -e "${locked_commit}^{commit}" 2>/dev/null; then
  git -C "${RUNTIME_DIR}" fetch --depth 1 origin "${locked_commit}"
fi
git -C "${RUNTIME_DIR}" checkout --detach "${locked_commit}"
[ "$(git -C "${RUNTIME_DIR}" rev-parse HEAD)" = "${locked_commit}" ] || fail "frappe_docker lock verification failed."

source_compose=(
  docker compose
  --env-file "${ENV_FILE}"
  -f "${RUNTIME_DIR}/compose.yaml"
  -f "${RUNTIME_DIR}/overrides/compose.mariadb.yaml"
  -f "${RUNTIME_DIR}/overrides/compose.redis.yaml"
  -f "${RUNTIME_DIR}/overrides/compose.https.yaml"
  -f "${ORACLE_DIR}/compose.platform.yaml"
)

umask 077
generated_tmp="${GENERATED_COMPOSE}.tmp.$$"
trap 'rm -f -- "${generated_tmp}"' EXIT
"${source_compose[@]}" config > "${generated_tmp}"
mv -- "${generated_tmp}" "${GENERATED_COMPOSE}"
chmod 600 "${GENERATED_COMPOSE}"
trap - EXIT

prepare_compose_command
"${COMPOSE_COMMAND[@]}" pull
"${COMPOSE_COMMAND[@]}" up -d

backend_ready=0
for _ in $(seq 1 60); do
  if [ -n "$("${COMPOSE_COMMAND[@]}" ps --status running -q backend)" ]; then
    backend_ready=1
    break
  fi
  sleep 2
done
[ "${backend_ready}" -eq 1 ] || fail "Backend did not become ready within 120 seconds."

validate_site_name "${SITE_NAME}"
if ! "${COMPOSE_COMMAND[@]}" exec -T backend test -f "sites/${SITE_NAME}/site_config.json"; then
  "${COMPOSE_COMMAND[@]}" exec -T \
    -e SITE_NAME -e DB_PASSWORD -e ADMIN_PASSWORD \
    backend bash -lc '
      set -euo pipefail
      bench new-site "${SITE_NAME}" \
        --mariadb-user-host-login-scope="%" \
        --admin-password "${ADMIN_PASSWORD}" \
        --db-root-username root \
        --db-root-password "${DB_PASSWORD}" \
        --install-app erpnext \
        --install-app crm \
        --install-app autoflow_360 \
        --set-default
    '
fi

"${COMPOSE_COMMAND[@]}" exec -T -e SITE_NAME backend bash -lc '
  set -euo pipefail
  bench --site "${SITE_NAME}" migrate
  bench --site "${SITE_NAME}" enable-scheduler
  bench --site "${SITE_NAME}" list-apps
'

printf 'Deployment is running for site: %s\n' "${SITE_NAME}"
printf 'Compose state: %s\n' "${GENERATED_COMPOSE}"
"${COMPOSE_COMMAND[@]}" ps
