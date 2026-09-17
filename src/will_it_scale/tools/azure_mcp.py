from agent_framework import MCPStdioTool

AZURE_MCP_NAMESPACES = (
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


def create_azure_mcp_tool() -> MCPStdioTool:
    """Create the curated, read-only Azure MCP server connection."""

    args = [
        "-y",
        "@azure/mcp@3.0.0-beta.44",
        "server",
        "start",
        "--read-only",
        "--mode",
        "namespace",
    ]
    for namespace in AZURE_MCP_NAMESPACES:
        args.extend(("--namespace", namespace))
    return MCPStdioTool(
        name="azure-mcp",
        command="npx",
        args=args,
        description="Read-only Azure resource, quota, health, and telemetry tools.",
        approval_mode="never_require",
    )
