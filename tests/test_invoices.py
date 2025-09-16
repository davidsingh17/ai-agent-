import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app  # apps/backend/app/main.py

@pytest.mark.asyncio
async def test_extract_invoice_pdf():
    pdf_path = "tests/data/invoice_sample.pdf"
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/invoices/extract",
            files={"file": ("invoice.pdf", file_bytes, "application/pdf")},
        )

    assert resp.status_code == 200
    data = resp.json()
    # nuova shape: InvoiceOut diretto
    assert "id" in data
    assert "s3" in data
    assert "filename" in data
    assert "fields" in data
    assert "totale" in data["fields"]

@pytest.mark.asyncio
async def test_list_invoices():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # route senza slash finale per evitare 307
        resp = await ac.get("/api/v1/invoices?limit=5&offset=0")

    # in test mockiamo → 200, senza DB reale
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
