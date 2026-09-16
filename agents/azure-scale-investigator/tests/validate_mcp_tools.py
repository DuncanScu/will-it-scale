"""Validate the pinned Azure MCP namespace tool contract."""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import tempfile
import time

AZURE_MCP_VERSION = "3.0.0-beta.44"
NAMESPACES = (
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
)
EXPECTED_TOOLS = {
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


def request_tools() -> set[str]:
    """Start Azure MCP and return the registered tool names."""

    command = [
        "npx",
        "-y",
        f"@azure/mcp@{AZURE_MCP_VERSION}",
        "server",
        "start",
        "--read-only",
        "--mode",
        "namespace",
    ]
    for namespace in NAMESPACES:
        command.extend(("--namespace", namespace))

    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr_file:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr_file,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        if process.stdin is None or process.stdout is None:
            raise RuntimeError("Failed to open Azure MCP standard streams.")

        messages = (
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "azure-scale-investigator-validation",
                        "version": "1.0",
                    },
                },
            },
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
        )
        for message in messages:
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()

        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + 30
        tools: set[str] | None = None
        timed_out = False
        try:
            while time.monotonic() < deadline:
                timeout = max(0, deadline - time.monotonic())
                if not selector.select(timeout):
                    timed_out = process.poll() is None
                    break
                line = process.stdout.readline()
                if not line:
                    if process.poll() is not None:
                        break
                    continue
                try:
                    response = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if response.get("id") != 2:
                    continue
                tools = {
                    tool["name"]
                    for tool in response.get("result", {}).get("tools", [])
                }
                break
            if (
                tools is None
                and process.poll() is None
                and time.monotonic() >= deadline
            ):
                timed_out = True
        finally:
            selector.close()
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)

        if tools is not None:
            return tools

        stderr_file.seek(0)
        stderr = stderr_file.read()
        if timed_out:
            reason = "timed out"
        else:
            reason = f"exited with status {process.returncode}"
        raise RuntimeError(
            f"Azure MCP tools/list {reason}: {stderr[-2_000:]}"
        )


def main() -> None:
    """Verify the pinned server exposes the expected tool set."""

    actual_tools = request_tools()
    if actual_tools != EXPECTED_TOOLS:
        missing = sorted(EXPECTED_TOOLS - actual_tools)
        unexpected = sorted(actual_tools - EXPECTED_TOOLS)
        raise AssertionError(
            f"Azure MCP tool contract changed. Missing={missing}, "
            f"unexpected={unexpected}"
        )
    print(
        f"Azure MCP {AZURE_MCP_VERSION} exposes "
        f"{len(actual_tools)} approved tools."
    )


if __name__ == "__main__":
    main()
