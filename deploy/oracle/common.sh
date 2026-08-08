#!/usr/bin/env bash

set -euo pipefail

ORACLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${ORACLE_DIR}/../.." && pwd)"
ENV_FILE="${AUTOFLOW_COMPOSE_ENV:-${ORACLE_DIR}/compose.env}"
RUNTIME_DIR="${AUTOFLOW_FRAPPE_DOCKER:-${PROJECT_DIR}/.runtime/frappe_docker-production}"
GENERATED_COMPOSE="${ORACLE_DIR}/compose.generated.yaml"
BACKUP_ROOT="${ORACLE_DIR}/backups"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command is missing: $1"
}

load_compose_env() {
  [ -f "${ENV_FILE}" ] || fail "Missing ${ENV_FILE}. Copy compose.env.example and replace placeholders."

  local raw_line key value
  declare -A seen_keys=()
  while IFS= read -r raw_line || [ -n "${raw_line}" ]; do
    raw_line="${raw_line%$'\r'}"
    if [[ -z "${raw_line}" || "${raw_line}" =~ ^[[:space:]]*# ]]; then
      continue
    fi
    if [[ ! "${raw_line}" =~ ^([A-Z][A-Z0-9_]*)=(.*)$ ]]; then
      fail "Invalid compose.env line. Use unquoted KEY=value entries only."
    fi
    key="${BASH_REMATCH[1]}"
    value="${BASH_REMATCH[2]}"
    case "${key}" in
      CUSTOM_IMAGE|CUSTOM_TAG|PULL_POLICY|AUTOFLOW_PLATFORM|DB_PASSWORD|ADMIN_PASSWORD|SITE_NAME|FRAPPE_SITE_NAME_HEADER|LETSENCRYPT_EMAIL|SITES_RULE|HTTP_PUBLISH_PORT|HTTPS_PUBLISH_PORT|GUNICORN_THREADS|GUNICORN_WORKERS|GUNICORN_TIMEOUT|CLIENT_MAX_BODY_SIZE|RESTART_POLICY)
        ;;
      *)
        fail "Unsupported compose.env key: ${key}"
        ;;
    esac
    [ -z "${seen_keys[${key}]+x}" ] || fail "Duplicate compose.env key: ${key}"
    seen_keys["${key}"]=1
    printf -v "${key}" '%s' "${value}"
    export "${key}"
  done < "${ENV_FILE}"
}

require_value() {
  local key="$1"
  local value="${!key-}"
  [ -n "${value}" ] || fail "compose.env value is required: ${key}"
  [[ "${value}" != *CHANGE_ME* ]] || fail "Replace the placeholder for ${key}."
}

validate_deployment_config() {
  local key expected_rule
  for key in CUSTOM_IMAGE CUSTOM_TAG DB_PASSWORD ADMIN_PASSWORD SITE_NAME FRAPPE_SITE_NAME_HEADER LETSENCRYPT_EMAIL SITES_RULE; do
    require_value "${key}"
  done

  [[ "${CUSTOM_IMAGE}" =~ ^[a-z0-9.-]+(/[a-z0-9._-]+)+$ ]] || fail "CUSTOM_IMAGE must be a lowercase registry image name."
  [[ "${CUSTOM_TAG}" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]] || fail "CUSTOM_TAG is invalid."
  [[ "${SITE_NAME}" =~ ^[a-z0-9][a-z0-9.-]{1,251}[a-z0-9]$ && "${SITE_NAME}" == *.* ]] || fail "SITE_NAME must be a lowercase DNS name."
  [ "${FRAPPE_SITE_NAME_HEADER}" = "${SITE_NAME}" ] || fail "FRAPPE_SITE_NAME_HEADER must equal SITE_NAME for this single-site deployment."
  [[ "${LETSENCRYPT_EMAIL}" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]] || fail "LETSENCRYPT_EMAIL is invalid."
  expected_rule="$(printf 'Host(`%s`)' "${SITE_NAME}")"
  [ "${SITES_RULE}" = "${expected_rule}" ] || fail "SITES_RULE must be Host(\`${SITE_NAME}\`)."
  [ "${#DB_PASSWORD}" -ge 20 ] || fail "DB_PASSWORD must contain at least 20 characters."
  [ "${#ADMIN_PASSWORD}" -ge 20 ] || fail "ADMIN_PASSWORD must contain at least 20 characters."
  [ "${DB_PASSWORD}" != "${ADMIN_PASSWORD}" ] || fail "Database and administrator passwords must be different."
  [[ "${AUTOFLOW_PLATFORM:-linux/arm64}" =~ ^linux/(arm64|amd64)$ ]] || fail "AUTOFLOW_PLATFORM must be linux/arm64 or linux/amd64."
  [[ "${HTTP_PUBLISH_PORT:-80}" =~ ^[0-9]{1,5}$ ]] || fail "HTTP_PUBLISH_PORT is invalid."
  [[ "${HTTPS_PUBLISH_PORT:-443}" =~ ^[0-9]{1,5}$ ]] || fail "HTTPS_PUBLISH_PORT is invalid."
  [[ "${GUNICORN_THREADS:-2}" =~ ^[1-9][0-9]*$ ]] || fail "GUNICORN_THREADS must be positive."
  [[ "${GUNICORN_WORKERS:-2}" =~ ^[1-9][0-9]*$ ]] || fail "GUNICORN_WORKERS must be positive."
  [[ "${GUNICORN_TIMEOUT:-120}" =~ ^[1-9][0-9]*$ ]] || fail "GUNICORN_TIMEOUT must be positive."
}

require_private_env_file() {
  local mode mode_value
  mode="$(stat -c '%a' "${ENV_FILE}")"
  [[ "${mode}" =~ ^[0-7]{3,4}$ ]] || fail "Unable to validate compose.env permissions."
  mode_value=$((8#${mode}))
  (( (mode_value & 8#077) == 0 )) || fail "compose.env must not be readable or writable by group/others. Run: chmod 600 ${ENV_FILE}"
}

prepare_compose_command() {
  [ -d "${RUNTIME_DIR}" ] || fail "Missing locked frappe_docker checkout: ${RUNTIME_DIR}"
  [ -f "${GENERATED_COMPOSE}" ] || fail "Missing generated Compose file. Run deploy.sh first."
  COMPOSE_COMMAND=(docker compose --env-file "${ENV_FILE}" -f "${GENERATED_COMPOSE}")
}

validate_site_name() {
  [[ "$1" =~ ^[a-z0-9][a-z0-9.-]{1,251}[a-z0-9]$ && "$1" == *.* ]] || fail "Invalid site name: $1"
}
