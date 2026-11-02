"""Server MCP usato solo dai test dell'adattatore: python -m tests.server_mcp_prova."""

import os
import time

from mcp.server.mcpserver import MCPServer

server = MCPServer("prova")


@server.tool()
def pid() -> str:
    """Restituisce il PID del server."""
    return str(os.getpid())


@server.tool()
def dormi(secondi: float) -> str:
    """Attende il numero di secondi indicato."""
    time.sleep(secondi)
    return "sveglio"


@server.tool()
def termina() -> str:
    """Termina il processo del server senza rispondere."""
    os._exit(1)


if __name__ == "__main__":
    server.run("stdio")
