# op-akv-sync

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that bridges **1Password** and **Azure Key Vault**, letting an AI assistant sync secrets and generate [External Secrets Operator](https://external-secrets.io) manifests.

---

## What problem does this solve?

Dev teams often store secrets in **1Password** (easy UX, great sharing), but Kubernetes clusters running ESO are configured to pull from **Azure Key Vault**. This creates a manual sync step that is tedious and error-prone.

This MCP server lets you ask Claude to:

> *"Sync all secrets from the `payments` vault in 1Password to AKV, then generate ESO manifests for each one"*

…and have it done in seconds, without leaving your editor.

---

## Architecture

```
┌─────────────────┐        stdio        ┌──────────────────────┐
│  Claude Desktop │ ◄─────────────────► │  op-akv-sync         │
│  Claude Code    │                     │  (MCP Server)        │
│  Cursor etc.    │                     │                      │
└─────────────────┘                     │  ┌────────────────┐  │
                                        │  │ 1Password SDK  │  │──► 1Password Cloud
                                        │  └────────────────┘  │
                                        │  ┌────────────────┐  │
                                        │  │ Azure SDK      │  │──► Azure Key Vault
                                        │  └────────────────┘  │
                                        └──────────────────────┘
```

> **Note:** The MCP server is infrastructure — it has no coupling to your application code. It is a standalone process launched by the MCP client, communicating over stdio.

---

## Available tools

| Tool | Description |
|------|-------------|
| `list_vaults` | List accessible 1Password vaults |
| `list_secrets` | List item names in a vault (no values) |
| `get_secret` | Fetch a secret value from 1Password |
| `list_akv_secrets` | List secret names in AKV (no values) |
| `get_akv_secret` | Fetch a secret value from AKV |
| `diff_vault_akv` | Compare 1P vault vs AKV — find missing/extra/synced |
| `sync_secret` | Push one secret from 1P → AKV |
| `sync_vault` | Bulk sync a 1P vault → AKV (supports `dry_run`) |
| `generate_eso_manifest` | Generate an ESO `ExternalSecret` YAML for a secret |

---

## Setup

### Prerequisites

- Python 3.11+
- A [1Password Service Account](https://developer.1password.com/docs/service-accounts/) token
- An Azure Key Vault instance
- Azure credentials: `az login` locally, or Workload Identity in AKS

### Install

```bash
git clone https://github.com/your-org/op-akv-sync
cd op-akv-sync

pip install -e ".[dev]"

cp .env.example .env
# Edit .env with your credentials
```

### Configure Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "op-akv-sync": {
      "command": "op-akv-sync",
      "env": {
        "OP_SERVICE_ACCOUNT_TOKEN": "ops_...",
        "AZURE_KEY_VAULT_URL": "https://your-vault.vault.azure.net"
      }
    }
  }
}
```

---

## Example usage

```
You:     Diff the 'payments' vault (id: abc123) against AKV
Claude:  [calls diff_vault_akv] Missing from AKV: database-url, redis-password

You:     Sync them both
Claude:  [calls sync_secret x2] ✓ Synced database-url, ✓ Synced redis-password

You:     Generate ESO manifests for both in the payments namespace
Claude:  [calls generate_eso_manifest x2] 
         ---
         apiVersion: external-secrets.io/v1beta1
         kind: ExternalSecret
         ...
```

---

## Authentication

| Environment | How it works |
|---|---|
| Local dev | `az login` — `DefaultAzureCredential` picks it up automatically |
| AKS | [Workload Identity](https://learn.microsoft.com/en-us/azure/aks/workload-identity-overview) — no secrets needed |
| CI/CD | `AZURE_CLIENT_ID` + `AZURE_CLIENT_SECRET` + `AZURE_TENANT_ID` env vars |

The same binary works in all three environments — zero code changes.

---

## Development

```bash
# Run tests (no real credentials needed — fully mocked)
pytest

# Run with live credentials
op-akv-sync
```

---

## Security

- Secret **values are never logged**
- `list_*` tools return names/metadata only
- Secrets synced to AKV are tagged `managed-by: op-akv-sync` for auditability
- The service account should be scoped to read-only vaults it needs; AKV access should follow least-privilege

---

## Roadmap

- [ ] Support syncing non-password fields (API keys, certificates)
- [ ] `rotate_secret` tool — generate a new value, update both stores
- [ ] Webhook / GitHub Actions trigger for automated sync on vault change
