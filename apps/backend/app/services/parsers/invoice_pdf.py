import re
from io import BytesIO
from typing import Dict, Any, List, Optional
from collections import Counter

from pdfminer.high_level import extract_text
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image, ImageOps, ImageFilter

from .common import (
    first_match, _to_float, _to_date, lines as split_lines, prev_nonempty,
    IVA_RAW, IVA_LABELED, CF_SPACED, CURRENCY_REGEX,
    TOTAL_LABELED, NET_LABELED, VAT_LABELED,
    DATE_EMISSIONE, DATE_SCADENZA, DATE_ANY, INVOICE_NO_REGEX,
    is_noise_name, normalize_cf
)

# -------- Regex importi/numero documento --------
AMOUNT = r"(\d{1,3}(?:[.,\s\u202F\u00A0]\d{3})*(?:[.,]\d{2}))"
RE_AMOUNT = re.compile(AMOUNT)

RE_FATTURA_ONELINE = re.compile(r"\bfattura\b[^\S\r\n]*([A-Za-z0-9/\-]{1,20})", re.IGNORECASE)
RE_IMP_ONELINE     = re.compile(r"(?:imponibile(?:\s+prestazione)?)\s*[:€]?\s*" + AMOUNT, re.IGNORECASE)
RE_IVA_ONELINE     = re.compile(r"\biva\b[^\n\r%]*%?[^\d]{0,10}" + AMOUNT, re.IGNORECASE)
# escludi "totale imponibile"
RE_TOT_ONELINE     = re.compile(r"\btotale\b(?!\s*imponibile)[^\d€]*€?\s*" + AMOUNT, re.IGNORECASE)

# percentuale IVA (es. "IVA 22%", "IVA: 10 %")
RE_VAT_PERCENT = re.compile(r"\biva\b[^\n\r]{0,20}?(\d{1,2})(?:[.,]\d+)?\s*%", re.IGNORECASE)

# data vicino a "Fattura ... del DD/MM/YYYY"
RE_FATTURA_DATE = re.compile(
    r"fattura\s+nr?\.?[^,\n\r]{0,60}?del\s+(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
    re.IGNORECASE | re.DOTALL
)

# anno a 4 cifre (per "dominant year")
RE_YEAR_4 = re.compile(r"\b(20\d{2})\b")

DATE_LIKE    = re.compile(r"^\d{2}[./]\d{2}[./](\d{2}|\d{4})$")
DATE_LIKE_ANYWHERE = re.compile(r"\b\d{2}[./]\d{2}[./](\d{2}|\d{4})\b")
CAND_INVOICE = re.compile(r"^(?:[A-Za-z]?\d{1,6}|[A-Za-z]?\d{1,4}/\d{2,4})$")
LABELY       = {"data", "cliente", "indirizzo", "citta'", "città"}

def _clean_amount(s: str) -> str:
    return s.replace("\u202f", "").replace("\xa0", "").replace(" ", "")

def _is_amount_inside_date(line: str, start: int, end: int) -> bool:
    for dm in DATE_LIKE_ANYWHERE.finditer(line):
        ds, de = dm.span()
        if start >= ds and end <= de:
            return True
    return False

def _amount_in_line(s: str) -> Optional[float]:
    for m in RE_AMOUNT.finditer(s):
        if _is_amount_inside_date(s, m.start(1), m.end(1)):
            continue
        return _to_float(_clean_amount(m.group(1)))
    return None

def _iva_from_oneline_safe(one_line: str) -> Optional[float]:
    m = RE_IVA_ONELINE.search(one_line)
    if not m:
        return None
    if _is_amount_inside_date(one_line, m.start(1), m.end(1)):
        return None
    start_iva = one_line.lower().find("iva")
    num_start = m.start(1)
    between = one_line[start_iva:num_start].lower()
    if "totale" in between or "imponibile" in between or "totale documento" in between:
        return None
    return _to_float(_clean_amount(m.group(1)))

def _vat_percent(text: str) -> Optional[float]:
    m = RE_VAT_PERCENT.search(text)
    if not m:
        return None
    try:
        p = float(m.group(1).replace(",", "."))
        if 4 <= p <= 30:
            return p
    except ValueError:
        pass
    return None

def _looks_like_name(s: str) -> bool:
    s = s.strip()
    if is_noise_name(s):
        return False
    words = [w for w in s.split() if w.isalpha()]
    return 2 <= len(words) <= 4 and sum(ch.isdigit() for ch in s) == 0

def _guess_intestatario(ll: List[str], idx_piva: Optional[int]) -> Optional[str]:
    if idx_piva is not None:
        for look in range(1, 6):
            j = idx_piva - look
            if j < 0:
                break
            cand = ll[j].strip()
            if _looks_like_name(cand):
                return cand
    idx_cliente = next((i for i, l in enumerate(ll) if "cliente" in l.lower()), None)
    for i, cand in enumerate(ll):
        if idx_cliente is not None and abs(i - idx_cliente) <= 2:
            continue
        if _looks_like_name(cand):
            return cand
    return None

