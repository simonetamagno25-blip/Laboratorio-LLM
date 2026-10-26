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
