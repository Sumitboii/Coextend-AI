"""
Coextend Prospect Intelligence MVP â€” application entry point.
Run with:  uvicorn main:app --reload
"""
from __future__ import annotations

import logging
import logging.config
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.database import init_db
from api.routes import router
from config import settings

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — initialising database …")
    await init_db()
    # Ensure output directories exist
    Path(settings.exports_path).mkdir(parents=True, exist_ok=True)
    Path(settings.knowledge_base_path).mkdir(parents=True, exist_ok=True)
    from knowledge.retrieval import warm_embed_cache
    await warm_embed_cache()
    logger.info("Startup complete.")
    yield
    logger.info("Shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Coextend Prospect Intelligence MVP",
    description=(
        "AI-assisted prospect research: web research, deterministic scoring, "
        "cited briefs, CRM export, and outreach drafts."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static files and templates for the minimal UI
_static = Path(__file__).parent / "ui" / "static"
_templates_dir = Path(__file__).parent / "ui" / "templates"

if _static.exists():
    app.mount("/static", StaticFiles(directory=str(_static)), name="static")

# Workaround for Starlette 1.6.0 + Jinja2 cache key incompatibility
from jinja2 import Environment, FileSystemLoader
_jinja_env = Environment(
    loader=FileSystemLoader(str(_templates_dir)),
    autoescape=True,
)
templates = Jinja2Templates(env=_jinja_env)

# API routes
app.include_router(router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# UI routes
# ---------------------------------------------------------------------------

@app.get("/manifest.json", include_in_schema=False)
async def manifest():
    """Serve PWA manifest for installability."""
    ui_path = Path(__file__).parent / "ui"
    return FileResponse(
        path=ui_path / "manifest.json",
        media_type="application/manifest+json",
    )


@app.get("/service-worker.js", include_in_schema=False)
@app.get("/sw.js", include_in_schema=False)
@app.get("/static/sw.js", include_in_schema=False)
async def service_worker():
    """Serve service worker for offline support and caching."""
    ui_path = Path(__file__).parent / "ui"
    response = FileResponse(
        path=ui_path / "service-worker.js",
        media_type="application/javascript",
    )
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/results/{job_id}", response_class=HTMLResponse, include_in_schema=False)
async def results(request: Request, job_id: str):
    return templates.TemplateResponse(request=request, name="results.html", context={"job_id": job_id})
