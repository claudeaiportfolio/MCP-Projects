# op-akv-sync — Claude Code Guide

## 📋 Daily review rule

Every time this project is opened, check whether `claude-product-limitations.md` has been reviewed today:

1. Read the last entry in the **Review schedule** table at the bottom of `claude-product-limitations.md`
2. If the date is **before today**, prompt the user:
   > "It's been X days since the Claude product limitations were last reviewed. Want me to run through them now? I can check whether any have been resolved and update the tracker."
3. If the date is **today**, skip silently and proceed normally

Only add a row to the Review schedule table when an actual review takes place — i.e. when limitations are assessed and statuses are updated. Do not log a row simply because the project was opened.

---

## 🚀 First run — push to GitHub

If this project hasn't been pushed to GitHub yet, do the following:

1. Create a **public** GitHub repo called `MCP-Projects` (if it doesn't already exist):
   ```bash
   gh repo create MCP-Projects --public --description "MCP servers for DevOps and platform engineering" --clone
   ```

2. Copy this project into the cloned repo under a `1password-akv-sync/` subfolder.

3. Create a root-level `README.md` in `MCP-Projects/` with this content:
   ```markdown
   # MCP Projects

   A portfolio of [Model Context Protocol (MCP)](https://modelcontextprotocol.io) servers built to solve real DevOps and platform engineering problems.

   MCP servers are standalone processes that expose tools to AI assistants (Claude, Cursor, etc.) over a standard protocol. They are infrastructure — not application code — and can be written in any language.

   ## Projects

   | Project | Language | Description |
   |---------|----------|-------------|
   | [1password-akv-sync](./1password-akv-sync) | Python | Sync secrets from 1Password → Azure Key Vault and generate ESO `ExternalSecret` manifests |

   ## Roadmap

   - **ESO Auditor** — Cross-reference running AKS pods against ESO `ExternalSecret` objects, flag missing or stale secrets
   - **Helm values manager** — Read `values.yaml`, diff against AKV, auto-generate or patch `ExternalSecret` CRDs, open PRs via GitHub API
   - **Full secrets lifecycle** — Combine all three with rotation logic
   ```

4. Commit and push:
   ```bash
   cd MCP-Projects
   git add .
   git commit -m "feat: initial commit — 1password-akv-sync MCP server

   Adds a Python MCP server that bridges 1Password (Service Account)
   and Azure Key Vault with the following tools:
   - list_vaults / list_secrets / get_secret (1Password)
   - list_akv_secrets / get_akv_secret (Azure Key Vault)
   - diff_vault_akv — compare stores without fetching values
   - sync_secret / sync_vault — push secrets from 1P to AKV
   - generate_eso_manifest — produce ready-to-apply ExternalSecret YAML"
   git push -u origin main
   ```

5. Print the repo URL when done.

---

This is an MCP server written in Python. It bridges 1Password (via Service Account)
and Azure Key Vault, and exposes tools for syncing secrets and generating ESO manifests.

## Setup

```bash
cp .env.example .env
# Fill in OP_SERVICE_ACCOUNT_TOKEN and AZURE_KEY_VAULT_URL

pip install -e ".[dev]"
```

## Running the MCP server

```bash
op-akv-sync
# or
python -m op_akv_sync.server
```

The server communicates over **stdio** — it is designed to be launched by an MCP client
(Claude Desktop, Claude Code, Cursor, etc.), not run interactively.

## Running tests

```bash
pytest
```

Tests are fully mocked — no real 1Password or Azure credentials are needed to run them.

## Adding the server to Claude Desktop

Add this to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "op-akv-sync": {
      "command": "op-akv-sync",
      "env": {
        "OP_SERVICE_ACCOUNT_TOKEN": "ops_your_token_here",
        "AZURE_KEY_VAULT_URL": "https://your-vault.vault.azure.net"
      }
    }
  }
}
```

## Project structure

```
src/op_akv_sync/
  server.py          # MCP server entrypoint — registers all tools
  clients/
    op_client.py     # 1Password SDK wrapper
    akv_client.py    # Azure Key Vault SDK wrapper
  tools/
    onepassword.py   # list_vaults, list_secrets, get_secret
    akv.py           # list_akv_secrets, get_akv_secret
    sync.py          # diff_vault_akv, sync_secret, sync_vault, generate_eso_manifest
```

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
| `sync_vault` | Bulk sync a 1P vault → AKV (supports dry_run) |
| `generate_eso_manifest` | Generate ESO ExternalSecret YAML for a secret |

## Security notes

- Secret values are **never logged**
- `list_*` tools only return names/metadata
- AKV secrets synced by this tool are tagged with `managed-by: op-akv-sync` for auditability
- Azure auth uses `DefaultAzureCredential` — works with `az login` locally and
  Workload Identity in AKS with zero code changes
