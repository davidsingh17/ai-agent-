from typing import Dict, Any, List, Optional
from lxml import etree

def _txt(node: Optional[etree._Element]) -> Optional[str]:
    return node.text.strip() if node is not None and node.text else None

def _first(root, tag: str) -> Optional[etree._Element]:
    if root is None:
        return None
    res = root.xpath(f".//*[local-name()='{tag}']")
    return res[0] if res else None

def _to_float_str(s: Optional[str]) -> Optional[float]:
    """
    Converte stringhe numeriche in float gestendo:
    - Formato IT: 1.234,56  -> 1234.56
    - Formato EN: 1,234.56  -> 1234.56
    - Semplice:    1220.00  -> 1220.00
    Regola:
      - Se contiene SIA '.' che ',' -> assume '.' migliaia e ',' decimale (stile IT)
      - Se contiene SOLO ','        -> ',' decimale (sostituita con '.')
      - Se contiene SOLO '.'        -> '.' decimale (lascia)
    """
    if not s:
        return None
    s = s.strip()
    if "." in s and "," in s:
        # es: 1.234,56 -> 1234.56
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        # es: 1220,50 -> 1220.50
        s = s.replace(",", ".")
    else:
        # es: 1220.00 -> 1220.00 (già ok)
        pass
    try:
        return float(s)
    except Exception:
        return None

def parse_xml_fatturapa(file_bytes: bytes) -> Dict[str, Any]:
    parser = etree.XMLParser(recover=True, huge_tree=True)
    xml = etree.fromstring(file_bytes, parser=parser)

    # Cedente/Prestatore
    cedente = _first(xml, "CedentePrestatore")
    anagrafica = _first(cedente, "Anagrafica") if cedente is not None else None
    denominazione = _first(anagrafica, "Denominazione") if anagrafica is not None else None
    nome = _first(anagrafica, "Nome") if anagrafica is not None else None
    cognome = _first(anagrafica, "Cognome") if anagrafica is not None else None

    intestatario = _txt(denominazione) if denominazione is not None else None
    if not intestatario:
        intestatario = " ".join([p for p in [_txt(nome), _txt(cognome)] if p])

    # P.IVA
    id_fiscale = _first(cedente, "IdFiscaleIVA") if cedente is not None else None
    id_paese = _first(id_fiscale, "IdPaese") if id_fiscale is not None else None
    id_codice = _first(id_fiscale, "IdCodice") if id_fiscale is not None else None
    paese = _txt(id_paese) or "IT"
    codice = _txt(id_codice)
    partita_iva = f"{paese}{codice}" if codice else None

    # Codice Fiscale (se presente)
    codice_fiscale = _txt(_first(cedente, "CodiceFiscale")) if cedente is not None else None

    # Dati documento
    dati_generali_doc = _first(xml, "DatiGeneraliDocumento")
    invoice_number = _txt(_first(dati_generali_doc, "Numero")) if dati_generali_doc is not None else None
    issue_date = _txt(_first(dati_generali_doc, "Data")) if dati_generali_doc is not None else None
    currency = _txt(_first(dati_generali_doc, "Divisa")) if dati_generali_doc is not None else "EUR"
    total = _to_float_str(_txt(_first(dati_generali_doc, "ImportoTotaleDocumento"))) if dati_generali_doc is not None else None
    iva = _to_float_str(_txt(_first(dati_generali_doc, "TotaleImposta"))) if dati_generali_doc is not None else None
    imponibile = _to_float_str(_txt(_first(dati_generali_doc, "TotaleImponibile"))) if dati_generali_doc is not None else None

    # Scadenza (se presente)
    dettaglio_pag = _first(xml, "DettaglioPagamento")
    due_date = _txt(_first(dettaglio_pag, "DataScadenzaPagamento")) if dettaglio_pag is not None else None

    # Linee
    lines: List[Dict[str, Any]] = []
    for det in xml.xpath("//*[local-name()='DettaglioLinee']"):
        def _num(tag: str) -> float:
            return _to_float_str(_txt(_first(det, tag))) or 0.0

        lines.append({
            "descrizione": _txt(_first(det, "Descrizione")),
            "qta": _num("Quantita"),
            "prezzo_unitario": _num("PrezzoUnitario"),
            "aliquota_iva": _num("AliquotaIVA"),
            "totale_riga": _num("PrezzoTotale"),
        })

    return {
        "fields": {
            "intestatario": intestatario,
            "partita_iva": partita_iva,
            "codice_fiscale": codice_fiscale,
            "invoice_number": invoice_number,
            "data_emissione": issue_date,
            "data_scadenza": due_date,
            "valuta": currency or "EUR",
            "imponibile": imponibile,
            "iva": iva,
            "totale": total
        },
        "righe": lines
    }
