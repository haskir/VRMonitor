import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--obs",
        action="store_true",
        help="Запустить тесты с настоящей виртуальной камерой OBS (выводят тестовую картинку в OBS)",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "obs: тест с настоящей виртуальной камерой OBS, запускается с --obs")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--obs"):
        return
    skip = pytest.mark.skip(reason="нужен флаг --obs: тест выводит картинку в настоящую виртуальную камеру OBS")
    for item in items:
        if "obs" in item.keywords:
            item.add_marker(skip)
