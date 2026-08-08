#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_command docker
require_command realpath
require_command sha256sum
load_compose_env
validate_deployment_config
require_private_env_file
prepare_compose_command

backup_root_real="$(realpath -m "${BACKUP_ROOT}")"
if [ "$#" -gt 1 ]; then
  fail "Usage: restore-check.sh [backup-directory]"
elif [ "$#" -eq 1 ]; then
  backup_dir="$(realpath -e "$1")"
else
  [ -d "${BACKUP_ROOT}" ] || fail "No backup directory exists. Run backup.sh first."
  mapfile -t backup_names < <(find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort -r)
  [ "${#backup_names[@]}" -gt 0 ] || fail "No backup set exists. Run backup.sh first."
  backup_dir="$(realpath -e "${BACKUP_ROOT}/${backup_names[0]}")"
fi
[[ "${backup_dir}" == "${backup_root_real}/"* ]] || fail "Backup directory must be inside ${BACKUP_ROOT}."
[ -f "${backup_dir}/SHA256SUMS" ] || fail "SHA256SUMS is missing from the backup set."
(
  cd "${backup_dir}"
  sha256sum -c SHA256SUMS
)

mapfile -t database_files < <(find "${backup_dir}" -maxdepth 1 -type f \( -name '*-database.sql' -o -name '*-database.sql.gz' \) -print)
mapfile -t public_files < <(find "${backup_dir}" -maxdepth 1 -type f -name '*-files.tgz' ! -name '*-private-files.tgz' -print)
mapfile -t private_files < <(find "${backup_dir}" -maxdepth 1 -type f -name '*-private-files.tgz' -print)
[ "${#database_files[@]}" -eq 1 ] || fail "Expected exactly one database backup file."
[ "${#public_files[@]}" -eq 1 ] || fail "Expected exactly one public-files archive."
[ "${#private_files[@]}" -eq 1 ] || fail "Expected exactly one private-files archive."

restore_site="restore-check-$(date -u +%Y%m%d%H%M%S)-$$.localhost"
validate_site_name "${restore_site}"
remote_backup_dir="$("${COMPOSE_COMMAND[@]}" exec -T backend mktemp -d /tmp/autoflow-restore.XXXXXXXX | tr -d '\r' | tail -n 1)"
remote_archive_dir="$("${COMPOSE_COMMAND[@]}" exec -T backend mktemp -d /tmp/autoflow-archive.XXXXXXXX | tr -d '\r' | tail -n 1)"
[[ "${remote_backup_dir}" =~ ^/tmp/autoflow-restore\.[A-Za-z0-9]+$ ]] || fail "Unexpected remote restore directory."
[[ "${remote_archive_dir}" =~ ^/tmp/autoflow-archive\.[A-Za-z0-9]+$ ]] || fail "Unexpected remote archive directory."
site_created=0

cleanup() {
  set +e
  if [ "${site_created}" -eq 1 ]; then
    "${COMPOSE_COMMAND[@]}" exec -T \
      -e RESTORE_SITE="${restore_site}" -e DB_PASSWORD -e REMOTE_ARCHIVE_DIR="${remote_archive_dir}" \
      backend bash -lc '
        bench drop-site "${RESTORE_SITE}" \
          --db-root-username root \
          --db-root-password "${DB_PASSWORD}" \
          --no-backup \
          --archived-sites-path "${REMOTE_ARCHIVE_DIR}"
      ' >/dev/null 2>&1
  fi
  if [[ "${remote_backup_dir:-}" =~ ^/tmp/autoflow-restore\.[A-Za-z0-9]+$ ]]; then
    "${COMPOSE_COMMAND[@]}" exec -T backend rm -rf -- "${remote_backup_dir}" >/dev/null 2>&1
  fi
  if [[ "${remote_archive_dir:-}" =~ ^/tmp/autoflow-archive\.[A-Za-z0-9]+$ ]]; then
    "${COMPOSE_COMMAND[@]}" exec -T backend rm -rf -- "${remote_archive_dir}" >/dev/null 2>&1
  fi
}
trap cleanup EXIT

"${COMPOSE_COMMAND[@]}" cp "${backup_dir}/." "backend:${remote_backup_dir}/"
remote_database="${remote_backup_dir}/$(basename "${database_files[0]}")"
remote_public="${remote_backup_dir}/$(basename "${public_files[0]}")"
remote_private="${remote_backup_dir}/$(basename "${private_files[0]}")"

"${COMPOSE_COMMAND[@]}" exec -T \
  -e RESTORE_SITE="${restore_site}" -e DB_PASSWORD -e ADMIN_PASSWORD \
  backend bash -lc '
    set -euo pipefail
    bench new-site "${RESTORE_SITE}" \
      --mariadb-user-host-login-scope="%" \
      --admin-password "${ADMIN_PASSWORD}" \
      --db-root-username root \
      --db-root-password "${DB_PASSWORD}"
  '
site_created=1

"${COMPOSE_COMMAND[@]}" exec -T \
  -e RESTORE_SITE="${restore_site}" -e DB_PASSWORD \
  -e REMOTE_DATABASE="${remote_database}" -e REMOTE_PUBLIC="${remote_public}" -e REMOTE_PRIVATE="${remote_private}" \
  backend bash -lc '
    set -euo pipefail
    bench --site "${RESTORE_SITE}" restore "${REMOTE_DATABASE}" \
      --db-root-username root \
      --db-root-password "${DB_PASSWORD}" \
      --with-public-files "${REMOTE_PUBLIC}" \
      --with-private-files "${REMOTE_PRIVATE}"
    bench --site "${RESTORE_SITE}" migrate
    bench --site "${RESTORE_SITE}" list-apps
    bench --site "${RESTORE_SITE}" execute frappe.db.exists --args "[\"DocType\", \"Customer Project\"]"
  '

printf 'Restore test site: %s\n' "${restore_site}"
printf 'RESTORE_CHECK_PASSED\n'
