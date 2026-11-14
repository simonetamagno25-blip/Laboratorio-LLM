"""Front-end: contratto OpenAPI allineato, test JavaScript (Node) e server statico locale."""

import shutil
import subprocess
import threading
from pathlib import Path

import httpx
import pytest

from frontend import genera_api
from frontend.__main__ import crea_server

CARTELLA = Path(genera_api.__file__).resolve().parent


def test_api_js_e_openapi_allineati_al_backend():
    # Se il back-end cambia, va rigenerato il client: python -m frontend.genera_api
    assert genera_api.main(["--verifica"]) == 0


def test_ogni_operazione_del_backend_ha_la_sua_funzione():
    contratto = genera_api.contratto_dal_backend()
    api = (CARTELLA / "api.js").read_text(encoding="utf-8")
    for operazioni in contratto["paths"].values():
        for operazione in operazioni.values():
            assert f"export function {operazione['operationId']}(" in api


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js non installato")
def test_javascript_del_frontend():
    esito = subprocess.run(
        ["node", "--test", str(CARTELLA / "test" / "front.test.mjs")],
        capture_output=True, text=True, timeout=120,
    )
    assert esito.returncode == 0, esito.stdout + esito.stderr


@pytest.fixture
def server_frontend():
    server = crea_server("127.0.0.1", 0, "http://backend.esempio:8200/")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_server_statico(server_frontend):
    indice = httpx.get(server_frontend + "/")
    assert indice.status_code == 200 and "Assistente del laboratorio" in indice.text
    config = httpx.get(server_frontend + "/config.js")
    assert config.text == 'window.CONFIG = {"backend": "http://backend.esempio:8200"};\n'
    assert httpx.get(server_frontend + "/app.js").headers["content-type"].startswith("text/javascript")
    # Solo i file dell'interfaccia: niente sorgenti né test.
    assert httpx.get(server_frontend + "/__main__.py").status_code == 404
    assert httpx.get(server_frontend + "/test/front.test.mjs").status_code == 404
