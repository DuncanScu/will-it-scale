import unittest

from will_it_scale.tools.azure_mcp import AZURE_MCP_NAMESPACES, create_azure_mcp_tool


class AzureScaleInvestigatorTests(unittest.TestCase):
    def test_mcp_tool_is_curated_read_only_and_pinned(self) -> None:
        mcp_tool = create_azure_mcp_tool()

        self.assertEqual(mcp_tool.name, "azure-mcp")
        self.assertEqual(mcp_tool.command, "npx")
        self.assertEqual(mcp_tool.args[:6], [
            "-y",
            "@azure/mcp@3.0.0-beta.44",
            "server",
            "start",
            "--read-only",
            "--mode",
        ])
        self.assertEqual(mcp_tool.args[6], "namespace")
        self.assertEqual(
            mcp_tool.args[7:],
            [item for namespace in AZURE_MCP_NAMESPACES for item in ("--namespace", namespace)],
        )
        self.assertEqual(mcp_tool.approval_mode, "never_require")


if __name__ == "__main__":
    unittest.main()
