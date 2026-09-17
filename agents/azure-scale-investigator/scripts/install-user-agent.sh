#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${script_dir}/../../.." && pwd)"
source_profile="${repository_root}/.github/agents/azure-scale-investigator.agent.md"
source_runner="${script_dir}/run-assessment.sh"
target_directory="${HOME}/.copilot/agents"
target_profile="${target_directory}/azure-scale-investigator.agent.md"
target_bin_directory="${HOME}/.local/bin"
target_runner="${target_bin_directory}/will-it-scale-azure"

if [[ ! -f "${source_profile}" ]]; then
  echo "Agent profile not found: ${source_profile}" >&2
  exit 1
fi

if [[ ! -f "${source_runner}" ]]; then
  echo "Assessment runner not found: ${source_runner}" >&2
  exit 1
fi

if [[ "${1:-}" == "--dry-run" ]]; then
  if [[ $# -ne 1 ]]; then
    echo "Usage: install-user-agent.sh [--dry-run]" >&2
    exit 2
  fi
  echo "Would install:"
  echo "  ${source_profile}"
  echo "  ${source_runner}"
  echo "to:"
  echo "  ${target_profile}"
  echo "  ${target_runner}"
  exit 0
fi

if [[ $# -ne 0 ]]; then
  echo "Usage: install-user-agent.sh [--dry-run]" >&2
  exit 2
fi

for required_command in chmod cmp cp date install mkdir mktemp; do
  if ! command -v "${required_command}" >/dev/null 2>&1; then
    echo "Required command is unavailable: ${required_command}" >&2
    exit 127
  fi
done

mkdir -p "${target_directory}"
mkdir -p "${target_bin_directory}"

install_artifact() {
  local source="$1"
  local target="$2"
  local mode="$3"
  local backup
  local timestamp

  if [[ -L "${target}" ]]; then
    echo "Refusing to replace symbolic link: ${target}" >&2
    exit 1
  fi

  if [[ -f "${target}" ]] && cmp -s "${source}" "${target}"; then
    chmod "${mode}" "${target}"
    echo "Already current: ${target}"
    return
  fi

  if [[ -e "${target}" ]]; then
    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    backup="$(mktemp "${target}.backup.${timestamp}.XXXXXX")"
    cp -p "${target}" "${backup}"
    echo "Backed up existing file to ${backup}"
  fi

  install -m "${mode}" "${source}" "${target}"
}

install_artifact "${source_profile}" "${target_profile}" 0644
install_artifact "${source_runner}" "${target_runner}" 0755

echo "Installed Azure Scale Investigator:"
echo "  ${target_profile}"
echo "  ${target_runner}"
echo "Restart Copilot CLI, then run from any project:"
echo "  will-it-scale-azure ."
