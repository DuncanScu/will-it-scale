"""Validate the Azure Scale Investigator package without external dependencies."""

from __future__ import annotations

import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROFILE = (
    REPOSITORY_ROOT
    / ".github"
    / "agents"
    / "azure-scale-investigator.agent.md"
)
README = (
    REPOSITORY_ROOT
    / "agents"
    / "azure-scale-investigator"
    / "README.md"
)
RUBRIC = (
    REPOSITORY_ROOT
    / "agents"
    / "azure-scale-investigator"
    / "checks"
    / "resource-classification.md"
)
TOOL_POLICY = (
    REPOSITORY_ROOT
    / "agents"
    / "azure-scale-investigator"
    / "checks"
    / "tool-policy.md"
)
SCHEMA = (
    REPOSITORY_ROOT
    / "agents"
    / "azure-scale-investigator"
    / "schemas"
    / "assessment-report.schema.json"
)
INSTALLER = (
    REPOSITORY_ROOT
    / "agents"
    / "azure-scale-investigator"
    / "scripts"
    / "install-user-agent.sh"
)
RUNNER = (
    REPOSITORY_ROOT
    / "agents"
    / "azure-scale-investigator"
    / "scripts"
    / "run-assessment.sh"
)
CASE = (
    REPOSITORY_ROOT
    / "agents"
    / "azure-scale-investigator"
    / "tests"
    / "cases"
    / "scale-street.md"
)
MCP_VALIDATOR = (
    REPOSITORY_ROOT
    / "agents"
    / "azure-scale-investigator"
    / "tests"
    / "validate_mcp_tools.py"
)
REPORT_RUNNER_VALIDATOR = (
    REPOSITORY_ROOT
    / "agents"
    / "azure-scale-investigator"
    / "tests"
    / "validate_report_runner.py"
)
INSTALLER_VALIDATOR = (
    REPOSITORY_ROOT
    / "agents"
    / "azure-scale-investigator"
    / "tests"
    / "validate_installer.py"
)
MONITOR_ERROR_CASE = (
    REPOSITORY_ROOT
    / "agents"
    / "azure-scale-investigator"
    / "tests"
    / "cases"
    / "monitor-error.md"
)


def parse_frontmatter(content: str) -> str:
    """Return YAML frontmatter from an agent profile."""

    if not content.startswith("---\n"):
        raise AssertionError("Agent profile must start with YAML frontmatter.")
    try:
        frontmatter, _ = content[4:].split("\n---\n", maxsplit=1)
    except ValueError as error:
        raise AssertionError("Agent profile frontmatter is not closed.") from error
    return frontmatter


def require_text(content: str, expected: str, source: Path) -> None:
    """Require a safety or workflow invariant in a text file."""

    if expected not in content:
        raise AssertionError(f"{source}: missing required text: {expected}")


def parse_top_level_list(frontmatter: str, key: str) -> list[str]:
    """Parse a simple top-level YAML string list without adding a dependency."""

    lines = frontmatter.splitlines()
    try:
        start = lines.index(f"{key}:") + 1
    except ValueError as error:
        raise AssertionError(f"Missing frontmatter list: {key}") from error

    values = []
    for line in lines[start:]:
        if not line.startswith("  - "):
            break
        values.append(line.removeprefix("  - ").strip('"'))
    return values


