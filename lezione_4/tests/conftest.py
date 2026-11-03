import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--lmstudio",
        action="store_true",
        default=False,
        help="esegue le prove reali con LM Studio",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--lmstudio"):
        return
    salta = pytest.mark.skip(reason="richiede --lmstudio")
    for item in items:
        if "lmstudio" in item.keywords:
            item.add_marker(salta)


@pytest.fixture(scope="session")
def servizio_scadenze():
    """Servizio HTTP di giorni e scadenze su una porta libera; restituisce l'indirizzo base."""
    import threading

    from scadenze_api.servizio import crea_server

    server = crea_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
