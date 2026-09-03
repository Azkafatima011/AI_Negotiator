"""
AI Negotiator — An Autonomous B2B Wholesale Negotiation Platform
FastAPI Application Entry Point

Architecture: Alibaba Cloud + Qwen AI + WhatsApp Business Platform
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
import os

from app.config import get_settings
from app.database.database import init_db
from app.api.negotiations import router as negotiations_router
from app.api.contracts import router as contracts_router
from app.api.suppliers import router as suppliers_router
from app.api.whatsapp import router as whatsapp_router
from app.api.batches import router as batches_router
from app.security.auth import router as auth_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-powered B2B wholesale negotiation platform. "
        "Autonomous buyer and seller agents negotiate price, quantity, delivery, "
        "and payment terms using Alibaba Cloud Model Studio / Qwen AI."
    ),
    version=settings.version,
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(auth_router)
app.include_router(negotiations_router)
app.include_router(contracts_router)
app.include_router(suppliers_router)
app.include_router(whatsapp_router)
app.include_router(batches_router)

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.on_event("startup")
def on_startup():
    logger.info("Initializing database...")
    init_db()
    logger.info(f"{settings.app_name} v{settings.version} started")


@app.get("/")
def root():
    """Serve the frontend dashboard."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "app": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "healthy", "version": settings.version}


@app.get("/seller-respond/{token}", response_class=HTMLResponse)
def seller_respond_page(token: str):
    """Serve the standalone seller response page (no auth required)."""
    page_path = os.path.join(frontend_dir, "seller-respond.html")
    if os.path.exists(page_path):
        with open(page_path, "r", encoding="utf-8") as f:
            html = f.read()
        # Inject token into the page for JS to use
        html = html.replace("__SELLER_TOKEN__", token)
        return HTMLResponse(html)
    return HTMLResponse("<h1>Page not found</h1>", status_code=404)
