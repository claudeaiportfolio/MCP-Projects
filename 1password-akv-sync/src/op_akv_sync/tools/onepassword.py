"""
MCP tools for reading from 1Password.
Secret values are never logged — only names/metadata are surfaced in list operations.
"""

from mcp.server import Server
from mcp.types import Tool, TextContent
import json

from op_akv_sync.clients import OnePasswordClient


def register_onepassword_tools(server: Server, op: OnePasswordClient) -> None:

    @server.tool()
    async def list_vaults() -> list[TextContent]:
        """List all 1Password vaults the service account has access to."""
        vaults = await op.list_vaults()
        return [TextContent(type="text", text=json.dumps(vaults, indent=2))]

    @server.tool()
    async def list_secrets(vault_id: str) -> list[TextContent]:
        """
        List all item names in a 1Password vault.
        Returns metadata only — no secret values.

        Args:
            vault_id: The 1Password vault ID (get from list_vaults).
        """
        items = await op.list_items(vault_id)
        return [TextContent(type="text", text=json.dumps(items, indent=2))]

    @server.tool()
    async def get_secret(
        vault_id: str,
        item_title: str,
        field_label: str = "password",
    ) -> list[TextContent]:
        """
        Fetch a single secret value from 1Password.

        Args:
            vault_id:    The 1Password vault ID.
            item_title:  The item title (e.g. "payments-api-key").
            field_label: The field to fetch (default: "password").
        """
        value = await op.get_secret(vault_id, item_title, field_label)
        # Return value in a structured envelope — never log raw secrets
        return [TextContent(
            type="text",
            text=json.dumps({
                "vault_id": vault_id,
                "item": item_title,
                "field": field_label,
                "value": value,
            }, indent=2),
        )]
