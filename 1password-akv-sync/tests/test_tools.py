"""
Tests for sync tools — diff, sync, and ESO manifest generation.
Uses pytest-mock to avoid real API calls.
"""

import json
import pytest
import yaml
from unittest.mock import AsyncMock, MagicMock, patch

from mcp.server import Server

from op_akv_sync.clients import AzureKeyVaultClient, OnePasswordClient
from op_akv_sync.tools import register_sync_tools, register_akv_tools, register_onepassword_tools


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_op():
    client = MagicMock(spec=OnePasswordClient)
    client.list_items = AsyncMock(return_value=[
        {"id": "abc1", "title": "payments-api-key", "category": "LOGIN"},
        {"id": "abc2", "title": "database-password", "category": "LOGIN"},
    ])
    client.get_secret = AsyncMock(return_value="super-secret-value")

    async def fake_get_all(vault_id):
        yield "payments-api-key", "secret-1"
        yield "database-password", "secret-2"

    client.get_all_secrets = fake_get_all
    return client


@pytest.fixture
def mock_akv():
    client = MagicMock(spec=AzureKeyVaultClient)
    client.list_secrets.return_value = [
        {"name": "payments-api-key", "enabled": True, "updated_on": None},
    ]
    client.secret_exists.return_value = False
    client.set_secret.return_value = {
        "name": "payments-api-key",
        "id": "https://vault.azure.net/secrets/payments-api-key/1",
        "enabled": True,
    }
    client.get_secret.return_value = "existing-value"
    return client


@pytest.fixture
def server():
    return Server("test-server")


# ---------------------------------------------------------------------------
# diff_vault_akv
# ---------------------------------------------------------------------------

class TestDiffVaultAkv:
    async def test_identifies_missing_and_synced(self, server, mock_op, mock_akv):
        register_sync_tools(server, mock_op, mock_akv)
        tool = server._tools["diff_vault_akv"]
        result = await tool(vault_id="vault-123")
        data = json.loads(result[0].text)

        assert "database-password" in data["missing_from_akv"]
        assert "payments-api-key" in data["in_sync"]
        assert data["summary"]["missing"] == 1
        assert data["summary"]["synced"] == 1

    async def test_no_secrets_in_akv(self, server, mock_op, mock_akv):
        mock_akv.list_secrets.return_value = []
        register_sync_tools(server, mock_op, mock_akv)
        tool = server._tools["diff_vault_akv"]
        result = await tool(vault_id="vault-123")
        data = json.loads(result[0].text)

        assert len(data["missing_from_akv"]) == 2
        assert data["in_sync"] == []


# ---------------------------------------------------------------------------
# sync_secret
# ---------------------------------------------------------------------------

class TestSyncSecret:
    async def test_syncs_successfully(self, server, mock_op, mock_akv):
        register_sync_tools(server, mock_op, mock_akv)
        tool = server._tools["sync_secret"]
        result = await tool(vault_id="vault-123", item_title="payments-api-key")
        data = json.loads(result[0].text)

        assert data["status"] == "synced"
        mock_akv.set_secret.assert_called_once()

    async def test_skips_existing_when_overwrite_false(self, server, mock_op, mock_akv):
        mock_akv.secret_exists.return_value = True
        register_sync_tools(server, mock_op, mock_akv)
        tool = server._tools["sync_secret"]
        result = await tool(vault_id="vault-123", item_title="payments-api-key", overwrite=False)
        data = json.loads(result[0].text)

        assert data["status"] == "skipped"
        mock_akv.set_secret.assert_not_called()


# ---------------------------------------------------------------------------
# sync_vault
# ---------------------------------------------------------------------------

class TestSyncVault:
    async def test_dry_run_does_not_write(self, server, mock_op, mock_akv):
        register_sync_tools(server, mock_op, mock_akv)
        tool = server._tools["sync_vault"]
        result = await tool(vault_id="vault-123", dry_run=True)
        data = json.loads(result[0].text)

        mock_akv.set_secret.assert_not_called()
        assert all(d["action"].startswith("would_") for d in data["details"])

    async def test_syncs_all_secrets(self, server, mock_op, mock_akv):
        register_sync_tools(server, mock_op, mock_akv)
        tool = server._tools["sync_vault"]
        result = await tool(vault_id="vault-123")
        data = json.loads(result[0].text)

        assert data["summary"]["synced"] == 2
        assert data["summary"]["errors"] == 0


# ---------------------------------------------------------------------------
# generate_eso_manifest
# ---------------------------------------------------------------------------

class TestGenerateEsoManifest:
    async def test_generates_valid_yaml(self, server, mock_op, mock_akv):
        register_sync_tools(server, mock_op, mock_akv)
        tool = server._tools["generate_eso_manifest"]
        result = await tool(secret_name="payments-api-key", namespace="payments")
        manifest = yaml.safe_load(result[0].text)

        assert manifest["kind"] == "ExternalSecret"
        assert manifest["metadata"]["namespace"] == "payments"
        assert manifest["spec"]["secretStoreRef"]["kind"] == "ClusterSecretStore"
        assert manifest["spec"]["data"][0]["remoteRef"]["key"] == "payments-api-key"

    async def test_sanitises_akv_name(self, server, mock_op, mock_akv):
        register_sync_tools(server, mock_op, mock_akv)
        tool = server._tools["generate_eso_manifest"]
        result = await tool(
            secret_name="my secret",
            namespace="default",
            akv_secret_name="my_secret_key",
        )
        manifest = yaml.safe_load(result[0].text)
        # underscores should be converted to hyphens
        assert manifest["spec"]["data"][0]["remoteRef"]["key"] == "my-secret-key"

    async def test_custom_secret_store(self, server, mock_op, mock_akv):
        register_sync_tools(server, mock_op, mock_akv)
        tool = server._tools["generate_eso_manifest"]
        result = await tool(
            secret_name="db-password",
            namespace="backend",
            secret_store_name="my-cluster-store",
            secret_store_kind="SecretStore",
        )
        manifest = yaml.safe_load(result[0].text)
        assert manifest["spec"]["secretStoreRef"]["name"] == "my-cluster-store"
        assert manifest["spec"]["secretStoreRef"]["kind"] == "SecretStore"
