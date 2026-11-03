"""Server MCP che espone il convertitore di unità."""

from mcp.server.mcpserver import MCPServer

from convertitore_mcp.unita import Unita, descrivi_conversione

server = MCPServer("convertitore")


@server.tool()
def converti_unita(valore: float, da: Unita, a: Unita) -> str:
    """Converte un valore tra due unità della stessa grandezza (lunghezza, massa,
    temperatura, volume, tempo). Usare solo i simboli ammessi dallo schema."""
    return descrivi_conversione(valore, da, a)
