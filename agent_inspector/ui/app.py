"""
Web UI for Agent Inspector.

Simple, responsive web interface with three-panel layout:
- Left Panel (30%): Run list with filters and search
- Center Panel (45%): Timeline visualization
- Right Panel (25%): Detail view for selected events
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


# UI router that can be mounted to FastAPI app
ui_router = APIRouter(prefix="/ui", tags=["UI"])


def setup_ui(app, template_dir: Optional[Path] = None):
    """
    Setup UI routes on FastAPI app.

    Args:
        app: FastAPI app instance.
        template_dir: Directory for HTML templates (default: ./ui/templates).
    """
    if template_dir is None:
        template_dir = Path(__file__).parent / "templates"

    # Create template directory if it doesn't exist
    template_dir.mkdir(parents=True, exist_ok=True)

    # Ensure index.html exists (fallback only)
    index_path = template_dir / "index.html"
    if not index_path.exists():
        index_path.write_text(get_index_html(), encoding="utf-8")

    # Initialize templates
    templates = Jinja2Templates(directory=str(template_dir))

    @ui_router.get("/", response_class=HTMLResponse)
    async def ui_index(request: Request):
        """
        Serve the main UI page.

        Returns:
            HTML response with the web interface.
        """
        return templates.TemplateResponse(request, "index.html")

    # Mount static assets
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/ui/static", StaticFiles(directory=str(static_dir)), name="ui-static")

    # Mount router to app
    app.include_router(ui_router)

    logger.info("UI routes setup complete")


def get_index_html() -> str:
    """
    Get the HTML template for the main UI page.

    Returns:
        HTML string for the web interface.
    """
    return "<!DOCTYPE html><html><body><p>UI template missing.</p></body></html>"
