"""Validate report persistence without invoking Copilot or Azure."""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RUNNER = (
    REPOSITORY_ROOT
    / "agents"
    / "azure-scale-investigator"
    / "scripts"
    / "run-assessment.sh"
)

FAKE_REPORT = """# Will It Scale? Azure Assessment

## TL;DR

The test assessment completed.

## Application and deployment understanding

Test application.

## Azure scope

Test scope.

## Resource inventory

Test inventory.

## Relevant resource findings

Test findings.

## Bottleneck chains

Test chain.

## Excluded resources

None.

## Unknowns and missing evidence

None.

## Tool execution notes

None.

## Prioritized findings

None.

## Actions and recommendations

| Priority | Recommendation | Finding or evidence | Why this should help | Expected scale benefit | Confidence | Confidence rationale |
|---|---|---|---|---|---|---|
| 1 | Measure throughput | Missing load evidence | Establishes a baseline | Better capacity planning | High | Direct measurement |
"""


def main() -> None:
    """Run the launcher twice and verify collision-safe Markdown reports."""

    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary = Path(temporary_directory)
        project = temporary / "project"
        fake_bin = temporary / "bin"
        project.mkdir()
        fake_bin.mkdir()

        fake_copilot = fake_bin / "copilot"
        fake_copilot.write_text(
            "#!/usr/bin/env bash\n"
            "sleep \"${FAKE_COPILOT_DELAY:-0}\"\n"
            "printf '%s' \"$FAKE_COPILOT_REPORT\"\n"
            "printf '%s' \"$FAKE_COPILOT_DETAILS\" >&2\n"
            "printf '%s\\n' \"$@\" > \"$FAKE_COPILOT_ARGS\"\n",
            encoding="utf-8",
        )
        fake_copilot.chmod(0o755)

        args_file = temporary / "copilot-args.txt"
        environment = os.environ.copy()
        environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
        environment["FAKE_COPILOT_REPORT"] = FAKE_REPORT
        environment["FAKE_COPILOT_DETAILS"] = "tool details must be hidden"
        environment["FAKE_COPILOT_ARGS"] = str(args_file)
        environment["FAKE_COPILOT_DELAY"] = "0.1"
        environment["WILL_IT_SCALE_PROGRESS_INTERVAL"] = "0.02"

        default_runs = []
        for _ in range(2):
            default_runs.append(
                subprocess.run(
                    [str(RUNNER), str(project)],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=environment,
                )
            )

        for run in default_runs:
            if run.stdout:
                raise AssertionError("Default mode exposed assessment details.")
            if "tool details must be hidden" in run.stderr:
                raise AssertionError("Default mode exposed Copilot diagnostics.")
            for status_text in ("0% complete", "100% complete"):
                if status_text not in run.stderr:
                    raise AssertionError(
                        f"Default mode did not display {status_text}."
                    )

        report_directory = project / "reports" / "willitscale"
        reports = sorted(report_directory.glob("willitscale_results_*.md"))
        if len(reports) != 2:
            raise AssertionError(f"Expected two unique reports, found {reports}")
        if reports[0].name == reports[1].name:
            raise AssertionError("Report filenames are not unique.")
        for report in reports:
            if report.read_text(encoding="utf-8") != FAKE_REPORT:
                raise AssertionError(f"Unexpected report content: {report}")

        arguments = args_file.read_text(encoding="utf-8")
        for required_argument in (
            "--allow-all-tools",
            "--no-ask-user",
            "--no-custom-instructions",
            "--no-auto-update",
            "--disable-builtin-mcps",
            "--disable-mcp-server",
            "workiq",
            "workiq-preview",
            "--no-color",
            "--silent",
            "--stream",
            "off",
            "--output-format",
            "json",
        ):
            if required_argument not in arguments:
                raise AssertionError(
                    f"Runner did not pass {required_argument}."
                )

        verbose_run = subprocess.run(
            [str(RUNNER), "--verbose", str(project)],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        if verbose_run.stdout != FAKE_REPORT:
            raise AssertionError("Verbose mode did not display the assessment.")
        if "tool details must be hidden" not in verbose_run.stderr:
            raise AssertionError("Verbose mode did not display diagnostics.")
        if "100% complete" not in verbose_run.stderr:
            raise AssertionError("Verbose mode did not display completion.")

        failed_environment = environment.copy()
        failed_environment["FAKE_COPILOT_EXIT"] = "17"
        fake_copilot.write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s' \"$FAKE_COPILOT_REPORT\"\n"
            "printf '%s' \"$FAKE_COPILOT_DETAILS\" >&2\n"
            "exit \"${FAKE_COPILOT_EXIT:-0}\"\n",
            encoding="utf-8",
        )
        failed_run = subprocess.run(
            [str(RUNNER), str(project)],
            check=False,
            capture_output=True,
            text=True,
            env=failed_environment,
        )
        if failed_run.returncode != 17:
            raise AssertionError(
                f"Expected failed run status 17, got {failed_run.returncode}."
            )
        failed_reports = list(
            report_directory.glob("willitscale_results_*_failed.md")
        )
        if len(failed_reports) != 1:
            raise AssertionError(
                f"Expected one marked failed report, found {failed_reports}"
            )
        failed_content = failed_reports[0].read_text(encoding="utf-8")
        if not failed_content.startswith("# Assessment did not complete"):
            raise AssertionError("Failed report has no partial-output warning.")
        if FAKE_REPORT not in failed_content:
            raise AssertionError("Failed report did not preserve partial output.")
        if "tool details must be hidden" in failed_content:
            raise AssertionError("Failed report persisted raw diagnostics.")
        if "Rerun with --verbose" not in failed_run.stderr:
            raise AssertionError("Failure did not explain how to see diagnostics.")

        retry_project = temporary / "retry-project"
        retry_project.mkdir()
        retry_counter = temporary / "retry-counter"
        fake_copilot.write_text(
            "#!/usr/bin/env bash\n"
            "count=0\n"
            "if [[ -f \"$FAKE_RETRY_COUNTER\" ]]; then\n"
            "  count=$(cat \"$FAKE_RETRY_COUNTER\")\n"
            "fi\n"
            "count=$((count + 1))\n"
            "printf '%s' \"$count\" > \"$FAKE_RETRY_COUNTER\"\n"
            "printf '%s\\n' \"$@\" > \"$FAKE_COPILOT_ARGS\"\n"
            "if [[ \"$count\" -eq 1 ]]; then\n"
            "  exit 0\n"
            "fi\n"
            "printf '%s' \"$FAKE_COPILOT_REPORT\"\n",
            encoding="utf-8",
        )
        retry_environment = environment.copy()
        retry_environment["FAKE_RETRY_COUNTER"] = str(retry_counter)
        retry_run = subprocess.run(
            [str(RUNNER), str(retry_project)],
            check=True,
            capture_output=True,
            text=True,
            env=retry_environment,
        )
        if retry_counter.read_text(encoding="utf-8") != "2":
            raise AssertionError("Transient failure was not retried exactly once.")
        if "retrying (attempt 2 of 2)" not in retry_run.stderr:
            raise AssertionError("Automatic retry was not visible.")
        retry_reports = list(
            (retry_project / "reports" / "willitscale").glob(
                "willitscale_results_*.md"
            )
        )
        if len(retry_reports) != 1:
            raise AssertionError("Successful retry did not produce one report.")
        if retry_reports[0].read_text(encoding="utf-8") != FAKE_REPORT:
            raise AssertionError("Successful retry report is incorrect.")
        retry_arguments = args_file.read_text(encoding="utf-8")
        for recovery_instruction in (
            "Recovery attempt:",
            "Do not invoke hierarchical Azure MCP namespace tools",
            "A useful degraded report is required",
        ):
            if recovery_instruction not in retry_arguments:
                raise AssertionError(
                    "Retry did not use bounded recovery instructions: "
                    f"{recovery_instruction}"
                )

        json_project = temporary / "json-output-project"
        json_project.mkdir()
        fake_copilot.write_text(
            "#!/usr/bin/env bash\n"
            "python3 - <<'PY'\n"
            "import json\n"
            "import os\n"
            "print(json.dumps({'type': 'session.tools_updated', 'data': {}}))\n"
            "print(json.dumps({\n"
            "    'type': 'assistant.message',\n"
            "    'data': {\n"
            "        'content': os.environ['FAKE_COPILOT_REPORT'],\n"
            "        'phase': 'final_answer',\n"
            "    },\n"
            "}))\n"
            "print(json.dumps({'type': 'result', 'exitCode': 0}))\n"
            "PY\n",
            encoding="utf-8",
        )
        json_run = subprocess.run(
            [str(RUNNER), str(json_project)],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        json_reports = list(
            (json_project / "reports" / "willitscale").glob(
                "willitscale_results_*.md"
            )
        )
        if len(json_reports) != 1:
            raise AssertionError("JSONL run did not produce one report.")
        if json_reports[0].read_text(encoding="utf-8") != FAKE_REPORT:
            raise AssertionError("JSONL final Markdown extraction is incorrect.")
        if "session.tools_updated" in json_reports[0].read_text(
            encoding="utf-8"
        ):
            raise AssertionError("JSONL protocol events leaked into the report.")

        invalid_project = temporary / "invalid-report-project"
        invalid_project.mkdir()
        fake_copilot.write_text(
            "#!/usr/bin/env bash\n"
            "exit 0\n",
            encoding="utf-8",
        )
        invalid_run = subprocess.run(
            [str(RUNNER), str(invalid_project)],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        if invalid_run.returncode != 65:
            raise AssertionError(
                f"Invalid report returned {invalid_run.returncode}, not 65."
            )
        invalid_reports = list(
            (invalid_project / "reports" / "willitscale").glob(
                "willitscale_results_*_failed.md"
            )
        )
        if len(invalid_reports) != 1:
            raise AssertionError("Invalid successful output was not quarantined.")
        invalid_content = invalid_reports[0].read_text(encoding="utf-8")
        if "did not return the required report format" not in invalid_content:
            raise AssertionError("Invalid report failure reason is missing.")
        if "_No assessment content was produced" not in invalid_content:
            raise AssertionError("Empty report was not explicitly documented.")

        timeout_project = temporary / "timeout-project"
        timeout_project.mkdir()
        fake_copilot.write_text(
            "#!/usr/bin/env bash\n"
            "while true; do\n"
            "  printf '.' >&2\n"
            "  sleep 0.1\n"
            "done\n",
            encoding="utf-8",
        )
        timeout_environment = environment.copy()
        started_at = time.monotonic()
        timeout_run = subprocess.run(
            [
                str(RUNNER),
                "--idle-timeout",
                "1",
                "--max-runtime",
                "10",
                "--activity-bytes",
                "4096",
                str(timeout_project),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=timeout_environment,
            timeout=10,
        )
        elapsed = time.monotonic() - started_at
        if timeout_run.returncode == 0:
            raise AssertionError(
                "Heartbeat-only assessment unexpectedly succeeded."
            )
        if elapsed >= 8:
            raise AssertionError(
                f"Idle watchdog took too long to terminate: {elapsed:.1f}s"
            )
        timeout_reports = list(
            (timeout_project / "reports" / "willitscale").glob(
                "willitscale_results_*_failed.md"
            )
        )
        if len(timeout_reports) != 1:
            raise AssertionError(
                f"Expected one timeout report, found {timeout_reports}"
            )
        timeout_content = timeout_reports[0].read_text(encoding="utf-8")
        if "No Copilot I/O was observed for 1 seconds." not in timeout_content:
            raise AssertionError("Timeout report omitted the watchdog reason.")
        if "stopping (idle timeout)" not in timeout_run.stderr:
            raise AssertionError("Heartbeat idle timeout was not visible.")

        runtime_project = temporary / "runtime-project"
        runtime_project.mkdir()
        fake_copilot.write_text(
            "#!/usr/bin/env bash\n"
            "while true; do\n"
            "  printf '.'\n"
            "  sleep 0.1\n"
            "done\n",
            encoding="utf-8",
        )
        runtime_run = subprocess.run(
            [
                str(RUNNER),
                "--idle-timeout",
                "10",
                "--max-runtime",
                "1",
                str(runtime_project),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=10,
        )
        runtime_reports = list(
            (runtime_project / "reports" / "willitscale").glob(
                "willitscale_results_*_failed.md"
            )
        )
        if runtime_run.returncode == 0 or len(runtime_reports) != 1:
            raise AssertionError("Maximum-runtime watchdog did not fail the run.")
        if "Maximum runtime of 1 seconds was exceeded." not in (
            runtime_reports[0].read_text(encoding="utf-8")
        ):
            raise AssertionError("Maximum-runtime reason is missing.")

        interrupted_project = temporary / "interrupted-project"
        interrupted_project.mkdir()
        fake_copilot.write_text(
            "#!/usr/bin/env bash\n"
            "sleep 30\n",
            encoding="utf-8",
        )
        interrupted_process = subprocess.Popen(
            [str(RUNNER), str(interrupted_project)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
        interrupted_report_directory = (
            interrupted_project / "reports" / "willitscale"
        )
        initialization_deadline = time.monotonic() + 5
        while time.monotonic() < initialization_deadline:
            if list(interrupted_report_directory.glob("willitscale_results_*.md")):
                break
            time.sleep(0.02)
        else:
            interrupted_process.kill()
            interrupted_process.communicate(timeout=5)
            raise AssertionError("Interrupted runner did not initialize.")
        time.sleep(0.1)
        interrupted_process.send_signal(signal.SIGINT)
        interrupted_process.communicate(timeout=10)
        if interrupted_process.returncode == 0:
            raise AssertionError("Interrupted assessment unexpectedly succeeded.")
        interrupted_reports = list(
            interrupted_report_directory.glob("willitscale_results_*_failed.md")
        )
        if len(interrupted_reports) != 1:
            raise AssertionError("Interrupted run did not preserve a report.")
        if "Assessment interrupted by SIGINT." not in (
            interrupted_reports[0].read_text(encoding="utf-8")
        ):
            raise AssertionError("Interrupted report omitted the signal reason.")

        print(
            "Report runner provides quiet progress, bounded retries, "
            "verbose output, and idle-hang protection."
        )


if __name__ == "__main__":
    main()
