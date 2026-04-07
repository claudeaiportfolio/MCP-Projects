"""
op-akv-sync: MCP Server entrypoint.

Runs over stdio (default for Claude Desktop / Claude Code).
All tools are registered at startup; clients are initialised lazily on first use.
"""

import asyncio
from dotenv import load_dotenv

from mcp.server import Server
from mcp.server.stdio import stdio_server

from op_akv_sync.clients import AzureKeyVaultClient, OnePasswordClient
from op_akv_sync.tools import (
    register_akv_tools,
    register_onepassword_tools,
    register_sync_tools,
)

load_dotenv()


def build_server() -> Server:
    server = Server("op-akv-sync")

    op = OnePasswordClient()
    akv = AzureKeyVaultClient()

    register_onepassword_tools(server, op)
    register_akv_tools(server, akv)
    register_sync_tools(server, op, akv)

    return server


async def _run() -> None:
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
