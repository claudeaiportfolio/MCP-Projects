"""
Azure Key Vault client wrapper using the Azure SDK.

Authentication uses DefaultAzureCredential, which automatically works with:
  - Local development:   `az login` (Azure CLI)
  - AKS:                 Workload Identity (no secrets needed in-cluster)
  - CI/CD:               AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID env vars

This means zero code changes between environments.
"""

import os
from functools import cached_property

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.core.exceptions import ResourceNotFoundError


class AzureKeyVaultClient:
    """Thin wrapper around the Azure Key Vault SecretClient."""

    def __init__(self, vault_url: str | None = None):
        self._vault_url = vault_url or os.environ.get("AZURE_KEY_VAULT_URL")
        if not self._vault_url:
            raise ValueError(
                "AZURE_KEY_VAULT_URL must be set or passed explicitly. "
                "Format: https://<vault-name>.vault.azure.net"
            )

    @cached_property
    def _client(self) -> SecretClient:
        credential = DefaultAzureCredential()
        return SecretClient(vault_url=self._vault_url, credential=credential)

    def list_secrets(self) -> list[dict]:
        """Return metadata (no values) for all enabled secrets in the vault."""
        secrets = []
        for secret in self._client.list_properties_of_secrets():
            secrets.append({
                "name": secret.name,
                "enabled": secret.enabled,
                "updated_on": secret.updated_on.isoformat() if secret.updated_on else None,
            })
        return secrets

    def get_secret(self, name: str) -> str | None:
        """Fetch a secret value by name. Returns None if not found."""
        try:
            return self._client.get_secret(name).value
        except ResourceNotFoundError:
            return None

    def set_secret(self, name: str, value: str, tags: dict | None = None) -> dict:
        """
        Create or update a secret. Tags are optional but useful for tracking origin.
        AKV secret names must match: ^[0-9a-zA-Z-]+$
        """
        safe_name = _sanitise_name(name)
        secret = self._client.set_secret(safe_name, value, tags=tags or {})
        return {
            "name": secret.name,
            "id": secret.id,
            "enabled": secret.properties.enabled,
        }

    def secret_exists(self, name: str) -> bool:
        """Check if a secret exists without fetching its value."""
        try:
            self._client.get_secret(_sanitise_name(name))
            return True
        except ResourceNotFoundError:
            return False


def _sanitise_name(name: str) -> str:
    """
    AKV secret names only allow alphanumerics and hyphens.
    Converts underscores and spaces → hyphens, strips other chars.
    """
    return "".join(c if c.isalnum() or c == "-" else "-" for c in name).strip("-")
