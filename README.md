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
- **Full secrets lifecycle** — Combine all three with rotation logic, rebuild in TypeScript to show language breadth
