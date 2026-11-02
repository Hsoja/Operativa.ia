"""Revisiones estáticas: secretos, SQL construido con cadenas y salida sin escapar (puntos 2, 5, 7, 20)."""

import ast
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
KEY_PATTERN = re.compile(r"gsk_[A-Za-z0-9]{16,}|AIza[0-9A-Za-z_-]{30,}|\bAQ\.[A-Za-z0-9_-]{20,}|\bsk-[A-Za-z0-9_-]{20,}")
PY_FILES = [*(ROOT / "backend" / "app").rglob("*.py"), ROOT / "frontend" / "app.py"]


def _tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ROOT / line for line in out.splitlines() if (ROOT / line).is_file()]


def test_no_key_patterns_in_tracked_files():
    hits = []
    for path in _tracked_files():
        if KEY_PATTERN.search(path.read_text(encoding="utf-8", errors="ignore")):
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def test_no_client_bundle_or_vite_secrets():
    """Hoy no existe paquete JS: si aparece uno, también debe pasar por esta revisión."""
    for bundle_dir in (ROOT / "frontend" / "dist", ROOT / "frontend" / "build"):
        for path in bundle_dir.rglob("*") if bundle_dir.exists() else []:
            if path.is_file():
                assert not KEY_PATTERN.search(path.read_text(encoding="utf-8", errors="ignore")), path
    for path in _tracked_files():
        if path.suffix in {".ts", ".tsx", ".js", ".jsx", ".example"}:
            assert not re.search(r"VITE_\w*(KEY|SECRET|TOKEN)", path.read_text(encoding="utf-8")), path


def _sql_calls(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"execute", "executemany", "executescript"} and node.args:
                yield node


@pytest.mark.parametrize("path", PY_FILES, ids=lambda p: p.name)
def test_sql_is_never_built_from_strings(path):
    """Solo se permiten literales, cadenas adyacentes o una constante del módulo en mayúsculas."""
    for call in _sql_calls(ast.parse(path.read_text(encoding="utf-8"))):
        sql = call.args[0]
        is_literal = isinstance(sql, ast.Constant) and isinstance(sql.value, str)
        is_constant = isinstance(sql, ast.Name) and sql.id.isupper()
        assert is_literal or is_constant, f"{path.name}:{call.lineno} construye SQL dinámico"


def test_sql_check_catches_string_built_sql():
    bad = 'db.execute(f"SELECT * FROM t WHERE a = {x}")\ndb.execute("SELECT " + y)'
    for call in _sql_calls(ast.parse(bad)):
        assert not isinstance(call.args[0], ast.Constant)


def test_panel_never_renders_html_or_dynamic_markdown():
    tree = ast.parse((ROOT / "frontend" / "app.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"html", "markdown", "write"}, f"línea {node.lineno}"
            for keyword in node.keywords:
                assert keyword.arg != "unsafe_allow_html"


def test_exposed_file_scan_passes():
    result = subprocess.run(["bash", "scripts/scan_exposed_files.sh"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


def test_streamlit_config_is_local_only():
    text = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'address = "localhost"' in text and "enableXsrfProtection = true" in text
