import uuid
from typing import List, Dict, Any, Optional
from .db import execute

def _to_float(x) -> float:
    try:
        if x is None: return 0.0
        if isinstance(x, str):
            x = x.replace(".", "").replace(",", ".").replace("%", "").strip()
        return float(x)
    except Exception:
        return 0.0

def _norm_aliquota(v: float) -> float:
    # accetta 0..100; se > 1000 probabile valore *100 → riducilo
    if v > 1000:
        return round(v / 100.0, 3)
    return round(v, 3)

def insert_invoice_header(
    *,
    id: str,
    s3_bucket: str,
    s3_key: str,
    filename: str,
    invoice_number: Optional[str],
    intestatario: Optional[str],
    partita_iva: Optional[str],
    codice_fiscale: Optional[str],
    issue_date: Optional[str],
    due_date: Optional[str],
    currency: Optional[str],
    imponibile: Optional[float],
    iva: Optional[float],
    totale: Optional[float],
):
    query = """
    INSERT INTO invoices (
      id, s3_bucket, s3_key, filename, invoice_number, intestatario, partita_iva,
      codice_fiscale, issue_date, due_date, currency, imponibile, iva, totale
    ) VALUES (
      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    """
    params = (
        id, s3_bucket, s3_key, filename, invoice_number, intestatario, partita_iva,
        codice_fiscale, issue_date, due_date, currency,
        None if imponibile is None else round(_to_float(imponibile), 2),
        None if iva is None else round(_to_float(iva), 2),
        None if totale is None else round(_to_float(totale), 2),
    )
    execute(query, params)

def insert_invoice_lines(*, invoice_id: str, lines: List[Dict[str, Any]]):
    if not lines:
        return
    for idx, line in enumerate(lines, start=1):
        line_id = str(uuid.uuid4())
        descrizione = line.get("descrizione")
        qta = _to_float(line.get("qta", 0))
        prezzo_unitario = round(_to_float(line.get("prezzo_unitario", 0)), 2)
        aliquota_iva = _norm_aliquota(_to_float(line.get("aliquota_iva", 0)))
        totale_riga = round(_to_float(line.get("totale_riga", qta * prezzo_unitario * (1 + aliquota_iva/100.0))), 2)

        query = """
        INSERT INTO invoice_lines (
          id, invoice_id, line_number, descrizione, qta, prezzo_unitario, aliquota_iva, totale_riga
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (line_id, invoice_id, idx, descrizione, qta, prezzo_unitario, aliquota_iva, totale_riga)
        execute(query, params)
