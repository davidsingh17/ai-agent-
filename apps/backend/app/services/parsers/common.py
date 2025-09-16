import re
from datetime import datetime
from typing import Optional, List

# --- Regex più robuste (IT) ---
# P.IVA: etichettata o raw, 10-11 cifre (alcune P.IVA hanno uno zero iniziale omesso nei documenti)
IVA_RAW = re.compile(r"\b(?:IT)?\s?(\d{10,11})\b")
IVA_LABELED = re.compile(r"(?:P\.?\s*IVA|Partita\s*IVA)[^\d]{0,10}(\d{10,11})", re.IGNORECASE)

# CF persona fisica: consenti spazi interni (es. "RSS MRA 90A01 A794T")
CF_SPACED = re.compile(r"\b([A-Z]{3}\s*[A-Z]{3}\s*\d{2}\s*[A-Z]\s*\d{2}\s*[A-Z]\s*\d{3}\s*[A-Z])\b")

# Valuta / importi
CURRENCY_REGEX = re.compile(r"(EUR|€)", re.IGNORECASE)

# Importi etichettati (accetta anche "TOTALE" su riga da solo)
TOTAL_LABELED = re.compile(
    r"(?:totale\s*(?:documento)?|^totale$)\s*[:€]?\s*([\d\.,]+)",
    re.IGNORECASE | re.MULTILINE
)
NET_LABELED = re.compile(r"(?:imponibile|totale\s*imponibile)\s*[:€]?\s*([\d\.,]+)", re.IGNORECASE)

# IVA come IMPORTO (non percentuale): cattura valori con decimali tipo "220,00"
VAT_LABELED = re.compile(
    r"(?:\biva\b[^\n\r]*?)"                           # “IVA …”
    r"(\d{1,3}(?:[\.\,]\d{3})*(?:[\.,]\d{2}))",       # importo con decimali
    re.IGNORECASE
)

# IVA in percentuale (es. "IVA 22%" oppure "Iva: 22 %")
VAT_PERCENT = re.compile(
    r"\biva\b[^\n\r%]*?(\d{1,2}(?:[.,]\d{1,2})?)\s*%",
    re.IGNORECASE
)

# Date: supporta dd.mm.yy, dd.mm.yyyy, dd/mm/yy, yyyy-mm-dd
DATE_ANY = re.compile(r"(\d{2}[./]\d{2}[./](\d{2}|\d{4})|\d{4}-\d{2}-\d{2})")
DATE_EMISSIONE = re.compile(
    r"(?:\bdata\b(?:\s*(?:emissione|fattura))?\s*:?\s*)"
    r"(\d{2}[./]\d{2}[./](\d{2}|\d{4})|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE
)
DATE_SCADENZA = re.compile(
    r"(?:\bscadenza\b|\bdata\s*scadenza\b)\s*:?\s*"
    r"(\d{2}[./]\d{2}[./](\d{2}|\d{4})|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE
)

INVOICE_NO_REGEX = re.compile(r"(?:fattura|fatt\.|n[°o])\s*[:\-]?\s*([A-Za-z0-9/\\\-]+)", re.IGNORECASE)

# Etichette che NON sono nomi (da saltare quando cerchiamo l'intestatario)
LABEL_NO_NAME = {
    "indirizzo", "citta'", "città", "partita iva", "cod. fisc", "codice fiscale", "p. iva", "p iva"
}

# Righe rumorose: CAP + città, indirizzo, solo numeri/segni
CITY_LINE = re.compile(r"\b\d{5}\b\s*[-–]?\s*[A-Za-zÀ-ÖØ-öø-ÿ].*")  # es: 24100 - Bergamo (Bg)
ADDRESS_LINE = re.compile(r"^(via|viale|piazza|corso|vicolo|largo)\b", re.IGNORECASE)
ONLY_NUMERIC = re.compile(r"^[\d\.\,€\s]+$")

def is_noise_name(line: str) -> bool:
    low = line.lower()
    if any(lbl in low for lbl in LABEL_NO_NAME):
        return True
    if CITY_LINE.search(line):
        return True
    if ADDRESS_LINE.search(line):
        return True
    if ONLY_NUMERIC.match(line):
        return True
    return False

# --- Utils numeri/date ---

def _to_float(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    s = s.strip().replace("€", "")
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None

def _norm_year(y: int) -> int:
    # per date tipo 02.01.17 → 2017 (assumi 00-79 → 2000+, 80-99 → 1900+)
    return (2000 + y) if y <= 79 else (1900 + y)

def _to_date(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.replace(".", "/")
    # dd/mm/yy
    m = re.match(r"^(\d{2})/(\d{2})/(\d{2})$", s)
    if m:
        d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(_norm_year(y), mth, d).date().isoformat()
        except ValueError:
            return None
    # dd/mm/yyyy
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    if m:
        d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(y, mth, d).date().isoformat()
        except ValueError:
            return None
    # yyyy-mm-dd
    try:
        return datetime.strptime(s, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None

# --- Helpers generici ---

def first_match(regex, text: str) -> Optional[str]:
    m = regex.search(text)
    return m.group(1) if m else None

def lines(text: str) -> List[str]:
    return [l.strip() for l in text.splitlines() if l.strip()]

def prev_nonempty(ll: List[str], idx: int, lookback: int = 3) -> Optional[str]:
    for i in range(1, lookback+1):
        j = idx - i
        if j >= 0 and ll[j]:
            return ll[j]
    return None

def normalize_cf(cf: Optional[str]) -> Optional[str]:
    if not cf:
        return None
    return re.sub(r"\s+", "", cf).upper()
