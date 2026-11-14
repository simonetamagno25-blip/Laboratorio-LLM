import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--lmstudio",
        action="store_true",
        default=False,
        help="esegue le prove reali con LM Studio",
    )
    parser.addoption(
        "--postgres",
        action="store_true",
        default=False,
        help="esegue i test dell'archivio PostgreSQL (serve POSTGRES_TEST_URL)",
    )


def pytest_collection_modifyitems(config, items):
    for opzione in ("lmstudio", "postgres"):
        if config.getoption(f"--{opzione}"):
            continue
        salta = pytest.mark.skip(reason=f"richiede --{opzione}")
        for item in items:
            if opzione in item.keywords:
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
