from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from vortex.config import settings
from vortex.serving.client import FeatureStoreClient
from vortex.api.routes_ingest import router as ingest_router
from vortex.api.routes_serving import router as serving_router
from vortex.api.routes_registry import router as registry_router
from vortex.api.routes_monitor import router as monitor_router
from vortex.api.routes_inference import router as inference_router
from vortex.api.routes_simulator import router as simulator_router

# Singleton Client Instance
_client_instance: FeatureStoreClient = None


def get_client() -> FeatureStoreClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = FeatureStoreClient()
    return _client_instance


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start stream processing background flushers
    client = get_client()
    client.stream_processor.start_background_flusher()
    yield
    # Shutdown: Flush remaining stream buffers and close connections
    client.flush()
    client.stream_processor.stop_background_flusher()
    if hasattr(client.offline_store, "close"):
        client.offline_store.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Event-Driven Real-Time Feature Store inspired by PostHog, Feast, and DuckDB OLAP engines.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(ingest_router)
app.include_router(serving_router)
app.include_router(registry_router)
app.include_router(monitor_router)
app.include_router(inference_router)
app.include_router(simulator_router)

# Dashboard HTML UI Route
DASHBOARD_PATH = Path(__file__).parent.parent / "ui" / "templates" / "dashboard.html"


@app.get("/", response_class=HTMLResponse, tags=["Dashboard UI"])
@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard UI"])
async def serve_dashboard():
    """Serves the interactive single-page Feature Store console."""
    if DASHBOARD_PATH.exists():
        with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>VortexFS Running</h1><p>Dashboard template not found.</p>")
