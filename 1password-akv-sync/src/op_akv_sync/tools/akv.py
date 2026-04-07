"""
MCP tools for reading from Azure Key Vault.
Secret values are never returned in list operations.
"""

from mcp.server import Server
from mcp.types import TextContent
import json

from op_akv_sync.clients import AzureKeyVaultClient


def register_akv_tools(server: Server, akv: AzureKeyVaultClient) -> None:

    @server.tool()
    async def list_akv_secrets() -> list[TextContent]:
        """
        List all secret names and metadata in the configured Azure Key Vault.
        Does not return any secret values.
        """
        secrets = akv.list_secrets()
        return [TextContent(type="text", text=json.dumps(secrets, indent=2))]

    @server.tool()
    async def get_akv_secret(name: str) -> list[TextContent]:
        """
        Fetch a single secret value from Azure Key Vault.

        Args:
            name: The secret name in AKV.
        """
        value = akv.get_secret(name)
        if value is None:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Secret '{name}' not found in AKV."}),
            )]
        return [TextContent(
            type="text",
            text=json.dumps({"name": name, "value": value}, indent=2),
        )]
