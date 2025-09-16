from typing import Optional, List
from pydantic import BaseModel, Field


class S3Ref(BaseModel):
    bucket: str
    key: str


class InvoiceLine(BaseModel):
    descrizione: Optional[str] = None
    qta: Optional[float] = None
    prezzo_unitario: Optional[float] = None
    aliquota_iva: Optional[float] = None
    totale_riga: Optional[float] = None


class InvoiceFields(BaseModel):
    intestatario: Optional[str] = None
    partita_iva: Optional[str] = None
    codice_fiscale: Optional[str] = None
    invoice_number: Optional[str] = None

    # Le date possono mancare o non essere parse → opzionali
    data_emissione: Optional[str] = None  # oppure date: Optional[date] se preferisci
    data_scadenza: Optional[str] = None

    valuta: Optional[str] = "EUR"

    # 🔑 Qui la fix: importi opzionali (XML può non fornirli)
    imponibile: Optional[float] = None
    iva: Optional[float] = None
    totale: Optional[float] = None


class InvoiceOut(BaseModel):
    id: str
    s3: S3Ref
    filename: Optional[str] = None
    fields: InvoiceFields
    righe: List[InvoiceLine] = Field(default_factory=list)


# ---- Liste / paginazione ----

class InvoiceListItem(BaseModel):
    id: str
    filename: Optional[str] = None
    intestatario: Optional[str] = None
    invoice_number: Optional[str] = None
    data_emissione: Optional[str] = None
    totale: Optional[float] = None


class InvoiceListResponse(BaseModel):
    items: List[InvoiceListItem]
    total: int
    limit: int
    offset: int


class PresignedUrlOut(BaseModel):
    url: str
    expires_in: int