def _invoice_number_from_lines(ll: List[str]) -> Optional[str]:
    for i, l in enumerate(ll):
        if "fattura" in l.lower():
            m = RE_FATTURA_ONELINE.search(l)
            if m:
                cand = m.group(1).strip()
                if cand and not DATE_LIKE.match(cand) and "." not in cand and CAND_INVOICE.match(cand):
                    return cand
            steps = 0
            j = i + 1
            while j < len(ll) and steps < 4:
                nxt = ll[j].strip()
                if nxt:
                    low = nxt.lower()
                    if not DATE_LIKE.match(nxt) and "." not in nxt and not any(lbl in low for lbl in LABELY):
                        if CAND_INVOICE.match(nxt):
                            return nxt
                    steps += 1
                j += 1
    return None

# -------- Block parser per importi etichettati --------
def _find_amount_block(ll: List[str], label: str, window: int = 6) -> Optional[float]:
    label_l = label.lower()
    for i, line in enumerate(ll):
        low = line.lower()
        if label_l in low:
            if label_l == "totale" and "imponibile" in low:
                continue
            val_same = _amount_in_line(line)
            if val_same is not None:
                return val_same
            steps = 0
            j = i + 1
            while j < len(ll) and steps < window:
                nxt = ll[j].strip()
                if nxt:
                    if "%" in nxt and not RE_AMOUNT.search(nxt):
                        j += 1
                        continue
                    v = _amount_in_line(nxt)
                    if v is not None:
                        return v
                    steps += 1
                j += 1
    return None

# -------- Lettura esplicita da etichette "Totale ..." --------
LABELS_IMPONIBILE = ("totale imponibile", "imponibile totale")
LABELS_IVA        = ("totale iva",)
LABELS_TOTALE     = ("totale documento", "netto a pagare", "totale fattura")

def _amount_after_label(ll: List[str], labels: tuple[str, ...], window: int = 6, role: Optional[str] = None) -> Optional[float]:
    for i, line in enumerate(ll):
        low = line.lower()
        if any(lbl in low for lbl in labels):
            steps = 0
            j = i + 1
            cands: List[float] = []
            while j < len(ll) and steps < window:
                nxt = ll[j].strip()
                if nxt:
                    if "%" in nxt and not RE_AMOUNT.search(nxt):
                        j += 1
                        continue
                    v = _amount_in_line(nxt)
                    if v is not None:
                        cands.append(v)
                    steps += 1
                j += 1
            if cands:
                if role == "iva":
                    return min(cands)              # l'IVA è quasi sempre la più piccola
                if role == "totale":
                    return max(cands)              # il totale è quasi sempre il più grande
                return max(cands)                  # imponibile: tipicamente il più grande fra i candidati
    return None

def _totals_by_explicit_labels(ll: List[str]) -> Dict[str, Optional[float]]:
    return {
        "imponibile": _amount_after_label(ll, LABELS_IMPONIBILE, window=8, role="imponibile"),
        "iva":        _amount_after_label(ll, LABELS_IVA,        window=8, role="iva"),
        "totale":     _amount_after_label(ll, LABELS_TOTALE,     window=8, role="totale"),
    }

# -------- Euristiche sugli importi --------
def _amounts_with_indexes(ll: List[str]) -> List[tuple[int, float]]:
    res: List[tuple[int, float]] = []
    for idx, line in enumerate(ll):
        for m in RE_AMOUNT.finditer(line):
            if _is_amount_inside_date(line, m.start(1), m.end(1)):
                continue
            v = _to_float(_clean_amount(m.group(1)))
            if v is not None:
                res.append((idx, v))
    return res

def _assign_from_bottom(ll: List[str]) -> Dict[str, Optional[float]]:
    tail = ll[-20:] if len(ll) > 20 else ll[:]
    base = len(ll) - len(tail)
    pairs = []
    for i, line in enumerate(tail):
        for m in RE_AMOUNT.finditer(line):
            if _is_amount_inside_date(line, m.start(1), m.end(1)):
                continue
            v = _to_float(_clean_amount(m.group(1)))
            if v is not None:
                pairs.append((base + i, v))

    best = {"iva": None, "imponibile": None, "totale": None}
    best_err = 1e9
    n = len(pairs)
    for i in range(n):
        for j in range(i+1, n):
            for k in range(j+1, n):
                a = pairs[i][1]; b = pairs[j][1]; c = pairs[k][1]
                for iva, imp, tot in ((a,b,c),(a,c,b),(b,a,c),(b,c,a),(c,a,b),(c,b,a)):
                    if tot < imp or tot < iva:
                        continue
                    if tot > 50 and iva < 1:
                        continue
                    err = abs((imp + iva) - tot)
                    if err <= 0.05 and tot >= imp > 0 and iva > 0:
                        if err < best_err or (abs(err-best_err) <= 0.001 and tot > (best["totale"] or 0)):
                            best = {"iva": round(iva,2), "imponibile": round(imp,2), "totale": round(tot,2)}
                            best_err = err
    return best

