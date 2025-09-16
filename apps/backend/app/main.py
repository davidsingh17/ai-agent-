from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.routers.health import router as health_router
from app.api.v1.routers.debug import router as debug_router
from app.api.v1.routers.invoices import router as invoices_router  # ✅ router corretto

app = FastAPI(title="AI Agent API", version="0.1.0")

# Configura CORS (robusto e con default per Vite)
raw_origins = getattr(settings, "cors_origins", "") or ""
parsed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

# Default sicuro per sviluppo (Vite su :8081)
if not parsed_origins:
    parsed_origins = ["http://localhost:8081"]

# Nota: se usi "*", i browser non permettono credenziali con wildcard
allow_credentials = True
if "*" in parsed_origins:
    allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=parsed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Monta i router
app.include_router(health_router, prefix="/api/v1")
app.include_router(invoices_router, prefix="/api/v1")  # => /api/v1/invoices/...
app.include_router(debug_router, prefix="/api/v1")


@app.get("/")
def root():
    return {"name": "AI Agent API", "status": "ok"}
