"""Punto d'ingresso: python -m convertitore_mcp (trasporto stdio)."""

from convertitore_mcp.server import server

if __name__ == "__main__":
    server.run("stdio")