def _assign_amounts_by_heuristic(text: str, ll: List[str]) -> Dict[str, Optional[float]]:
    best = _assign_from_bottom(ll)
    if best["totale"] is not None:
        return best

    vals = sorted(set(round(v,2) for _, v in _amounts_with_indexes(ll)))
    m = len(vals)
    best = {"iva": None, "imponibile": None, "totale": None}
    best_err = 1e9
    for i in range(m):
        for j in range(i+1, m):
            for k in range(j+1, m):
                iva, imp, tot = vals[i], vals[j], vals[k]
                if tot < imp or tot < iva:
                    continue
                if tot > 50 and iva < 1:
                    continue
                err = abs((imp + iva) - tot)
                if err <= 0.05 and tot >= imp > 0 and iva > 0:
                    if err < best_err or (abs(err-best_err) <= 0.001 and tot > (best["totale"] or 0)):
                        best = {"iva": iva, "imponibile": imp, "totale": tot}
                        best_err = err
    return best

# -------- Utility per anno dominante --------
def _dominant_year(text: str) -> Optional[int]:
    years = [int(m.group(1)) for m in RE_YEAR_4.finditer(text)]
    years = [y for y in years if 2010 <= y <= 2035]
    if not years:
        return None
    counts = Counter(years).most_common()
    top = counts[0][1]
    candidates = [y for y, c in counts if c == top]
    return max(candidates)

def _replace_year_iso(date_s: Optional[str], year: int) -> Optional[str]:
    if not date_s:
        return date_s
    try:
        y, m, d = date_s.split("-")
        return f"{year:04d}-{m}-{d}"
    except Exception:
        return date_s

# -------- Estrazione testo --------
def _extract_text_pdfminer(file_bytes: bytes) -> str:
    try:
        return extract_text(BytesIO(file_bytes)) or ""
    except Exception:
        return ""

def _preprocess(img: Image.Image) -> Image.Image:
    try:
        g = img.convert("L")
        g = ImageOps.autocontrast(g)
        w, h = g.size
        g = g.resize((int(w*1.5), int(h*1.5)))
        g = g.filter(ImageFilter.SHARPEN)
        g = g.point(lambda p: 255 if p > 180 else 0)
        return g
    except Exception:
        return img

def _ocr_one(img: Image.Image) -> str:
    try:
        return pytesseract.image_to_string(img, lang="ita+eng")
    except Exception:
        try:
            return pytesseract.image_to_string(img, lang="eng")
        except Exception:
            return ""

def _extract_text_ocr(file_bytes: bytes) -> str:
    try:
        images = convert_from_bytes(file_bytes, dpi=300, first_page=1, last_page=1, fmt="png", thread_count=1)
        if not images:
            return ""
        base = images[0]
        variants = [_preprocess(base), _preprocess(base.rotate(90, expand=True)), _preprocess(base.rotate(270, expand=True))]
        candidates: List[str] = [_ocr_one(v) for v in variants]
        return max(candidates, key=lambda t: len(t.strip())) if candidates else ""
    except Exception:
        return ""

def _extract_text_auto(file_bytes: bytes) -> str:
    txt = _extract_text_pdfminer(file_bytes)
    if len(txt.strip()) >= 200:
        return txt
    ocr_txt = _extract_text_ocr(file_bytes)
    return ocr_txt if len(ocr_txt.strip()) > len(txt.strip()) else txt

