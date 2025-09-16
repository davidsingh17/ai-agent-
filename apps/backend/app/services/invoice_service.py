import os
from typing import List, Tuple, Optional, Dict, Any
from decimal import Decimal
import boto3
from botocore.client import Config

from app.services.db import execute

IS_TESTING = os.getenv("TESTING") == "1"


def _to_float_db(x) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float, Decimal)):
        return float(x)
    try:
        return float(x)
    except Exception:
        return None


def _row_to_api_item(r: Dict[str, Any]) -> Dict[str, Any]:
    issue_date = r.get("issue_date")
    due_date = r.get("due_date")

    fields = {
        "invoice_number": r.get("invoice_number"),
        "intestatario": r.get("intestatario"),
        "partita_iva": r.get("partita_iva"),
        "codice_fiscale": r.get("codice_fiscale"),
        "data_emissione": issue_date.isoformat() if issue_date else None,
        "data_scadenza": due_date.isoformat() if due_date else None,
        "valuta": r.get("currency") or "EUR",
        "imponibile": _to_float_db(r.get("imponibile")),
        "iva": _to_float_db(r.get("iva")),
        "totale": _to_float_db(r.get("totale")),
    }

    return {
        "id": str(r.get("id")),
        "filename": r.get("filename"),
        "s3": {"bucket": r.get("s3_bucket"), "key": r.get("s3_key")},
        "fields": fields,
    }


# -------------------------
# Lista fatture con filtri
# -------------------------
def list_invoices(
    limit: int,
    offset: int,
    q: Optional[str] = None,
    date_from: Optional[str] = None,  # YYYY-MM-DD
    date_to: Optional[str] = None,    # YYYY-MM-DD
    order_by: Optional[str] = "created_at",
    order_dir: Optional[str] = "desc",
) -> Tuple[List[Dict[str, Any]], int]:
    if IS_TESTING:
        return [], 0

    allowed_order_by = {
        "created_at": "created_at",
        "issue_date": "issue_date",
        "totale": "totale",
        "invoice_number": "invoice_number",  # allineato al frontend
    }
    order_by_sql = allowed_order_by.get((order_by or "created_at").lower(), "created_at")
    order_dir_sql = "ASC" if (order_dir or "desc").lower() == "asc" else "DESC"

    where = []
    params: List[Any] = []

    if q:
        where.append(
            """(
                COALESCE(filename,'') ILIKE %s OR
                COALESCE(invoice_number,'') ILIKE %s OR
                COALESCE(intestatario,'') ILIKE %s OR
                COALESCE(partita_iva,'') ILIKE %s OR
                COALESCE(codice_fiscale,'') ILIKE %s
            )"""
        )
        p = f"%{q}%"
        params += [p, p, p, p, p]

    if date_from:
        where.append("issue_date >= %s")
        params.append(date_from)

    if date_to:
        where.append("issue_date <= %s")
        params.append(date_to)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    sql_items = f"""
        SELECT
          id, filename, s3_bucket, s3_key,
          invoice_number, intestatario, partita_iva, codice_fiscale,
          issue_date, due_date, currency, imponibile, iva, totale,
          created_at
        FROM invoices
        {where_sql}
        ORDER BY {order_by_sql} {order_dir_sql}, created_at DESC
        LIMIT %s OFFSET %s
    """
    rows = execute(sql_items, tuple(params + [limit, offset])) or []
    items = [_row_to_api_item(r) for r in rows]

    sql_count = f"SELECT COUNT(*) AS total FROM invoices {where_sql}"
    total_row = execute(sql_count, tuple(params)) or [{"total": 0}]
    total = int(total_row[0]["total"])
    return items, total


def get_invoice(invoice_id: str) -> Optional[Dict[str, Any]]:
    if IS_TESTING:
        return None

    sql = """
        SELECT
          id, filename, s3_bucket, s3_key,
          invoice_number, intestatario, partita_iva, codice_fiscale,
          issue_date, due_date, currency, imponibile, iva, totale
        FROM invoices
        WHERE id = %s
        LIMIT 1
    """
    rows = execute(sql, (invoice_id,)) or []
    if not rows:
        return None
    return _row_to_api_item(rows[0])


# ---------- MinIO / S3 presigned URL ----------

def _s3_client(signing_endpoint: Optional[str] = None):
    """
    Crea un client S3. Se signing_endpoint è passato, lo usa per la FIRMA
    (host incluso nella firma). Altrimenti usa S3_ENDPOINT/MINIO_ENDPOINT.
    """
    endpoint = (
        signing_endpoint
        or os.getenv("S3_ENDPOINT")
        or os.getenv("MINIO_ENDPOINT")
        or "http://minio:9000"
    )
    access_key = os.getenv("S3_ACCESS_KEY") or os.getenv("MINIO_ACCESS_KEY") or "minioadmin"
    secret_key = os.getenv("S3_SECRET_KEY") or os.getenv("MINIO_SECRET_KEY") or "minioadmin"
    region = os.getenv("S3_REGION") or "us-east-1"

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def get_presigned_url(
    bucket: str,
    key: str,
    expires_in: int = 900,
    *,
    inline: bool = False,
    content_type: Optional[str] = None,
    filename: Optional[str] = None,
) -> Optional[str]:
    """
    Genera un URL presigned usando **l'endpoint pubblico** se disponibile,
    così l'host nella firma coincide con quello usato dal browser.
    """
    # In test ritorniamo solo un URL "finto" ma già pubblico
    if IS_TESTING:
        base = (
            os.getenv("S3_PUBLIC_ENDPOINT")
            or os.getenv("MINIO_PUBLIC_ENDPOINT")
            or os.getenv("S3_ENDPOINT")
            or os.getenv("MINIO_ENDPOINT")
            or "http://localhost:9000"
        )
        return f"{base.rstrip('/')}/{bucket}/{key}?exp={expires_in}"

    public_base = os.getenv("S3_PUBLIC_ENDPOINT") or os.getenv("MINIO_PUBLIC_ENDPOINT")
    internal_base = os.getenv("S3_ENDPOINT") or os.getenv("MINIO_ENDPOINT") or "http://minio:9000"

    # Se abbiamo un endpoint pubblico, firmiamo direttamente con quello
    signing_endpoint = public_base or internal_base
    s3 = _s3_client(signing_endpoint)

    try:
        params = {"Bucket": bucket, "Key": key}
        disp = "inline" if inline else "attachment"
        if filename:
            disp += f'; filename="{filename}"'
        params["ResponseContentDisposition"] = disp
        if content_type:
            params["ResponseContentType"] = content_type

        url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=expires_in,
        )
        # Non riscrivere l'URL: è già firmato con il giusto host.
        return url
    except Exception:
        return None
