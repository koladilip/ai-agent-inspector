"""
UI setup tests.
"""

from pathlib import Path

from fastapi import FastAPI

from agent_inspector.ui.app import setup_ui


def test_setup_ui_writes_fallback(tmp_path: Path):
    app = FastAPI()
    template_dir = tmp_path / "templates"
    setup_ui(app, template_dir=template_dir)

    index_path = template_dir / "index.html"
    assert index_path.exists()
    assert "UI template missing" in index_path.read_text(encoding="utf-8")
