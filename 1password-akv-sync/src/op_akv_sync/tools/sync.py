"""
Sync tools: diff, sync, and ESO ExternalSecret manifest generation.
These are the high-value tools that elevate this beyond a basic sync script.
"""

from __future__ import annotations

import json
from typing import Literal

import yaml
from mcp.server import Server
from mcp.types import TextContent

from op_akv_sync.clients import AzureKeyVaultClient, OnePasswordClient
from op_akv_sync.clients.akv_client import _sanitise_name


def register_sync_tools(
    server: Server,
    op: OnePasswordClient,
    akv: AzureKeyVaultClient,
) -> None:

    @server.tool()
    async def diff_vault_akv(vault_id: str) -> list[TextContent]:
        """
        Compare a 1Password vault against Azure Key Vault and report:
          - missing:  secrets in 1P but not in AKV
          - extra:    secrets in AKV but not in 1P (may be managed elsewhere)
          - in_sync:  secrets present in both

        Does NOT fetch secret values — safe to run at any time.

        Args:
            vault_id: The 1Password vault ID to compare.
        """
        op_items = await op.list_items(vault_id)
        akv_secrets = akv.list_secrets()

        op_names = {_sanitise_name(item["title"]) for item in op_items}
        akv_names = {s["name"] for s in akv_secrets}

        result = {
            "missing_from_akv": sorted(op_names - akv_names),
            "extra_in_akv": sorted(akv_names - op_names),
            "in_sync": sorted(op_names & akv_names),
            "summary": {
                "op_total": len(op_names),
                "akv_total": len(akv_names),
                "missing": len(op_names - akv_names),
                "extra": len(akv_names - op_names),
                "synced": len(op_names & akv_names),
            },
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    @server.tool()
    async def sync_secret(
        vault_id: str,
        item_title: str,
        field_label: str = "password",
        overwrite: bool = True,
    ) -> list[TextContent]:
        """
        Sync a single secret from 1Password → Azure Key Vault.
        Tags the AKV secret with its 1Password origin for auditability.

        Args:
            vault_id:    The 1Password vault ID.
            item_title:  The 1Password item title.
            field_label: The field to sync (default: "password").
            overwrite:   If False, skip secrets that already exist in AKV.
        """
        safe_name = _sanitise_name(item_title)

        if not overwrite and akv.secret_exists(safe_name):
            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "skipped",
                    "reason": f"'{safe_name}' already exists in AKV and overwrite=False.",
                }),
            )]

        value = await op.get_secret(vault_id, item_title, field_label)
        result = akv.set_secret(
            name=safe_name,
            value=value,
            tags={
                "managed-by": "op-akv-sync",
                "op-vault-id": vault_id,
                "op-item-title": item_title,
            },
        )
        return [TextContent(
            type="text",
            text=json.dumps({"status": "synced", "akv_secret": result}, indent=2),
        )]

    @server.tool()
    async def sync_vault(
        vault_id: str,
        overwrite: bool = True,
        dry_run: bool = False,
    ) -> list[TextContent]:
        """
        Bulk sync all secrets in a 1Password vault → Azure Key Vault.

        Args:
            vault_id:  The 1Password vault ID.
            overwrite: If False, skip secrets that already exist in AKV.
            dry_run:   If True, report what would be synced without writing anything.
        """
        results: list[dict] = []

        async for title, value in op.get_all_secrets(vault_id):
            safe_name = _sanitise_name(title)
            exists = akv.secret_exists(safe_name)

            if dry_run:
                action = "would_skip" if (exists and not overwrite) else "would_sync"
                results.append({"item": title, "akv_name": safe_name, "action": action})
                continue

            if exists and not overwrite:
                results.append({"item": title, "akv_name": safe_name, "status": "skipped"})
                continue

            try:
                akv.set_secret(
                    name=safe_name,
                    value=value,
                    tags={
                        "managed-by": "op-akv-sync",
                        "op-vault-id": vault_id,
                        "op-item-title": title,
                    },
                )
                results.append({"item": title, "akv_name": safe_name, "status": "synced"})
            except Exception as e:
                results.append({"item": title, "akv_name": safe_name, "status": "error", "detail": str(e)})

        summary = {
            "total": len(results),
            "synced": sum(1 for r in results if r.get("status") == "synced"),
            "skipped": sum(1 for r in results if r.get("status") == "skipped"),
            "errors": sum(1 for r in results if r.get("status") == "error"),
        }
        return [TextContent(
            type="text",
            text=json.dumps({"summary": summary, "details": results}, indent=2),
        )]

    @server.tool()
    async def generate_eso_manifest(
        secret_name: str,
        namespace: str,
        akv_secret_name: str | None = None,
        k8s_secret_name: str | None = None,
        refresh_interval: str = "1h",
        secret_store_name: str = "azure-store",
        secret_store_kind: Literal["SecretStore", "ClusterSecretStore"] = "ClusterSecretStore",
    ) -> list[TextContent]:
        """
        Generate an ESO ExternalSecret manifest for a secret already in Azure Key Vault.

        Produces a ready-to-apply Kubernetes YAML that ESO will reconcile into
        a native Kubernetes Secret.

        Args:
            secret_name:        Friendly name used for the K8s secret (and as default AKV name).
            namespace:          Kubernetes namespace to create the secret in.
            akv_secret_name:    AKV secret name if different from secret_name.
            k8s_secret_name:    K8s secret name if different from secret_name.
            refresh_interval:   How often ESO re-syncs from AKV (default: "1h").
            secret_store_name:  Name of the ESO SecretStore/ClusterSecretStore resource.
            secret_store_kind:  "SecretStore" (namespaced) or "ClusterSecretStore" (global).
        """
        safe_akv_name = _sanitise_name(akv_secret_name or secret_name)
        k8s_name = k8s_secret_name or secret_name

        manifest = {
            "apiVersion": "external-secrets.io/v1beta1",
            "kind": "ExternalSecret",
            "metadata": {
                "name": k8s_name,
                "namespace": namespace,
                "annotations": {
                    "managed-by": "op-akv-sync",
                },
            },
            "spec": {
                "refreshInterval": refresh_interval,
                "secretStoreRef": {
                    "name": secret_store_name,
                    "kind": secret_store_kind,
                },
                "target": {
                    "name": k8s_name,
                    "creationPolicy": "Owner",
                },
                "data": [
                    {
                        "secretKey": secret_name,
                        "remoteRef": {
                            "key": safe_akv_name,
                        },
                    }
                ],
            },
        }

        yaml_output = yaml.dump(manifest, default_flow_style=False, sort_keys=False)
        return [TextContent(type="text", text=yaml_output)]
