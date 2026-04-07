"""
1Password client wrapper using the official 1Password Python SDK.
Authenticates via OP_SERVICE_ACCOUNT_TOKEN environment variable.
"""

import os
from functools import cached_property
from typing import AsyncIterator

import onepassword


class OnePasswordClient:
    """Thin async wrapper around the 1Password SDK client."""

    def __init__(self, token: str | None = None):
        self._token = token or os.environ.get("OP_SERVICE_ACCOUNT_TOKEN")
        if not self._token:
            raise ValueError(
                "OP_SERVICE_ACCOUNT_TOKEN must be set or passed explicitly."
            )

    @cached_property
    def _client(self) -> onepassword.Client:
        return onepassword.Client(
            auth=self._token,
            integration_name="op-akv-sync MCP Server",
            integration_version="0.1.0",
        )

    async def list_vaults(self) -> list[dict]:
        """Return a list of vaults the service account can access."""
        vaults = []
        async for vault in await self._client.vaults.list_all():
            vaults.append({"id": vault.id, "name": vault.name})
        return vaults

    async def list_items(self, vault_id: str) -> list[dict]:
        """Return metadata (no secret values) for all items in a vault."""
        items = []
        async for item in await self._client.items.list_all(vault_id):
            items.append({
                "id": item.id,
                "title": item.title,
                "category": str(item.category),
            })
        return items

    async def get_secret(self, vault_id: str, item_title: str, field_label: str = "password") -> str:
        """
        Fetch a single secret value using 1Password secret reference syntax.
        Reference format: op://<vault-id>/<item-title>/<field-label>
        """
        reference = f"op://{vault_id}/{item_title}/{field_label}"
        return await self._client.secrets.resolve(reference)

    async def get_all_secrets(self, vault_id: str) -> AsyncIterator[tuple[str, str]]:
        """
        Yield (item_title, secret_value) pairs for all Login/Password items in a vault.
        Only resolves the primary 'password' field to avoid over-fetching.
        """
        async for item in await self._client.items.list_all(vault_id):
            try:
                value = await self.get_secret(vault_id, item.title)
                yield item.title, value
            except Exception:
                # Skip items where the password field doesn't exist or can't be resolved
                continue