def main() -> None:
    """Validate profile structure, safety constraints, and package files."""

    required_files = (
        PROFILE,
        README,
        RUBRIC,
        TOOL_POLICY,
        SCHEMA,
        INSTALLER,
        RUNNER,
        CASE,
        MCP_VALIDATOR,
        REPORT_RUNNER_VALIDATOR,
        INSTALLER_VALIDATOR,
        MONITOR_ERROR_CASE,
    )
    missing = [path for path in required_files if not path.is_file()]
    if missing:
        raise AssertionError(f"Missing package files: {missing}")

    profile = PROFILE.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(profile)

    for expected in (
        "name: azure-scale-investigator",
        "target: github-copilot",
        "model: gpt-5.4",
        "disable-model-invocation: true",
        "user-invocable: true",
        "command: npx",
        "--read-only",
        "@azure/mcp@3.0.0-beta.44",
    ):
        require_text(frontmatter, expected, PROFILE)

    for prohibited_tool in ("edit", "execute"):
        if f"\n  - {prohibited_tool}\n" in frontmatter:
            raise AssertionError(
                f"Read-only agent must not enable {prohibited_tool}."
            )

    if "azure-mcp/*" in frontmatter:
        raise AssertionError("Agent must use a curated Azure MCP allowlist.")

    expected_azure_tools = {
        "subscription_list",
        "group_list",
        "group_resource_list",
        "insights",
        "advisor",
        "optimization",
        "quota",
        "resourcehealth",
        "monitor",
        "applicationinsights",
        "applens",
        "grafana",
        "aks",
        "acr",
        "foundry",
        "appservice",
        "containerapps",
        "functionapp",
        "compute",
        "cosmos",
        "sql",
        "postgres",
        "mysql",
        "redis",
        "servicebus",
        "eventhubs",
        "storage",
        "fileshares",
        "kusto",
        "search",
        "eventgrid",
        "signalr",
        "iothub",
        "servicefabric",
        "datadog",
        "workbooks",
    }
    expected_profile_tools = {
        "read",
        "search",
        *(f"azure-mcp/{tool}" for tool in expected_azure_tools),
    }
    actual_profile_tool_values = parse_top_level_list(frontmatter, "tools")
    if len(actual_profile_tool_values) != len(set(actual_profile_tool_values)):
        raise AssertionError("Agent tool allowlist contains duplicate entries.")
    actual_profile_tools = set(actual_profile_tool_values)
    if actual_profile_tools != expected_profile_tools:
        missing = sorted(expected_profile_tools - actual_profile_tools)
        unexpected = sorted(actual_profile_tools - expected_profile_tools)
        raise AssertionError(
            f"Agent tool allowlist changed. Missing={missing}, "
            f"unexpected={unexpected}"
        )

    for tool in expected_azure_tools:
        require_text(frontmatter, f"azure-mcp/{tool}", PROFILE)

    expected_namespaces = {
        "subscription",
        "group",
        "insights",
        "advisor",
        "optimization",
        "quota",
        "resourcehealth",
        "monitor",
        "applicationinsights",
        "applens",
        "grafana",
        "aks",
        "acr",
        "foundry",
        "appservice",
        "containerapps",
        "functionapp",
        "compute",
        "cosmos",
        "sql",
        "postgres",
        "mysql",
        "redis",
        "servicebus",
        "eventhubs",
        "storage",
        "fileshares",
        "kusto",
        "search",
        "eventgrid",
        "signalr",
        "iothub",
        "servicefabric",
        "datadog",
        "workbooks",
    }
    frontmatter_lines = frontmatter.splitlines()
    actual_namespace_values = [
        frontmatter_lines[index + 1].strip().removeprefix("- ")
        for index, line in enumerate(frontmatter_lines[:-1])
        if line.strip() == "- --namespace"
    ]
    if len(actual_namespace_values) != len(set(actual_namespace_values)):
        raise AssertionError("Azure MCP namespace list contains duplicates.")
    actual_namespaces = set(actual_namespace_values)
    if actual_namespaces != expected_namespaces:
        missing = sorted(expected_namespaces - actual_namespaces)
        unexpected = sorted(actual_namespaces - expected_namespaces)
        raise AssertionError(
            f"Azure MCP namespaces changed. Missing={missing}, "
            f"unexpected={unexpected}"
        )

    for expected in (
        "Never modify project files.",
        "Never retrieve secret values",
        "expected-resource manifest",
        "Managed identity is normally a scale-path dependency",
        "Analyze bottleneck chains",
        "Evidence labels",
        "Do not ask whether a particular Azure MCP tool should be used.",
        "do not interrupt the run",
        "A tool failure must not abort the overall assessment",
        "metric definitions",
        "Tool execution notes",
        "## TL;DR",
        "## Actions and recommendations",
        "Confidence rationale",
        "Do not emit interim narration",
    ):
        require_text(profile, expected, PROFILE)

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if schema.get("title") != "Azure Scale Investigator Assessment":
        raise AssertionError("Assessment schema title is incorrect.")

    required = set(schema.get("required", []))
    expected_required = {
        "verdict",
        "metadata",
        "tldr",
        "confidence",
        "application",
        "azureScope",
        "resources",
        "bottleneckChains",
        "findings",
        "toolIssues",
        "recommendations",
        "unknowns",
    }
    if required != expected_required:
        raise AssertionError("Assessment schema required fields changed.")

    installer = INSTALLER.read_text(encoding="utf-8")
    require_text(installer, "--dry-run", INSTALLER)
    require_text(installer, "will-it-scale-azure", INSTALLER)
    require_text(installer, "Already current:", INSTALLER)
    require_text(installer, "Refusing to replace symbolic link", INSTALLER)
    readme = README.read_text(encoding="utf-8")
    require_text(readme, "~/.copilot/agents", README)
    require_text(readme, "--allow-all-tools", README)
    require_text(readme, "--no-ask-user", README)

    tool_policy = TOOL_POLICY.read_text(encoding="utf-8")
    for tool in expected_azure_tools:
        require_text(tool_policy, f"`azure-mcp/{tool}`", TOOL_POLICY)
    for excluded_namespace in ("loadtesting", "deploy", "keyvault"):
        require_text(tool_policy, f"`{excluded_namespace}`", TOOL_POLICY)

    monitor_case = MONITOR_ERROR_CASE.read_text(encoding="utf-8")
    require_text(monitor_case, "ClientErrors", MONITOR_ERROR_CASE)
    require_text(
        monitor_case,
        "Continue checking independent resources",
        MONITOR_ERROR_CASE,
    )

    runner = RUNNER.read_text(encoding="utf-8")
    require_text(runner, "--agent azure-scale-investigator", RUNNER)
    require_text(runner, "--allow-all-tools", RUNNER)
    require_text(runner, "--no-ask-user", RUNNER)
    require_text(runner, "--no-custom-instructions", RUNNER)
    require_text(runner, "reports/willitscale", RUNNER)
    require_text(runner, "willitscale_results_", RUNNER)
    require_text(runner, "--silent", RUNNER)
    require_text(runner, "tee", RUNNER)
    require_text(runner, "--verbose", RUNNER)
    require_text(runner, "estimated_percent", RUNNER)
    require_text(runner, "render_status 100", RUNNER)
    require_text(runner, "--idle-timeout", RUNNER)
    require_text(runner, "--max-runtime", RUNNER)
    require_text(runner, "No Copilot I/O was observed", RUNNER)
    require_text(runner, "setsid copilot", RUNNER)
    require_text(runner, "validate_report", RUNNER)
    require_text(runner, "did not return the required report format", RUNNER)
    if "--allow-all \\" in runner or "--yolo" in runner:
        raise AssertionError("Runner must not grant unrestricted permissions.")

    print("Azure Scale Investigator package is valid.")


if __name__ == "__main__":
    main()
