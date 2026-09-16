#!/usr/bin/env bash
set -euo pipefail

verbose=false
progress_interval="${WILL_IT_SCALE_PROGRESS_INTERVAL:-1}"
idle_timeout="${WILL_IT_SCALE_IDLE_TIMEOUT_SECONDS:-300}"
max_runtime="${WILL_IT_SCALE_MAX_RUNTIME_SECONDS:-1800}"

usage() {
  cat <<'EOF'
Usage: will-it-scale-azure [options] [project-directory] [prompt]

Options:
  -v, --verbose          Show the completed assessment and diagnostics.
  --idle-timeout SEC     Fail after no Copilot I/O (default: 300).
  --max-runtime SEC      Fail after total runtime (default: 1800).
  -h, --help             Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -v | --verbose)
      verbose=true
      shift
      ;;
    --idle-timeout)
      if [[ $# -lt 2 ]]; then
        echo "--idle-timeout requires a value in seconds." >&2
        exit 2
      fi
      idle_timeout="$2"
      shift 2
      ;;
    --max-runtime)
      if [[ $# -lt 2 ]]; then
        echo "--max-runtime requires a value in seconds." >&2
        exit 2
      fi
      max_runtime="$2"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      break
      ;;
  esac
done

for timeout_value in "${idle_timeout}" "${max_runtime}"; do
  if [[ ! "${timeout_value}" =~ ^[1-9][0-9]*$ ]]; then
    echo "Timeout values must be positive whole seconds." >&2
    exit 2
  fi
done

if ! awk -v value="${progress_interval}" \
  'BEGIN { exit !(value ~ /^[0-9]+([.][0-9]+)?$/ && value > 0) }'; then
  echo "WILL_IT_SCALE_PROGRESS_INTERVAL must be a positive number." >&2
  exit 2
fi

for required_command in \
  awk cat copilot cut date grep mkdir mktemp mv rm setsid sleep tee; do
  if ! command -v "${required_command}" >/dev/null 2>&1; then
    echo "Required command is unavailable: ${required_command}" >&2
    exit 127
  fi
done

project_directory="${1:-${PWD}}"
if [[ $# -gt 0 ]]; then
  shift
fi

if [[ ! -d "${project_directory}" ]]; then
  echo "Project directory does not exist: ${project_directory}" >&2
  exit 1
fi

project_directory="$(cd "${project_directory}" && pwd)"
prompt="${*:-Will it scale?}"
report_directory="${project_directory}/reports/willitscale"
timestamp="$(date -u +%Y%m%d_%H%M%S)"
generated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
details_file=""
copilot_pid=""
progress_pid=""
watchdog_file=""
report_finalized=false
exit_reason=""

mkdir -p "${report_directory}"
report_file="$(
  mktemp \
    --suffix=.md \
    "${report_directory}/willitscale_results_${timestamp}_XXXXXX"
)"
details_file="$(mktemp "${report_directory}/.willitscale_details_XXXXXX")"
watchdog_file="$(mktemp "${report_directory}/.willitscale_watchdog_XXXXXX")"

cleanup() {
  if [[ -n "${progress_pid}" ]]; then
    kill "${progress_pid}" 2>/dev/null || true
  fi
  if [[ -n "${copilot_pid}" ]]; then
    terminate_process_group "${copilot_pid}"
  fi
  if [[ -n "${details_file}" ]]; then
    rm -f "${details_file}"
  fi
  if [[ -n "${watchdog_file}" ]]; then
    rm -f "${watchdog_file}"
  fi
}

terminate_process_group() {
  local process_group_leader="$1"
  local attempt

  kill -TERM -- "-${process_group_leader}" 2>/dev/null || true
  for ((attempt = 0; attempt < 20; attempt += 1)); do
    if ! kill -0 -- "-${process_group_leader}" 2>/dev/null; then
      return
    fi
    sleep 0.1
  done
  kill -KILL -- "-${process_group_leader}" 2>/dev/null || true
}

handle_signal() {
  local signal_name="$1"
  local exit_status="$2"

  exit_reason="Assessment interrupted by ${signal_name}."
  exit "${exit_status}"
}

estimated_percent() {
  local elapsed="$1"

  if ((elapsed < 15)); then
    printf '%d' "$((elapsed * 20 / 15))"
  elif ((elapsed < 60)); then
    printf '%d' "$((20 + (elapsed - 15) * 25 / 45))"
  elif ((elapsed < 180)); then
    printf '%d' "$((45 + (elapsed - 60) * 25 / 120))"
  elif ((elapsed < 480)); then
    printf '%d' "$((70 + (elapsed - 180) * 20 / 300))"
  else
    printf '95'
  fi
}

render_status() {
  local percent="$1"
  local state="$2"
  local message

  message="Will It Scale assessment: ${percent}% ${state}"
  if [[ -t 2 ]]; then
    printf '\r\033[K%s' "${message}" >&2
  else
    printf '%s\n' "${message}" >&2
  fi
}

progress_loop() {
  trap - EXIT INT TERM

  local monitored_pid="$1"
  local started_at="$SECONDS"
  local last_activity_at="$SECONDS"
  local last_activity
  local current_activity
  local elapsed
  local idle_for
  local percent
  local activity_supported=true

  if last_activity="$(
      awk '/^(rchar|wchar):/ {total += $2} END {print total + 0}' \
        "/proc/${monitored_pid}/io" 2>/dev/null
    )"; then
    :
  else
    activity_supported=false
    last_activity=0
  fi

  while kill -0 "${monitored_pid}" 2>/dev/null; do
    sleep "${progress_interval}"
    if ! kill -0 "${monitored_pid}" 2>/dev/null; then
      break
    fi
    elapsed="$((SECONDS - started_at))"
    if [[ "${activity_supported}" == true ]]; then
      if current_activity="$(
          awk '/^(rchar|wchar):/ {total += $2} END {print total + 0}' \
            "/proc/${monitored_pid}/io" 2>/dev/null
        )"; then
        if [[ "${current_activity}" != "${last_activity}" ]]; then
          last_activity="${current_activity}"
          last_activity_at="$SECONDS"
        fi
      else
        activity_supported=false
      fi
    fi
    idle_for="$((SECONDS - last_activity_at))"

    if ((elapsed >= max_runtime)); then
      printf 'Maximum runtime of %s seconds was exceeded.' \
        "${max_runtime}" >"${watchdog_file}"
      render_status "$(estimated_percent "${elapsed}")" "stopping (time limit)"
      terminate_process_group "${monitored_pid}"
      return
    fi

    if [[ "${activity_supported}" == true ]] &&
      ((idle_for >= idle_timeout)); then
      printf 'No Copilot I/O was observed for %s seconds.' \
        "${idle_timeout}" >"${watchdog_file}"
      render_status "$(estimated_percent "${elapsed}")" "stopping (idle timeout)"
      terminate_process_group "${monitored_pid}"
      return
    fi

    percent="$(estimated_percent "${elapsed}")"
    render_status "${percent}" "complete (estimated)"
  done
}

finalize_failure() {
  local status="$1"
  local elapsed
  local failed_file
  local failure_reason
  local partial_output

  report_finalized=true
  elapsed="$((SECONDS - assessment_started_at))"
  render_status "$(estimated_percent "${elapsed}")" "failed"
  [[ -t 2 ]] && printf '\n' >&2
  if [[ -s "${watchdog_file}" ]]; then
    failure_reason="$(cat "${watchdog_file}")"
  else
    failure_reason="Copilot exited with status ${status}."
  fi
  failed_file="${report_file%.md}_failed.md"
  mv "${report_file}" "${failed_file}"
  partial_output="$(mktemp "${report_directory}/.partial_XXXXXX")"
  {
    printf '# Assessment did not complete\n\n'
    printf '> %s ' "${failure_reason}"
    printf 'The content below is partial output and not a completed assessment.\n\n'
    cat "${failed_file}"
  } >"${partial_output}"
  mv "${partial_output}" "${failed_file}"
  if [[ "${verbose}" == true ]]; then
    cat "${failed_file}"
  elif [[ -s "${details_file}" ]]; then
    printf 'Rerun with --verbose to display Copilot diagnostics.\n' >&2
  fi
  printf 'Assessment failed; partial output written to: %s\n' \
    "${failed_file}" >&2
}

on_exit() {
  local status=$?

  trap - EXIT INT TERM
  set +e

  if [[ -n "${progress_pid}" ]]; then
    kill "${progress_pid}" 2>/dev/null
    wait "${progress_pid}" 2>/dev/null
    progress_pid=""
  fi
  if [[ -n "${copilot_pid}" ]]; then
    terminate_process_group "${copilot_pid}"
    copilot_pid=""
  fi

  if [[ "${status}" -ne 0 ]] &&
    [[ "${report_finalized}" != true ]] &&
    [[ -f "${report_file}" ]]; then
    if [[ -n "${exit_reason}" ]]; then
      printf '%s' "${exit_reason}" >"${watchdog_file}"
    fi
    finalize_failure "${status}"
  fi

  cleanup
  exit "${status}"
}

validate_report() {
  local first_content_line
  local heading
  local heading_line
  local previous_line=0
  local required_headings=(
    "## TL;DR"
    "## Application and deployment understanding"
    "## Azure scope"
    "## Resource inventory"
    "## Relevant resource findings"
    "## Bottleneck chains"
    "## Excluded resources"
    "## Unknowns and missing evidence"
    "## Tool execution notes"
    "## Prioritized findings"
    "## Actions and recommendations"
  )

  first_content_line="$(awk 'NF { print; exit }' "${report_file}")"
  if [[ "${first_content_line}" != "# Will It Scale? Azure Assessment" ]]; then
    return 1
  fi

  for heading in "${required_headings[@]}"; do
    heading_line="$(
      grep -n -F -x -m 1 "${heading}" "${report_file}" |
        cut -d: -f1
    )"
    if [[ -z "${heading_line}" ]] || ((heading_line <= previous_line)); then
      return 1
    fi
    previous_line="${heading_line}"
  done
}

assessment_prompt="${prompt}

Report generation context:
- Generated at: ${generated_at}
- Project path: ${project_directory}
- Return only the final Markdown assessment.
- Follow the required report section order, beginning with the title and TL;DR.
- End with Actions and recommendations.
"

assessment_started_at="$SECONDS"
trap on_exit EXIT
trap 'handle_signal SIGINT 130' INT
trap 'handle_signal SIGTERM 143' TERM
render_status 0 "complete (estimated)"

if [[ "${verbose}" == true ]]; then
  setsid copilot \
      -C "${project_directory}" \
      --agent azure-scale-investigator \
      --allow-all-tools \
      --no-ask-user \
      --no-custom-instructions \
      --no-color \
      --silent \
      --stream off \
      --prompt "${assessment_prompt}" \
      >"${report_file}" \
      2> >(tee "${details_file}" >&2) &
else
  setsid copilot \
      -C "${project_directory}" \
      --agent azure-scale-investigator \
      --allow-all-tools \
      --no-ask-user \
      --no-custom-instructions \
      --no-color \
      --silent \
      --stream off \
      --prompt "${assessment_prompt}" \
      >"${report_file}" \
      2>"${details_file}" &
fi

copilot_pid="$!"
progress_loop "${copilot_pid}" &
progress_pid="$!"

if wait "${copilot_pid}"; then
  status=0
else
  status=$?
fi
copilot_pid=""

kill "${progress_pid}" 2>/dev/null || true
wait "${progress_pid}" 2>/dev/null || true
progress_pid=""

if [[ "${status}" -eq 0 ]] && ! validate_report; then
  status=65
  printf '%s' \
    'Copilot exited successfully but did not return the required report format.' \
    >"${watchdog_file}"
fi

if [[ "${status}" -eq 0 ]]; then
  report_finalized=true
  render_status 100 "complete"
  [[ -t 2 ]] && printf '\n' >&2
  if [[ "${verbose}" == true ]]; then
    cat "${report_file}"
  fi
  printf 'Report written to: %s\n' "${report_file}" >&2
else
  finalize_failure "${status}"
  exit "${status}"
fi
