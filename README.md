# AI Agent – Starter (Backend + Infra)
Base ordinata per backend FastAPI + infrastruttura locale (Postgres, Redis, MinIO).

## Avvio rapido
```bash
cp .env.example .env
docker compose up -d --build
curl http://localhost:8000/api/v1/healthz

### `.gitignore`
```gitignore
__pycache__/
*.pyc
.env
.venv/
venv/
.DS_Store
*.log
node_modules/
.next/
dist/
build/
