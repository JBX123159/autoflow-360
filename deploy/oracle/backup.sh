#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_command docker
require_command sha256sum
load_compose_env
validate_deployment_config
require_private_env_file
prepare_compose_command
validate_site_name "${SITE_NAME}"

umask 077
mkdir -p "${BACKUP_ROOT}"
backup_id="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="${BACKUP_ROOT}/${backup_id}"
[ ! -e "${backup_dir}" ] || fail "Backup directory already exists: ${backup_dir}"
mkdir "${backup_dir}"

remote_backup_dir="$("${COMPOSE_COMMAND[@]}" exec -T backend mktemp -d /tmp/autoflow-backup.XXXXXXXX | tr -d '\r' | tail -n 1)"
[[ "${remote_backup_dir}" =~ ^/tmp/autoflow-backup\.[A-Za-z0-9]+$ ]] || fail "Unexpected remote backup directory."

cleanup_remote_backup() {
  if [[ "${remote_backup_dir:-}" =~ ^/tmp/autoflow-backup\.[A-Za-z0-9]+$ ]]; then
    "${COMPOSE_COMMAND[@]}" exec -T backend rm -rf -- "${remote_backup_dir}" >/dev/null 2>&1 || true
  fi
}
trap cleanup_remote_backup EXIT

"${COMPOSE_COMMAND[@]}" exec -T -e SITE_NAME -e REMOTE_BACKUP_DIR="${remote_backup_dir}" backend bash -lc '
  set -euo pipefail
  bench --site "${SITE_NAME}" backup --with-files --compress --backup-path "${REMOTE_BACKUP_DIR}"
'
"${COMPOSE_COMMAND[@]}" cp "backend:${remote_backup_dir}/." "${backup_dir}/"

mapfile -t database_files < <(find "${backup_dir}" -maxdepth 1 -type f \( -name '*-database.sql' -o -name '*-database.sql.gz' \) -print)
mapfile -t public_files < <(find "${backup_dir}" -maxdepth 1 -type f -name '*-files.tgz' ! -name '*-private-files.tgz' -print)
mapfile -t private_files < <(find "${backup_dir}" -maxdepth 1 -type f -name '*-private-files.tgz' -print)
[ "${#database_files[@]}" -eq 1 ] || fail "Expected exactly one database backup file."
[ "${#public_files[@]}" -eq 1 ] || fail "Expected exactly one public-files archive."
[ "${#private_files[@]}" -eq 1 ] || fail "Expected exactly one private-files archive."

(
  cd "${backup_dir}"
  find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum -c SHA256SUMS
)
chmod 600 "${backup_dir}"/*

printf 'Backup created: %s\n' "${backup_dir}"
printf 'SHA-256 manifest: %s\n' "${backup_dir}/SHA256SUMS"