# -------- Parsing principale --------
def _parse_from_text(text: str) -> Dict[str, Any]:
    ll = split_lines(text)
    one_line = re.sub(r"[\r\n]+", " ", text)

    # P.IVA / CF
    piva = first_match(IVA_LABELED, text) or first_match(IVA_RAW, text)
    cf_raw = first_match(CF_SPACED, text)
    cf = normalize_cf(cf_raw)

    # Valuta
    currency = "EUR" if ("€" in text or first_match(CURRENCY_REGEX, text)) else "EUR"

    # === Importi da etichette esplicite (PRIORITARI) ===
    lbl = _totals_by_explicit_labels(ll)
    imponibile = lbl.get("imponibile")
    iva        = lbl.get("iva")
    totale     = lbl.get("totale")

    # --- Importi (fallback 1): regex globali / one-line, SOLO se mancanti
    if imponibile is None:
        imponibile = _to_float(first_match(NET_LABELED, text))
        if imponibile is None:
            m = RE_IMP_ONELINE.search(one_line)
            imponibile = _to_float(_clean_amount(m.group(1))) if m else None

    if iva is None:
        iva = _to_float(first_match(VAT_LABELED, text))
        if iva is None:
            iva = _iva_from_oneline_safe(one_line)

    if totale is None:
        totale = _to_float(first_match(TOTAL_LABELED, text))
        if totale is None:
            m = RE_TOT_ONELINE.search(one_line)
            totale = _to_float(_clean_amount(m.group(1))) if m else None

    # --- Importi (fallback 2): usa percentuale se presente
    vat_perc = _vat_percent(text)
    if vat_perc and imponibile is not None:
        if iva is None or abs(iva - imponibile) <= 0.01:
            iva = round(imponibile * vat_perc / 100.0, 2)

    # --- Importi (fallback 3): euristica
    incoerente = (imponibile is not None and iva is not None and totale is not None and abs((imponibile + iva) - totale) > 0.05)
    if (imponibile is None or iva is None or totale is None) or incoerente:
        guess = _assign_amounts_by_heuristic(text, ll)
        if iva is None or incoerente:
            if guess["iva"] is not None: iva = guess["iva"]
        if imponibile is None or incoerente:
            if guess["imponibile"] is not None: imponibile = guess["imponibile"]
        if totale is None or incoerente:
            if guess["totale"] is not None: totale = guess["totale"]

    # --- Sanity: fix inversione IVA/Imponibile se rapporto non plausibile
    def _rate_ok(imp: Optional[float], v: Optional[float]) -> bool:
        if imp is None or v is None or imp <= 0:
            return False
        r = v / imp
        return (0.04 - 0.005) <= r <= (0.30 + 0.005)

    if imponibile is not None and iva is not None:
        if vat_perc:
            # se la % nota non quadra ma quadra dopo swap -> swap
            err      = abs(iva - round(imponibile * vat_perc / 100.0, 2))
            err_swap = abs(imponibile - round(iva * vat_perc / 100.0, 2))
            if err > 0.5 and err_swap < 0.5:
                imponibile, iva = iva, imponibile
        elif not _rate_ok(imponibile, iva) and _rate_ok(iva, imponibile):
            imponibile, iva = iva, imponibile

    # Coerenza finale
    if imponibile is not None and iva is not None:
        calc = round(imponibile + iva, 2)
        if totale is None or abs(totale - calc) <= 0.05:
            totale = calc

    # === Date ===
    issue_date = None
    mfd = RE_FATTURA_DATE.search(one_line)
    if mfd:
        issue_date = _to_date(mfd.group(1))
    if not issue_date:
        issue_date = _to_date(first_match(DATE_EMISSIONE, text))
    if not issue_date:
        any_date = first_match(DATE_ANY, text)
        issue_date = _to_date(any_date)
    due_date = _to_date(first_match(DATE_SCADENZA, text))

    # correzione anno con "dominant year" (se differenza significativa)
    dom_year = _dominant_year(one_line)
    if issue_date and dom_year and 2015 <= dom_year <= 2035:
        try:
            iy = int(issue_date.split("-")[0])
            if abs(dom_year - iy) >= 2:
                issue_date = _replace_year_iso(issue_date, dom_year)
        except Exception:
            pass

    # Numero fattura
    invoice_number = _invoice_number_from_lines(ll)
    if not invoice_number:
        m = RE_FATTURA_ONELINE.search(one_line)
        if m:
            cand = m.group(1).strip()
            if cand and not DATE_LIKE.match(cand) and "." not in cand and CAND_INVOICE.match(cand):
                invoice_number = cand
    if not invoice_number:
        invoice_number = first_match(INVOICE_NO_REGEX, text)

    # Intestatario
    idx_piva = next((i for i, l in enumerate(ll) if IVA_LABELED.search(l) or IVA_RAW.search(l)), None)
    intestatario = _guess_intestatario(ll, idx_piva)

    # P.IVA → canonicalizza
    if piva:
        raw = piva.replace("IT", "")
        raw = re.sub(r"\D", "", raw)
        if len(raw) < 11:
            raw = raw.zfill(11)
        piva = "IT" + raw

    return {
        "fields": {
            "intestatario": intestatario,
            "partita_iva": piva,
            "codice_fiscale": cf,
            "invoice_number": invoice_number,
            "data_emissione": issue_date,
            "data_scadenza": due_date,
            "valuta": currency,
            "imponibile": imponibile,
            "iva": iva,
            "totale": totale
        },
        "righe": []
    }

def parse_pdf_invoice(file_bytes: bytes) -> Dict[str, Any]:
    text = _extract_text_auto(file_bytes)
    return _parse_from_text(text)
