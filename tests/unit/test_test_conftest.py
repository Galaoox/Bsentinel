import importlib
from pathlib import Path


def test_build_test_db_path_uses_base_dir_and_unique_names(tmp_path):
    conftest_module = importlib.import_module("tests.conftest")

    first = conftest_module._build_test_db_path(tmp_path)
    second = conftest_module._build_test_db_path(tmp_path)

    assert first.parent == tmp_path
    assert second.parent == tmp_path
    assert first != second
    assert first.suffix == ".db"
    assert second.suffix == ".db"


def test_build_test_db_url_returns_sqlite_aiosqlite_url():
    conftest_module = importlib.import_module("tests.conftest")

    db_url = conftest_module._build_test_db_url(Path("C:/tmp/example.db"))

    assert db_url == "sqlite+aiosqlite:///C:/tmp/example.db"
