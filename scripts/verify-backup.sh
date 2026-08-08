#!/usr/bin/env bash

set -euo pipefail

site_name="${1:-}"
bench_dir="/workspace/development/frappe-bench"
database_root_password="123"

if [[ ! "${site_name}" =~ ^[a-z0-9][a-z0-9.-]{1,251}[a-z0-9]$ || "${site_name}" != *.localhost ]]; then
  printf 'ERROR: invalid local development site name.\n' >&2
  exit 1
fi
[ -d "${bench_dir}" ] || { printf 'ERROR: local Bench directory is missing.\n' >&2; exit 1; }

cd "${bench_dir}"
backup_dir="$(mktemp -d /tmp/autoflow-local-backup.XXXXXXXX)"
archive_dir="$(mktemp -d /tmp/autoflow-local-archive.XXXXXXXX)"
restore_site="restore-check-$(date -u +%Y%m%d%H%M%S)-$$.localhost"
temporary_admin_password="$(python -c 'import secrets; print(secrets.token_urlsafe(36))')"
site_created=0

cleanup() {
  set +e
  if [ "${site_created}" -eq 1 ]; then
    bench drop-site "${restore_site}" \
      --db-root-password "${database_root_password}" \
      --no-backup \
      --archived-sites-path "${archive_dir}" >/dev/null 2>&1
  fi
  if [[ "${backup_dir}" =~ ^/tmp/autoflow-local-backup\.[A-Za-z0-9]+$ ]]; then
    rm -rf -- "${backup_dir}"
  fi
  if [[ "${archive_dir}" =~ ^/tmp/autoflow-local-archive\.[A-Za-z0-9]+$ ]]; then
    rm -rf -- "${archive_dir}"
  fi
}
trap cleanup EXIT

bench --site "${site_name}" backup --with-files --compress --backup-path "${backup_dir}"

mapfile -t database_files < <(find "${backup_dir}" -maxdepth 1 -type f \( -name '*-database.sql' -o -name '*-database.sql.gz' \) -print)
mapfile -t public_files < <(find "${backup_dir}" -maxdepth 1 -type f -name '*-files.tgz' ! -name '*-private-files.tgz' -print)
mapfile -t private_files < <(find "${backup_dir}" -maxdepth 1 -type f -name '*-private-files.tgz' -print)
[ "${#database_files[@]}" -eq 1 ] || { printf 'ERROR: expected one database backup.\n' >&2; exit 1; }
[ "${#public_files[@]}" -eq 1 ] || { printf 'ERROR: expected one public-files archive.\n' >&2; exit 1; }
[ "${#private_files[@]}" -eq 1 ] || { printf 'ERROR: expected one private-files archive.\n' >&2; exit 1; }

(
  cd "${backup_dir}"
  find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum -c SHA256SUMS
)

bench new-site "${restore_site}" \
  --mariadb-user-host-login-scope="%" \
  --admin-password "${temporary_admin_password}" \
  --db-root-password "${database_root_password}"
site_created=1

bench --site "${restore_site}" restore "${database_files[0]}" \
  --db-root-password "${database_root_password}" \
  --with-public-files "${public_files[0]}" \
  --with-private-files "${private_files[0]}"
bench --site "${restore_site}" migrate
bench --site "${restore_site}" list-apps
bench --site "${restore_site}" execute frappe.db.exists --args '["DocType", "Customer Project"]'

printf 'Restore test site: %s\n' "${restore_site}"
printf 'RESTORE_CHECK_PASSED\n'
